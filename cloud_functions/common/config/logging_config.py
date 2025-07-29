"""
Configuración centralizada de logging para el sistema DrCecim Upload.
"""
import logging
import logging.config
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


def get_logging_config(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    enable_file_logging: bool = True,
    enable_console_logging: bool = True,
    log_format: Optional[str] = None
) -> Dict[str, Any]:
    """
    Genera configuración de logging estandarizada.
    
    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directorio para archivos de log
        enable_file_logging: Si habilitar logging a archivo
        enable_console_logging: Si habilitar logging a consola
        log_format: Formato personalizado de logs
        
    Returns:
        Dict: Configuración para logging.config.dictConfig
    """
    if log_dir is None:
        log_dir = Path("logs")
    
    log_dir.mkdir(exist_ok=True)
    
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    
    # Archivos de log con timestamp
    timestamp = datetime.now().strftime("%Y%m%d")
    app_log_file = log_dir / f"drcecim_upload_{timestamp}.log"
    error_log_file = log_dir / f"drcecim_upload_errors_{timestamp}.log"
    
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": log_format,
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "simple": {
                "format": "%(levelname)s - %(message)s"
            },
            "json": {
                "format": "%(asctime)s %(name)s %(levelname)s %(funcName)s %(lineno)d %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {},
        "loggers": {
            "": {  # Root logger
                "level": log_level,
                "handlers": []
            },
            "services": {
                "level": log_level,
                "handlers": [],
                "propagate": False
            },
            "config": {
                "level": log_level,
                "handlers": [],
                "propagate": False
            },
            "models": {
                "level": log_level,
                "handlers": [],
                "propagate": False
            },
            "utils": {
                "level": log_level,
                "handlers": [],
                "propagate": False
            },
            "cloud_functions": {
                "level": log_level,
                "handlers": [],
                "propagate": False
            }
        }
    }
    
    handlers = []
    
    # Handler de consola
    if enable_console_logging:
        config["handlers"]["console"] = {
            "class": "logging.StreamHandler",
            "level": log_level,
            "formatter": "detailed",
            "stream": sys.stdout
        }
        handlers.append("console")
    
    # Handler de archivo para logs generales
    if enable_file_logging:
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": log_level,
            "formatter": "detailed",
            "filename": str(app_log_file),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf8"
        }
        handlers.append("file")
        
        # Handler específico para errores
        config["handlers"]["error_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "detailed",
            "filename": str(error_log_file),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf8"
        }
        handlers.append("error_file")
    
    # Asignar handlers a todos los loggers
    for logger_name in config["loggers"]:
        config["loggers"][logger_name]["handlers"] = handlers
    
    return config


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    enable_file_logging: bool = True,
    enable_console_logging: bool = True,
    log_format: Optional[str] = None
) -> None:
    """
    Configura el sistema de logging.
    
    Args:
        log_level: Nivel de logging
        log_dir: Directorio para archivos de log
        enable_file_logging: Si habilitar logging a archivo
        enable_console_logging: Si habilitar logging a consola
        log_format: Formato personalizado de logs
    """
    config = get_logging_config(
        log_level=log_level,
        log_dir=log_dir,
        enable_file_logging=enable_file_logging,
        enable_console_logging=enable_console_logging,
        log_format=log_format
    )
    
    logging.config.dictConfig(config)
    
    # Log inicial de configuración
    logger = logging.getLogger(__name__)
    logger.info("Sistema de logging configurado")
    logger.info(f"Nivel de logging: {log_level}")
    logger.info(f"Directorio de logs: {log_dir}")
    logger.info(f"Logging a archivo: {enable_file_logging}")
    logger.info(f"Logging a consola: {enable_console_logging}")


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger configurado.
    
    Args:
        name: Nombre del logger
        
    Returns:
        logging.Logger: Logger configurado
    """
    return logging.getLogger(name)


class StructuredLogger:
    """Logger con soporte para logging estructurado."""
    
    def __init__(self, name: str):
        """
        Inicializa el logger estructurado.
        
        Args:
            name: Nombre del logger
        """
        self.logger = logging.getLogger(name)
    
    def log_structured(self, level: str, message: str, **kwargs) -> None:
        """
        Log estructurado con contexto adicional.
        
        Args:
            level: Nivel de log
            message: Mensaje principal
            **kwargs: Contexto adicional
        """
        extra = {"structured_data": kwargs}
        log_method = getattr(self.logger, level.lower())
        log_method(message, extra=extra)
    
    def info(self, message: str, **kwargs) -> None:
        """Log de nivel INFO."""
        self.log_structured("INFO", message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log de nivel WARNING."""
        self.log_structured("WARNING", message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log de nivel ERROR."""
        self.log_structured("ERROR", message, **kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log de nivel DEBUG."""
        self.log_structured("DEBUG", message, **kwargs)


# Configuración por defecto para desarrollo
def setup_development_logging() -> None:
    """Configura logging para desarrollo."""
    setup_logging(
        log_level="DEBUG",
        log_dir=Path("logs"),
        enable_file_logging=True,
        enable_console_logging=True
    )


# Configuración para producción
def setup_production_logging() -> None:
    """Configura logging para producción."""
    setup_logging(
        log_level="INFO",
        log_dir=Path("/var/log/drcecim"),
        enable_file_logging=True,
        enable_console_logging=False,
        log_format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ) 