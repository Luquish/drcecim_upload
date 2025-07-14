"""
Google Cloud Function para generar embeddings y actualizar el índice FAISS.
Se activa cuando aparecen archivos de chunks procesados en el bucket intermedio.

Esta función implementa la actualización incremental del índice FAISS global,
combinando los nuevos embeddings con el índice existente.
"""
import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, List

import functions_framework
import pandas as pd
import numpy as np
import faiss

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importar nuestros servicios (ahora como paquete instalado)
try:
    from services.embeddings_service import EmbeddingService
    from services.gcs_service import GCSService
    from services.status_service import StatusService, DocumentStatus
    from utils.monitoring import get_logger, get_processing_monitor, log_system_info
    from config.settings import (
        GCS_BUCKET_NAME, TEMP_DIR, GCS_PROCESSED_PREFIX,
        GCS_EMBEDDINGS_PREFIX, GCS_METADATA_PREFIX,
        GCS_FAISS_INDEX_NAME, GCS_METADATA_NAME
    )
except ImportError as e:
    logger.error(f"Error al importar módulos: {str(e)}")
    raise

# Inicializar monitoreo
app_logger = get_logger("create_embeddings_function")
processing_monitor = get_processing_monitor()

# Log información del sistema al inicio
log_system_info()


def is_chunks_file(file_name: str) -> bool:
    """
    Verifica si el archivo es un archivo de chunks procesados.
    
    Args:
        file_name (str): Nombre del archivo
        
    Returns:
        bool: True si es un archivo de chunks
    """
    return file_name.lower().endswith('_chunks.json')


def load_existing_faiss_index(gcs_service: GCSService) -> tuple:
    """
    Carga el índice FAISS existente y los metadatos desde GCS.
    
    Args:
        gcs_service (GCSService): Servicio de GCS
        
    Returns:
        tuple: (faiss_index, metadata_df, index_exists)
    """
    try:
        faiss_index_path = f"{GCS_EMBEDDINGS_PREFIX}{GCS_FAISS_INDEX_NAME}"
        metadata_path = f"{GCS_METADATA_PREFIX}{GCS_METADATA_NAME}"
        
        # Verificar si existe el índice
        if not gcs_service.file_exists(faiss_index_path):
            app_logger.info("No existe índice FAISS previo. Creando nuevo índice.")
            return None, pd.DataFrame(), False
        
        # Crear directorio temporal
        temp_dir = tempfile.mkdtemp(prefix='drcecim_faiss_')
        
        # Descargar índice FAISS
        app_logger.info("Descargando índice FAISS existente")
        local_index_path = os.path.join(temp_dir, GCS_FAISS_INDEX_NAME)
        gcs_service.download_file(faiss_index_path, local_index_path)
        
        # Cargar índice FAISS
        faiss_index = faiss.read_index(local_index_path)
        app_logger.info(f"Índice FAISS cargado con {faiss_index.ntotal} vectores")
        
        # Descargar y cargar metadatos
        metadata_df = pd.DataFrame()
        if gcs_service.file_exists(metadata_path):
            app_logger.info("Descargando metadatos existentes")
            local_metadata_path = os.path.join(temp_dir, GCS_METADATA_NAME)
            gcs_service.download_file(metadata_path, local_metadata_path)
            metadata_df = pd.read_csv(local_metadata_path)
            app_logger.info(f"Metadatos cargados con {len(metadata_df)} registros")
        
        # Limpiar archivos temporales
        try:
            os.remove(local_index_path)
            if os.path.exists(local_metadata_path):
                os.remove(local_metadata_path)
            os.rmdir(temp_dir)
        except:
            pass
        
        return faiss_index, metadata_df, True
        
    except Exception as e:
        app_logger.error(f"Error al cargar índice existente: {str(e)}")
        return None, pd.DataFrame(), False


def remove_old_document_chunks(existing_index, existing_metadata: pd.DataFrame, 
                              document_id: str) -> tuple:
    """
    Elimina chunks viejos de un documento específico del índice FAISS y metadatos.
    
    Args:
        existing_index: Índice FAISS existente
        existing_metadata (pd.DataFrame): Metadatos existentes
        document_id (str): ID del documento cuyos chunks viejos se eliminarán
        
    Returns:
        tuple: (updated_index, updated_metadata_df, removed_indices)
    """
    try:
        if existing_index is None or existing_metadata.empty:
            app_logger.info("No hay índice existente o metadatos para limpiar")
            return existing_index, existing_metadata, []
        
        # Verificar si existe la columna document_id
        if 'document_id' not in existing_metadata.columns:
            app_logger.warning("Columna 'document_id' no encontrada en metadatos existentes. "
                             "Usando 'filename' como fallback.")
            # Crear document_id temporal basado en filename
            existing_metadata['document_id'] = existing_metadata['filename'].apply(
                lambda x: x.replace('.pdf', '') if x.endswith('.pdf') else x
            )
        
        # Encontrar índices de los chunks del documento a eliminar
        chunks_to_remove = existing_metadata[
            existing_metadata['document_id'] == document_id
        ].index.tolist()
        
        if not chunks_to_remove:
            app_logger.info(f"No se encontraron chunks existentes para el documento: {document_id}")
            return existing_index, existing_metadata, []
        
        app_logger.info(f"Eliminando {len(chunks_to_remove)} chunks viejos del documento: {document_id}")
        
        # Eliminar del índice FAISS
        # Nota: FAISS no tiene remove_ids nativo, necesitamos reconstruir el índice
        remaining_indices = [i for i in range(len(existing_metadata)) if i not in chunks_to_remove]
        
        if not remaining_indices:
            # Si no quedan chunks, retornar índice vacío
            app_logger.info("Todos los chunks han sido eliminados")
            return None, pd.DataFrame(), chunks_to_remove
        
        # Reconstruir índice con los vectores restantes
        dimension = existing_index.d
        new_index = faiss.IndexFlatIP(dimension)
        
        # Extraer vectores que queremos mantener
        all_vectors = existing_index.reconstruct_n(0, existing_index.ntotal)
        remaining_vectors = all_vectors[remaining_indices]
        
        # Añadir vectores restantes al nuevo índice
        new_index.add(remaining_vectors)
        
        # Actualizar metadatos eliminando las filas correspondientes
        updated_metadata = existing_metadata.drop(chunks_to_remove).reset_index(drop=True)
        
        app_logger.info(f"Índice reconstruido. Vectores restantes: {new_index.ntotal}")
        return new_index, updated_metadata, chunks_to_remove
        
    except Exception as e:
        app_logger.error(f"Error al eliminar chunks viejos: {str(e)}")
        # En caso de error, retornar el índice original
        return existing_index, existing_metadata, []


def update_faiss_index(existing_index, existing_metadata: pd.DataFrame, 
                      new_embeddings: np.ndarray, new_metadata: List[Dict]) -> tuple:
    """
    Actualiza el índice FAISS con nuevos embeddings.
    
    Args:
        existing_index: Índice FAISS existente (puede ser None)
        existing_metadata (pd.DataFrame): Metadatos existentes
        new_embeddings (np.ndarray): Nuevos embeddings
        new_metadata (List[Dict]): Nuevos metadatos
        
    Returns:
        tuple: (updated_index, updated_metadata_df)
    """
    try:
        # Crear nuevo DataFrame con los metadatos nuevos
        new_metadata_df = pd.DataFrame(new_metadata)
        
        if existing_index is None:
            # Crear nuevo índice si no existe uno previo
            dimension = new_embeddings.shape[1]
            faiss_index = faiss.IndexFlatIP(dimension)  # Usar producto interno
            faiss_index.add(new_embeddings)
            combined_metadata = new_metadata_df
            app_logger.info(f"Nuevo índice FAISS creado con {faiss_index.ntotal} vectores")
        else:
            # Agregar nuevos vectores al índice existente
            existing_index.add(new_embeddings)
            # Combinar metadatos
            combined_metadata = pd.concat([existing_metadata, new_metadata_df], ignore_index=True)
            faiss_index = existing_index
            app_logger.info(f"Índice FAISS actualizado. Total: {faiss_index.ntotal} vectores")
        
        return faiss_index, combined_metadata
        
    except Exception as e:
        app_logger.error(f"Error al actualizar índice FAISS: {str(e)}")
        raise


def save_updated_index(gcs_service: GCSService, faiss_index, metadata_df: pd.DataFrame) -> Dict[str, str]:
    """
    Guarda el índice actualizado y metadatos en GCS.
    
    Args:
        gcs_service (GCSService): Servicio de GCS
        faiss_index: Índice FAISS actualizado
        metadata_df (pd.DataFrame): Metadatos actualizados
        
    Returns:
        Dict[str, str]: Rutas de archivos subidos
    """
    try:
        # Crear directorio temporal
        temp_dir = tempfile.mkdtemp(prefix='drcecim_save_')
        uploaded_files = {}
        
        # Guardar índice FAISS
        local_index_path = os.path.join(temp_dir, GCS_FAISS_INDEX_NAME)
        faiss.write_index(faiss_index, local_index_path)
        
        gcs_index_path = f"{GCS_EMBEDDINGS_PREFIX}{GCS_FAISS_INDEX_NAME}"
        if gcs_service.upload_file(local_index_path, gcs_index_path):
            uploaded_files['faiss_index'] = gcs_index_path
            app_logger.info(f"Índice FAISS guardado en: {gcs_index_path}")
        
        # Guardar metadatos
        local_metadata_path = os.path.join(temp_dir, GCS_METADATA_NAME)
        metadata_df.to_csv(local_metadata_path, index=False)
        
        gcs_metadata_path = f"{GCS_METADATA_PREFIX}{GCS_METADATA_NAME}"
        if gcs_service.upload_file(local_metadata_path, gcs_metadata_path):
            uploaded_files['metadata'] = gcs_metadata_path
            app_logger.info(f"Metadatos guardados en: {gcs_metadata_path}")
        
        # Limpiar archivos temporales
        try:
            os.remove(local_index_path)
            os.remove(local_metadata_path)
            os.rmdir(temp_dir)
        except:
            pass
        
        return uploaded_files
        
    except Exception as e:
        app_logger.error(f"Error al guardar índice actualizado: {str(e)}")
        raise


@functions_framework.cloud_event
def create_embeddings_from_chunks(cloud_event):
    """
    Cloud Function que se activa por eventos de Cloud Storage.
    Genera embeddings y actualiza el índice FAISS global.
    
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
        
        # Verificar que sea un archivo de chunks
        if not is_chunks_file(file_name):
            app_logger.info(f"Ignorando archivo no-chunks: {file_name}")
            return
        
        # Iniciar monitoreo de procesamiento
        session_id = processing_monitor.start_processing(file_name)
        app_logger.info(f"Iniciando generación de embeddings: {file_name}", {'session_id': session_id})
        
        # Inicializar servicio de estado
        status_service = StatusService()
        document_id = None
        
        try:
            # Inicializar servicios
            gcs_service = GCSService(bucket_name=bucket_name)
            temp_dir = tempfile.mkdtemp(prefix='drcecim_embeddings_')
            
            # Descargar archivo de chunks
            app_logger.info("Descargando archivo de chunks", {'session_id': session_id})
            chunks_content = gcs_service.read_file_as_string(file_name)
            chunks_data = json.loads(chunks_content)
            
            processing_monitor.log_step(session_id, "chunks_downloaded", {
                'num_chunks': chunks_data.get('num_chunks', 0)
            })
            
            # Buscar el document_id correspondiente basado en el nombre del archivo
            original_filename = chunks_data.get('filename', '')
            if original_filename:
                # Buscar documentos que coincidan con el nombre del archivo
                all_docs = status_service.get_all_documents(limit=50)
                for doc in all_docs:
                    if doc.get('filename') == original_filename:
                        document_id = doc.get('document_id')
                        break
                
                # Actualizar estado para indicar inicio de generación de embeddings
                if document_id:
                    status_service.update_status(
                        document_id, 
                        DocumentStatus.PROCESSING, 
                        f"Iniciando generación de embeddings para {chunks_data.get('num_chunks', 0)} chunks",
                        "embeddings_generation_start"
                    )
            
            # Generar embeddings para los chunks
            app_logger.info("Generando embeddings", {'session_id': session_id})
            processing_monitor.log_step(session_id, "embeddings_generation_started")
            
            embedding_service = EmbeddingService(temp_dir)
            embeddings_result = embedding_service.process_document_embeddings(chunks_data)
            
            if not embeddings_result.get('processed_successfully', False):
                error_msg = embeddings_result.get('error', 'Error en generación de embeddings')
                app_logger.error(error_msg, {'session_id': session_id})
                processing_monitor.finish_processing(session_id, success=False, error_message=error_msg)
                if document_id:
                    status_service.update_status(
                        document_id, 
                        DocumentStatus.ERROR, 
                        f"Error en generación de embeddings: {error_msg}",
                        "embeddings_error"
                    )
                return
            
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
            
            # Cargar índice FAISS existente
            app_logger.info("Cargando índice FAISS existente", {'session_id': session_id})
            existing_index, existing_metadata, index_exists = load_existing_faiss_index(gcs_service)
            
            processing_monitor.log_step(session_id, "existing_index_loaded", {
                'index_exists': index_exists,
                'existing_vectors': existing_index.ntotal if existing_index else 0
            })
            
            # Eliminar chunks viejos del mismo documento si existen
            document_id = embeddings_result.get('config', {}).get('filename', '').replace('.pdf', '')
            if document_id and existing_index is not None:
                app_logger.info(f"Eliminando chunks viejos del documento: {document_id}", {'session_id': session_id})
                existing_index, existing_metadata, removed_chunks = remove_old_document_chunks(
                    existing_index, existing_metadata, document_id
                )
                
                processing_monitor.log_step(session_id, "old_chunks_removed", {
                    'document_id': document_id,
                    'removed_chunks_count': len(removed_chunks),
                    'remaining_vectors': existing_index.ntotal if existing_index else 0
                })
            
            # Actualizar índice FAISS
            app_logger.info("Actualizando índice FAISS", {'session_id': session_id})
            updated_index, updated_metadata = update_faiss_index(
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
            uploaded_files = save_updated_index(gcs_service, updated_index, updated_metadata)
            
            processing_monitor.log_step(session_id, "index_saved", {'uploaded_files': uploaded_files})
            processing_monitor.finish_processing(session_id, success=True)
            
            if document_id:
                status_service.update_status(
                    document_id, 
                    DocumentStatus.COMPLETED, 
                    f"Procesamiento completo. Índice FAISS actualizado con {updated_index.ntotal} vectores totales",
                    "embeddings_completed",
                    metadata={
                        'total_vectors': updated_index.ntotal,
                        'uploaded_files': uploaded_files
                    }
                )
            
            app_logger.info(
                f"Embeddings procesados exitosamente. Índice actualizado: {updated_index.ntotal} vectores totales",
                {'session_id': session_id}
            )
            
        except Exception as e:
            error_msg = f"Error durante el procesamiento de embeddings: {str(e)}"
            app_logger.error(error_msg, {'session_id': session_id})
            processing_monitor.finish_processing(session_id, success=False, error_message=error_msg)
            if document_id:
                status_service.update_status(
                    document_id, 
                    DocumentStatus.ERROR, 
                    error_msg,
                    "embeddings_exception_error"
                )
            raise
        
        finally:
            # Limpiar directorio temporal
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                try:
                    os.rmdir(temp_dir)
                except:
                    pass
    
    except Exception as e:
        logger.error(f"Error en create_embeddings_from_chunks: {str(e)}")
        raise


@functions_framework.http
def health_check(request):
    """
    Endpoint de health check para la función.
    """
    return {
        'status': 'healthy',
        'function': 'create_embeddings_from_chunks',
        'version': '1.0.0'
    }


if __name__ == '__main__':
    # Para testing local
    pass 