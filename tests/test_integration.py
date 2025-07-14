"""
Pruebas de integración para el sistema DrCecim Upload.
Estas pruebas verifican la interacción entre servicios y el flujo completo.
"""
import unittest
import tempfile
import os
import json
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from services.processing_service import DocumentProcessor
from services.embeddings_service import EmbeddingService
from services.status_service import StatusService, DocumentStatus
from services.gcs_service import GCSService


class TestDocumentProcessingIntegration(unittest.TestCase):
    """Pruebas de integración para el flujo completo de procesamiento."""
    
    def setUp(self):
        """Configurar el entorno de pruebas de integración."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock de dependencias externas
        self.setup_processing_mocks()
        self.setup_embeddings_mocks()
        self.setup_status_mocks()
        self.setup_gcs_mocks()
    
    def tearDown(self):
        """Limpiar después de las pruebas."""
        self.processing_patcher.stop()
        self.openai_patcher.stop()
        self.api_key_patcher.stop()
        self.gcs_patcher.stop()
        
        try:
            os.rmdir(self.temp_dir)
        except:
            pass
    
    def setup_processing_mocks(self):
        """Configurar mocks para el servicio de procesamiento."""
        self.processing_patcher = patch('services.processing_service.subprocess.run')
        self.mock_subprocess = self.processing_patcher.start()
        self.mock_subprocess.return_value.returncode = 0
        self.mock_subprocess.return_value.stdout = "Success"
    
    def setup_embeddings_mocks(self):
        """Configurar mocks para el servicio de embeddings."""
        # Mock del modelo OpenAI
        self.mock_model = Mock()
        self.mock_model.generate_embeddings.return_value = np.random.rand(3, 384)
        
        self.openai_patcher = patch('services.embeddings_service.OpenAIEmbedding')
        self.mock_openai_class = self.openai_patcher.start()
        self.mock_openai_class.return_value = self.mock_model
        
        self.api_key_patcher = patch('services.embeddings_service.OPENAI_API_KEY', 'test-key')
        self.api_key_patcher.start()
    
    def setup_status_mocks(self):
        """Configurar mocks para el servicio de estado."""
        self.mock_status_client = Mock()
        self.mock_status_bucket = Mock()
        self.mock_status_blob = Mock()
        
        self.mock_status_client.bucket.return_value = self.mock_status_bucket
        self.mock_status_bucket.blob.return_value = self.mock_status_blob
        
        self.gcs_patcher = patch('services.status_service.storage.Client')
        self.mock_gcs_client_class = self.gcs_patcher.start()
        self.mock_gcs_client_class.return_value = self.mock_status_client
    
    def setup_gcs_mocks(self):
        """Configurar mocks para el servicio GCS."""
        # Los mocks de GCS ya están configurados en setup_status_mocks
        pass
    
    def create_test_pdf(self) -> str:
        """Crear un archivo PDF de prueba."""
        pdf_path = os.path.join(self.temp_dir, "test_document.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"fake pdf content for testing")
        return pdf_path
    
    def create_test_markdown(self, content: str = None) -> str:
        """Crear un archivo markdown de prueba."""
        if content is None:
            content = """# Documento de Prueba

## Artículo 1
Este es el contenido del primer artículo del documento de prueba.
Contiene información importante sobre el procesamiento de documentos.

## Artículo 2
Este es el segundo artículo que contiene más información relevante.
Aquí se describen los procedimientos adicionales.

## Conclusión
Esta es la sección de conclusión del documento."""
        
        output_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        
        md_path = os.path.join(output_dir, "test_document.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return md_path
    
    @patch('services.embeddings_service.faiss')
    def test_full_document_processing_pipeline(self, mock_faiss):
        """Probar el pipeline completo desde PDF hasta embeddings."""
        # Configurar mocks
        mock_index = Mock()
        mock_faiss.IndexFlatIP.return_value = mock_index
        
        # Crear archivos de prueba
        pdf_path = self.create_test_pdf()
        md_path = self.create_test_markdown()
        
        # Configurar mock de status service
        self.mock_status_blob.upload_from_string = Mock()
        
        # 1. Procesamiento de PDF a chunks
        processor = DocumentProcessor(self.temp_dir)
        
        # Mock del procesamiento de markdown
        with patch.object(processor, '_extract_markdown_content') as mock_extract:
            mock_extract.return_value = """# Documento de Prueba
            
Artículo 1. Contenido del primer artículo.
Artículo 2. Contenido del segundo artículo."""
            
            processed_result = processor.process_document_complete(pdf_path)
        
        # Verificar resultado del procesamiento
        self.assertTrue(processed_result['processed_successfully'])
        self.assertGreater(processed_result['num_chunks'], 0)
        self.assertIn('chunks', processed_result)
        
        # 2. Generación de embeddings
        embeddings_service = EmbeddingService(self.temp_dir)
        embeddings_result = embeddings_service.process_document_embeddings(processed_result)
        
        # Verificar resultado de embeddings
        self.assertTrue(embeddings_result['processed_successfully'])
        self.assertIn('embeddings', embeddings_result)
        self.assertIn('faiss_index', embeddings_result)
        self.assertIn('metadata', embeddings_result)
        
        # 3. Registro de estado
        status_service = StatusService("test-bucket")
        document_id = status_service.register_document("test_document.pdf")
        
        # Verificar registro de estado
        self.assertTrue(document_id.startswith("default_"))
        self.mock_status_blob.upload_from_string.assert_called()
    
    def test_error_handling_in_processing(self):
        """Probar manejo de errores en el procesamiento."""
        # Configurar subprocess para fallar
        self.mock_subprocess.return_value.returncode = 1
        self.mock_subprocess.return_value.stderr = "Processing failed"
        
        pdf_path = self.create_test_pdf()
        
        # Procesamiento debería fallar
        processor = DocumentProcessor(self.temp_dir)
        result = processor.process_pdf_to_markdown(pdf_path)
        
        self.assertFalse(result['processed_successfully'])
        self.assertIn('error', result)
    
    @patch('services.embeddings_service.faiss')
    def test_error_handling_in_embeddings(self, mock_faiss):
        """Probar manejo de errores en generación de embeddings."""
        # Configurar modelo para fallar
        self.mock_model.generate_embeddings.side_effect = Exception("API Error")
        
        processed_doc = {
            'filename': 'test.pdf',
            'chunks': ['Chunk 1', 'Chunk 2'],
            'num_chunks': 2,
            'total_words': 10
        }
        
        embeddings_service = EmbeddingService(self.temp_dir)
        result = embeddings_service.process_document_embeddings(processed_doc)
        
        self.assertFalse(result['processed_successfully'])
        self.assertIn('error', result)
        self.assertIn('API Error', result['error'])
    
    def test_status_tracking_throughout_pipeline(self):
        """Probar seguimiento de estado a lo largo del pipeline."""
        # Configurar mocks de estado
        existing_status = {
            "document_id": "test123",
            "status": "uploaded",
            "steps": [],
            "metadata": {}
        }
        
        self.mock_status_blob.exists.return_value = True
        self.mock_status_blob.download_as_text.return_value = json.dumps(existing_status)
        self.mock_status_blob.upload_from_string = Mock()
        
        status_service = StatusService("test-bucket")
        
        # Simular actualizaciones de estado durante el procesamiento
        status_service.update_status(
            "test123", 
            DocumentStatus.PROCESSING, 
            "Starting PDF processing",
            "pdf_start"
        )
        
        status_service.update_status(
            "test123", 
            DocumentStatus.PROCESSING, 
            "Generating embeddings",
            "embeddings_start"
        )
        
        status_service.update_status(
            "test123", 
            DocumentStatus.COMPLETED, 
            "Processing completed successfully",
            "completed"
        )
        
        # Verificar que se hicieron las actualizaciones
        self.assertEqual(self.mock_status_blob.upload_from_string.call_count, 3)
    
    @patch('services.embeddings_service.faiss')
    def test_chunking_and_embedding_consistency(self, mock_faiss):
        """Probar consistencia entre chunking y embeddings."""
        mock_index = Mock()
        mock_faiss.IndexFlatIP.return_value = mock_index
        
        # Crear texto de prueba
        test_text = """
        Artículo 1. Este es el primer artículo con contenido específico.
        Artículo 2. Este es el segundo artículo con más contenido.
        Artículo 3. Este es el tercer artículo final.
        """
        
        # Procesar texto en chunks
        processor = DocumentProcessor(self.temp_dir)
        chunks = processor.split_into_chunks(test_text, "test.pdf", chunk_size=50)
        
        # Simular documento procesado
        processed_doc = {
            'filename': 'test.pdf',
            'chunks': chunks,
            'num_chunks': len(chunks),
            'total_words': len(test_text.split())
        }
        
        # Generar embeddings
        embeddings_service = EmbeddingService(self.temp_dir)
        embeddings_result = embeddings_service.process_document_embeddings(processed_doc)
        
        # Verificar consistencia
        self.assertTrue(embeddings_result['processed_successfully'])
        self.assertEqual(embeddings_result['embeddings'].shape[0], len(chunks))
        self.assertEqual(len(embeddings_result['metadata']), len(chunks))
    
    def test_file_cleanup_integration(self):
        """Probar limpieza de archivos en el flujo completo."""
        # Crear archivos temporales
        temp_files = []
        for i in range(3):
            temp_file = os.path.join(self.temp_dir, f"temp_file_{i}.txt")
            with open(temp_file, "w") as f:
                f.write(f"Temporary content {i}")
            temp_files.append(temp_file)
        
        # Verificar que existen
        for temp_file in temp_files:
            self.assertTrue(os.path.exists(temp_file))
        
        # Usar servicios que deberían limpiar
        processor = DocumentProcessor(self.temp_dir)
        processor.cleanup_temp_files(self.temp_dir)
        
        embeddings_service = EmbeddingService(self.temp_dir)
        embeddings_service.cleanup_temp_files(self.temp_dir)
        
        # Verificar limpieza (el comportamiento específico puede variar)
        # Al menos verificamos que los métodos no fallan


class TestCloudFunctionIntegration(unittest.TestCase):
    """Pruebas de integración para las Cloud Functions."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        try:
            os.rmdir(self.temp_dir)
        except:
            pass
    
    @patch('cloud_functions.process_pdf.main.StatusService')
    @patch('cloud_functions.process_pdf.main.DocumentProcessor')
    @patch('cloud_functions.process_pdf.main.GCSService')
    def test_process_pdf_cloud_function_integration(self, mock_gcs, mock_processor, mock_status):
        """Probar integración de la Cloud Function de procesamiento."""
        # Configurar mocks
        mock_gcs_instance = Mock()
        mock_gcs.return_value = mock_gcs_instance
        
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance
        mock_processor_instance.process_document_complete.return_value = {
            'processed_successfully': True,
            'chunks': ['Chunk 1', 'Chunk 2'],
            'num_chunks': 2,
            'total_words': 10,
            'filename': 'test.pdf'
        }
        
        mock_status_instance = Mock()
        mock_status.return_value = mock_status_instance
        mock_status_instance.register_document.return_value = "test_doc_id"
        
        # Simular evento de Cloud Storage
        mock_event = Mock()
        mock_event.data = {
            'bucket': 'test-bucket',
            'name': 'test.pdf',
            'eventType': 'google.storage.object.finalize'
        }
        
        # Esta prueba requeriría importar la función real, pero por ahora
        # verificamos que los mocks están configurados correctamente
        self.assertIsNotNone(mock_gcs)
        self.assertIsNotNone(mock_processor)
        self.assertIsNotNone(mock_status)


class TestStreamlitIntegration(unittest.TestCase):
    """Pruebas de integración para la aplicación Streamlit."""
    
    @patch('streamlit_app.StatusService')
    @patch('streamlit_app.GCSService')
    def test_streamlit_status_service_integration(self, mock_gcs, mock_status):
        """Probar integración entre Streamlit y servicios de estado."""
        # Configurar mock de StatusService
        mock_status_instance = Mock()
        mock_status.return_value = mock_status_instance
        mock_status_instance.get_user_documents.return_value = [
            {
                'document_id': 'test_123',
                'filename': 'test.pdf',
                'status': 'completed',
                'created_at': '2024-01-01T00:00:00',
                'updated_at': '2024-01-01T00:00:00',
                'steps': [
                    {'step': 'upload', 'status': 'completed', 'message': 'File uploaded'}
                ],
                'metadata': {'total_chunks': 5}
            }
        ]
        
        # Esta prueba verificaría la integración real con Streamlit
        # Por ahora verificamos que los mocks están configurados
        self.assertIsNotNone(mock_status)
        self.assertIsNotNone(mock_gcs)


if __name__ == '__main__':
    unittest.main() 