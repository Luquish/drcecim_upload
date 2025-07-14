"""
Pruebas unitarias para el servicio de generación de embeddings.
"""
import unittest
import tempfile
import os
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from services.embeddings_service import EmbeddingService


class TestEmbeddingService(unittest.TestCase):
    """Pruebas para el EmbeddingService."""
    
    def setUp(self):
        """Configurar el entorno de pruebas."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock del modelo OpenAI
        self.mock_model = Mock()
        self.mock_model.generate_embeddings.return_value = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9]
        ])
        
        # Patchear la importación del modelo OpenAI
        self.openai_patcher = patch('services.embeddings_service.OpenAIEmbedding')
        self.mock_openai_class = self.openai_patcher.start()
        self.mock_openai_class.return_value = self.mock_model
        
        # Patchear la verificación de API key
        self.api_key_patcher = patch('services.embeddings_service.OPENAI_API_KEY', 'test-key')
        self.api_key_patcher.start()
        
        self.service = EmbeddingService(self.temp_dir)
    
    def tearDown(self):
        """Limpiar después de las pruebas."""
        self.openai_patcher.stop()
        self.api_key_patcher.stop()
        
        # Limpiar directorio temporal
        try:
            os.rmdir(self.temp_dir)
        except:
            pass
    
    def test_init_success(self):
        """Probar inicialización exitosa del servicio."""
        self.assertEqual(str(self.service.temp_dir), self.temp_dir)
        self.assertIsNotNone(self.service.model)
        self.assertTrue(Path(self.temp_dir).exists())
    
    @patch('services.embeddings_service.OPENAI_API_KEY', '')
    def test_init_no_api_key(self):
        """Probar fallo en inicialización sin API key."""
        with self.assertRaises(ValueError):
            EmbeddingService(self.temp_dir)
    
    def test_generate_embeddings_success(self):
        """Probar generación exitosa de embeddings."""
        texts = ["Texto 1", "Texto 2", "Texto 3"]
        
        embeddings = self.service.generate_embeddings(texts)
        
        self.assertEqual(embeddings.shape, (3, 3))
        self.mock_model.generate_embeddings.assert_called_once_with(texts)
    
    def test_generate_embeddings_empty_list(self):
        """Probar generación con lista vacía."""
        embeddings = self.service.generate_embeddings([])
        
        self.assertEqual(embeddings.shape, (0, 0))
        self.mock_model.generate_embeddings.assert_not_called()
    
    def test_generate_embeddings_batch_processing(self):
        """Probar procesamiento por lotes."""
        # Simular muchos textos para activar el procesamiento por lotes
        texts = [f"Texto {i}" for i in range(50)]
        
        # Configurar el mock para retornar embeddings apropiados
        self.mock_model.generate_embeddings.side_effect = [
            np.random.rand(16, 3),  # Primer lote
            np.random.rand(16, 3),  # Segundo lote
            np.random.rand(16, 3),  # Tercer lote
            np.random.rand(2, 3)    # Último lote parcial
        ]
        
        embeddings = self.service.generate_embeddings(texts, batch_size=16)
        
        self.assertEqual(embeddings.shape, (50, 3))
        # Debería llamarse 4 veces (50 textos / 16 por lote = 4 lotes)
        self.assertEqual(self.mock_model.generate_embeddings.call_count, 4)
    
    @patch('services.embeddings_service.faiss')
    def test_create_faiss_index(self, mock_faiss):
        """Probar creación de índice FAISS."""
        embeddings = np.random.rand(10, 5)
        mock_index = Mock()
        mock_faiss.IndexFlatIP.return_value = mock_index
        
        index = self.service.create_faiss_index(embeddings)
        
        self.assertEqual(index, mock_index)
        mock_faiss.IndexFlatIP.assert_called_once_with(5)  # Dimensión
        mock_index.add.assert_called_once()
    
    def test_create_metadata(self):
        """Probar creación de metadatos."""
        texts = ["Chunk 1", "Chunk 2", "Chunk 3"]
        filenames = ["doc1.pdf", "doc1.pdf", "doc2.pdf"]
        chunk_indices = [0, 1, 0]
        
        metadata = self.service.create_metadata(texts, filenames, chunk_indices)
        
        self.assertIsInstance(metadata, pd.DataFrame)
        self.assertEqual(len(metadata), 3)
        self.assertIn('text', metadata.columns)
        self.assertIn('filename', metadata.columns)
        self.assertIn('chunk_index', metadata.columns)
        self.assertIn('word_count', metadata.columns)
        self.assertIn('char_count', metadata.columns)
    
    def test_create_metadata_summary(self):
        """Probar creación de resumen de metadatos."""
        metadata = pd.DataFrame({
            'filename': ['doc1.pdf', 'doc1.pdf', 'doc2.pdf'],
            'word_count': [100, 150, 200],
            'char_count': [500, 750, 1000]
        })
        
        summary = self.service.create_metadata_summary(metadata)
        
        self.assertIsInstance(summary, pd.DataFrame)
        self.assertEqual(len(summary), 2)  # 2 documentos únicos
        self.assertIn('total_chunks', summary.columns)
        self.assertIn('total_words', summary.columns)
        self.assertIn('total_chars', summary.columns)
    
    def test_save_faiss_index(self):
        """Probar guardado de índice FAISS."""
        mock_index = Mock()
        filepath = os.path.join(self.temp_dir, "test_index.faiss")
        
        self.service.save_faiss_index(mock_index, filepath)
        
        mock_index.write_index.assert_called_once_with(filepath)
    
    def test_save_metadata(self):
        """Probar guardado de metadatos."""
        metadata = pd.DataFrame({
            'text': ['Chunk 1', 'Chunk 2'],
            'filename': ['doc1.pdf', 'doc1.pdf']
        })
        filepath = os.path.join(self.temp_dir, "test_metadata.parquet")
        
        self.service.save_metadata(metadata, filepath)
        
        # Verificar que el archivo se creó
        self.assertTrue(os.path.exists(filepath))
    
    def test_save_config(self):
        """Probar guardado de configuración."""
        config = {
            'model': 'test-model',
            'dimension': 3,
            'num_vectors': 10
        }
        filepath = os.path.join(self.temp_dir, "test_config.json")
        
        self.service.save_config(config, filepath)
        
        # Verificar que el archivo se creó
        self.assertTrue(os.path.exists(filepath))
        
        # Verificar contenido
        import json
        with open(filepath, 'r') as f:
            saved_config = json.load(f)
        
        self.assertEqual(saved_config, config)
    
    @patch.object(EmbeddingService, 'generate_embeddings')
    @patch.object(EmbeddingService, 'create_faiss_index')
    @patch.object(EmbeddingService, 'create_metadata')
    def test_process_document_embeddings_success(self, mock_metadata, mock_index, mock_embeddings):
        """Probar procesamiento completo exitoso de embeddings."""
        # Datos de entrada
        processed_doc = {
            'filename': 'test.pdf',
            'chunks': ['Chunk 1', 'Chunk 2', 'Chunk 3'],
            'num_chunks': 3,
            'total_words': 100
        }
        
        # Mock de respuestas
        mock_embeddings.return_value = np.random.rand(3, 5)
        mock_index.return_value = Mock()
        mock_metadata.return_value = pd.DataFrame({
            'text': ['Chunk 1', 'Chunk 2', 'Chunk 3'],
            'filename': ['test.pdf'] * 3
        })
        
        result = self.service.process_document_embeddings(processed_doc)
        
        self.assertTrue(result['processed_successfully'])
        self.assertIn('embeddings', result)
        self.assertIn('faiss_index', result)
        self.assertIn('metadata', result)
        self.assertIn('config', result)
    
    def test_process_document_embeddings_empty_chunks(self):
        """Probar procesamiento con chunks vacíos."""
        processed_doc = {
            'filename': 'test.pdf',
            'chunks': [],
            'num_chunks': 0,
            'total_words': 0
        }
        
        result = self.service.process_document_embeddings(processed_doc)
        
        self.assertFalse(result['processed_successfully'])
        self.assertIn('error', result)
    
    @patch.object(EmbeddingService, 'generate_embeddings')
    def test_process_document_embeddings_generation_error(self, mock_embeddings):
        """Probar procesamiento con error en generación."""
        processed_doc = {
            'filename': 'test.pdf',
            'chunks': ['Chunk 1', 'Chunk 2'],
            'num_chunks': 2,
            'total_words': 50
        }
        
        # Mock que lanza excepción
        mock_embeddings.side_effect = Exception("API Error")
        
        result = self.service.process_document_embeddings(processed_doc)
        
        self.assertFalse(result['processed_successfully'])
        self.assertIn('error', result)
        self.assertIn('API Error', result['error'])
    
    @patch.object(EmbeddingService, 'save_faiss_index')
    @patch.object(EmbeddingService, 'save_metadata')
    @patch.object(EmbeddingService, 'save_config')
    def test_save_embeddings_data(self, mock_save_config, mock_save_metadata, mock_save_index):
        """Probar guardado de datos de embeddings."""
        embeddings_data = {
            'faiss_index': Mock(),
            'metadata': pd.DataFrame({'text': ['Chunk 1']}),
            'config': {'dimension': 5}
        }
        
        result = self.service.save_embeddings_data(embeddings_data, self.temp_dir)
        
        self.assertIn('faiss_index_path', result)
        self.assertIn('metadata_path', result)
        self.assertIn('config_path', result)
        
        mock_save_index.assert_called_once()
        mock_save_metadata.assert_called_once()
        mock_save_config.assert_called_once()
    
    def test_cleanup_temp_files(self):
        """Probar limpieza de archivos temporales."""
        # Crear archivo temporal
        temp_file = os.path.join(self.temp_dir, "temp_test.txt")
        with open(temp_file, "w") as f:
            f.write("temp content")
        
        self.assertTrue(os.path.exists(temp_file))
        
        # Limpiar
        self.service.cleanup_temp_files(self.temp_dir)
        
        # El archivo debería haberse eliminado
        self.assertFalse(os.path.exists(temp_file))


class TestEmbeddingIntegration(unittest.TestCase):
    """Pruebas de integración para embeddings."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock más realista del modelo
        self.mock_model = Mock()
        
        # Patchear dependencias
        self.openai_patcher = patch('services.embeddings_service.OpenAIEmbedding')
        self.mock_openai_class = self.openai_patcher.start()
        self.mock_openai_class.return_value = self.mock_model
        
        self.api_key_patcher = patch('services.embeddings_service.OPENAI_API_KEY', 'test-key')
        self.api_key_patcher.start()
        
        self.service = EmbeddingService(self.temp_dir)
    
    def tearDown(self):
        self.openai_patcher.stop()
        self.api_key_patcher.stop()
        
        try:
            os.rmdir(self.temp_dir)
        except:
            pass
    
    @patch('services.embeddings_service.faiss')
    def test_full_embedding_pipeline(self, mock_faiss):
        """Probar el pipeline completo de embeddings."""
        # Configurar mocks
        self.mock_model.generate_embeddings.return_value = np.array([
            [0.1, 0.2, 0.3, 0.4, 0.5],
            [0.6, 0.7, 0.8, 0.9, 1.0],
            [1.1, 1.2, 1.3, 1.4, 1.5]
        ])
        
        mock_index = Mock()
        mock_faiss.IndexFlatIP.return_value = mock_index
        
        # Datos de entrada
        processed_doc = {
            'filename': 'test_document.pdf',
            'chunks': [
                'Primer chunk del documento de prueba.',
                'Segundo chunk con más contenido para probar.',
                'Tercer chunk final del documento.'
            ],
            'num_chunks': 3,
            'total_words': 15,
            'metadata': {'pages': 2}
        }
        
        # Ejecutar pipeline completo
        result = self.service.process_document_embeddings(processed_doc)
        
        # Verificaciones
        self.assertTrue(result['processed_successfully'])
        self.assertEqual(result['embeddings'].shape, (3, 5))
        self.assertEqual(len(result['metadata']), 3)
        self.assertEqual(result['config']['num_vectors'], 3)
        self.assertEqual(result['config']['dimension'], 5)
        
        # Verificar que se llamaron los métodos necesarios
        self.mock_model.generate_embeddings.assert_called_once()
        mock_faiss.IndexFlatIP.assert_called_once_with(5)
        mock_index.add.assert_called_once()


if __name__ == '__main__':
    unittest.main() 