"""
Google Cloud Function para procesar documentos PDF a chunks de texto.
Se activa cuando se sube un archivo PDF al bucket de entrada.
"""
import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

import functions_framework
from google.cloud import storage
import marker_pdf

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar configuración compartida
try:
    from common.config import get_config, get_gcs_config
    config = get_config()
    gcs_config = get_gcs_config()
except ImportError:
    # Fallback: usar variables de entorno directamente
    config = {
        'project_id': os.getenv('GCF_PROJECT_ID'),
        'bucket_name': os.getenv('GCS_BUCKET_NAME'),
        'region': os.getenv('GCF_REGION', 'us-central1'),
        'environment': os.getenv('ENVIRONMENT', 'production'),
        'log_level': os.getenv('LOG_LEVEL', 'INFO')
    }
    gcs_config = {
        'processed_prefix': 'processed/',
        'embeddings_prefix': 'embeddings/',
        'temp_prefix': 'temp/'
    }

# Configurar parámetros de procesamiento
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '250'))
CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '50'))


def is_pdf_file(file_name: str) -> bool:
    """Verifica si el archivo es un PDF."""
    return file_name.lower().endswith('.pdf')


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrae texto de un archivo PDF usando marker-pdf."""
    try:
        with open(pdf_path, 'rb') as file:
            doc = marker_pdf.Pdf(file.read())
            return doc.text()
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
            chunks_gcs_path = f"{gcs_config['processed_prefix']}{chunks_filename}"
            
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


@functions_framework.http
def health_check(request):
    """Endpoint de health check para la función."""
    return {
        'status': 'healthy',
        'function': 'process_pdf_to_chunks',
        'version': '1.0.0'
    }


if __name__ == '__main__':
    # Para testing local
    pass 