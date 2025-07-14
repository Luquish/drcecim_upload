"""
Pruebas unitarias para el servicio de estado de documentos.
"""
import unittest
import json
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import pytest

from services.status_service import StatusService, DocumentStatus


class TestStatusService(unittest.TestCase):
    """Pruebas para el StatusService."""
    
    def setUp(self):
        """Configurar mocks para las pruebas."""
        # Mock del cliente de GCS
        self.mock_client = Mock()
        self.mock_bucket = Mock()
        self.mock_blob = Mock()
        
        self.mock_client.bucket.return_value = self.mock_bucket
        self.mock_bucket.blob.return_value = self.mock_blob
        
        # Patchear el cliente de GCS
        self.gcs_patcher = patch('services.status_service.storage.Client')
        self.mock_gcs_client = self.gcs_patcher.start()
        self.mock_gcs_client.return_value = self.mock_client
        
        # Crear instancia del servicio
        self.status_service = StatusService("test-bucket")
    
    def tearDown(self):
        """Limpiar mocks después de las pruebas."""
        self.gcs_patcher.stop()
    
    def test_register_document_success(self):
        """Probar registro exitoso de documento."""
        # Configurar mock
        self.mock_blob.upload_from_string = Mock()
        
        # Ejecutar
        document_id = self.status_service.register_document("test.pdf", "user123")
        
        # Verificar
        self.assertTrue(document_id.startswith("user123_"))
        self.assertTrue(document_id.endswith("_test.pdf"))
        self.mock_blob.upload_from_string.assert_called_once()
    
    def test_register_document_with_default_user(self):
        """Probar registro con usuario por defecto."""
        self.mock_blob.upload_from_string = Mock()
        
        document_id = self.status_service.register_document("test.pdf")
        
        self.assertTrue(document_id.startswith("default_"))
    
    def test_update_status_success(self):
        """Probar actualización exitosa de estado."""
        # Mock existente documento
        existing_data = {
            "document_id": "test123",
            "status": DocumentStatus.UPLOADED.value,
            "steps": [],
            "metadata": {}
        }
        
        self.mock_blob.exists.return_value = True
        self.mock_blob.download_as_text.return_value = json.dumps(existing_data)
        self.mock_blob.upload_from_string = Mock()
        
        # Ejecutar
        self.status_service.update_status(
            "test123", 
            DocumentStatus.PROCESSING, 
            "Test message",
            "test_step"
        )
        
        # Verificar que se llamó upload_from_string
        self.mock_blob.upload_from_string.assert_called_once()
        
        # Verificar que los datos incluyen el nuevo paso
        call_args = self.mock_blob.upload_from_string.call_args[0][0]
        data = json.loads(call_args)
        self.assertEqual(data["status"], DocumentStatus.PROCESSING.value)
        self.assertEqual(len(data["steps"]), 1)
        self.assertEqual(data["steps"][0]["step"], "test_step")
    
    def test_update_status_document_not_found(self):
        """Probar actualización con documento inexistente."""
        self.mock_blob.exists.return_value = False
        self.mock_blob.download_as_text.return_value = None
        
        # Ejecutar (no debería lanzar excepción)
        self.status_service.update_status(
            "nonexistent", 
            DocumentStatus.ERROR, 
            "Test"
        )
        
        # Verificar que no se intentó subir
        self.mock_blob.upload_from_string.assert_not_called()
    
    def test_get_document_status_exists(self):
        """Probar obtención de estado de documento existente."""
        test_data = {"document_id": "test123", "status": "completed"}
        
        self.mock_blob.exists.return_value = True
        self.mock_blob.download_as_text.return_value = json.dumps(test_data)
        
        result = self.status_service.get_document_status("test123")
        
        self.assertEqual(result, test_data)
    
    def test_get_document_status_not_exists(self):
        """Probar obtención de estado de documento inexistente."""
        self.mock_blob.exists.return_value = False
        
        result = self.status_service.get_document_status("nonexistent")
        
        self.assertIsNone(result)
    
    def test_get_user_documents(self):
        """Probar obtención de documentos de usuario."""
        # Mock de blobs en el bucket
        mock_blob1 = Mock()
        mock_blob1.name = "status/user1_123_doc1.json"
        mock_blob1.download_as_text.return_value = json.dumps({
            "document_id": "user1_123_doc1",
            "user_id": "user1",
            "filename": "doc1.pdf",
            "created_at": "2024-01-01T00:00:00"
        })
        
        mock_blob2 = Mock()
        mock_blob2.name = "status/user2_456_doc2.json"
        mock_blob2.download_as_text.return_value = json.dumps({
            "document_id": "user2_456_doc2",
            "user_id": "user2",
            "filename": "doc2.pdf",
            "created_at": "2024-01-02T00:00:00"
        })
        
        self.mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2]
        
        # Obtener documentos del user1
        documents = self.status_service.get_user_documents("user1")
        
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["user_id"], "user1")
    
    def test_delete_document_status_success(self):
        """Probar eliminación exitosa de estado."""
        self.mock_blob.delete = Mock()
        
        result = self.status_service.delete_document_status("test123")
        
        self.assertTrue(result)
        self.mock_blob.delete.assert_called_once()
    
    def test_delete_document_status_error(self):
        """Probar eliminación con error."""
        self.mock_blob.delete.side_effect = Exception("Delete error")
        
        result = self.status_service.delete_document_status("test123")
        
        self.assertFalse(result)


class TestDocumentStatus(unittest.TestCase):
    """Pruebas para el enum DocumentStatus."""
    
    def test_enum_values(self):
        """Probar que los valores del enum son correctos."""
        self.assertEqual(DocumentStatus.UPLOADED.value, "uploaded")
        self.assertEqual(DocumentStatus.PROCESSING.value, "processing")
        self.assertEqual(DocumentStatus.COMPLETED.value, "completed")
        self.assertEqual(DocumentStatus.ERROR.value, "error")
        self.assertEqual(DocumentStatus.CANCELLED.value, "cancelled")


if __name__ == '__main__':
    unittest.main() 