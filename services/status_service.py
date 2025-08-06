"""
Servicio de seguimiento de estado para documentos procesados.
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from google.cloud import storage
from config.settings import GCS_BUCKET_NAME

logger = logging.getLogger(__name__)


class DocumentStatus(Enum):
    """Estados posibles de un documento en procesamiento."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class StatusService:
    """
    Servicio para gestionar el estado de los documentos procesados.
    """
    
    def __init__(self, bucket_name: str = GCS_BUCKET_NAME):
        """
        Inicializa el servicio de estado.
        
        Args:
            bucket_name (str): Nombre del bucket de GCS
        """
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(self.bucket_name)
        self.status_prefix = "status/"
        
    def register_document(self, filename: str, user_id: str = "default") -> str:
        """
        Registra un nuevo documento en el sistema de seguimiento.
        
        Args:
            filename (str): Nombre del archivo
            user_id (str): ID del usuario (opcional)
            
        Returns:
            str: ID único del documento
        """
        document_id = f"{filename}_{int(datetime.now().timestamp())}"
        
        status_data = {
            "document_id": document_id,
            "filename": filename,
            "user_id": user_id,
            "status": DocumentStatus.UPLOADED.value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "steps": [
                {
                    "step": "upload",
                    "status": "completed",
                    "timestamp": datetime.now().isoformat(),
                    "message": "Archivo subido exitosamente"
                }
            ],
            "metadata": {
                "file_size": 0,
                "total_chunks": 0,
                "processing_time": 0
            }
        }
        
        self._save_status(document_id, status_data)
        logger.info(f"Documento registrado: {document_id}")
        return document_id
    
    def update_status(self, document_id: str, status: DocumentStatus, 
                     message: str = "", step: str = "", metadata: Dict = None):
        """
        Actualiza el estado de un documento.
        
        Args:
            document_id (str): ID del documento
            status (DocumentStatus): Nuevo estado
            message (str): Mensaje descriptivo
            step (str): Paso actual del procesamiento
            metadata (Dict): Metadatos adicionales
        """
        try:
            status_data = self._load_status(document_id)
            if not status_data:
                logger.error(f"Documento no encontrado: {document_id}")
                return
            
            # Actualizar estado principal
            status_data["status"] = status.value
            status_data["updated_at"] = datetime.now().isoformat()
            
            # Agregar paso
            if step:
                status_data["steps"].append({
                    "step": step,
                    "status": status.value,
                    "timestamp": datetime.now().isoformat(),
                    "message": message
                })
            
            # Actualizar metadatos
            if metadata:
                status_data["metadata"].update(metadata)
            
            self._save_status(document_id, status_data)
            logger.info(f"Estado actualizado para {document_id}: {status.value}")
            
        except Exception as e:
            logger.error(f"Error actualizando estado: {str(e)}")
    
    def get_document_status(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene el estado actual de un documento.
        
        Args:
            document_id (str): ID del documento
            
        Returns:
            Dict: Estado del documento o None si no existe
        """
        return self._load_status(document_id)
    
    def get_user_documents(self, user_id: str = "default") -> List[Dict[str, Any]]:
        """
        Obtiene todos los documentos de un usuario.
        
        Args:
            user_id (str): ID del usuario
            
        Returns:
            List[Dict]: Lista de documentos del usuario
        """
        documents = []
        try:
            # Listar archivos de estado en GCS
            blobs = self.bucket.list_blobs(prefix=self.status_prefix)
            
            for blob in blobs:
                if blob.name.endswith('.json'):
                    status_data = self._load_status_from_blob(blob)
                    if status_data and status_data.get("user_id") == user_id:
                        documents.append(status_data)
            
            # Ordenar por fecha de creación (más reciente primero)
            documents.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
        except Exception as e:
            logger.error(f"Error obteniendo documentos del usuario {user_id}: {str(e)}")
        
        return documents
    
    def get_all_documents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Obtiene todos los documentos en el sistema.
        
        Args:
            limit (int): Límite de documentos a retornar
            
        Returns:
            List[Dict]: Lista de todos los documentos
        """
        documents = []
        try:
            blobs = self.bucket.list_blobs(prefix=self.status_prefix)
            
            for blob in blobs:
                if blob.name.endswith('.json') and len(documents) < limit:
                    status_data = self._load_status_from_blob(blob)
                    if status_data:
                        documents.append(status_data)
            
            # Ordenar por fecha de creación (más reciente primero)
            documents.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
        except Exception as e:
            logger.error(f"Error obteniendo todos los documentos: {str(e)}")
        
        return documents
    
    def delete_document_status(self, document_id: str) -> bool:
        """
        Elimina el estado de un documento.
        
        Args:
            document_id (str): ID del documento
            
        Returns:
            bool: True si se eliminó exitosamente
        """
        try:
            blob_name = f"{self.status_prefix}{document_id}.json"
            blob = self.bucket.blob(blob_name)
            blob.delete()
            logger.info(f"Estado eliminado para documento: {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error eliminando estado: {str(e)}")
            return False
    
    def _save_status(self, document_id: str, status_data: Dict[str, Any]):
        """Guarda el estado en GCS."""
        try:
            blob_name = f"{self.status_prefix}{document_id}.json"
            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(
                json.dumps(status_data, indent=2, ensure_ascii=False),
                content_type='application/json'
            )
        except Exception as e:
            logger.error(f"Error guardando estado: {str(e)}")
            raise
    
    def _load_status(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Carga el estado desde GCS."""
        try:
            blob_name = f"{self.status_prefix}{document_id}.json"
            blob = self.bucket.blob(blob_name)
            
            if not blob.exists():
                return None
            
            data = blob.download_as_text()
            return json.loads(data)
        except Exception as e:
            logger.error(f"Error cargando estado: {str(e)}")
            return None
    
    def _load_status_from_blob(self, blob) -> Optional[Dict[str, Any]]:
        """Carga el estado desde un blob de GCS."""
        try:
            data = blob.download_as_text()
            return json.loads(data)
        except Exception as e:
            logger.error(f"Error cargando estado desde blob: {str(e)}")
            return None


# Instancia global del servicio
status_service = StatusService() 