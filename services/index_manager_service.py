"""
Servicio para gestionar operaciones del índice FAISS.

Este servicio centraliza todas las operaciones relacionadas con el índice FAISS:
- Carga de índices existentes
- Eliminación de chunks viejos
- Actualización con nuevos embeddings
- Guardado del índice actualizado

Incluye manejo robusto de errores y reintentos para operaciones de red.
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import pandas as pd
import numpy as np
import faiss
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from google.api_core.exceptions import (
    NotFound, ServiceUnavailable, TooManyRequests, InternalServerError
)

from .gcs_service import GCSService
from utils.monitoring import get_logger
from config.settings import (
    GCS_EMBEDDINGS_PREFIX, GCS_METADATA_PREFIX,
    GCS_FAISS_INDEX_NAME, GCS_METADATA_NAME
)


class IndexManagerService:
    """Servicio para gestionar operaciones del índice FAISS."""
    
    def __init__(self, gcs_service: GCSService):
        """
        Inicializa el servicio del gestor de índices.
        
        Args:
            gcs_service (GCSService): Servicio de Google Cloud Storage
        """
        self.gcs_service = gcs_service
        self.logger = get_logger("index_manager_service")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ServiceUnavailable, TooManyRequests, InternalServerError))
    )
    def load_existing_index(self) -> Tuple[Optional[faiss.Index], pd.DataFrame, bool]:
        """
        Carga el índice FAISS existente y los metadatos desde GCS con reintentos.
        
        Returns:
            Tuple[Optional[faiss.Index], pd.DataFrame, bool]: 
                (faiss_index, metadata_df, index_exists)
        """
        try:
            faiss_index_path = f"{GCS_EMBEDDINGS_PREFIX}{GCS_FAISS_INDEX_NAME}"
            metadata_path = f"{GCS_METADATA_PREFIX}{GCS_METADATA_NAME}"
            
            # Verificar si existe el índice
            if not self.gcs_service.file_exists(faiss_index_path):
                self.logger.info("No existe índice FAISS previo. Creando nuevo índice.")
                return None, pd.DataFrame(), False
            
            # Crear directorio temporal
            temp_dir = tempfile.mkdtemp(prefix='drcecim_faiss_load_')
            
            try:
                # Descargar índice FAISS
                self.logger.info("Descargando índice FAISS existente")
                local_index_path = os.path.join(temp_dir, GCS_FAISS_INDEX_NAME)
                self.gcs_service.download_file(faiss_index_path, local_index_path)
                
                # Cargar índice FAISS
                faiss_index = faiss.read_index(local_index_path)
                self.logger.info(f"Índice FAISS cargado con {faiss_index.ntotal} vectores")
                
                # Descargar y cargar metadatos
                metadata_df = pd.DataFrame()
                if self.gcs_service.file_exists(metadata_path):
                    self.logger.info("Descargando metadatos existentes")
                    local_metadata_path = os.path.join(temp_dir, GCS_METADATA_NAME)
                    self.gcs_service.download_file(metadata_path, local_metadata_path)
                    metadata_df = pd.read_csv(local_metadata_path)
                    self.logger.info(f"Metadatos cargados con {len(metadata_df)} registros")
                
                return faiss_index, metadata_df, True
                
            finally:
                # Limpiar archivos temporales
                self._cleanup_temp_dir(temp_dir)
                
        except NotFound as e:
            self.logger.warning(f"Archivo no encontrado en GCS: {str(e)}")
            return None, pd.DataFrame(), False
        except Exception as e:
            self.logger.error(f"Error al cargar índice existente: {str(e)}")
            return None, pd.DataFrame(), False
    
    def remove_old_document_chunks(self, existing_index: Optional[faiss.Index], 
                                 existing_metadata: pd.DataFrame, 
                                 document_id: str) -> Tuple[Optional[faiss.Index], pd.DataFrame, List[int]]:
        """
        Elimina chunks viejos de un documento específico del índice FAISS y metadatos.
        
        Args:
            existing_index: Índice FAISS existente
            existing_metadata (pd.DataFrame): Metadatos existentes
            document_id (str): ID del documento cuyos chunks viejos se eliminarán
            
        Returns:
            Tuple[Optional[faiss.Index], pd.DataFrame, List[int]]: 
                (updated_index, updated_metadata_df, removed_indices)
        """
        try:
            if existing_index is None or existing_metadata.empty:
                self.logger.info("No hay índice existente o metadatos para limpiar")
                return existing_index, existing_metadata, []
            
            # Verificar si existe la columna document_id
            if 'document_id' not in existing_metadata.columns:
                self.logger.warning("Columna 'document_id' no encontrada en metadatos existentes. "
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
                self.logger.info(f"No se encontraron chunks existentes para el documento: {document_id}")
                return existing_index, existing_metadata, []
            
            self.logger.info(f"Eliminando {len(chunks_to_remove)} chunks viejos del documento: {document_id}")
            
            # Eliminar del índice FAISS
            # Nota: FAISS no tiene remove_ids nativo, necesitamos reconstruir el índice
            remaining_indices = [i for i in range(len(existing_metadata)) if i not in chunks_to_remove]
            
            if not remaining_indices:
                # Si no quedan chunks, retornar índice vacío
                self.logger.info("Todos los chunks han sido eliminados")
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
            
            self.logger.info(f"Índice reconstruido. Vectores restantes: {new_index.ntotal}")
            return new_index, updated_metadata, chunks_to_remove
            
        except Exception as e:
            self.logger.error(f"Error al eliminar chunks viejos: {str(e)}")
            # En caso de error, retornar el índice original
            return existing_index, existing_metadata, []
    
    def update_index(self, existing_index: Optional[faiss.Index], 
                    existing_metadata: pd.DataFrame, 
                    new_embeddings: np.ndarray, 
                    new_metadata: List[Dict]) -> Tuple[faiss.Index, pd.DataFrame]:
        """
        Actualiza el índice FAISS con nuevos embeddings.
        
        Args:
            existing_index: Índice FAISS existente (puede ser None)
            existing_metadata (pd.DataFrame): Metadatos existentes
            new_embeddings (np.ndarray): Nuevos embeddings
            new_metadata (List[Dict]): Nuevos metadatos
            
        Returns:
            Tuple[faiss.Index, pd.DataFrame]: (updated_index, updated_metadata_df)
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
                self.logger.info(f"Nuevo índice FAISS creado con {faiss_index.ntotal} vectores")
            else:
                # Agregar nuevos vectores al índice existente
                existing_index.add(new_embeddings)
                # Combinar metadatos
                combined_metadata = pd.concat([existing_metadata, new_metadata_df], ignore_index=True)
                faiss_index = existing_index
                self.logger.info(f"Índice FAISS actualizado. Total: {faiss_index.ntotal} vectores")
            
            return faiss_index, combined_metadata
            
        except Exception as e:
            self.logger.error(f"Error al actualizar índice FAISS: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ServiceUnavailable, TooManyRequests, InternalServerError))
    )
    def save_index(self, faiss_index: faiss.Index, metadata_df: pd.DataFrame) -> Dict[str, str]:
        """
        Guarda el índice actualizado y metadatos en GCS con reintentos.
        
        Args:
            faiss_index: Índice FAISS actualizado
            metadata_df (pd.DataFrame): Metadatos actualizados
            
        Returns:
            Dict[str, str]: Rutas de archivos subidos
        """
        try:
            # Crear directorio temporal
            temp_dir = tempfile.mkdtemp(prefix='drcecim_faiss_save_')
            uploaded_files = {}
            
            try:
                # Guardar índice FAISS
                local_index_path = os.path.join(temp_dir, GCS_FAISS_INDEX_NAME)
                faiss.write_index(faiss_index, local_index_path)
                
                gcs_index_path = f"{GCS_EMBEDDINGS_PREFIX}{GCS_FAISS_INDEX_NAME}"
                if self.gcs_service.upload_file(local_index_path, gcs_index_path):
                    uploaded_files['faiss_index'] = gcs_index_path
                    self.logger.info(f"Índice FAISS guardado en: {gcs_index_path}")
                
                # Guardar metadatos
                local_metadata_path = os.path.join(temp_dir, GCS_METADATA_NAME)
                metadata_df.to_csv(local_metadata_path, index=False)
                
                gcs_metadata_path = f"{GCS_METADATA_PREFIX}{GCS_METADATA_NAME}"
                if self.gcs_service.upload_file(local_metadata_path, gcs_metadata_path):
                    uploaded_files['metadata'] = gcs_metadata_path
                    self.logger.info(f"Metadatos guardados en: {gcs_metadata_path}")
                
                return uploaded_files
                
            finally:
                # Limpiar archivos temporales
                self._cleanup_temp_dir(temp_dir)
                
        except Exception as e:
            self.logger.error(f"Error al guardar índice actualizado: {str(e)}")
            raise
    
    def _cleanup_temp_dir(self, temp_dir: str) -> None:
        """
        Limpia un directorio temporal de forma segura.
        
        Args:
            temp_dir (str): Ruta del directorio temporal a limpiar
        """
        try:
            if os.path.exists(temp_dir):
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                os.rmdir(temp_dir)
        except Exception as e:
            self.logger.warning(f"No se pudo limpiar directorio temporal {temp_dir}: {str(e)}") 