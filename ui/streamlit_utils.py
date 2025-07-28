"""
Utilidades para la aplicación Streamlit de DrCecim Upload.
Contiene funciones auxiliares para formateo, validación y operaciones comunes.
"""
import math
import tempfile
from typing import Dict, Any, Optional
from pathlib import Path

# Imports con manejo de errores
try:
    from services.file_validator import pdf_validator
except ImportError as e:
    import logging
    logging.error(f"Error importando file_validator: {e}")
    # Crear un validador mock para casos donde no esté disponible
    class MockValidator:
        def validate_file(self, file_data):
            return {'valid': True}
    pdf_validator = MockValidator()

try:
    from config.streamlit_constants import (
        MAX_FILE_SIZE_MB, 
        ALLOWED_FILE_TYPES,
        ERROR_NO_FILE_SELECTED,
        ERROR_FILE_TOO_LARGE,
        ERROR_INVALID_FILE_TYPE,
        MAX_FILENAME_LENGTH,
        SAFE_FILENAME_LENGTH
    )
except ImportError as e:
    import logging
    logging.error(f"Error importando constantes: {e}")
    # Valores por defecto en caso de error
    MAX_FILE_SIZE_MB = 50
    ALLOWED_FILE_TYPES = ['pdf']
    ERROR_NO_FILE_SELECTED = "No se seleccionó ningún archivo"
    ERROR_FILE_TOO_LARGE = f"El archivo excede el tamaño máximo de {MAX_FILE_SIZE_MB}MB"
    ERROR_INVALID_FILE_TYPE = f"Tipo de archivo no permitido. Solo se permiten: {', '.join(ALLOWED_FILE_TYPES)}"
    MAX_FILENAME_LENGTH = 100
    SAFE_FILENAME_LENGTH = 90


def format_file_size(size_bytes: int) -> str:
    """
    Formatea el tamaño del archivo de manera legible.
    
    Args:
        size_bytes (int): Tamaño en bytes
        
    Returns:
        str: Tamaño formateado (ej: "1.5 MB")
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


def validate_file(uploaded_file: Optional[Any]) -> Dict[str, Any]:
    """
    Valida que el archivo sea válido para procesamiento con validaciones de seguridad.
    
    Args:
        uploaded_file: Archivo subido por Streamlit
        
    Returns:
        Dict con 'valid' (bool) y 'error' (str) si hay error
        
    Raises:
        FileNotFoundError: Si el archivo no se encuentra
        PermissionError: Si no hay permisos para leer el archivo
        ValueError: Si los datos del archivo son inválidos
    """
    if not uploaded_file:
        return {'valid': False, 'error': ERROR_NO_FILE_SELECTED}
    
    try:
        # Verificar extensión
        file_extension = Path(uploaded_file.name).suffix.lower().lstrip('.')
        if file_extension not in ALLOWED_FILE_TYPES:
            return {
                'valid': False,
                'error': ERROR_INVALID_FILE_TYPE
            }
        
        # Verificar tamaño
        file_size_mb = uploaded_file.size / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            return {
                'valid': False,
                'error': ERROR_FILE_TOO_LARGE
            }
        
        # Validaciones avanzadas de seguridad
        try:
            # Leer el archivo para validación de seguridad
            file_data = uploaded_file.read()
            uploaded_file.seek(0)  # Resetear posición del archivo
            
            # Realizar validación de seguridad completa
            security_validation = pdf_validator.validate_file(file_data=file_data)
            
            if not security_validation['valid']:
                return {
                    'valid': False,
                    'error': f"Validación de seguridad: {security_validation.get('error', 'Error desconocido')}"
                }
            
            return {'valid': True, 'file_data': file_data}
            
        except FileNotFoundError as e:
            return {
                'valid': False,
                'error': f"Archivo no encontrado: {str(e)}"
            }
        except PermissionError as e:
            return {
                'valid': False,
                'error': f"Sin permisos para leer el archivo: {str(e)}"
            }
        except ValueError as e:
            return {
                'valid': False,
                'error': f"Datos del archivo inválidos: {str(e)}"
            }
            
    except Exception as e:
        return {
            'valid': False,
            'error': f"Error inesperado en validación: {str(e)}"
        }


def create_temp_file(file_data: bytes, filename: str) -> str:
    """
    Crea un archivo temporal con los datos proporcionados.
    
    Args:
        file_data (bytes): Datos del archivo
        filename (str): Nombre del archivo original
        
    Returns:
        str: Ruta del archivo temporal creado
        
    Raises:
        OSError: Si hay error creando el archivo temporal
        PermissionError: Si no hay permisos para crear el archivo
    """
    try:
        # Crear archivo temporal
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=Path(filename).suffix,
            prefix="drcecim_upload_"
        )
        
        # Escribir datos
        temp_file.write(file_data)
        temp_file.flush()
        temp_file.close()
        
        return temp_file.name
        
    except OSError as e:
        raise OSError(f"Error creando archivo temporal: {str(e)}")
    except PermissionError as e:
        raise PermissionError(f"Sin permisos para crear archivo temporal: {str(e)}")


def cleanup_temp_file(temp_path: str) -> bool:
    """
    Limpia un archivo temporal de manera segura.
    
    Args:
        temp_path (str): Ruta del archivo temporal
        
    Returns:
        bool: True si se eliminó exitosamente
    """
    try:
        if Path(temp_path).exists():
            Path(temp_path).unlink()
            return True
        return False
    except (OSError, PermissionError):
        # Log del error pero no falla la operación
        return False


def safe_filename(filename: str) -> str:
    """
    Limpia un nombre de archivo para hacerlo seguro.
    
    Args:
        filename (str): Nombre de archivo original
        
    Returns:
        str: Nombre de archivo seguro
    """
    # Caracteres peligrosos a reemplazar
    dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    
    safe_name = filename
    for char in dangerous_chars:
        safe_name = safe_name.replace(char, '_')
    
    # Limitar longitud usando constantes configurables
    if len(safe_name) > MAX_FILENAME_LENGTH:
        name_part = Path(safe_name).stem[:SAFE_FILENAME_LENGTH]
        extension = Path(safe_name).suffix
        safe_name = f"{name_part}{extension}"
    
    return safe_name


def extract_file_info(uploaded_file: Any) -> Dict[str, Any]:
    """
    Extrae información básica de un archivo subido.
    
    Args:
        uploaded_file: Archivo subido por Streamlit
        
    Returns:
        Dict con información del archivo
    """
    if not uploaded_file:
        return {}
    
    return {
        'name': uploaded_file.name,
        'size': uploaded_file.size,
        'size_formatted': format_file_size(uploaded_file.size),
        'extension': Path(uploaded_file.name).suffix.lower(),
        'safe_name': safe_filename(uploaded_file.name)
    } 