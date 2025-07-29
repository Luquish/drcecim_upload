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
from marker.converters.pdf import PdfConverter

# Importar configuración compartida
from common.config import settings
from common.services.embeddings_service import EmbeddingService
from common.services.gcs_service import GCSService
from common.services.status_service import StatusService, DocumentStatus
from common.services.index_manager_service import IndexManagerService
from common.utils.monitoring import get_logger, get_processing_monitor, log_system_info
import openai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurar parámetros de procesamiento
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '250'))
CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '50'))

# Inicializar monitoreo para create_embeddings
app_logger = get_logger("create_embeddings_function")
processing_monitor = get_processing_monitor()

# Log información del sistema al inicio
log_system_info()

# =============================================================================
# FUNCIÓN 1: PROCESS_PDF_TO_CHUNKS
# =============================================================================

def is_pdf_file(file_name: str) -> bool:
    """Verifica si el archivo es un PDF."""
    return file_name.lower().endswith('.pdf')


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrae texto de un archivo PDF usando marker-pdf."""
    try:
        converter = PdfConverter()
        with open(pdf_path, 'rb') as file:
            result = converter.convert(file.read())
            return result.text
    except Exception as e:
        logger.error(f"Error al extraer texto del PDF: {str(e)}")
        raise


def create_chunks(text: str, chunk_size: int = 250, chunk_overlap: int = 50) -> list:
    """Divide el texto en chunks."""
    if not text:
        return []
    
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - chunk_overlap):
        chunk_words = words[i:i + chunk_size]
        chunk_text = ' '.join(chunk_words)
        if chunk_text.strip():
            chunks.append({
                'text': chunk_text,
                'start_word': i,
                'end_word': min(i + chunk_size, len(words)),
                'word_count': len(chunk_words)
            })
    
    return chunks


def process_pdf_document(pdf_path: str, filename: str) -> Dict:
    """Procesa un documento PDF completo."""
    try:
        # Extraer texto
        text = extract_text_from_pdf(pdf_path)
        
        # Crear chunks
        chunks = create_chunks(text, CHUNK_SIZE, CHUNK_OVERLAP)
        
        # Preparar resultado
        result = {
            'filename': filename,
            'chunks': chunks,
            'num_chunks': len(chunks),
            'total_words': len(text.split()),
            'processing_timestamp': str(Path(pdf_path).stat().st_mtime),
            'processed_successfully': True,
            'metadata': {
                'chunk_size': CHUNK_SIZE,
                'chunk_overlap': CHUNK_OVERLAP,
                'total_text_length': len(text)
            }
        }
        
        logger.info(f"PDF procesado exitosamente: {len(chunks)} chunks creados")
        return result
        
    except Exception as e:
        logger.error(f"Error procesando PDF: {str(e)}")
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
        event_type = event_data.get('eventType')
        
        # Validar datos del evento
        if not bucket_name or not file_name or not event_type:
            raise ValueError("Datos del evento incompletos")
        
        logger.info(f"Evento recibido: {event_type} para archivo: {file_name}")
        
        # Verificar que sea un evento de creación/actualización
        if 'finalize' not in event_type:
            logger.info(f"Ignorando evento {event_type}")
            return
        
        # Verificar que sea un archivo PDF
        if not is_pdf_file(file_name):
            logger.info(f"Ignorando archivo no-PDF: {file_name}")
            return
        
        # Inicializar cliente de Storage
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        
        # Crear directorio temporal
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file_path = Path(temp_dir) / Path(file_name).name
            
            # Descargar archivo PDF
            logger.info(f"Descargando PDF: {file_name}")
            blob.download_to_filename(str(temp_file_path))
            
            # Procesar PDF
            logger.info(f"Procesando PDF: {file_name}")
            result = process_pdf_document(str(temp_file_path), file_name)
            
            if not result.get('processed_successfully', False):
                logger.error(f"Error procesando PDF: {result.get('error', 'Error desconocido')}")
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
            
            # Subir chunks procesados
            chunks_filename = f"{Path(file_name).stem}_chunks.json"
            chunks_gcs_path = f"processed/{chunks_filename}"
            
            logger.info(f"Subiendo chunks a: {chunks_gcs_path}")
            chunks_blob = bucket.blob(chunks_gcs_path)
            chunks_blob.upload_from_string(
                json.dumps(chunks_data, ensure_ascii=False, indent=2),
                content_type='application/json'
            )
            
            logger.info(f"PDF procesado exitosamente. Chunks guardados en: {chunks_gcs_path}")
    
    except Exception as e:
        logger.error(f"Error en process_pdf_to_chunks: {str(e)}")
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
    Genera embeddings y actualiza el índice FAISS global.
    
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
                f"Embeddings procesados exitosamente. Índice actualizado: {result['total_vectors']} vectores totales",
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
    event_type = event_data.get('eventType')
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
    temp_dir = tempfile.mkdtemp(prefix='drcecim_embeddings_')
    
    try:
        # 1. Descargar y cargar chunks
        chunks_data = _download_and_load_chunks(gcs_service, file_name, session_id)
        
        # 2. Buscar document_id y actualizar estado
        document_id = _update_document_status_start(status_service, chunks_data)
        
        # 3. Generar embeddings
        embeddings_result = _generate_embeddings(chunks_data, temp_dir, session_id, document_id, status_service)
        
        # 4. Gestionar índice FAISS
        result = _manage_faiss_index(gcs_service, embeddings_result, session_id)
        
        # 5. Actualizar estado final
        _update_document_status_completed(status_service, document_id, result)
        
        return result
        
    finally:
        # Limpiar recursos
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except (OSError, PermissionError) as e:
                logger.debug(f"No se pudo eliminar directorio temporal {temp_dir}: {e}")


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
            f"Embeddings generados exitosamente. Actualizando índice FAISS",
            "embeddings_generated",
            metadata={
                'embedding_dimension': embeddings_result.get('config', {}).get('dimension', 0),
                'num_vectors': embeddings_result.get('config', {}).get('num_vectors', 0)
            }
        )
    
    return embeddings_result


def _manage_faiss_index(gcs_service: GCSService, embeddings_result: Dict, session_id: str) -> Dict[str, Any]:
    """
    Gestiona la carga, actualización y guardado del índice FAISS.
    """
    index_manager = IndexManagerService(gcs_service)
    
    # Cargar índice existente
    app_logger.info("Cargando índice FAISS existente", {'session_id': session_id})
    existing_index, existing_metadata, index_exists = index_manager.load_existing_index()
    
    processing_monitor.log_step(session_id, "existing_index_loaded", {
        'index_exists': index_exists,
        'existing_vectors': existing_index.ntotal if existing_index else 0
    })
    
    # Eliminar chunks viejos del mismo documento si existen
    document_id = embeddings_result.get('config', {}).get('filename', '').replace('.pdf', '')
    if document_id and existing_index is not None:
        app_logger.info(f"Eliminando chunks viejos del documento: {document_id}", {'session_id': session_id})
        existing_index, existing_metadata, removed_chunks = index_manager.remove_old_document_chunks(
            existing_index, existing_metadata, document_id
        )
        
        processing_monitor.log_step(session_id, "old_chunks_removed", {
            'document_id': document_id,
            'removed_chunks_count': len(removed_chunks),
            'remaining_vectors': existing_index.ntotal if existing_index else 0
        })
    
    # Actualizar índice FAISS
    app_logger.info("Actualizando índice FAISS", {'session_id': session_id})
    updated_index, updated_metadata = index_manager.update_index(
        existing_index, 
        existing_metadata,
        embeddings_result['embeddings'],
        embeddings_result['metadata']
    )
    
    processing_monitor.log_step(session_id, "index_updated", {
        'total_vectors': updated_index.ntotal,
        'total_metadata_records': len(updated_metadata)
    })
    
    # Guardar índice actualizado en GCS
    app_logger.info("Guardando índice actualizado en GCS", {'session_id': session_id})
    uploaded_files = index_manager.save_index(updated_index, updated_metadata)
    
    processing_monitor.log_step(session_id, "index_saved", {'uploaded_files': uploaded_files})
    
    return {
        'total_vectors': updated_index.ntotal,
        'uploaded_files': uploaded_files
    }


def _update_document_status_completed(status_service: StatusService, document_id: str, result: Dict):
    """
    Actualiza el estado final del documento.
    """
    if document_id:
        status_service.update_status(
            document_id, 
            DocumentStatus.COMPLETED, 
            f"Procesamiento completo. Índice FAISS actualizado con {result['total_vectors']} vectores totales",
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