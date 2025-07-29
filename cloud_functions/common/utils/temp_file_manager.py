"""
Utilidades para manejo de archivos temporales.
Proporciona context managers y funciones para crear y limpiar archivos temporales de manera segura.
"""
import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Generator, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class TempFileManager:
    """
    Gestor de archivos temporales con limpieza automática.
    """
    
    def __init__(self, prefix: str = "drcecim_", suffix: str = "", directory: Optional[str] = None):
        """
        Inicializa el gestor de archivos temporales.
        
        Args:
            prefix: Prefijo para los archivos temporales
            suffix: Sufijo para los archivos temporales
            directory: Directorio donde crear los archivos (opcional)
        """
        self.prefix = prefix
        self.suffix = suffix
        self.directory = directory
        self._temp_files = []
    
    def create_temp_file(self, content: Optional[bytes] = None, **kwargs) -> str:
        """
        Crea un archivo temporal.
        
        Args:
            content: Contenido opcional para escribir en el archivo
            **kwargs: Argumentos adicionales para tempfile.NamedTemporaryFile
            
        Returns:
            str: Ruta del archivo temporal creado
        """
        temp_file = tempfile.NamedTemporaryFile(
            prefix=self.prefix,
            suffix=self.suffix,
            dir=self.directory,
            delete=False,
            **kwargs
        )
        
        if content:
            temp_file.write(content)
            temp_file.flush()
        
        temp_file.close()
        self._temp_files.append(temp_file.name)
        return temp_file.name
    
    def create_temp_directory(self, **kwargs) -> str:
        """
        Crea un directorio temporal.
        
        Args:
            **kwargs: Argumentos adicionales para tempfile.mkdtemp
            
        Returns:
            str: Ruta del directorio temporal creado
        """
        temp_dir = tempfile.mkdtemp(
            prefix=self.prefix,
            dir=self.directory,
            **kwargs
        )
        self._temp_files.append(temp_dir)
        return temp_dir
    
    def cleanup(self) -> None:
        """Limpia todos los archivos y directorios temporales creados."""
        for temp_path in self._temp_files:
            try:
                if os.path.isfile(temp_path):
                    os.unlink(temp_path)
                elif os.path.isdir(temp_path):
                    shutil.rmtree(temp_path)
                logger.debug(f"Archivo temporal eliminado: {temp_path}")
            except (OSError, PermissionError) as e:
                logger.warning(f"No se pudo eliminar archivo temporal {temp_path}: {e}")
        
        self._temp_files.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


@contextmanager
def temp_file(prefix: str = "drcecim_", suffix: str = "", directory: Optional[str] = None, **kwargs) -> Generator[str, None, None]:
    """
    Context manager para crear un archivo temporal.
    
    Args:
        prefix: Prefijo para el archivo temporal
        suffix: Sufijo para el archivo temporal
        directory: Directorio donde crear el archivo
        **kwargs: Argumentos adicionales para tempfile.NamedTemporaryFile
        
    Yields:
        str: Ruta del archivo temporal
        
    Example:
        with temp_file(suffix='.pdf') as temp_path:
            # Usar temp_path
            pass
        # Archivo eliminado automáticamente
    """
    temp_path = None
    try:
        temp_file_obj = tempfile.NamedTemporaryFile(
            prefix=prefix,
            suffix=suffix,
            dir=directory,
            delete=False,
            **kwargs
        )
        temp_path = temp_file_obj.name
        temp_file_obj.close()
        yield temp_path
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except (OSError, PermissionError) as e:
                logger.warning(f"No se pudo eliminar archivo temporal {temp_path}: {e}")


@contextmanager
def temp_dir(prefix: str = "drcecim_", directory: Optional[str] = None, **kwargs) -> Generator[str, None, None]:
    """
    Context manager para crear un directorio temporal.
    
    Args:
        prefix: Prefijo para el directorio temporal
        directory: Directorio padre donde crear el directorio temporal
        **kwargs: Argumentos adicionales para tempfile.mkdtemp
        
    Yields:
        str: Ruta del directorio temporal
        
    Example:
        with temp_dir() as temp_dir_path:
            # Usar temp_dir_path
            pass
        # Directorio eliminado automáticamente
    """
    temp_dir_path = None
    try:
        temp_dir_path = tempfile.mkdtemp(prefix=prefix, dir=directory, **kwargs)
        yield temp_dir_path
    finally:
        if temp_dir_path and os.path.exists(temp_dir_path):
            try:
                shutil.rmtree(temp_dir_path)
            except (OSError, PermissionError) as e:
                logger.warning(f"No se pudo eliminar directorio temporal {temp_dir_path}: {e}")


# Instancia global para uso directo
temp_manager = TempFileManager() 