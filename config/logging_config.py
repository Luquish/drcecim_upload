"""
Configuración de logging específica para la aplicación Streamlit.
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from config.settings import LOG_LEVEL, LOG_FORMAT, ENVIRONMENT


def setup_streamlit_logging(
    log_level: str = LOG_LEVEL,
    log_format: str = LOG_FORMAT,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Configura el sistema de logging para la aplicación Streamlit.
    
    Args:
        log_level (str): Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format (str): Formato de los mensajes de log
        log_file (Optional[str]): Ruta al archivo de log (opcional)
        max_bytes (int): Tamaño máximo del archivo de log antes de rotar
        backup_count (int): Número de archivos de backup a mantener
        
    Returns:
        logging.Logger: Logger configurado
    """
    
    # Crear logger principal
    logger = logging.getLogger("streamlit_app")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Limpiar handlers existentes para evitar duplicados
    logger.handlers.clear()
    
    # Crear formatter
    formatter = logging.Formatter(log_format)
    
    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler para archivo (si se especifica)
    if log_file:
        # Crear directorio de logs si no existe
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Handler rotativo para archivo
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Configurar logging para bibliotecas externas
    _setup_external_logging(log_level)
    
    logger.info(f"Logging configurado para Streamlit - Nivel: {log_level}")
    return logger


def _setup_external_logging(log_level: str) -> None:
    """
    Configura el logging para bibliotecas externas.
    
    Args:
        log_level (str): Nivel de logging
    """
    # Configurar logging para bibliotecas específicas
    external_loggers = [
        "streamlit",
        "google.cloud",
        "openai",
        "urllib3",
        "requests"
    ]
    
    for logger_name in external_loggers:
        external_logger = logging.getLogger(logger_name)
        external_logger.setLevel(getattr(logging, log_level.upper()))
        
        # Evitar propagación duplicada
        if not external_logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(LOG_FORMAT))
            external_logger.addHandler(handler)


def get_streamlit_logger(name: str = "streamlit_app") -> logging.Logger:
    """
    Obtiene un logger configurado para la aplicación Streamlit.
    
    Args:
        name (str): Nombre del logger
        
    Returns:
        logging.Logger: Logger configurado
    """
    return logging.getLogger(name)


def log_streamlit_event(event_type: str, details: dict, logger: Optional[logging.Logger] = None) -> None:
    """
    Registra eventos específicos de Streamlit.
    
    Args:
        event_type (str): Tipo de evento (upload, process, error, etc.)
        details (dict): Detalles del evento
        logger (Optional[logging.Logger]): Logger a usar (opcional)
    """
    if logger is None:
        logger = get_streamlit_logger()
    
    logger.info(f"STREAMLIT_EVENT: {event_type}", extra={
        "event_type": event_type,
        "details": details,
        "environment": ENVIRONMENT
    })


def log_streamlit_error(error: Exception, context: str = "", logger: Optional[logging.Logger] = None) -> None:
    """
    Registra errores específicos de Streamlit.
    
    Args:
        error (Exception): Error a registrar
        context (str): Contexto del error
        logger (Optional[logging.Logger]): Logger a usar (opcional)
    """
    if logger is None:
        logger = get_streamlit_logger()
    
    logger.error(f"STREAMLIT_ERROR: {context}", extra={
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context,
        "environment": ENVIRONMENT
    }, exc_info=True)


# Configuración inicial
streamlit_logger = setup_streamlit_logging()
