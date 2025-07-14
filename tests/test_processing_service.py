"""
Pruebas unitarias para el servicio de procesamiento de documentos.
"""
import unittest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from services.processing_service import DocumentProcessor


class TestDocumentProcessor(unittest.TestCase):
    """Pruebas para el DocumentProcessor."""
    
    def setUp(self):
        """Configurar el entorno de pruebas."""
        self.temp_dir = tempfile.mkdtemp()
        self.processor = DocumentProcessor(self.temp_dir)
    
    def tearDown(self):
        """Limpiar después de las pruebas."""
        # Limpiar directorio temporal
        try:
            os.rmdir(self.temp_dir)
        except:
            pass
    
    def test_init(self):
        """Probar inicialización del procesador."""
        self.assertEqual(str(self.processor.temp_dir), self.temp_dir)
        self.assertTrue(Path(self.temp_dir).exists())
    
    @patch('services.processing_service.subprocess.run')
    def test_verify_marker_installation_success(self, mock_run):
        """Probar verificación exitosa de marker."""
        mock_run.return_value.returncode = 0
        
        # No debería lanzar excepción
        processor = DocumentProcessor(self.temp_dir)
        
        mock_run.assert_called_once()
    
    @patch('services.processing_service.subprocess.run')
    def test_verify_marker_installation_failure(self, mock_run):
        """Probar fallo en verificación de marker."""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "marker_single not found"
        
        with self.assertRaises(RuntimeError):
            DocumentProcessor(self.temp_dir)
    
    def test_split_into_chunks_basic(self):
        """Probar división básica en chunks."""
        text = "Este es un texto de prueba. " * 100  # Texto largo
        filename = "test.pdf"
        
        chunks = self.processor.split_into_chunks(text, filename, chunk_size=50, overlap=10)
        
        self.assertIsInstance(chunks, list)
        self.assertGreater(len(chunks), 1)
        
        # Verificar que los chunks no están vacíos
        for chunk in chunks:
            self.assertGreater(len(chunk.strip()), 0)
    
    def test_split_into_chunks_small_text(self):
        """Probar división con texto pequeño."""
        text = "Texto pequeño."
        filename = "test.pdf"
        
        chunks = self.processor.split_into_chunks(text, filename)
        
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)
    
    def test_split_into_chunks_with_articles(self):
        """Probar división por artículos."""
        text = """
        Artículo 1. Primer artículo del documento.
        Este es el contenido del primer artículo.
        
        Artículo 2. Segundo artículo del documento.
        Este es el contenido del segundo artículo.
        """
        filename = "test.pdf"
        
        chunks = self.processor.split_into_chunks(text, filename, chunk_size=100)
        
        # Debería dividirse por artículos
        self.assertGreaterEqual(len(chunks), 2)
    
    def test_combine_small_chunks(self):
        """Probar combinación de chunks pequeños."""
        small_chunks = ["A", "B", "C", "Texto largo que supera el mínimo"]
        
        combined = self.processor._combine_small_chunks(small_chunks, min_chunk_size=10)
        
        # Los chunks pequeños deberían combinarse
        self.assertLess(len(combined), len(small_chunks))
        
        # El chunk largo debería mantenerse separado
        self.assertIn("Texto largo que supera el mínimo", combined)
    
    @patch('services.processing_service.subprocess.run')
    def test_process_pdf_to_markdown_success(self, mock_run):
        """Probar conversión exitosa de PDF a Markdown."""
        # Mock del subprocess
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Conversion successful"
        
        # Crear archivo PDF falso
        pdf_path = os.path.join(self.temp_dir, "test.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"fake pdf content")
        
        # Crear archivo markdown falso que sería generado por marker
        output_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        md_path = os.path.join(output_dir, "test.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Test Document\nContent of the document.")
        
        result = self.processor.process_pdf_to_markdown(pdf_path, output_dir)
        
        self.assertTrue(result['processed_successfully'])
        self.assertIn('output_directory', result)
    
    @patch('services.processing_service.subprocess.run')
    def test_process_pdf_to_markdown_failure(self, mock_run):
        """Probar fallo en conversión de PDF."""
        # Mock del subprocess con error
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Conversion failed"
        
        # Crear archivo PDF falso
        pdf_path = os.path.join(self.temp_dir, "test.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"fake pdf content")
        
        result = self.processor.process_pdf_to_markdown(pdf_path)
        
        self.assertFalse(result['processed_successfully'])
        self.assertIn('error', result)
    
    def test_extract_markdown_content(self):
        """Probar extracción de contenido markdown."""
        # Crear directorio y archivo markdown de prueba
        output_dir = Path(self.temp_dir) / "output"
        output_dir.mkdir(exist_ok=True)
        
        md_file = output_dir / "test.md"
        test_content = "# Test\nThis is test content."
        
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(test_content)
        
        content = self.processor._extract_markdown_content(output_dir, "test")
        
        self.assertEqual(content, test_content)
    
    def test_extract_markdown_content_file_not_found(self):
        """Probar extracción con archivo inexistente."""
        output_dir = Path(self.temp_dir) / "output"
        output_dir.mkdir(exist_ok=True)
        
        content = self.processor._extract_markdown_content(output_dir, "nonexistent")
        
        self.assertEqual(content, "")
    
    @patch.object(DocumentProcessor, 'process_pdf_to_markdown')
    @patch.object(DocumentProcessor, 'split_into_chunks')
    def test_process_document_complete_success(self, mock_split, mock_convert):
        """Probar procesamiento completo exitoso."""
        # Mock conversión exitosa
        mock_convert.return_value = {
            'processed_successfully': True,
            'markdown_content': "# Test\nContent",
            'output_directory': self.temp_dir
        }
        
        # Mock división en chunks
        mock_split.return_value = ["Chunk 1", "Chunk 2", "Chunk 3"]
        
        # Crear archivo PDF falso
        pdf_path = os.path.join(self.temp_dir, "test.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"fake pdf content")
        
        result = self.processor.process_document_complete(pdf_path)
        
        self.assertTrue(result['processed_successfully'])
        self.assertEqual(result['num_chunks'], 3)
        self.assertEqual(len(result['chunks']), 3)
        self.assertIn('metadata', result)
    
    @patch.object(DocumentProcessor, 'process_pdf_to_markdown')
    def test_process_document_complete_conversion_failure(self, mock_convert):
        """Probar procesamiento con fallo en conversión."""
        # Mock conversión fallida
        mock_convert.return_value = {
            'processed_successfully': False,
            'error': 'Conversion failed'
        }
        
        # Crear archivo PDF falso
        pdf_path = os.path.join(self.temp_dir, "test.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"fake pdf content")
        
        result = self.processor.process_document_complete(pdf_path)
        
        self.assertFalse(result['processed_successfully'])
        self.assertIn('error', result)
    
    def test_cleanup_temp_files(self):
        """Probar limpieza de archivos temporales."""
        # Crear archivo temporal
        temp_file = os.path.join(self.temp_dir, "temp_test.txt")
        with open(temp_file, "w") as f:
            f.write("temp content")
        
        self.assertTrue(os.path.exists(temp_file))
        
        # Limpiar
        self.processor.cleanup_temp_files(self.temp_dir)
        
        # El directorio debería seguir existiendo pero vacío
        self.assertTrue(os.path.exists(self.temp_dir))


class TestChunkingSplitting(unittest.TestCase):
    """Pruebas específicas para la lógica de chunking."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.processor = DocumentProcessor(self.temp_dir)
    
    def tearDown(self):
        try:
            os.rmdir(self.temp_dir)
        except:
            pass
    
    def test_split_by_articles_detection(self):
        """Probar detección de artículos."""
        text = """
        Introducción del documento.
        
        Artículo 1.- Primer artículo.
        Contenido del primer artículo.
        
        Art. 2. Segundo artículo.
        Contenido del segundo artículo.
        
        Artículo 3º Tercer artículo.
        Contenido del tercer artículo.
        """
        
        lines = text.split('\n')
        chunks = self.processor.split_into_chunks(text, "test.pdf", chunk_size=50)
        
        # Debería detectar artículos y dividir apropiadamente
        self.assertGreater(len(chunks), 1)
        
        # Verificar que los chunks no están vacíos
        for chunk in chunks:
            self.assertGreater(len(chunk.strip()), 0)
    
    def test_split_by_sections_detection(self):
        """Probar detección de secciones."""
        text = """
        # Sección 1
        Contenido de la primera sección.
        
        ## Subsección 1.1
        Contenido de la subsección.
        
        # Sección 2
        Contenido de la segunda sección.
        """
        
        chunks = self.processor.split_into_chunks(text, "test.pdf", chunk_size=50)
        
        # Debería dividirse por secciones
        self.assertGreater(len(chunks), 1)


if __name__ == '__main__':
    unittest.main() 