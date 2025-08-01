"""
Google Cloud Functions - Estructura Monorepo
Combina las funciones process_pdf_to_chunks y create_embeddings_from_chunks
en un único archivo para mejor organización y despliegue.
"""

import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

import functions_framework
from google.cloud import storage

# Importar configuración compartida
from common.config import settings
from common.config.logging_config import setup_logging, get_logger, StructuredLogger
from common.services.embeddings_service import EmbeddingService
from common.services.gcs_service import GCSService
from common.services.status_service import StatusService, DocumentStatus
# IndexManagerService eliminado - ahora usamos PostgreSQL directamente
from common.services.processing_service import DocumentProcessor
from common.utils.monitoring import get_logger as get_monitoring_logger, get_processing_monitor, log_system_info
from common.utils.temp_file_manager import temp_dir
from common.utils.resource_managers import (
    document_processing_context,
    with_processing_resources,
    error_handling_context
)
import openai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configurar logging mejorado (sin file logging en Cloud Functions)
setup_logging(log_level="INFO", enable_file_logging=False, enable_console_logging=True)
logger = get_logger(__name__)
structured_logger = StructuredLogger("main")

# Variables globales para pre-warm (cold-start optimization)
_embedding_service = None
_document_processor = None
_gcs_service = None

def get_embedding_service() -> EmbeddingService:
    """Obtiene una instancia global del servicio de embeddings."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

def get_document_processor() -> DocumentProcessor:
    """Obtiene una instancia global del procesador de documentos."""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor

def get_gcs_service() -> GCSService:
    """Obtiene una instancia global del servicio de GCS."""
    global _gcs_service
    if _gcs_service is None:
        from common.config.settings import GCS_BUCKET_NAME
        _gcs_service = GCSService(GCS_BUCKET_NAME)
    return _gcs_service

# Configurar parámetros de procesamiento usando configuración centralizada
from common.config.settings import CHUNK_SIZE, CHUNK_OVERLAP

# Inicializar monitoreo para create_embeddings
app_logger = get_monitoring_logger("create_embeddings_function")
processing_monitor = get_processing_monitor()

# Log información del sistema al inicio
log_system_info()

# =============================================================================
# FUNCIÓN 1: PROCESS_PDF_TO_CHUNKS
# =============================================================================

def is_pdf_file(file_name: str) -> bool:
    """Verifica si el archivo es un PDF."""
    return file_name.lower().endswith('.pdf')


# FUNCIÓN DE OPTIMIZACIÓN TEMPORAL - COMENTADA PARA DEPLOYMENT INICIAL
# def _process_chunks_to_embeddings_direct(chunks_data: Dict, source_file: str) -> Dict:
#     """
#     OPTIMIZACIÓN FUTURA: Procesa chunks directamente a embeddings y PostgreSQL
#     sin almacenamiento intermedio en GCS. Comentada temporalmente para deployment.
#     """
#     pass


def process_pdf_document(pdf_path: str, filename: str) -> Dict:
    """Procesa un documento PDF completo usando DocumentProcessor."""
    try:
        structured_logger.info("Iniciando procesamiento de documento PDF", 
            filename=filename,
            pdf_path=pdf_path,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP
        )
        
        # Usar DocumentProcessor del processing_service
        processor = DocumentProcessor()
        result = processor.process_document_complete(pdf_path)
        
        if not result.get('processed_successfully', False):
            structured_logger.error("Error en procesamiento de PDF con DocumentProcessor", 
                filename=filename,
                error=result.get('error', 'Error desconocido')
            )
            return {
                'filename': filename,
                'chunks': [],
                'num_chunks': 0,
                'total_words': 0,
                'processed_successfully': False,
                'error': result.get('error', 'Error desconocido')
            }
        
        # Adaptar el formato de chunks al formato esperado por el resto del código
        adapted_chunks = []
        for i, chunk_text in enumerate(result.get('chunks', [])):
            adapted_chunks.append({
                'text': chunk_text,
                'start_word': i * CHUNK_SIZE,  # Aproximación
                'end_word': (i + 1) * CHUNK_SIZE,
                'word_count': len(chunk_text.split())
            })
        
        # Preparar resultado adaptado
        adapted_result = {
            'filename': filename,
            'chunks': adapted_chunks,
            'num_chunks': len(adapted_chunks),
            'total_words': result.get('total_words', 0),
            'processing_timestamp': str(Path(pdf_path).stat().st_mtime),
            'processed_successfully': True,
            'metadata': {
                'chunk_size': CHUNK_SIZE,
                'chunk_overlap': CHUNK_OVERLAP,
                'total_text_length': len(result.get('markdown_content', '')),
                'processing_method': 'markdown_enhanced'
            }
        }
        
        structured_logger.info("PDF procesado exitosamente con DocumentProcessor", 
            filename=filename,
            num_chunks=len(adapted_chunks),
            total_words=result.get('total_words', 0),
            processing_method='markdown_enhanced'
        )
        return adapted_result
        
    except Exception as e:
        structured_logger.error("Error crítico procesando PDF", 
            filename=filename,
            pdf_path=pdf_path,
            error=str(e),
            error_type=type(e).__name__
        )
        return {
            'filename': filename,
            'chunks': [],
            'num_chunks': 0,
            'total_words': 0,
            'processed_successfully': False,
            'error': str(e)
        }


@functions_framework.cloud_event
def process_pdf_to_chunks(cloud_event: Any) -> None:
    """
    Cloud Function que se activa por eventos de Cloud Storage.
    Procesa PDFs y genera chunks de texto.
    """
    try:
        # Extraer información del evento
        if not hasattr(cloud_event, 'data') or not cloud_event.data:
            raise ValueError("Evento de Cloud Storage inválido: sin datos")
        
        event_data = cloud_event.data
        bucket_name = event_data.get('bucket')
        file_name = event_data.get('name')
        event_type = cloud_event['type']

        # Solo procesamos el evento real de Storage → FINALIZED
        if event_type != "google.cloud.storage.object.v1.finalized":
            return "ignored", 204                # ⚠️  NO lances excepción

        if not file_name or not bucket_name:
            # Cuando llegue el “ping” del trigger-check, saldrá por aquí
            return "ignored", 204

        if (not file_name.startswith("uploads/") or
            not file_name.lower().endswith(".pdf")):
            return "ignored", 204
        
        # Debug: Log completo del evento
        structured_logger.info("Evento completo recibido", 
            cloud_event_type=getattr(cloud_event, 'type', 'unknown'),
            cloud_event_data=str(event_data),
            bucket_name=bucket_name,
            file_name=file_name,
            event_type=event_type
        )
                
        # Inicializar cliente de Storage
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        
        # Procesar con context managers para robustez
        with document_processing_context() as doc_context:
            with error_handling_context() as error_context:
                # Crear directorio temporal usando TempFileManager
                with temp_dir(prefix="drcecim_pdf_") as temp_dir_path:
                    temp_file_path = Path(temp_dir_path) / Path(file_name).name
                    
                    # Descargar archivo PDF
                    structured_logger.info("Iniciando descarga de PDF", 
                        file_name=file_name,
                        temp_path=str(temp_file_path)
                    )
                    blob.download_to_filename(str(temp_file_path))
                    
                    # Procesar PDF
                    structured_logger.info("Iniciando procesamiento de PDF", 
                        file_name=file_name,
                        chunk_size=CHUNK_SIZE,
                        chunk_overlap=CHUNK_OVERLAP
                    )
                    result = process_pdf_document(str(temp_file_path), file_name)
                    
                    if not result.get('processed_successfully', False):
                        structured_logger.error("Error en procesamiento de PDF", 
                            file_name=file_name,
                            error=result.get('error', 'Error desconocido')
                        )
                        return
                    
                    # Preparar datos para subir
                    chunks_data = {
                        'filename': result['filename'],
                        'chunks': result['chunks'],
                        'metadata': result['metadata'],
                        'num_chunks': result['num_chunks'],
                        'total_words': result['total_words'],
                        'processing_timestamp': result['processing_timestamp'],
                        'source_file': file_name
                    }
                    
                    # Subir chunks procesados (mantenemos el comportamiento original por ahora)
                    chunks_filename = f"{Path(file_name).stem}_chunks.json"
                    chunks_gcs_path = f"processed/{chunks_filename}"
                    
                    structured_logger.info("Subiendo chunks procesados", 
                        file_name=file_name,
                        chunks_path=chunks_gcs_path,
                        num_chunks=result['num_chunks'],
                        total_words=result['total_words']
                    )
                    chunks_blob = bucket.blob(chunks_gcs_path)
                    chunks_blob.upload_from_string(
                        json.dumps(chunks_data, ensure_ascii=False, indent=2),
                        content_type='application/json'
                    )
                    
                    structured_logger.info("PDF procesado exitosamente", 
                        file_name=file_name,
                        chunks_path=chunks_gcs_path,
                        num_chunks=result['num_chunks'],
                        processing_time='completed'
                    )
    
    except Exception as e:
        structured_logger.error("Error crítico en process_pdf_to_chunks", 
            error=str(e),
            file_name=file_name if 'file_name' in locals() else 'unknown'
        )
        raise


# =============================================================================
# FUNCIÓN 2: CREATE_EMBEDDINGS_FROM_CHUNKS
# =============================================================================

def is_chunks_file(file_name: str) -> bool:
    """
    Verifica si el archivo es un archivo de chunks procesados.
    
    Args:
        file_name (str): Nombre del archivo
        
    Returns:
        bool: True si es un archivo de chunks
    """
    return file_name.lower().endswith('_chunks.json')


def find_document_id_from_status(status_service: StatusService, filename: str) -> str:
    """
    Busca el document_id basado en el nombre del archivo original.
    
    Args:
        status_service (StatusService): Servicio de estado
        filename (str): Nombre del archivo original
        
    Returns:
        str: ID del documento o None si no se encuentra
    """
    try:
        if not filename:
            return None
            
        # Buscar documentos que coincidan con el nombre del archivo
        all_docs = status_service.get_all_documents(limit=50)
        for doc in all_docs:
            if doc.get('filename') == filename:
                return doc.get('document_id')
        return None
    except Exception as e:
        app_logger.error(f"Error al buscar document_id: {str(e)}")
        return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((openai.APITimeoutError, openai.RateLimitError))
)
def generate_embeddings_with_retry(embedding_service: EmbeddingService, chunks_data: Dict) -> Dict:
    """
    Genera embeddings con reintentos para errores de red.
    
    Args:
        embedding_service (EmbeddingService): Servicio de embeddings
        chunks_data (Dict): Datos de chunks
        
    Returns:
        Dict: Resultado del procesamiento de embeddings
    """
    return embedding_service.process_document_embeddings(chunks_data)


@functions_framework.cloud_event
def create_embeddings_from_chunks(cloud_event):
    """
    Cloud Function que se activa por eventos de Cloud Storage.
    Genera embeddings y los almacena en PostgreSQL.
    
    Args:
        cloud_event: Evento de Cloud Storage
    """
    try:
        # Validar evento
        if not _validate_cloud_event(cloud_event):
            return
        
        event_data = cloud_event.data
        file_name = event_data.get('name')
        bucket_name = event_data.get('bucket')
        
        # Iniciar procesamiento
        session_id = processing_monitor.start_processing(file_name)
        app_logger.info(f"Iniciando generación de embeddings: {file_name}", {'session_id': session_id})
        
        try:
            # Procesar embeddings
            result = _process_embeddings_pipeline(bucket_name, file_name, session_id)
            
            processing_monitor.finish_processing(session_id, success=True)
            app_logger.info(
                f"Embeddings procesados y almacenados exitosamente en PostgreSQL",
                {'session_id': session_id}
            )
            
        except Exception as e:
            error_msg = f"Error durante el procesamiento de embeddings: {str(e)}"
            app_logger.error(error_msg, {'session_id': session_id})
            processing_monitor.finish_processing(session_id, success=False, error_message=error_msg)
            raise
    
    except Exception as e:
        logger.error(f"Error en create_embeddings_from_chunks: {str(e)}")
        raise


def _validate_cloud_event(cloud_event) -> bool:
    """
    Valida si el evento de Cloud Storage debe ser procesado.
    
    Args:
        cloud_event: Evento de Cloud Storage
        
    Returns:
        bool: True si debe procesarse, False si debe ignorarse
    """
    event_data = cloud_event.data
    event_type = cloud_event['type']
    file_name = event_data.get('name')
    
    app_logger.info(f"Evento recibido: {event_type} para archivo: {file_name}")
    
    # Verificar que sea un evento de creación/actualización
    if 'finalize' not in event_type:
        app_logger.info(f"Ignorando evento {event_type}")
        return False
    
    # Verificar que sea un archivo de chunks
    if not is_chunks_file(file_name):
        app_logger.info(f"Ignorando archivo no-chunks: {file_name}")
        return False
    
    # Verificar que esté en la carpeta processed/
    if not file_name.startswith('processed/'):
        app_logger.info(f"Ignorando archivo fuera de carpeta processed/: {file_name}")
        return False
    
    return True


def _process_embeddings_pipeline(bucket_name: str, file_name: str, session_id: str) -> Dict[str, Any]:
    """
    Pipeline principal de procesamiento de embeddings.
    
    Args:
        bucket_name (str): Nombre del bucket de GCS
        file_name (str): Nombre del archivo de chunks
        session_id (str): ID de sesión para monitoreo
        
    Returns:
        Dict[str, Any]: Resultado del procesamiento
    """
    # Inicializar servicios
    gcs_service = GCSService(bucket_name=bucket_name)
    status_service = StatusService()
    
    # Usar context managers para robustez y límites de recursos
    with with_processing_resources(max_memory_mb=2048, timeout_seconds=900) as resources:
        with error_handling_context() as error_context:
            with temp_dir(prefix='drcecim_embeddings_') as temp_dir_path:
                try:
                    # 1. Descargar y cargar chunks
                    chunks_data = _download_and_load_chunks(gcs_service, file_name, session_id)
                    
                    # 2. Buscar document_id y actualizar estado
                    document_id = _update_document_status_start(status_service, chunks_data)
                    
                    # 3. Generar embeddings
                    embeddings_result = _generate_embeddings(chunks_data, temp_dir_path, session_id, document_id, status_service)
                    
                    # 4. Gestionar almacenamiento en PostgreSQL
                    result = _manage_postgresql_embeddings(embeddings_result, session_id)
                    
                    # 5. Actualizar estado final
                    _update_document_status_completed(status_service, document_id, result)
                    
                    return result
                    
                except Exception as e:
                    structured_logger.error("Error en pipeline de embeddings", 
                        session_id=session_id,
                        file_name=file_name,
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    raise


def _download_and_load_chunks(gcs_service: GCSService, file_name: str, session_id: str) -> Dict:
    """
    Descarga y carga los datos de chunks desde GCS.
    """
    app_logger.info("Descargando archivo de chunks", {'session_id': session_id})
    chunks_content = gcs_service.read_file_as_string(file_name)
    chunks_data = json.loads(chunks_content)
    
    processing_monitor.log_step(session_id, "chunks_downloaded", {
        'num_chunks': chunks_data.get('num_chunks', 0)
    })
    
    return chunks_data


def _update_document_status_start(status_service: StatusService, chunks_data: Dict) -> str:
    """
    Busca el document_id y actualiza el estado inicial.
    """
    original_filename = chunks_data.get('filename', '')
    document_id = find_document_id_from_status(status_service, original_filename)
    
    if document_id:
        status_service.update_status(
            document_id, 
            DocumentStatus.PROCESSING, 
            f"Iniciando generación de embeddings para {chunks_data.get('num_chunks', 0)} chunks",
            "embeddings_generation_start"
        )
    
    return document_id


def _generate_embeddings(chunks_data: Dict, temp_dir: str, session_id: str, 
                        document_id: str, status_service: StatusService) -> Dict:
    """
    Genera embeddings con manejo de errores robusto.
    """
    app_logger.info("Generando embeddings", {'session_id': session_id})
    processing_monitor.log_step(session_id, "embeddings_generation_started")
    
    embedding_service = EmbeddingService(temp_dir)
    embeddings_result = generate_embeddings_with_retry(embedding_service, chunks_data)
    
    if not embeddings_result.get('processed_successfully', False):
        error_msg = embeddings_result.get('error', 'Error en generación de embeddings')
        if document_id:
            status_service.update_status(
                document_id, 
                DocumentStatus.ERROR, 
                f"Error en generación de embeddings: {error_msg}",
                "embeddings_error"
            )
        raise Exception(error_msg)
    
    processing_monitor.log_step(session_id, "embeddings_generation_completed", {
        'embedding_dimension': embeddings_result.get('config', {}).get('dimension', 0),
        'num_vectors': embeddings_result.get('config', {}).get('num_vectors', 0)
    })
    
    if document_id:
        status_service.update_status(
            document_id, 
            DocumentStatus.PROCESSING, 
            f"Embeddings generados exitosamente. Almacenando en PostgreSQL",
            "embeddings_generated",
            metadata={
                'embedding_dimension': embeddings_result.get('config', {}).get('dimension', 0),
                'num_vectors': embeddings_result.get('config', {}).get('num_vectors', 0)
            }
        )
    
    return embeddings_result


def _manage_postgresql_embeddings(embeddings_result: Dict, session_id: str) -> Dict[str, Any]:
    """
    Gestiona el almacenamiento de embeddings en PostgreSQL.
    """
    from common.services.vector_db_service import VectorDBService
    
    try:
        # Inicializar servicio de base de datos vectorial
        vector_db = VectorDBService()
        
        # Eliminar embeddings viejos del mismo documento si existen
        document_id = embeddings_result.get('config', {}).get('filename', '').replace('.pdf', '')
        if document_id:
            app_logger.info(f"Eliminando embeddings viejos del documento: {document_id}", {'session_id': session_id})
            removed_success = vector_db.delete_document_embeddings(document_id)
            
            processing_monitor.log_step(session_id, "old_embeddings_removed", {
                'document_id': document_id,
                'removal_success': removed_success
            })
        
        # Los embeddings ya fueron almacenados en PostgreSQL por el EmbeddingService
        # Solo necesitamos obtener estadísticas
        app_logger.info("Verificando almacenamiento en PostgreSQL", {'session_id': session_id})
        stats = vector_db.get_database_stats()
        
        processing_monitor.log_step(session_id, "postgresql_verified", {
            'total_embeddings': stats.get('total_embeddings', 0),
            'unique_documents': stats.get('unique_documents', 0)
        })
        
        return {
            'total_vectors': stats.get('total_embeddings', 0),
            'unique_documents': stats.get('unique_documents', 0),
            'storage_type': 'PostgreSQL'
        }
        
    except Exception as e:
        app_logger.error(f"Error gestionando embeddings en PostgreSQL: {str(e)}", {'session_id': session_id})
        raise


def _update_document_status_completed(status_service: StatusService, document_id: str, result: Dict):
    """
    Actualiza el estado final del documento.
    """
    if document_id:
        status_service.update_status(
            document_id, 
            DocumentStatus.COMPLETED, 
            f"Procesamiento completo. Base de datos PostgreSQL actualizada con {result['total_vectors']} vectores totales",
            "embeddings_completed",
            metadata={
                'total_vectors': result['total_vectors'],
                'uploaded_files': result['uploaded_files']
            }
        )


# =============================================================================
# HEALTH CHECKS
# =============================================================================

@functions_framework.http
def health_check_process_pdf(request):
    """Endpoint de health check para la función process_pdf_to_chunks."""
    return {
        'status': 'healthy',
        'function': 'process_pdf_to_chunks',
        'version': '1.0.0'
    }


@functions_framework.http
def health_check_create_embeddings(request):
    """Endpoint de health check para la función create_embeddings_from_chunks."""
    return {
        'status': 'healthy',
        'function': 'create_embeddings_from_chunks',
        'version': '1.0.0'
    }


if __name__ == '__main__':
    # Para testing local
    pass 