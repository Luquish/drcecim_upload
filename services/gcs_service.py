"""
Servicio para gestionar la interacción con Google Cloud Storage.
"""
import os
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from google.cloud import storage
import pandas as pd
import numpy as np
import faiss
import json

from config.settings import (
    GCS_BUCKET_NAME,
    GCS_CREDENTIALS_PATH,
    GCS_EMBEDDINGS_PREFIX,
    GCS_METADATA_PREFIX,
    GCS_PROCESSED_PREFIX,
    GCS_TEMP_PREFIX,
    GCS_FAISS_INDEX_NAME,
    GCS_METADATA_NAME,
    GCS_METADATA_SUMMARY_NAME,
    GCS_CONFIG_NAME,
    TEMP_DIR
)

# Configurar logger
logger = logging.getLogger(__name__)


class GCSService:
    """
    Servicio para gestionar la interacción con Google Cloud Storage.
    """
    
    def __init__(self, bucket_name: str = None, credentials_path: str = None):
        """
        Inicializa el servicio de Google Cloud Storage.
        
        Args:
            bucket_name (str): Nombre del bucket de GCS
            credentials_path (str): Ruta al archivo de credenciales
        """
        self.bucket_name = bucket_name or GCS_BUCKET_NAME
        self.credentials_path = credentials_path or GCS_CREDENTIALS_PATH
        
        if not self.bucket_name:
            raise ValueError("Se requiere el nombre del bucket de GCS (GCS_BUCKET_NAME)")
        
        # Configurar credenciales (opcional para desarrollo local)
        # En producción (Cloud Functions/Cloud Run) usar la cuenta de servicio asignada
        if self.credentials_path and os.path.exists(self.credentials_path):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.credentials_path
            logger.info(f"Credenciales configuradas desde archivo: {self.credentials_path}")
        else:
            logger.info("Usando credenciales por defecto (ADC - Application Default Credentials)")
        
        # Inicializar cliente de GCS
        try:
            self.client = storage.Client()
            self.bucket = self.client.bucket(self.bucket_name)
            logger.info(f"Servicio GCS inicializado para el bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Error al inicializar cliente GCS: {str(e)}")
            logger.error("Asegúrate de que las credenciales estén configuradas correctamente:")
            logger.error("- Desarrollo: Usar archivo de credenciales (GCS_CREDENTIALS_PATH)")
            logger.error("- Producción: Asignar cuenta de servicio al recurso (Cloud Function/Cloud Run)")
            raise
        
        # Directorio temporal para archivos descargados
        self.temp_dir = Path(TEMP_DIR)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directorio temporal: {self.temp_dir}")
    
    def list_files(self, prefix: str = "") -> List[str]:
        """
        Lista los archivos en el bucket con un prefijo especificado.
        
        Args:
            prefix (str): Prefijo para filtrar archivos
            
        Returns:
            List[str]: Lista de nombres de archivos
        """
        try:
            blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
            files = [blob.name for blob in blobs]
            logger.info(f"Encontrados {len(files)} archivos con prefijo '{prefix}'")
            return files
        except (ValueError, TypeError) as e:
            logger.error(f"Error en parámetros al listar archivos: {str(e)}")
            raise ValueError(f"Parámetros inválidos para listar archivos: {str(e)}")
        except Exception as e:
            logger.error(f"Error de conectividad al listar archivos: {str(e)}")
            raise ConnectionError(f"No se pudo conectar con GCS: {str(e)}")
    
    def upload_file(self, local_path: str, gcs_path: str, content_type: Optional[str] = None) -> bool:
        """
        Sube un archivo local a GCS.
        
        Args:
            local_path (str): Ruta local del archivo
            gcs_path (str): Ruta destino en GCS
            content_type (Optional[str]): Tipo de contenido del archivo
            
        Returns:
            bool: True si se subió exitosamente
        """
        try:
            blob = self.bucket.blob(gcs_path)
            
            if content_type:
                blob.content_type = content_type
            
            with open(local_path, 'rb') as f:
                blob.upload_from_file(f)
                
            logger.info(f"Archivo subido exitosamente: {local_path} -> gs://{self.bucket_name}/{gcs_path}")
            return True
            
        except FileNotFoundError as e:
            logger.error(f"Archivo local no encontrado: {local_path}")
            return False
        except PermissionError as e:
            logger.error(f"Sin permisos para leer archivo: {local_path}")
            return False
        except Exception as e:
            logger.error(f"Error de conectividad al subir archivo: {str(e)}")
            return False
    
    def upload_string(self, content: str, gcs_path: str, content_type: str = 'text/plain') -> bool:
        """
        Sube un string como archivo a GCS.
        
        Args:
            content (str): Contenido del string
            gcs_path (str): Ruta destino en GCS
            content_type (str): Tipo de contenido
            
        Returns:
            bool: True si se subió exitosamente
        """
        try:
            blob = self.bucket.blob(gcs_path)
            blob.content_type = content_type
            blob.upload_from_string(content)
            
            logger.info(f"String subido exitosamente: gs://{self.bucket_name}/{gcs_path}")
            return True
            
        except (ValueError, TypeError) as e:
            logger.error(f"Contenido o tipo de contenido inválido: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error de conectividad al subir string: {str(e)}")
            return False
    
    def download_file(self, gcs_path: str, local_path: Optional[str] = None) -> str:
        """
        Descarga un archivo de GCS a una ubicación local.
        
        Args:
            gcs_path (str): Ruta del archivo en GCS
            local_path (str): Ruta local donde guardar el archivo
            
        Returns:
            str: Ruta local donde se descargó el archivo
        """
        if local_path is None:
            local_path = self.temp_dir / os.path.basename(gcs_path)
        
        try:
            blob = self.bucket.blob(gcs_path)
            
            if not blob.exists():
                raise FileNotFoundError(f"El archivo {gcs_path} no existe en el bucket {self.bucket_name}")
            
            blob.download_to_filename(str(local_path))
            logger.info(f"Archivo descargado: gs://{self.bucket_name}/{gcs_path} -> {local_path}")
            return str(local_path)
            
        except FileNotFoundError:
            raise  # Re-lanzar FileNotFoundError tal como está
        except PermissionError as e:
            logger.error(f"Sin permisos para escribir en: {local_path}")
            raise PermissionError(f"Sin permisos de escritura: {local_path}")
        except Exception as e:
            logger.error(f"Error de conectividad al descargar archivo: {str(e)}")
            raise ConnectionError(f"Error de red al descargar desde GCS: {str(e)}")
    
    def read_file_as_string(self, gcs_path: str) -> str:
        """
        Lee un archivo de GCS como string.
        
        Args:
            gcs_path (str): Ruta del archivo en GCS
            
        Returns:
            str: Contenido del archivo como string
        """
        try:
            blob = self.bucket.blob(gcs_path)
            
            if not blob.exists():
                raise FileNotFoundError(f"El archivo {gcs_path} no existe en el bucket {self.bucket_name}")
            
            content = blob.download_as_string().decode('utf-8')
            logger.info(f"Archivo leído como string: gs://{self.bucket_name}/{gcs_path}")
            return content
            
        except FileNotFoundError:
            raise  # Re-lanzar FileNotFoundError tal como está
        except UnicodeDecodeError as e:
            logger.error(f"Error de codificación al leer archivo: {gcs_path}")
            raise ValueError(f"Archivo no es texto válido UTF-8: {gcs_path}")
        except Exception as e:
            logger.error(f"Error de conectividad al leer archivo como string: {str(e)}")
            raise ConnectionError(f"Error de red al leer desde GCS: {str(e)}")
    
    def read_file_as_bytes(self, gcs_path: str) -> bytes:
        """
        Lee un archivo de GCS como bytes.
        
        Args:
            gcs_path (str): Ruta del archivo en GCS
            
        Returns:
            bytes: Contenido del archivo como bytes
        """
        try:
            blob = self.bucket.blob(gcs_path)
            
            if not blob.exists():
                raise FileNotFoundError(f"El archivo {gcs_path} no existe en el bucket {self.bucket_name}")
            
            content = blob.download_as_bytes()
            logger.info(f"Archivo leído como bytes: gs://{self.bucket_name}/{gcs_path}")
            return content
            
        except FileNotFoundError:
            raise  # Re-lanzar FileNotFoundError tal como está
        except Exception as e:
            logger.error(f"Error de conectividad al leer archivo como bytes: {str(e)}")
            raise ConnectionError(f"Error de red al leer desde GCS: {str(e)}")
    
    def file_exists(self, gcs_path: str) -> bool:
        """
        Verifica si un archivo existe en GCS.
        
        Args:
            gcs_path (str): Ruta del archivo en GCS
            
        Returns:
            bool: True si el archivo existe
        """
        try:
            blob = self.bucket.blob(gcs_path)
            return blob.exists()
        except Exception as e:
            logger.error(f"Error de conectividad al verificar existencia del archivo: {str(e)}")
            return False
            return False
    
    def delete_file(self, gcs_path: str) -> bool:
        """
        Elimina un archivo de GCS.
        
        Args:
            gcs_path (str): Ruta del archivo en GCS
            
        Returns:
            bool: True si se eliminó exitosamente
        """
        try:
            blob = self.bucket.blob(gcs_path)
            
            if blob.exists():
                blob.delete()
                logger.info(f"Archivo eliminado: gs://{self.bucket_name}/{gcs_path}")
                return True
            else:
                logger.warning(f"El archivo no existe: gs://{self.bucket_name}/{gcs_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error al eliminar archivo: {str(e)}")
            return False
    
    def get_file_metadata(self, gcs_path: str) -> Dict[str, Any]:
        """
        Obtiene metadatos de un archivo en GCS.
        
        Args:
            gcs_path (str): Ruta del archivo en GCS
            
        Returns:
            Dict[str, Any]: Diccionario con metadatos del archivo
        """
        try:
            blob = self.bucket.blob(gcs_path)
            
            if not blob.exists():
                raise FileNotFoundError(f"El archivo {gcs_path} no existe en el bucket {self.bucket_name}")
            
            # Recargar para obtener metadatos actualizados
            blob.reload()
            
            metadata = {
                'name': blob.name,
                'size': blob.size,
                'content_type': blob.content_type,
                'created': blob.time_created.isoformat() if blob.time_created else None,
                'updated': blob.updated.isoformat() if blob.updated else None,
                'md5_hash': blob.md5_hash,
                'generation': blob.generation,
                'metageneration': blob.metageneration
            }
            
            logger.info(f"Metadatos obtenidos para: gs://{self.bucket_name}/{gcs_path}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error al obtener metadatos: {str(e)}")
            raise
    
    def upload_embeddings_data(self, embeddings_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Sube todos los datos de embeddings a GCS.
        
        Args:
            embeddings_data (Dict[str, Any]): Datos de embeddings
            
        Returns:
            Dict[str, str]: Diccionario con rutas GCS de archivos subidos
        """
        if not embeddings_data.get('processed_successfully', False):
            raise ValueError("Los datos de embeddings no se procesaron correctamente")
        
        filename = embeddings_data.get('filename', 'unknown')
        filename_stem = Path(filename).stem
        
        # Crear directorio temporal para guardar archivos
        temp_embed_dir = self.temp_dir / f"embeddings_{filename_stem}"
        temp_embed_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Guardar archivos temporalmente
            temp_files = {
                'faiss_index': temp_embed_dir / GCS_FAISS_INDEX_NAME,
                'metadata': temp_embed_dir / GCS_METADATA_NAME,
                'metadata_summary': temp_embed_dir / GCS_METADATA_SUMMARY_NAME,
                'config': temp_embed_dir / GCS_CONFIG_NAME
            }
            
            # Guardar índice FAISS
            faiss.write_index(embeddings_data['faiss_index'], str(temp_files['faiss_index']))
            
            # Guardar metadatos
            embeddings_data['metadata'].to_csv(temp_files['metadata'], index=False)
            embeddings_data['metadata_summary'].to_csv(temp_files['metadata_summary'], index=False)
            
            # Guardar configuración
            with open(temp_files['config'], 'w') as f:
                json.dump(embeddings_data['config'], f, indent=2)
            
            # Definir rutas GCS
            gcs_paths = {
                'faiss_index': f"{GCS_EMBEDDINGS_PREFIX}{GCS_FAISS_INDEX_NAME}",
                'metadata': f"{GCS_METADATA_PREFIX}{GCS_METADATA_NAME}",
                'metadata_summary': f"{GCS_METADATA_PREFIX}{GCS_METADATA_SUMMARY_NAME}",
                'config': f"{GCS_EMBEDDINGS_PREFIX}{GCS_CONFIG_NAME}"
            }
            
            # Subir archivos a GCS
            uploaded_files = {}
            for file_type, local_path in temp_files.items():
                gcs_path = gcs_paths[file_type]
                
                if self.upload_file(str(local_path), gcs_path):
                    uploaded_files[file_type] = f"gs://{self.bucket_name}/{gcs_path}"
                else:
                    raise RuntimeError(f"Error al subir {file_type} a GCS")
            
            logger.info(f"Datos de embeddings subidos exitosamente para {filename}")
            return uploaded_files
            
        except Exception as e:
            logger.error(f"Error al subir datos de embeddings: {str(e)}")
            raise
        finally:
            # Limpiar archivos temporales
            self._cleanup_directory(temp_embed_dir)
    
    def load_embeddings_data(self) -> Dict[str, Any]:
        """
        Carga los datos de embeddings desde GCS.
        
        Returns:
            Dict[str, Any]: Diccionario con los datos de embeddings cargados
        """
        try:
            # Definir rutas GCS
            gcs_paths = {
                'faiss_index': f"{GCS_EMBEDDINGS_PREFIX}{GCS_FAISS_INDEX_NAME}",
                'metadata': f"{GCS_METADATA_PREFIX}{GCS_METADATA_NAME}",
                'config': f"{GCS_EMBEDDINGS_PREFIX}{GCS_CONFIG_NAME}"
            }
            
            # Verificar que todos los archivos existan
            for file_type, gcs_path in gcs_paths.items():
                if not self.file_exists(gcs_path):
                    raise FileNotFoundError(f"No se encontró {file_type} en GCS: {gcs_path}")
            
            # Descargar archivos
            temp_files = {}
            for file_type, gcs_path in gcs_paths.items():
                temp_files[file_type] = self.download_file(gcs_path)
            
            # Cargar índice FAISS
            faiss_index = faiss.read_index(temp_files['faiss_index'])
            logger.info(f"Índice FAISS cargado con {faiss_index.ntotal} vectores")
            
            # Cargar metadatos
            metadata = pd.read_csv(temp_files['metadata'])
            logger.info(f"Metadatos cargados con {len(metadata)} registros")
            
            # Cargar configuración
            with open(temp_files['config'], 'r') as f:
                config = json.load(f)
            
            return {
                'faiss_index': faiss_index,
                'metadata': metadata,
                'config': config,
                'loaded_successfully': True
            }
            
        except Exception as e:
            logger.error(f"Error al cargar datos de embeddings desde GCS: {str(e)}")
            raise
        finally:
            # Limpiar archivos temporales
            for temp_file in temp_files.values():
                try:
                    os.remove(temp_file)
                except (OSError, FileNotFoundError, PermissionError) as e:
                    logger.debug(f"No se pudo eliminar archivo temporal {temp_file}: {e}")
    
    def _cleanup_directory(self, directory: Path):
        """
        Limpia un directorio temporal.
        
        Args:
            directory (Path): Directorio a limpiar
        """
        try:
            if directory.exists():
                import shutil
                shutil.rmtree(directory)
                logger.info(f"Directorio temporal limpiado: {directory}")
        except Exception as e:
            logger.error(f"Error al limpiar directorio temporal: {str(e)}")
    
    def get_bucket_info(self) -> Dict[str, Any]:
        """
        Obtiene información del bucket.
        
        Returns:
            Dict[str, Any]: Información del bucket
        """
        try:
            bucket = self.client.get_bucket(self.bucket_name)
            
            info = {
                'name': bucket.name,
                'location': bucket.location,
                'storage_class': bucket.storage_class,
                'created': bucket.time_created.isoformat() if bucket.time_created else None,
                'updated': bucket.updated.isoformat() if bucket.updated else None,
                'versioning_enabled': bucket.versioning_enabled,
                'labels': bucket.labels
            }
            
            logger.info(f"Información del bucket obtenida: {self.bucket_name}")
            return info
            
        except Exception as e:
            logger.error(f"Error al obtener información del bucket: {str(e)}")
            raise


# Funciones de conveniencia
def upload_embeddings_to_gcs(embeddings_data: Dict[str, Any], 
                           bucket_name: str = None) -> Dict[str, str]:
    """
    Función de conveniencia para subir datos de embeddings a GCS.
    
    Args:
        embeddings_data (Dict[str, Any]): Datos de embeddings
        bucket_name (str): Nombre del bucket (opcional)
        
    Returns:
        Dict[str, str]: Diccionario con rutas GCS de archivos subidos
    """
    service = GCSService(bucket_name)
    return service.upload_embeddings_data(embeddings_data)


def load_embeddings_from_gcs(bucket_name: str = None) -> Dict[str, Any]:
    """
    Función de conveniencia para cargar datos de embeddings desde GCS.
    
    Args:
        bucket_name (str): Nombre del bucket (opcional)
        
    Returns:
        Dict[str, Any]: Diccionario con los datos de embeddings cargados
    """
    service = GCSService(bucket_name)
    return service.load_embeddings_data() 