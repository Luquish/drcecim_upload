"""
Google Cloud Function para procesar documentos PDF a chunks de texto.
Se activa cuando se sube un archivo PDF al bucket de entrada.

Esta función es parte de la arquitectura orientada a eventos que divide el
procesamiento en dos etapas para mejorar la robustez y escalabilidad.
"""
import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any

import functions_framework
from google.cloud import storage

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar nuestros servicios (ahora como paquete instalado)
try:
    from services.processing_service import DocumentProcessor
    from services.gcs_service import GCSService
    from services.status_service import StatusService, DocumentStatus
    from utils.monitoring import get_logger, get_processing_monitor, log_system_info
except ImportError as e:
    logger.error(f"Error al importar módulos: {str(e)}")
    raise

# Inicializar monitoreo
app_logger = get_logger("process_pdf_function")
processing_monitor = get_processing_monitor()

# Log información del sistema al inicio
log_system_info()


def is_pdf_file(file_name: str) -> bool:
    """
    Verifica si el archivo es un PDF.
    
    Args:
        file_name (str): Nombre del archivo
        
    Returns:
        bool: True si es un PDF
    """
    return file_name.lower().endswith('.pdf')


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


@functions_framework.cloud_event
def process_pdf_to_chunks(cloud_event):
    """
    Cloud Function que se activa por eventos de Cloud Storage.
    Procesa PDFs y genera chunks de texto.
    
    Args:
        cloud_event: Evento de Cloud Storage
    """
    try:
        # Extraer información del evento
        event_data = cloud_event.data
        bucket_name = event_data.get('bucket')
        file_name = event_data.get('name')
        event_type = event_data.get('eventType')
        
        app_logger.info(f"Evento recibido: {event_type} para archivo: {file_name}")
        
        # Verificar que sea un evento de creación/actualización
        if 'finalize' not in event_type:
            app_logger.info(f"Ignorando evento {event_type}")
            return
        
        # Verificar que sea un archivo PDF
        if not is_pdf_file(file_name):
            app_logger.info(f"Ignorando archivo no-PDF: {file_name}")
            return
        
        # Iniciar monitoreo de procesamiento
        session_id = processing_monitor.start_processing(file_name)
        app_logger.info(f"Iniciando procesamiento de PDF: {file_name}", {'session_id': session_id})
        
        # Registrar documento en el servicio de estado
        status_service = StatusService()
        document_id = status_service.register_document(file_name)
        status_service.update_status(
            document_id, 
            DocumentStatus.PROCESSING, 
            "Iniciando procesamiento de PDF",
            "pdf_processing_start"
        )
        
        # Crear directorio temporal
        temp_dir = tempfile.mkdtemp(prefix='drcecim_pdf_')
        temp_file_path = None
        
        try:
            # Inicializar servicio GCS
            gcs_service = GCSService(bucket_name=bucket_name)
            
            # Descargar archivo PDF
            app_logger.info("Descargando PDF desde GCS", {'session_id': session_id})
            temp_file_path = os.path.join(temp_dir, Path(file_name).name)
            gcs_service.download_file(file_name, temp_file_path)
            
            processing_monitor.log_step(session_id, "pdf_downloaded", {'temp_path': temp_file_path})
            status_service.update_status(
                document_id, 
                DocumentStatus.PROCESSING, 
                "PDF descargado, iniciando conversión a texto",
                "pdf_downloaded"
            )
            
            # Procesar PDF a chunks
            app_logger.info("Procesando PDF con DocumentProcessor", {'session_id': session_id})
            processing_monitor.log_step(session_id, "pdf_processing_started")
            
            doc_processor = DocumentProcessor(temp_dir)
            processed_doc = doc_processor.process_document_complete(temp_file_path)
            
            if not processed_doc.get('processed_successfully', False):
                error_msg = processed_doc.get('error', 'Error desconocido en el procesamiento')
                app_logger.error(f"Error en procesamiento: {error_msg}", {'session_id': session_id})
                processing_monitor.finish_processing(session_id, success=False, error_message=error_msg)
                status_service.update_status(
                    document_id, 
                    DocumentStatus.ERROR, 
                    f"Error en procesamiento: {error_msg}",
                    "processing_error"
                )
                return
            
            processing_monitor.log_step(session_id, "pdf_processing_completed", {
                'num_chunks': processed_doc.get('num_chunks', 0),
                'total_words': processed_doc.get('total_words', 0)
            })
            status_service.update_status(
                document_id, 
                DocumentStatus.PROCESSING, 
                f"PDF convertido exitosamente. Generados {processed_doc.get('num_chunks', 0)} chunks",
                "pdf_processing_completed",
                metadata={
                    'num_chunks': processed_doc.get('num_chunks', 0),
                    'total_words': processed_doc.get('total_words', 0)
                }
            )
            
            # Preparar datos para subir al bucket intermedio
            chunks_data = {
                'filename': processed_doc['filename'],
                'chunks': processed_doc['chunks'],
                'metadata': processed_doc['metadata'],
                'num_chunks': processed_doc['num_chunks'],
                'total_words': processed_doc['total_words'],
                'processing_timestamp': processed_doc.get('processing_timestamp'),
                'source_file': file_name
            }
            
            # Subir chunks procesados al bucket intermedio
            chunks_filename = f"{Path(file_name).stem}_chunks.json"
            chunks_gcs_path = f"{GCS_PROCESSED_PREFIX}{chunks_filename}"
            
            app_logger.info("Subiendo chunks procesados a GCS", {'session_id': session_id})
            processing_monitor.log_step(session_id, "chunks_upload_started")
            
            chunks_json = json.dumps(chunks_data, ensure_ascii=False, indent=2)
            upload_success = gcs_service.upload_string(
                chunks_json, 
                chunks_gcs_path, 
                content_type='application/json'
            )
            
            if upload_success:
                processing_monitor.log_step(session_id, "chunks_upload_completed", {
                    'chunks_file': chunks_gcs_path
                })
                processing_monitor.finish_processing(session_id, success=True)
                status_service.update_status(
                    document_id, 
                    DocumentStatus.COMPLETED, 
                    f"Documento procesado exitosamente. Chunks guardados en: {chunks_gcs_path}",
                    "processing_completed",
                    metadata={'chunks_file': chunks_gcs_path}
                )
                app_logger.info(
                    f"PDF procesado exitosamente. Chunks guardados en: {chunks_gcs_path}",
                    {'session_id': session_id}
                )
            else:
                error_msg = "Error al subir chunks a GCS"
                app_logger.error(error_msg, {'session_id': session_id})
                processing_monitor.finish_processing(session_id, success=False, error_message=error_msg)
                status_service.update_status(
                    document_id, 
                    DocumentStatus.ERROR, 
                    error_msg,
                    "upload_error"
                )
            
        except Exception as e:
            error_msg = f"Error durante el procesamiento: {str(e)}"
            app_logger.error(error_msg, {'session_id': session_id})
            processing_monitor.finish_processing(session_id, success=False, error_message=error_msg)
            if 'document_id' in locals():
                status_service.update_status(
                    document_id, 
                    DocumentStatus.ERROR, 
                    error_msg,
                    "exception_error"
                )
            raise
        
        finally:
            # Limpiar archivos temporales
            if temp_file_path:
                cleanup_temp_files(temp_file_path)
            if temp_dir and os.path.exists(temp_dir):
                try:
                    os.rmdir(temp_dir)
                except:
                    pass
    
    except Exception as e:
        logger.error(f"Error en process_pdf_to_chunks: {str(e)}")
        raise


@functions_framework.http
def health_check(request):
    """
    Endpoint de health check para la función.
    """
    return {
        'status': 'healthy',
        'function': 'process_pdf_to_chunks',
        'version': '1.0.0'
    }


if __name__ == '__main__':
    # Para testing local
    pass 