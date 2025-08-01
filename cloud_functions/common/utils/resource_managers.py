"""
Gestores de recursos para el procesamiento de documentos.
Proporciona context managers para manejar recursos de manera segura.
"""
import os
import logging
import time
import uuid
from typing import Generator, Optional, Any
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)


@contextmanager
def document_processing_context(
    temp_dir: Optional[str] = None,
    cleanup_on_exit: bool = True
) -> Generator[dict, None, None]:
    """
    Context manager para el procesamiento de documentos.
    
    Args:
        temp_dir: Directorio temporal para el procesamiento
        cleanup_on_exit: Si limpiar recursos al salir
        
    Yields:
        dict: Contexto con información del procesamiento
        
    Example:
        with document_processing_context() as context:
            # Procesar documento
            pass
        # Recursos limpiados automáticamente
    """
    context = {
        'temp_dir': temp_dir,
        'cleanup_on_exit': cleanup_on_exit,
        'resources': []
    }
    
    try:
        yield context
    finally:
        if cleanup_on_exit:
            _cleanup_resources(context['resources'])


@contextmanager
def with_processing_resources(
    temp_dir: Optional[str] = None,
    max_memory_mb: Optional[int] = None,
    timeout_seconds: Optional[int] = None
) -> Generator[dict, None, None]:
    """
    Context manager para recursos de procesamiento con límites.
    
    Args:
        temp_dir: Directorio temporal
        max_memory_mb: Límite de memoria en MB
        timeout_seconds: Timeout en segundos
        
    Yields:
        dict: Contexto con recursos de procesamiento
    """
    import psutil
    import threading
    import os
    
    start_time = time.time()
    start_memory = psutil.virtual_memory().used
    
    context = {
        'temp_dir': temp_dir,
        'start_time': start_time,
        'start_memory': start_memory,
        'max_memory_mb': max_memory_mb,
        'timeout_seconds': timeout_seconds,
        'resources': [],
        'timeout_triggered': False
    }
    
    def timeout_checker():
        """Thread para verificar timeout manualmente"""
        if timeout_seconds:
            time.sleep(timeout_seconds)
            if not context.get('completed', False):
                context['timeout_triggered'] = True
                # En entornos serverless, la mejor opción es terminar el proceso
                logger.error(f"Timeout de {timeout_seconds} segundos alcanzado")
                os._exit(1)  # Terminar proceso de forma abrupta
    
    def memory_checker():
        """Thread para verificar uso de memoria"""
        if max_memory_mb:
            while not context.get('completed', False):
                current_memory = psutil.virtual_memory().used
                memory_used_mb = (current_memory - start_memory) / (1024 * 1024)
                if memory_used_mb > max_memory_mb:
                    context['timeout_triggered'] = True
                    logger.error(f"Límite de memoria {max_memory_mb}MB excedido")
                    os._exit(1)
                time.sleep(1)  # Verificar cada segundo
    
    timeout_thread = None
    memory_thread = None
    
    try:
        # Iniciar threads de monitoreo si se especifican límites
        if timeout_seconds:
            timeout_thread = threading.Thread(target=timeout_checker, daemon=True)
            timeout_thread.start()
        
        if max_memory_mb:
            memory_thread = threading.Thread(target=memory_checker, daemon=True)
            memory_thread.start()
        
        yield context
        
    finally:
        # Marcar como completado para detener threads
        context['completed'] = True
        
        # Limpiar recursos
        _cleanup_resources(context['resources'])
        
        # Log de uso de recursos
        elapsed_time = time.time() - start_time
        current_memory = psutil.virtual_memory().used
        memory_used_mb = (current_memory - start_memory) / (1024 * 1024)
        
        logger.info(f"Recursos utilizados - Tiempo: {elapsed_time:.2f}s, Memoria: {memory_used_mb:.2f}MB")


@contextmanager
def processing_session_context(
    session_id: Optional[str] = None,
    timeout: int = 900
) -> Generator[dict, None, None]:
    """
    Context manager para sesiones de procesamiento.
    
    Args:
        session_id: ID de la sesión (opcional, se genera automáticamente)
        timeout: Timeout en segundos
        
    Yields:
        dict: Contexto de la sesión de procesamiento
    """
    if not session_id:
        session_id = str(uuid.uuid4())
    
    start_time = time.time()
    
    context = {
        'session_id': session_id,
        'start_time': start_time,
        'timeout': timeout,
        'status': 'running',
        'resources': []
    }
    
    try:
        logger.info(f"Iniciando sesión de procesamiento: {session_id}")
        yield context
        context['status'] = 'completed'
        logger.info(f"Sesión completada: {session_id}")
    except Exception as e:
        context['status'] = 'failed'
        context['error'] = str(e)
        logger.error(f"Sesión falló: {session_id} - {str(e)}")
        raise
    finally:
        elapsed_time = time.time() - start_time
        context['elapsed_time'] = elapsed_time
        logger.info(f"Sesión finalizada: {session_id} - Tiempo: {elapsed_time:.2f}s")


@contextmanager
def gcs_client_context(
    bucket_name: Optional[str] = None,
    credentials_path: Optional[str] = None
) -> Generator[Any, None, None]:
    """
    Context manager para cliente de Google Cloud Storage.
    
    Args:
        bucket_name: Nombre del bucket (opcional)
        credentials_path: Ruta a las credenciales (opcional)
        
    Yields:
        Any: Cliente de GCS configurado
    """
    try:
        from google.cloud import storage
        
        # Configurar credenciales si se proporcionan
        if credentials_path and os.path.exists(credentials_path):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        
        # Crear cliente
        client = storage.Client()
        
        # Obtener bucket si se especifica
        bucket = None
        if bucket_name:
            bucket = client.bucket(bucket_name)
        
        context = {
            'client': client,
            'bucket': bucket,
            'bucket_name': bucket_name
        }
        
        yield context
        
    except ImportError:
        logger.warning("Google Cloud Storage no está disponible")
        yield {'client': None, 'bucket': None, 'bucket_name': bucket_name}
    except Exception as e:
        logger.error(f"Error configurando cliente GCS: {str(e)}")
        yield {'client': None, 'bucket': None, 'bucket_name': bucket_name}


@contextmanager
def openai_client_context(
    api_key: Optional[str] = None,
    model: str = "gpt-3.5-turbo",
    timeout: int = 60
) -> Generator[Any, None, None]:
    """
    Context manager para cliente de OpenAI.
    
    Args:
        api_key: API key de OpenAI (opcional)
        model: Modelo a usar
        timeout: Timeout en segundos
        
    Yields:
        Any: Cliente de OpenAI configurado
    """
    try:
        import openai
        
        # Configurar API key si se proporciona
        if api_key:
            openai.api_key = api_key
        elif os.getenv('OPENAI_API_KEY'):
            openai.api_key = os.getenv('OPENAI_API_KEY')
        
        # Configurar timeout
        openai.timeout = timeout
        
        context = {
            'client': openai,
            'model': model,
            'timeout': timeout
        }
        
        yield context
        
    except ImportError:
        logger.warning("OpenAI no está disponible")
        yield {'client': None, 'model': model, 'timeout': timeout}
    except Exception as e:
        logger.error(f"Error configurando cliente OpenAI: {str(e)}")
        yield {'client': None, 'model': model, 'timeout': timeout}


def _cleanup_resources(resources: list) -> None:
    """
    Limpia recursos de procesamiento.
    
    Args:
        resources: Lista de recursos a limpiar
    """
    for resource in resources:
        try:
            if isinstance(resource, str) and os.path.exists(resource):
                if os.path.isfile(resource):
                    os.unlink(resource)
                elif os.path.isdir(resource):
                    import shutil
                    shutil.rmtree(resource)
                logger.debug(f"Recurso limpiado: {resource}")
        except (OSError, PermissionError) as e:
            logger.warning(f"No se pudo limpiar recurso {resource}: {e}")


@contextmanager
def file_processing_context(
    input_file: str,
    output_dir: Optional[str] = None,
    preserve_input: bool = True
) -> Generator[dict, None, None]:
    """
    Context manager para procesamiento de archivos.
    
    Args:
        input_file: Ruta del archivo de entrada
        output_dir: Directorio de salida (opcional)
        preserve_input: Si preservar el archivo de entrada
        
    Yields:
        dict: Contexto con información del procesamiento
    """
    context = {
        'input_file': input_file,
        'output_dir': output_dir,
        'preserve_input': preserve_input,
        'temp_files': []
    }
    
    try:
        yield context
    finally:
        if not preserve_input and os.path.exists(input_file):
            try:
                os.unlink(input_file)
                logger.debug(f"Archivo de entrada eliminado: {input_file}")
            except (OSError, PermissionError) as e:
                logger.warning(f"No se pudo eliminar archivo de entrada {input_file}: {e}")


@contextmanager
def memory_context() -> Generator[dict, None, None]:
    """
    Context manager para gestión de memoria.
    
    Yields:
        dict: Contexto de memoria
    """
    import gc
    
    context = {
        'initial_objects': len(gc.get_objects())
    }
    
    try:
        yield context
    finally:
        # Forzar garbage collection
        collected = gc.collect()
        logger.debug(f"Garbage collection: {collected} objetos recolectados")


@contextmanager
def error_handling_context(
    log_errors: bool = True,
    reraise: bool = True
) -> Generator[dict, None, None]:
    """
    Context manager para manejo de errores.
    
    Args:
        log_errors: Si registrar errores
        reraise: Si relanzar excepciones
        
    Yields:
        dict: Contexto de manejo de errores
    """
    context = {
        'errors': [],
        'log_errors': log_errors,
        'reraise': reraise
    }
    
    try:
        yield context
    except Exception as e:
        if log_errors:
            logger.error(f"Error en contexto: {str(e)}")
        context['errors'].append(str(e))
        
        if reraise:
            raise 