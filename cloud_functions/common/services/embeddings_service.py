"""
Servicio de generación de embeddings usando OpenAI.

Este módulo proporciona funcionalidades para:
1. Generar embeddings de texto usando la API de OpenAI
2. Crear índices FAISS para búsqueda vectorial eficiente
3. Procesar chunks de documentos en lotes
4. Manejar reintentos automáticos en caso de errores de API
5. Almacenar embeddings y metadatos asociados

Dependencias:
- openai: Para generar embeddings usando la API
- faiss-cpu: Para indexación y búsqueda vectorial
- pandas: Para manipulación de datos
- numpy: Para operaciones numéricas
- tenacity: Para manejo de reintentos

Configuración:
- OPENAI_API_KEY: Clave de API de OpenAI (requerida)
- EMBEDDING_MODEL: Modelo de embeddings a usar (default: text-embedding-3-small)
- API_TIMEOUT: Timeout para peticiones a la API
"""
import os
import logging
import tempfile
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
import numpy as np
import faiss
import json
from datetime import datetime
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import openai

from common.models.openai_model import OpenAIEmbedding
from common.config.settings import (
    OPENAI_API_KEY, 
    EMBEDDING_MODEL, 
    API_TIMEOUT,
    TEMP_DIR
)

# Configuración de logging
logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Servicio para generar embeddings de texto usando OpenAI y crear índices FAISS.
    
    Esta clase maneja todo el flujo de generación de embeddings:
    1. Procesamiento de chunks de texto en lotes
    2. Generación de embeddings usando OpenAI API
    3. Creación de índices FAISS para búsqueda vectorial
    4. Manejo de errores y reintentos automáticos
    5. Almacenamiento de embeddings y metadatos
    
    Attributes:
        temp_dir (Path): Directorio temporal para archivos
        model (OpenAIEmbedding): Instancia del modelo de OpenAI
        
    Example:
        >>> service = EmbeddingService()
        >>> chunks = [{"text": "Texto 1", "id": "1"}, {"text": "Texto 2", "id": "2"}]
        >>> result = service.process_chunks_to_embeddings(chunks, "documento.pdf")
        >>> logger.info(f"Generados {result['num_embeddings']} embeddings")
    """
    
    def __init__(self, temp_dir: str = TEMP_DIR):
        """
        Inicializa el servicio de embeddings.
        
        Args:
            temp_dir (str): Directorio temporal para archivos
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Verificar API Key
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY no está configurada. Es necesaria para generar embeddings.")
        
        # Inicializar modelo OpenAI
        logger.info(f"Inicializando modelo de embeddings OpenAI: {EMBEDDING_MODEL}")
        self.model = OpenAIEmbedding(
            model_name=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY,
            timeout=API_TIMEOUT
        )
        
        self.embedding_dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Dimensión del modelo OpenAI: {self.embedding_dimension}")
        logger.info("OpenAI inicializado correctamente para embeddings")
    
    def generate_embeddings(self, texts: List[str], batch_size: int = 16) -> np.ndarray:
        """
        Genera embeddings para una lista de textos usando OpenAI.
        
        Args:
            texts (List[str]): Lista de textos a procesar
            batch_size (int): Tamaño del batch para procesamiento
            
        Returns:
            np.ndarray: Array de embeddings
        """
        if not texts:
            logger.warning("Lista de textos vacía, no se generarán embeddings")
            return np.array([])
        
        total_texts = len(texts)
        logger.info(f"Generando embeddings con OpenAI para {total_texts} textos")
        
        # Preprocesar textos
        valid_texts = self._preprocess_texts(texts)
        
        # Generar embeddings con OpenAI
        embeddings = []
        # OpenAI soporta batches más grandes, dividimos en bloques de 100 para seguridad
        openai_batch_size = min(batch_size * 4, 100)
        
        try:
            for i in tqdm(range(0, len(valid_texts), openai_batch_size), 
                         desc="Generando embeddings con OpenAI"):
                batch = valid_texts[i:i + openai_batch_size]
                batch_embeddings = self._generate_batch_embeddings_with_retry(batch)
                embeddings.append(batch_embeddings)
            
            # Concatenar y normalizar embeddings
            all_embeddings = self._finalize_embeddings(embeddings)
            return all_embeddings
                
        except Exception as e:
            logger.error(f"Error general en generación de embeddings con OpenAI: {str(e)}")
            raise
    
    def _preprocess_texts(self, texts: List[str]) -> List[str]:
        """
        Preprocesa textos para asegurar que sean válidos para la API de OpenAI.
        
        Args:
            texts (List[str]): Textos originales
            
        Returns:
            List[str]: Textos válidos y preprocesados
        """
        valid_texts = []
        
        for i, text in enumerate(texts):
            if not text or not isinstance(text, str):
                logger.warning(f"Texto inválido en índice {i}")
                valid_texts.append("texto inválido")
            else:
                # Limpiar y preparar el texto
                text = text.strip()
                if len(text) < 10:
                    logger.warning(f"Texto muy corto en índice {i}")
                    text = text + " " + text  # Duplicar texto corto
                valid_texts.append(text)
        
        return valid_texts
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((
            openai.APITimeoutError,
            openai.RateLimitError, 
            openai.APIConnectionError,
            openai.InternalServerError
        ))
    )
    def _generate_batch_embeddings_with_retry(self, batch: List[str]) -> np.ndarray:
        """
        Genera embeddings para un batch con reintentos automáticos.
        
        Args:
            batch (List[str]): Batch de textos
            
        Returns:
            np.ndarray: Embeddings del batch
        """
        try:
            return self.model.encode(
                batch,
                convert_to_numpy=True,
                normalize_embeddings=False
            )
        except openai.APIError as e:
            logger.error(f"Error específico de OpenAI API: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado en batch: {str(e)}")
            raise
    
    def _finalize_embeddings(self, embeddings: List[np.ndarray]) -> np.ndarray:
        """
        Concatena y normaliza los embeddings finales.
        
        Args:
            embeddings (List[np.ndarray]): Lista de arrays de embeddings
            
        Returns:
            np.ndarray: Array final de embeddings normalizados
        """
        # Concatenar embeddings
        all_embeddings = np.vstack(embeddings)
        
        # Normalizar si es necesario
        if np.any(np.sum(all_embeddings * all_embeddings, axis=1) > 1.0):
            logger.info("Normalizando embeddings finales...")
            all_embeddings = all_embeddings / np.sqrt(
                np.sum(all_embeddings * all_embeddings, axis=1, keepdims=True)
            )
        
        return all_embeddings
    
    def create_faiss_index(self, embeddings: np.ndarray) -> faiss.Index:
        """
        Crea un índice FAISS para los embeddings.
        
        Args:
            embeddings (np.ndarray): Array de embeddings
            
        Returns:
            faiss.Index: Índice FAISS
        """
        dimension = embeddings.shape[1]
        logger.info(f"Creando índice FAISS con {embeddings.shape[0]} vectores de dimensión {dimension}")
        
        # Asegurar que los embeddings sean float32 para FAISS
        embeddings = embeddings.astype('float32')
        
        # Verificar si tenemos suficientes vectores para usar índices más avanzados
        if embeddings.shape[0] > 10000:
            # Para colecciones grandes, usar un índice IVF para búsqueda más rápida
            nlist = min(int(np.sqrt(embeddings.shape[0])), 100)  # Número de clusters
            quantizer = faiss.IndexFlatL2(dimension)
            index = faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss.METRIC_L2)
            
            # Necesita entrenamiento
            logger.info(f"Entrenando índice IVFFlat con {nlist} clusters...")
            index.train(embeddings)
            index.add(embeddings)
            logger.info("Índice IVFFlat creado y entrenado")
        else:
            # Para colecciones pequeñas, usar un índice plano (más simple pero preciso)
            index = faiss.IndexFlatL2(dimension)
            index.add(embeddings)
            logger.info("Índice FlatL2 creado")
        
        return index
    
    def save_faiss_index(self, index: faiss.Index, filepath: str):
        """
        Guarda un índice FAISS en un archivo.
        
        Args:
            index (faiss.Index): Índice FAISS
            filepath (str): Ruta donde guardar el archivo
        """
        try:
            faiss.write_index(index, filepath)
            logger.info(f"Índice FAISS guardado en {filepath}")
        except Exception as e:
            logger.error(f"Error al guardar índice FAISS: {str(e)}")
            raise
    
    def create_metadata(self, texts: List[str], filenames: List[str], 
                       chunk_indices: List[int]) -> pd.DataFrame:
        """
        Crea metadatos para los embeddings.
        
        Args:
            texts (List[str]): Lista de textos
            filenames (List[str]): Lista de nombres de archivo
            chunk_indices (List[int]): Lista de índices de chunks
            
        Returns:
            pd.DataFrame: DataFrame con metadatos
        """
        import uuid
        from pathlib import Path
        
        # Crear IDs únicos para documento y chunks
        document_ids = []
        chunk_ids = []
        
        for filename in filenames:
            # Crear document_id basado en el nombre del archivo (sin extensión)
            document_id = Path(filename).stem
            document_ids.append(document_id)
            
            # Crear chunk_id único combinando document_id y chunk_index
            chunk_id = f"{document_id}_{chunk_indices[len(chunk_ids)]}"
            chunk_ids.append(chunk_id)
        
        # Crear DataFrame con información adicional
        metadata = pd.DataFrame({
            'document_id': document_ids,
            'chunk_id': chunk_ids,
            'text': texts,
            'filename': filenames,
            'chunk_index': chunk_indices,
            'text_length': [len(text) for text in texts],
            'word_count': [len(text.split()) for text in texts],
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        return metadata
    
    def save_metadata(self, metadata: pd.DataFrame, filepath: str):
        """
        Guarda metadatos en un archivo CSV.
        
        Args:
            metadata (pd.DataFrame): DataFrame con metadatos
            filepath (str): Ruta donde guardar el archivo
        """
        try:
            metadata.to_csv(filepath, index=False)
            logger.info(f"Metadatos guardados en {filepath}")
        except Exception as e:
            logger.error(f"Error al guardar metadatos: {str(e)}")
            raise
    
    def create_metadata_summary(self, metadata: pd.DataFrame) -> pd.DataFrame:
        """
        Crea un resumen de metadatos por archivo.
        
        Args:
            metadata (pd.DataFrame): DataFrame con metadatos
            
        Returns:
            pd.DataFrame: DataFrame con resumen
        """
        summary = metadata.groupby('filename').agg({
            'chunk_index': 'count',
            'text_length': ['sum', 'mean'],
            'word_count': ['sum', 'mean']
        }).reset_index()
        
        summary.columns = [
            'filename', 'num_chunks', 'total_chars', 'avg_chars_per_chunk',
            'total_words', 'avg_words_per_chunk'
        ]
        
        return summary
    
    def save_config(self, config: Dict[str, Any], filepath: str):
        """
        Guarda configuración en un archivo JSON.
        
        Args:
            config (Dict[str, Any]): Diccionario con configuración
            filepath (str): Ruta donde guardar el archivo
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Configuración guardada en {filepath}")
        except Exception as e:
            logger.error(f"Error al guardar configuración: {str(e)}")
            raise
    
    def process_document_embeddings(self, processed_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa un documento y genera embeddings para sus chunks.
        
        Args:
            processed_doc (Dict[str, Any]): Documento procesado con chunks
            
        Returns:
            Dict[str, Any]: Diccionario con embeddings y metadatos
        """
        try:
            if not processed_doc.get('processed_successfully', False):
                raise ValueError("El documento no se procesó correctamente")
            
            chunks = processed_doc.get('chunks', [])
            if not chunks:
                raise ValueError("No se encontraron chunks en el documento")
            
            filename = processed_doc.get('filename', 'unknown')
            
            # Preparar datos para embeddings
            texts = chunks
            filenames = [filename] * len(chunks)
            chunk_indices = list(range(len(chunks)))
            
            logger.info(f"Procesando {len(texts)} chunks de {filename}")
            
            # Generar embeddings
            embeddings = self.generate_embeddings(texts)
            
            if embeddings.size == 0:
                raise ValueError("No se generaron embeddings")
            
            # Crear índice FAISS
            faiss_index = self.create_faiss_index(embeddings)
            
            # Crear metadatos
            metadata = self.create_metadata(texts, filenames, chunk_indices)
            metadata_summary = self.create_metadata_summary(metadata)
            
            # Crear configuración
            config = {
                'date': datetime.now().isoformat(),
                'embedding_model': 'OpenAI',
                'model_name': EMBEDDING_MODEL,
                'dimension': self.embedding_dimension,
                'num_vectors': len(texts),
                'filename': filename,
                'num_chunks': len(chunks),
                'total_words': processed_doc.get('total_words', 0)
            }
            
            return {
                'filename': filename,
                'embeddings': embeddings,
                'faiss_index': faiss_index,
                'metadata': metadata,
                'metadata_summary': metadata_summary,
                'config': config,
                'processed_successfully': True
            }
            
        except Exception as e:
            logger.error(f"Error al procesar embeddings para documento: {str(e)}")
            return {
                'filename': processed_doc.get('filename', 'unknown'),
                'processed_successfully': False,
                'error': str(e)
            }
    
    def save_embeddings_data(self, embeddings_data: Dict[str, Any], 
                           output_dir: str = None) -> Dict[str, str]:
        """
        Guarda todos los datos de embeddings en archivos.
        
        Args:
            embeddings_data (Dict[str, Any]): Datos de embeddings
            output_dir (str): Directorio de salida (opcional)
            
        Returns:
            Dict[str, str]: Diccionario con rutas de archivos guardados
        """
        if not embeddings_data.get('processed_successfully', False):
            raise ValueError("Los datos de embeddings no se procesaron correctamente")
        
        # Usar directorio temporal si no se especifica
        if output_dir is None:
            output_dir = self.temp_dir / f"embeddings_{embeddings_data['filename']}"
        else:
            output_dir = Path(output_dir)
            
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Definir rutas de archivos
        files = {
            'faiss_index': output_dir / 'faiss_index.bin',
            'metadata': output_dir / 'metadata.csv',
            'metadata_summary': output_dir / 'metadata_summary.csv',
            'config': output_dir / 'config.json'
        }
        
        try:
            # Guardar índice FAISS
            self.save_faiss_index(embeddings_data['faiss_index'], str(files['faiss_index']))
            
            # Guardar metadatos
            self.save_metadata(embeddings_data['metadata'], str(files['metadata']))
            
            # Guardar resumen de metadatos
            self.save_metadata(embeddings_data['metadata_summary'], str(files['metadata_summary']))
            
            # Guardar configuración
            self.save_config(embeddings_data['config'], str(files['config']))
            
            # Convertir paths a strings
            file_paths = {k: str(v) for k, v in files.items()}
            
            logger.info(f"Datos de embeddings guardados en {output_dir}")
            return file_paths
            
        except Exception as e:
            logger.error(f"Error al guardar datos de embeddings: {str(e)}")
            raise
    
    def cleanup_temp_files(self, directory: str = None):
        """
        Limpia archivos temporales.
        
        Args:
            directory (str): Directorio específico a limpiar (opcional)
        """
        try:
            if directory:
                import shutil
                shutil.rmtree(directory)
                logger.info(f"Directorio temporal limpiado: {directory}")
            else:
                # Limpiar todo el directorio temporal
                import shutil
                if self.temp_dir.exists():
                    shutil.rmtree(self.temp_dir)
                    self.temp_dir.mkdir(parents=True, exist_ok=True)
                    logger.info("Directorio temporal de embeddings limpiado")
        except Exception as e:
            logger.error(f"Error al limpiar archivos temporales: {str(e)}")


# Función de conveniencia
def process_document_embeddings(processed_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Función de conveniencia para procesar embeddings de un documento.
    
    Args:
        processed_doc (Dict[str, Any]): Documento procesado con chunks
        
    Returns:
        Dict[str, Any]: Diccionario con embeddings y metadatos
    """
    service = EmbeddingService()
    return service.process_document_embeddings(processed_doc) 