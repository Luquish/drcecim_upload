"""
Servicio de generación de embeddings usando OpenAI.

Este módulo proporciona funcionalidades para:
1. Generar embeddings de texto usando la API de OpenAI
2. Almacenar embeddings en PostgreSQL con pgvector
3. Procesar chunks de documentos en lotes
4. Manejar reintentos automáticos en caso de errores de API
5. Almacenar embeddings y metadatos asociados

Dependencias:
- openai: Para generar embeddings usando la API
- pgvector: Para almacenamiento y búsqueda vectorial en PostgreSQL
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
import json
from datetime import datetime
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import openai
import time

from common.models.openai_model import OpenAIEmbedding
from common.config.settings import (
    OPENAI_API_KEY, 
    EMBEDDING_MODEL, 
    API_TIMEOUT,
    TEMP_DIR
)
from common.services.vector_db_service import VectorDBService

# Configuración de logging
logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Servicio para generar embeddings de texto usando OpenAI y almacenarlos en PostgreSQL.
    
    Esta clase maneja todo el flujo de generación de embeddings:
    1. Procesamiento de chunks de texto en lotes
    2. Generación de embeddings usando OpenAI API
    3. Almacenamiento en PostgreSQL con pgvector
    4. Manejo de errores y reintentos automáticos
    5. Almacenamiento de embeddings y metadatos
    
    Attributes:
        temp_dir (Path): Directorio temporal para archivos
        model (OpenAIEmbedding): Instancia del modelo de OpenAI
        vector_db (VectorDBService): Servicio de base de datos vectorial
        
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
        
        # Inicializar servicio de base de datos vectorial
        self.vector_db = VectorDBService()
        logger.info("Servicio de base de datos vectorial inicializado")
    
    def generate_embeddings(self, texts: List[str], batch_size: int = 16, use_batch_api: bool = False) -> np.ndarray:
        """
        Genera embeddings para una lista de textos usando OpenAI.
        
        Args:
            texts (List[str]): Lista de textos a procesar
            batch_size (int): Tamaño del batch para procesamiento
            use_batch_api (bool): Si usar Batch API para lotes grandes (>10k)
            
        Returns:
            np.ndarray: Array de embeddings
        """
        if not texts:
            logger.warning("Lista de textos vacía, no se generarán embeddings")
            return np.array([])
        
        total_texts = len(texts)
        logger.info(f"Generando embeddings con OpenAI para {total_texts} textos")
        
        # Decidir si usar Batch API para lotes grandes
        if use_batch_api and total_texts > 10000:
            logger.info("Usando Batch API de OpenAI para lote grande")
            return self._generate_embeddings_with_batch_api(texts)
        
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
    
    def store_embeddings_in_db(self, embeddings: np.ndarray, metadata_df: pd.DataFrame) -> bool:
        """
        Almacena embeddings en la base de datos PostgreSQL.
        
        Args:
            embeddings (np.ndarray): Array de embeddings
            metadata_df (pd.DataFrame): DataFrame con metadatos
            
        Returns:
            bool: True si se almacenaron exitosamente
        """
        try:
            logger.info(f"Almacenando {len(embeddings)} embeddings en PostgreSQL")
            
            # Usar el servicio de base de datos vectorial
            success = self.vector_db.store_embeddings(embeddings, metadata_df)
            
            if success:
                logger.info("Embeddings almacenados exitosamente en PostgreSQL")
            else:
                logger.error("Error al almacenar embeddings en PostgreSQL")
            
            return success
            
        except Exception as e:
            logger.error(f"Error al almacenar embeddings en PostgreSQL: {str(e)}")
            return False
    
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
            
            # Crear metadatos
            metadata = self.create_metadata(texts, filenames, chunk_indices)
            metadata_summary = self.create_metadata_summary(metadata)
            
            # Almacenar embeddings en PostgreSQL
            storage_success = self.store_embeddings_in_db(embeddings, metadata)
            
            if not storage_success:
                raise Exception("Error al almacenar embeddings en PostgreSQL")
            
            # Crear configuración
            config = {
                'date': datetime.now().isoformat(),
                'embedding_model': 'OpenAI',
                'model_name': EMBEDDING_MODEL,
                'dimension': self.embedding_dimension,
                'num_vectors': len(texts),
                'filename': filename,
                'num_chunks': len(chunks),
                'total_words': processed_doc.get('total_words', 0),
                'storage_type': 'PostgreSQL'
            }
            
            return {
                'filename': filename,
                'embeddings': embeddings,
                'metadata': metadata.to_dict(orient='records'),
                'metadata_summary': metadata_summary,
                'config': config,
                'processed_successfully': True,
                'storage_success': storage_success
            }
            
        except Exception as e:
            logger.error(f"Error al procesar embeddings para documento: {str(e)}")
            return {
                'filename': processed_doc.get('filename', 'unknown'),
                'processed_successfully': False,
                'error': str(e)
            }
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de la base de datos de embeddings.
        
        Returns:
            Dict[str, Any]: Estadísticas de la base de datos
        """
        try:
            return self.vector_db.get_database_stats()
        except Exception as e:
            logger.error(f"Error al obtener estadísticas de la base de datos: {str(e)}")
            return {}
    
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

    def _generate_embeddings_with_batch_api(self, texts: List[str]) -> np.ndarray:
        """
        Genera embeddings usando Batch API de OpenAI para lotes grandes.
        
        Args:
            texts (List[str]): Lista de textos
            
        Returns:
            np.ndarray: Array de embeddings
        """
        try:
            # Crear job de batch
            batch_job = openai.Batch.create(
                input_file_id=self._create_input_file(texts),
                endpoint="/v1/embeddings",
                completion_window="24h"
            )
            
            logger.info(f"Batch job creado: {batch_job.id}")
            
            # Esperar a que se complete (en producción, esto sería asíncrono)
            while batch_job.status != "completed":
                time.sleep(60)  # Verificar cada minuto
                batch_job = openai.Batch.retrieve(batch_job.id)
                
                if batch_job.status == "failed":
                    raise Exception(f"Batch job falló: {batch_job.error}")
            
            # Descargar resultados
            results = batch_job.download()
            embeddings = [result['embedding'] for result in results]
            
            return np.array(embeddings)
            
        except Exception as e:
            logger.error(f"Error en Batch API: {str(e)}")
            # Fallback a método normal
            logger.info("Fallback a método normal de embeddings")
            return self.generate_embeddings(texts, batch_size=16, use_batch_api=False)
    
    def _create_input_file(self, texts: List[str]) -> str:
        """
        Crea un archivo de entrada para Batch API.
        
        Args:
            texts (List[str]): Lista de textos
            
        Returns:
            str: ID del archivo creado
        """
        # Crear archivo temporal con los textos
        import tempfile
        import json
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for text in texts:
                json.dump({"input": text, "model": EMBEDDING_MODEL}, f)
                f.write('\n')
        
        # Subir archivo a OpenAI
        with open(f.name, 'rb') as file:
            file_upload = openai.files.create(
                file=file,
                purpose="batch"
            )
        
        # Limpiar archivo temporal
        import os
        os.unlink(f.name)
        
        return file_upload.id


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