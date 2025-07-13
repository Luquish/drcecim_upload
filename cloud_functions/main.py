"""
Google Cloud Function para procesar documentos PDF y generar embeddings.

⚠️  LEGACY: Esta función es considerada legacy. Para nuevos despliegues,
usar la nueva arquitectura orientada a eventos:
- process_pdf.py (procesar PDFs a chunks)
- create_embeddings.py (generar embeddings incremental)

Ver docs/NUEVA_ARQUITECTURA.md para más información.
"""
import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any

import flask
import functions_framework
from werkzeug.datastructures import FileStorage

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar nuestros servicios
try:
    from services.processing_service import DocumentProcessor
    from services.embeddings_service import EmbeddingService
    from services.gcs_service import GCSService
    from utils.monitoring import get_logger, get_processing_monitor, log_system_info
    from config.settings import (
        STREAMLIT_TITLE, MAX_FILE_SIZE_MB, ALLOWED_FILE_TYPES,
        GCS_BUCKET_NAME, TEMP_DIR
    )
except ImportError as e:
    logger.error(f"Error al importar módulos: {str(e)}")
    raise

# Inicializar monitoreo
app_logger = get_logger("cloud_function")
processing_monitor = get_processing_monitor()

# Log información del sistema al inicio
log_system_info()


def validate_file(file: FileStorage) -> Dict[str, Any]:
    """
    Valida que el archivo sea válido para procesamiento.
    
    Args:
        file (FileStorage): Archivo subido
        
    Returns:
        Dict[str, Any]: Resultado de validación
    """
    if not file or not file.filename:
        return {'valid': False, 'error': 'No se recibió ningún archivo'}
    
    # Verificar extensión
    file_extension = Path(file.filename).suffix.lower().lstrip('.')
    if file_extension not in ALLOWED_FILE_TYPES:
        return {
            'valid': False, 
            'error': f'Tipo de archivo no permitido. Solo se permiten: {", ".join(ALLOWED_FILE_TYPES)}'
        }
    
    # Verificar tamaño (aproximado)
    file.seek(0, 2)  # Ir al final del archivo
    file_size = file.tell()
    file.seek(0)  # Volver al inicio
    
    max_size_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_size_bytes:
        return {
            'valid': False,
            'error': f'El archivo excede el tamaño máximo permitido de {MAX_FILE_SIZE_MB}MB'
        }
    
    return {'valid': True}


def save_uploaded_file(file: FileStorage, temp_dir: str) -> str:
    """
    Guarda el archivo subido en un directorio temporal.
    
    Args:
        file (FileStorage): Archivo subido
        temp_dir (str): Directorio temporal
        
    Returns:
        str: Ruta del archivo guardado
    """
    temp_path = Path(temp_dir) / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Guardar archivo
    file.save(str(temp_path))
    logger.info(f"Archivo guardado temporalmente en: {temp_path}")
    
    return str(temp_path)


def cleanup_temp_files(temp_path: str):
    """
    Limpia archivos temporales.
    
    Args:
        temp_path (str): Ruta del archivo temporal
    """
    try:
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.info(f"Archivo temporal eliminado: {temp_path}")
    except Exception as e:
        logger.error(f"Error al eliminar archivo temporal: {str(e)}")


@functions_framework.http
def process_document(request: flask.Request) -> flask.Response:
    """
    Cloud Function HTTP para procesar documentos PDF.
    
    Args:
        request (flask.Request): Solicitud HTTP
        
    Returns:
        flask.Response: Respuesta HTTP con resultado del procesamiento
    """
    # Configurar CORS para permitir requests desde Streamlit
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return flask.Response('', 204, headers)
    
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'application/json'
    }
    
    try:
        # Validar método HTTP
        if request.method != 'POST':
            return flask.Response(
                json.dumps({'error': 'Método no permitido. Use POST.'}),
                405,
                headers
            )
        
        # Verificar que se haya subido un archivo
        if 'file' not in request.files:
            return flask.Response(
                json.dumps({'error': 'No se encontró el archivo en la solicitud'}),
                400,
                headers
            )
        
        file = request.files['file']
        
        # Validar archivo
        validation_result = validate_file(file)
        if not validation_result['valid']:
            return flask.Response(
                json.dumps({'error': validation_result['error']}),
                400,
                headers
            )
        
        # Iniciar monitoreo de procesamiento
        session_id = processing_monitor.start_processing(file.filename)
        app_logger.info(f"Iniciando procesamiento del archivo: {file.filename}", {'session_id': session_id})
        
        # Crear directorio temporal
        temp_dir = tempfile.mkdtemp(prefix='drcecim_')
        temp_file_path = None
        
        try:
            # Guardar archivo temporalmente
            temp_file_path = save_uploaded_file(file, temp_dir)
            processing_monitor.log_step(session_id, "file_uploaded", {'temp_path': temp_file_path})
            
            # Paso 1: Procesar PDF a Markdown y chunks
            app_logger.info("Paso 1: Procesando PDF con DocumentProcessor", {'session_id': session_id})
            processing_monitor.log_step(session_id, "pdf_processing_started")
            
            doc_processor = DocumentProcessor(temp_dir)
            processed_doc = doc_processor.process_document_complete(temp_file_path)
            
            if not processed_doc.get('processed_successfully', False):
                error_msg = processed_doc.get('error', 'Error desconocido en el procesamiento')
                app_logger.error(f"Error en procesamiento: {error_msg}", {'session_id': session_id})
                processing_monitor.finish_processing(session_id, success=False, error_message=error_msg)
                return flask.Response(
                    json.dumps({'error': f'Error al procesar documento: {error_msg}'}),
                    500,
                    headers
                )
            
            processing_monitor.log_step(session_id, "pdf_processing_completed", {
                'num_chunks': processed_doc.get('num_chunks', 0),
                'total_words': processed_doc.get('total_words', 0)
            })
            app_logger.info(f"Documento procesado exitosamente: {processed_doc['num_chunks']} chunks generados", {'session_id': session_id})
            
            # Paso 2: Generar embeddings
            app_logger.info("Paso 2: Generando embeddings con EmbeddingService", {'session_id': session_id})
            processing_monitor.log_step(session_id, "embeddings_generation_started")
            
            embedding_service = EmbeddingService(temp_dir)
            embeddings_data = embedding_service.process_document_embeddings(processed_doc)
            
            if not embeddings_data.get('processed_successfully', False):
                error_msg = embeddings_data.get('error', 'Error desconocido en embeddings')
                app_logger.error(f"Error en embeddings: {error_msg}", {'session_id': session_id})
                processing_monitor.finish_processing(session_id, success=False, error_message=error_msg)
                return flask.Response(
                    json.dumps({'error': f'Error al generar embeddings: {error_msg}'}),
                    500,
                    headers
                )
            
            processing_monitor.log_step(session_id, "embeddings_generation_completed", {
                'embedding_dimension': embeddings_data.get('config', {}).get('dimension', 0),
                'num_vectors': embeddings_data.get('config', {}).get('num_vectors', 0)
            })
            app_logger.info("Embeddings generados exitosamente", {'session_id': session_id})
            
            # Paso 3: Subir a Google Cloud Storage
            app_logger.info("Paso 3: Subiendo datos a Google Cloud Storage", {'session_id': session_id})
            processing_monitor.log_step(session_id, "gcs_upload_started")
            
            gcs_service = GCSService()
            uploaded_files = gcs_service.upload_embeddings_data(embeddings_data)
            
            processing_monitor.log_step(session_id, "gcs_upload_completed", {'uploaded_files': uploaded_files})
            app_logger.info(f"Datos subidos exitosamente a GCS: {uploaded_files}", {'session_id': session_id})
            
            # Preparar respuesta de éxito
            response_data = {
                'success': True,
                'message': 'Documento procesado exitosamente',
                'filename': processed_doc['filename'],
                'stats': {
                    'num_chunks': processed_doc['num_chunks'],
                    'total_words': processed_doc['total_words'],
                    'embedding_dimension': embeddings_data['config']['dimension'],
                    'num_vectors': embeddings_data['config']['num_vectors']
                },
                'gcs_files': uploaded_files,
                'processing_time': 'completado',
                'session_id': session_id
            }
            
            # Finalizar monitoreo exitoso
            processing_monitor.finish_processing(session_id, success=True, results=response_data['stats'])
            
            return flask.Response(
                json.dumps(response_data),
                200,
                headers
            )
            
        except Exception as e:
            app_logger.error(f"Error durante el procesamiento: {str(e)}", {
                'session_id': session_id if 'session_id' in locals() else 'unknown',
                'exception_type': type(e).__name__
            }, exc_info=True)
            
            # Finalizar monitoreo con error
            if 'session_id' in locals():
                processing_monitor.finish_processing(session_id, success=False, error_message=str(e))
            
            return flask.Response(
                json.dumps({'error': f'Error interno del servidor: {str(e)}'}),
                500,
                headers
            )
        
        finally:
            # Limpiar archivos temporales
            if temp_file_path:
                cleanup_temp_files(temp_file_path)
            
            # Limpiar directorio temporal
            try:
                import shutil
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    logger.info(f"Directorio temporal eliminado: {temp_dir}")
            except Exception as e:
                logger.error(f"Error al eliminar directorio temporal: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error crítico en process_document: {str(e)}", exc_info=True)
        return flask.Response(
            json.dumps({'error': 'Error crítico del servidor'}),
            500,
            headers
        )


@functions_framework.http
def metrics(request: flask.Request) -> flask.Response:
    """
    Endpoint de métricas para monitorear el estado del sistema.
    
    Args:
        request (flask.Request): Solicitud HTTP
        
    Returns:
        flask.Response: Respuesta con métricas del sistema
    """
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'application/json'
    }
    
    try:
        from utils.monitoring import get_metrics
        metrics_collector = get_metrics()
        
        # Obtener métricas del sistema
        system_metrics = metrics_collector.get_metrics()
        
        # Obtener estadísticas de procesamiento
        processing_stats = processing_monitor.get_processing_stats()
        
        # Combinar todas las métricas
        all_metrics = {
            'system': system_metrics,
            'processing': processing_stats,
            'health': 'healthy',
            'timestamp': flask.request.headers.get('X-Timestamp', 'unknown')
        }
        
        return flask.Response(
            json.dumps(all_metrics),
            200,
            headers
        )
        
    except Exception as e:
        app_logger.error(f"Error en endpoint de métricas: {str(e)}")
        return flask.Response(
            json.dumps({'error': str(e), 'health': 'unhealthy'}),
            500,
            headers
        )


@functions_framework.http
def health_check(request: flask.Request) -> flask.Response:
    """
    Endpoint de health check para verificar el estado de la función.
    
    Args:
        request (flask.Request): Solicitud HTTP
        
    Returns:
        flask.Response: Respuesta con estado de salud
    """
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'application/json'
    }
    
    try:
        # Verificar servicios básicos
        health_status = {
            'status': 'healthy',
            'timestamp': flask.request.headers.get('X-Timestamp', 'unknown'),
            'services': {
                'document_processor': 'available',
                'embedding_service': 'available',
                'gcs_service': 'available'
            },
            'config': {
                'bucket_name': GCS_BUCKET_NAME,
                'max_file_size_mb': MAX_FILE_SIZE_MB,
                'allowed_file_types': ALLOWED_FILE_TYPES
            }
        }
        
        return flask.Response(
            json.dumps(health_status),
            200,
            headers
        )
        
    except Exception as e:
        logger.error(f"Error en health check: {str(e)}")
        return flask.Response(
            json.dumps({'status': 'unhealthy', 'error': str(e)}),
            500,
            headers
        )


# Función por defecto para compatibilidad
def main(request: flask.Request) -> flask.Response:
    """
    Función principal que redirige a process_document.
    
    Args:
        request (flask.Request): Solicitud HTTP
        
    Returns:
        flask.Response: Respuesta HTTP
    """
    return process_document(request) 