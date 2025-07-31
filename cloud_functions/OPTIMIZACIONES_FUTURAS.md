# Optimizaciones Futuras - DrCecim Upload

## 1. Optimización FAISS

### Archivo: `cloud_functions/common/services/index_manager_service.py`

**Cambio:** Optimizar cuando índice > 500 MB

**Implementación sugerida:**
```python
def optimize_faiss_index(self, index_size_threshold: int = 500 * 1024 * 1024) -> bool:
    """
    Optimiza el índice FAISS cuando supera el umbral de tamaño.
    
    Args:
        index_size_threshold: Umbral en bytes (default: 500MB)
        
    Returns:
        bool: True si se optimizó exitosamente
    """
    try:
        # Verificar tamaño del índice
        index_size = self._get_index_size()
        
        if index_size > index_size_threshold:
            logger.info(f"Optimizando índice FAISS (tamaño: {index_size / 1024 / 1024:.2f}MB)")
            
            # Reconstruir índice con parámetros optimizados
            optimized_index = faiss.IndexIVFFlat(
                self.quantizer, 
                self.dimension, 
                min(self.nlist, 1000),  # Limitar número de clusters
                faiss.METRIC_INNER_PRODUCT
            )
            
            # Transferir vectores al nuevo índice
            self.index = optimized_index
            self._save_index()
            
            logger.info("Índice FAISS optimizado exitosamente")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error optimizando índice FAISS: {str(e)}")
        return False
```

## 2. Pulido de Detalles Menores

### Mayúsculas en ".PDF"
- **Archivo:** `cloud_functions/main.py`
- **Cambio:** Normalizar extensión de archivo a minúsculas
- **Implementación:**
```python
def is_pdf_file(file_name: str) -> bool:
    """Verifica si el archivo es un PDF."""
    return file_name.lower().endswith('.pdf')
```

### Cleanup de `/tmp`
- **Archivo:** `cloud_functions/common/utils/temp_file_manager.py`
- **Mejora:** Limpieza más agresiva en Cloud Functions
```python
def cleanup_temp_files(self, max_age_hours: int = 1) -> None:
    """Limpia archivos temporales más antiguos que max_age_hours."""
    current_time = time.time()
    for temp_path in self._temp_files:
        try:
            if os.path.exists(temp_path):
                file_age = current_time - os.path.getmtime(temp_path)
                if file_age > (max_age_hours * 3600):
                    os.unlink(temp_path)
                    logger.debug(f"Archivo temporal eliminado por edad: {temp_path}")
        except Exception as e:
            logger.warning(f"Error limpiando archivo temporal {temp_path}: {e}")
```

### Manejo de Errores Mejorado
- **Archivo:** `cloud_functions/main.py`
- **Mejora:** Retry automático para errores transitorios
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError))
)
def process_with_retry(self, pdf_path: str) -> Dict:
    """Procesa PDF con retry automático."""
    # Implementación del procesamiento
    pass
```

## 3. Optimizaciones de Rendimiento

### Compresión de Chunks
- **Archivo:** `cloud_functions/common/services/gcs_service.py`
- **Mejora:** Comprimir chunks antes de subir a GCS
```python
import gzip
import json

def upload_compressed_chunks(self, chunks_data: Dict) -> bool:
    """Sube chunks comprimidos a GCS."""
    compressed_data = gzip.compress(json.dumps(chunks_data).encode('utf-8'))
    return self.upload_bytes(compressed_data, f"{GCS_PROCESSED_PREFIX}/chunks.json.gz")
```

### Cache de Embeddings
- **Archivo:** `cloud_functions/common/services/embeddings_service.py`
- **Mejora:** Cache local para embeddings frecuentes
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cached_embedding(self, text: str) -> List[float]:
    """Obtiene embedding con cache local."""
    return self._generate_embedding(text)
```

## 4. Monitoreo y Observabilidad

### Métricas Personalizadas
- **Archivo:** `cloud_functions/common/utils/monitoring.py`
- **Mejora:** Métricas detalladas de rendimiento
```python
def track_processing_metrics(self, filename: str, processing_time: float, 
                           chunk_count: int, file_size: int) -> None:
    """Registra métricas de procesamiento."""
    self.logger.info("Processing metrics", {
        'filename': filename,
        'processing_time_seconds': processing_time,
        'chunk_count': chunk_count,
        'file_size_bytes': file_size,
        'chunks_per_second': chunk_count / processing_time if processing_time > 0 else 0
    })
```

### Health Checks Mejorados
- **Archivo:** `cloud_functions/main.py`
- **Mejora:** Health checks más detallados
```python
@functions_framework.http
def health_check_detailed(request):
    """Health check detallado con métricas del sistema."""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'memory_usage': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/tmp').percent,
        'gcs_connectivity': check_gcs_connectivity(),
        'openai_connectivity': check_openai_connectivity()
    }
```

## 5. Seguridad y Configuración

### Validación de Archivos Mejorada
- **Archivo:** `cloud_functions/services/file_validator.py`
- **Mejora:** Validación más estricta de archivos PDF
```python
def validate_pdf_security(self, file_path: str) -> bool:
    """Valida que el PDF no contenga contenido malicioso."""
    # Implementar validación de seguridad
    # - Verificar que no contenga JavaScript
    # - Verificar que no contenga URLs externas
    # - Verificar que no contenga formularios
    pass
```

### Configuración Dinámica
- **Archivo:** `cloud_functions/common/config/settings.py`
- **Mejora:** Configuración desde variables de entorno
```python
class Settings(BaseSettings):
    """Configuración dinámica desde variables de entorno."""
    
    # Configuración de procesamiento
    CHUNK_SIZE: int = Field(default=1000, env="CHUNK_SIZE")
    CHUNK_OVERLAP: int = Field(default=200, env="CHUNK_OVERLAP")
    
    # Configuración de embeddings
    EMBEDDING_MODEL: str = Field(default="text-embedding-ada-002", env="EMBEDDING_MODEL")
    API_TIMEOUT: int = Field(default=30, env="API_TIMEOUT")
    
    # Configuración de logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_TO_DISK: bool = Field(default=False, env="LOG_TO_DISK")
    
    class Config:
        env_file = ".env"
```

## 6. Escalabilidad

### Procesamiento Paralelo
- **Archivo:** `cloud_functions/common/services/processing_service.py`
- **Mejora:** Procesamiento de chunks en paralelo
```python
from concurrent.futures import ThreadPoolExecutor
import asyncio

async def process_chunks_parallel(self, chunks: List[str], max_workers: int = 4) -> List[Dict]:
    """Procesa chunks en paralelo."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(executor, self._process_single_chunk, chunk)
            for chunk in chunks
        ]
        return await asyncio.gather(*tasks)
```

### Batch Processing
- **Archivo:** `cloud_functions/common/services/embeddings_service.py`
- **Mejora:** Procesamiento en lotes para embeddings
```python
def generate_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
    """Genera embeddings en lotes para mejor rendimiento."""
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_embeddings = self._generate_embeddings_batch(batch)
        embeddings.extend(batch_embeddings)
    return embeddings
```

---

**Nota:** Estas optimizaciones deben implementarse gradualmente y probarse exhaustivamente en un entorno de desarrollo antes de desplegar a producción. 