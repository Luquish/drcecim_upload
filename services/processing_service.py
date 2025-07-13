"""
Servicio de procesamiento de documentos PDF usando Marker.
"""
import os
import logging
import subprocess
import tempfile
from pathlib import Path
import re
from typing import List, Dict, Optional, Any, Tuple
import pandas as pd
from tqdm import tqdm

from config.settings import CHUNK_SIZE, CHUNK_OVERLAP, TEMP_DIR

# Configuración de logging
logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Procesador de documentos PDF usando Marker.
    """
    
    def __init__(self, temp_dir: str = TEMP_DIR):
        """
        Inicializa el procesador de documentos.
        
        Args:
            temp_dir (str): Directorio temporal para procesamiento
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Verificar que marker esté instalado
        self._verify_marker_installation()
        
    def _verify_marker_installation(self):
        """Verifica que Marker esté instalado y disponible."""
        try:
            result = subprocess.run(['marker_single', '--help'], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True,
                                   check=False)
            
            if result.returncode != 0:
                logger.error(f"Error al verificar marker_single: {result.stderr}")
                raise RuntimeError("marker_single no está disponible o no funciona correctamente")
                
            logger.info("Marker detectado correctamente en el sistema")
        except FileNotFoundError:
            logger.error("No se encontró el comando marker_single")
            logger.error("Asegúrate de que marker-pdf esté instalado: pip install marker-pdf")
            raise RuntimeError("Marker no está instalado correctamente")
    
    def process_pdf_to_markdown(self, pdf_path: str, output_dir: str = None) -> Dict[str, Any]:
        """
        Procesa un PDF y lo convierte a Markdown usando Marker.
        
        Args:
            pdf_path (str): Ruta al archivo PDF
            output_dir (str): Directorio de salida (opcional)
            
        Returns:
            Dict[str, Any]: Diccionario con información del documento procesado
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo PDF: {pdf_path}")
        
        # Usar directorio temporal si no se especifica uno
        if output_dir is None:
            output_dir = self.temp_dir / f"processing_{pdf_path.stem}"
        else:
            output_dir = Path(output_dir)
            
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Procesando documento con Marker: {pdf_path}")
        
        # Preparar los argumentos para marker_single
        marker_cmd = [
            "marker_single",
            str(pdf_path),
            "--output_dir", str(output_dir),
            "--output_format", "markdown",
            "--paginate_output",
            "--force_ocr"
        ]
        
        # Ejecutar marker_single
        try:
            logger.info(f"Ejecutando: {' '.join(marker_cmd)}")
            result = subprocess.run(
                marker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"Error al ejecutar marker_single: {result.stderr}")
                raise RuntimeError(f"Error en marker_single: {result.stderr}")
                
            logger.info(f"Marker completado exitosamente para {pdf_path.name}")
            
        except Exception as e:
            logger.error(f"Excepción al ejecutar marker_single: {str(e)}")
            raise
        
        # Procesar archivos resultantes
        markdown_content = self._extract_markdown_content(output_dir, pdf_path.stem)
        
        if not markdown_content:
            raise RuntimeError(f"No se pudo extraer contenido markdown de {pdf_path}")
        
        return {
            'filename': pdf_path.name,
            'markdown_content': markdown_content,
            'output_dir': str(output_dir),
            'processed_successfully': True
        }
    
    def _extract_markdown_content(self, output_dir: Path, filename_stem: str) -> str:
        """
        Extrae el contenido markdown de los archivos procesados por Marker.
        
        Args:
            output_dir (Path): Directorio de salida
            filename_stem (str): Nombre base del archivo
            
        Returns:
            str: Contenido markdown
        """
        # Buscar archivos markdown en el directorio
        markdown_files = list(output_dir.glob(f"{filename_stem}*.md"))
        
        if not markdown_files:
            # Buscar en subdirectorios
            nested_dir = output_dir / filename_stem
            if nested_dir.exists():
                markdown_files = list(nested_dir.glob("*.md"))
        
        if not markdown_files:
            logger.error(f"No se encontraron archivos markdown en {output_dir}")
            return ""
        
        # Leer el primer archivo markdown encontrado
        markdown_path = markdown_files[0]
        try:
            with open(markdown_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            logger.info(f"Contenido markdown extraído: {len(content)} caracteres")
            return content
            
        except Exception as e:
            logger.error(f"Error al leer archivo markdown: {str(e)}")
            return ""
    
    def split_into_chunks(self, text: str, filename: str, 
                         chunk_size: int = CHUNK_SIZE, 
                         overlap: int = CHUNK_OVERLAP) -> List[str]:
        """
        Divide el texto Markdown en chunks respetando la estructura del documento.
        
        Args:
            text (str): Texto en formato Markdown
            filename (str): Nombre del archivo original
            chunk_size (int): Tamaño objetivo de cada chunk
            overlap (int): Cantidad de palabras de solapamiento
            
        Returns:
            List[str]: Lista de chunks
        """
        if not text:
            return []
        
        chunks = []
        lines = text.split('\n')
        
        # Detectar patrones markdown específicos
        title_pattern = re.compile(r'^#\s+')  # Título principal
        section_pattern = re.compile(r'^##\s+')  # Secciones
        article_pattern = re.compile(r'^###\s+Art(?:ículo|\.)\s*(\d+\º?)\.?', re.IGNORECASE)  # Artículos
        page_break_pattern = re.compile(r'^\d+\s*\n-{3,}$')  # Saltos de página
        
        # Identificar las secciones principales y los artículos
        section_indices = []
        article_indices = []
        page_breaks = []
        
        for i, line in enumerate(lines):
            if title_pattern.match(line):
                section_indices.append(i)
            elif section_pattern.match(line):
                section_indices.append(i)
            elif article_pattern.match(line):
                article_indices.append(i)
            elif page_break_pattern.match(line) and i < len(lines) - 1:
                page_breaks.append(i)
        
        # Dividir por artículos si existen
        if article_indices:
            chunks = self._split_by_articles(lines, article_indices, filename, chunk_size)
        # Dividir por secciones si existen
        elif section_indices:
            chunks = self._split_by_sections(lines, section_indices, filename, chunk_size)
        # Dividir por páginas si están marcadas
        elif page_breaks:
            chunks = self._split_by_pages(lines, page_breaks, filename, chunk_size)
        # División básica por párrafos
        else:
            chunks = self._split_by_paragraphs(text, filename, chunk_size)
        
        # Post-procesamiento para combinar chunks pequeños
        chunks = self._combine_small_chunks(chunks)
        
        logger.info(f"Documento dividido en {len(chunks)} chunks")
        return chunks
    
    def _split_by_articles(self, lines: List[str], article_indices: List[int], 
                          filename: str, chunk_size: int) -> List[str]:
        """Divide el texto por artículos."""
        chunks = []
        article_indices.append(len(lines))
        
        for i in range(len(article_indices) - 1):
            start_idx = article_indices[i]
            end_idx = article_indices[i + 1]
            
            article_lines = lines[start_idx:end_idx]
            article_text = '\n'.join(article_lines)
            
            if len(article_text.split()) <= chunk_size:
                doc_prefix = f"[Documento: {os.path.basename(filename)}] "
                chunks.append(doc_prefix + article_text)
            else:
                # Dividir artículos grandes
                sub_chunks = self._split_large_section(article_lines, filename, chunk_size)
                chunks.extend(sub_chunks)
        
        return chunks
    
    def _split_by_sections(self, lines: List[str], section_indices: List[int], 
                          filename: str, chunk_size: int) -> List[str]:
        """Divide el texto por secciones."""
        chunks = []
        section_indices.append(len(lines))
        
        for i in range(len(section_indices) - 1):
            start_idx = section_indices[i]
            end_idx = section_indices[i + 1]
            
            section_lines = lines[start_idx:end_idx]
            section_text = '\n'.join(section_lines)
            
            if len(section_text.split()) <= chunk_size:
                doc_prefix = f"[Documento: {os.path.basename(filename)}] "
                chunks.append(doc_prefix + section_text)
            else:
                # Dividir secciones grandes
                sub_chunks = self._split_large_section(section_lines, filename, chunk_size)
                chunks.extend(sub_chunks)
        
        return chunks
    
    def _split_by_pages(self, lines: List[str], page_breaks: List[int], 
                       filename: str, chunk_size: int) -> List[str]:
        """Divide el texto por páginas."""
        chunks = []
        page_breaks = [-1] + page_breaks + [len(lines)]
        
        for i in range(len(page_breaks) - 1):
            start_idx = page_breaks[i] + 1
            end_idx = page_breaks[i + 1]
            
            page_lines = lines[start_idx:end_idx]
            page_text = '\n'.join(page_lines)
            
            if len(page_text.split()) > chunk_size:
                # Dividir páginas grandes por párrafos
                sub_chunks = self._split_by_paragraphs(page_text, filename, chunk_size)
                chunks.extend(sub_chunks)
            else:
                doc_prefix = f"[Documento: {os.path.basename(filename)}] "
                chunks.append(doc_prefix + page_text)
        
        return chunks
    
    def _split_by_paragraphs(self, text: str, filename: str, chunk_size: int) -> List[str]:
        """Divide el texto por párrafos."""
        chunks = []
        paragraphs = text.split('\n\n')
        current_chunk = []
        current_size = 0
        
        for paragraph in paragraphs:
            words = paragraph.split()
            if current_size + len(words) <= chunk_size:
                current_chunk.append(paragraph)
                current_size += len(words)
            else:
                if current_chunk:
                    doc_prefix = f"[Documento: {os.path.basename(filename)}] "
                    chunks.append(doc_prefix + '\n\n'.join(current_chunk))
                current_chunk = [paragraph]
                current_size = len(words)
        
        if current_chunk:
            doc_prefix = f"[Documento: {os.path.basename(filename)}] "
            chunks.append(doc_prefix + '\n\n'.join(current_chunk))
        
        return chunks
    
    def _split_large_section(self, section_lines: List[str], filename: str, 
                           chunk_size: int) -> List[str]:
        """Divide una sección grande en chunks más pequeños."""
        chunks = []
        current_chunk = [section_lines[0]]  # Mantener el encabezado
        current_size = len(section_lines[0].split())
        
        for line in section_lines[1:]:
            line_words = len(line.split())
            
            if current_size + line_words <= chunk_size:
                current_chunk.append(line)
                current_size += line_words
            else:
                # Guardar chunk actual
                doc_prefix = f"[Documento: {os.path.basename(filename)}] "
                chunks.append(doc_prefix + '\n'.join(current_chunk))
                
                # Iniciar nuevo chunk con contexto
                current_chunk = [section_lines[0], line]
                current_size = len(section_lines[0].split()) + line_words
        
        # Guardar el último chunk
        if current_chunk:
            doc_prefix = f"[Documento: {os.path.basename(filename)}] "
            chunks.append(doc_prefix + '\n'.join(current_chunk))
        
        return chunks
    
    def _combine_small_chunks(self, chunks: List[str], min_chunk_size: int = 50) -> List[str]:
        """Combina chunks muy pequeños con el anterior."""
        if not chunks:
            return chunks
        
        processed_chunks = []
        title_pattern = re.compile(r'^#\s+')
        section_pattern = re.compile(r'^##\s+')
        
        for i, chunk in enumerate(chunks):
            chunk_words = len(chunk.split())
            
            if (chunk_words < min_chunk_size and i > 0 and 
                not title_pattern.search(chunk) and not section_pattern.search(chunk)):
                # Combinar con el chunk anterior
                if processed_chunks:
                    previous_chunk = processed_chunks[-1]
                    combined_chunk = previous_chunk + "\n\n" + chunk
                    processed_chunks[-1] = combined_chunk
                else:
                    processed_chunks.append(chunk)
            else:
                processed_chunks.append(chunk)
        
        return processed_chunks
    
    def process_document_complete(self, pdf_path: str) -> Dict[str, Any]:
        """
        Procesa completamente un documento PDF: conversión a markdown y chunking.
        
        Args:
            pdf_path (str): Ruta al archivo PDF
            
        Returns:
            Dict[str, Any]: Diccionario con toda la información del documento procesado
        """
        try:
            # Procesar PDF a Markdown
            markdown_result = self.process_pdf_to_markdown(pdf_path)
            
            # Dividir en chunks
            chunks = self.split_into_chunks(
                markdown_result['markdown_content'], 
                markdown_result['filename']
            )
            
            # Calcular estadísticas
            total_words = len(markdown_result['markdown_content'].split())
            
            return {
                'filename': markdown_result['filename'],
                'markdown_content': markdown_result['markdown_content'],
                'chunks': chunks,
                'num_chunks': len(chunks),
                'total_words': total_words,
                'processed_successfully': True,
                'output_dir': markdown_result['output_dir']
            }
            
        except Exception as e:
            logger.error(f"Error al procesar documento completo {pdf_path}: {str(e)}")
            return {
                'filename': os.path.basename(pdf_path),
                'processed_successfully': False,
                'error': str(e)
            }
    
    def cleanup_temp_files(self, output_dir: str = None):
        """
        Limpia archivos temporales.
        
        Args:
            output_dir (str): Directorio específico a limpiar (opcional)
        """
        try:
            if output_dir:
                import shutil
                shutil.rmtree(output_dir)
                logger.info(f"Directorio temporal limpiado: {output_dir}")
            else:
                # Limpiar todo el directorio temporal
                import shutil
                if self.temp_dir.exists():
                    shutil.rmtree(self.temp_dir)
                    self.temp_dir.mkdir(parents=True, exist_ok=True)
                    logger.info("Directorio temporal completamente limpiado")
        except Exception as e:
            logger.error(f"Error al limpiar archivos temporales: {str(e)}")


# Función de conveniencia
def process_pdf_document(pdf_path: str) -> Dict[str, Any]:
    """
    Función de conveniencia para procesar un documento PDF.
    
    Args:
        pdf_path (str): Ruta al archivo PDF
        
    Returns:
        Dict[str, Any]: Diccionario con información del documento procesado
    """
    processor = DocumentProcessor()
    return processor.process_document_complete(pdf_path) 