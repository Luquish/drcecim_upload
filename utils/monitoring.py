"""
Módulo de monitoreo y logging para el sistema DrCecim Upload.

Este módulo proporciona:
1. Logger personalizado con formato estructurado
2. Métricas básicas de performance y uso
3. Monitoreo de operaciones críticas
4. Alertas básicas para errores
5. Colección de estadísticas del sistema
"""
import os
import logging
import json
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Counter
from functools import wraps
from pathlib import Path
from collections import defaultdict, deque
from threading import Lock

from config.settings import LOG_LEVEL, LOG_FORMAT, ENVIRONMENT, DEBUG


class DrCecimLogger:
    """
    Logger personalizado para el sistema DrCecim Upload.
    """
    
    def __init__(self, name: str = "drcecim_upload"):
        """
        Inicializa el logger.
        
        Args:
            name (str): Nombre del logger
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self._setup_logger()
        
    def _setup_logger(self):
        """Configura el logger con handlers apropiados."""
        # Limpiar handlers existentes
        self.logger.handlers.clear()
        
        # Configurar nivel
        level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
        self.logger.setLevel(level)
        
        # Configurar formato
        formatter = logging.Formatter(
            LOG_FORMAT,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Handler para archivo en desarrollo
        if ENVIRONMENT == 'development':
            log_dir = Path('logs')
            log_dir.mkdir(exist_ok=True)
            
            file_handler = logging.FileHandler(log_dir / f'{self.name}.log')
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def info(self, message: str, extra: Dict[str, Any] = None):
        """Log info message."""
        self._log_with_context(logging.INFO, message, extra)
    
    def warning(self, message: str, extra: Dict[str, Any] = None):
        """Log warning message."""
        self._log_with_context(logging.WARNING, message, extra)
    
    def error(self, message: str, extra: Dict[str, Any] = None):
        """Log error message."""
        self._log_with_context(logging.ERROR, message, extra)
    
    def debug(self, message: str, extra: Dict[str, Any] = None):
        """Log debug message."""
        self._log_with_context(logging.DEBUG, message, extra)
    
    def _log_with_context(self, level: int, message: str, extra: Dict[str, Any] = None):
        """Log con contexto adicional."""
        if extra:
            context = json.dumps(extra, ensure_ascii=False)
            message = f"{message} | Context: {context}"
        
        self.logger.log(level, message)


class MetricsCollector:
    """
    Colector de métricas para el sistema.
    """
    
    def __init__(self):
        """Inicializa el colector de métricas."""
        self.metrics = {}
        self.start_time = time.time()
        
    def increment_counter(self, metric_name: str, value: int = 1, labels: Dict[str, str] = None):
        """
        Incrementa un contador.
        
        Args:
            metric_name (str): Nombre de la métrica
            value (int): Valor a incrementar
            labels (Dict[str, str]): Labels adicionales
        """
        key = self._get_metric_key(metric_name, labels)
        if key not in self.metrics:
            self.metrics[key] = {'type': 'counter', 'value': 0, 'labels': labels or {}}
        self.metrics[key]['value'] += value
    
    def set_gauge(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """
        Establece un valor de gauge.
        
        Args:
            metric_name (str): Nombre de la métrica
            value (float): Valor del gauge
            labels (Dict[str, str]): Labels adicionales
        """
        key = self._get_metric_key(metric_name, labels)
        self.metrics[key] = {
            'type': 'gauge',
            'value': value,
            'labels': labels or {},
            'timestamp': time.time()
        }
    
    def record_histogram(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """
        Registra un valor de histograma.
        
        Args:
            metric_name (str): Nombre de la métrica
            value (float): Valor a registrar
            labels (Dict[str, str]): Labels adicionales
        """
        key = self._get_metric_key(metric_name, labels)
        if key not in self.metrics:
            self.metrics[key] = {
                'type': 'histogram',
                'values': [],
                'labels': labels or {}
            }
        self.metrics[key]['values'].append({
            'value': value,
            'timestamp': time.time()
        })
    
    def _get_metric_key(self, metric_name: str, labels: Dict[str, str] = None) -> str:
        """Genera una clave única para la métrica."""
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{metric_name}_{label_str}"
        return metric_name
    
    def get_metrics(self) -> Dict[str, Any]:
        """Obtiene todas las métricas."""
        return {
            'metrics': self.metrics,
            'system': {
                'uptime': time.time() - self.start_time,
                'timestamp': datetime.now().isoformat()
            }
        }
    
    def reset_metrics(self):
        """Reinicia todas las métricas."""
        self.metrics.clear()
        self.start_time = time.time()


class ProcessingMonitor:
    """
    Monitor específico para el procesamiento de documentos.
    """
    
    def __init__(self, logger: DrCecimLogger, metrics: MetricsCollector):
        """
        Inicializa el monitor.
        
        Args:
            logger (DrCecimLogger): Logger a usar
            metrics (MetricsCollector): Colector de métricas
        """
        self.logger = logger
        self.metrics = metrics
        self.processing_sessions = {}
    
    def start_processing(self, filename: str, session_id: str = None) -> str:
        """
        Inicia el monitoreo de procesamiento.
        
        Args:
            filename (str): Nombre del archivo
            session_id (str): ID de sesión (opcional)
            
        Returns:
            str: ID de sesión
        """
        if not session_id:
            session_id = f"proc_{int(time.time())}"
        
        self.processing_sessions[session_id] = {
            'filename': filename,
            'start_time': time.time(),
            'steps': [],
            'status': 'started'
        }
        
        self.logger.info(f"Iniciando procesamiento", {
            'session_id': session_id,
            'filename': filename
        })
        
        self.metrics.increment_counter('documents_processing_started', labels={
            'filename': filename
        })
        
        return session_id
    
    def log_step(self, session_id: str, step_name: str, details: Dict[str, Any] = None):
        """
        Registra un paso del procesamiento.
        
        Args:
            session_id (str): ID de sesión
            step_name (str): Nombre del paso
            details (Dict[str, Any]): Detalles adicionales
        """
        if session_id not in self.processing_sessions:
            self.logger.warning(f"Sesión no encontrada: {session_id}")
            return
        
        step_data = {
            'name': step_name,
            'timestamp': time.time(),
            'details': details or {}
        }
        
        self.processing_sessions[session_id]['steps'].append(step_data)
        
        self.logger.info(f"Paso completado: {step_name}", {
            'session_id': session_id,
            'step_details': details
        })
        
        self.metrics.increment_counter('processing_steps_completed', labels={
            'step_name': step_name
        })
    
    def finish_processing(self, session_id: str, success: bool = True, 
                         error_message: str = None, results: Dict[str, Any] = None):
        """
        Finaliza el monitoreo de procesamiento.
        
        Args:
            session_id (str): ID de sesión
            success (bool): Si fue exitoso
            error_message (str): Mensaje de error (si aplica)
            results (Dict[str, Any]): Resultados del procesamiento
        """
        if session_id not in self.processing_sessions:
            self.logger.warning(f"Sesión no encontrada: {session_id}")
            return
        
        session = self.processing_sessions[session_id]
        processing_time = time.time() - session['start_time']
        
        session['status'] = 'completed' if success else 'failed'
        session['end_time'] = time.time()
        session['processing_time'] = processing_time
        session['results'] = results or {}
        
        if error_message:
            session['error_message'] = error_message
        
        # Log final
        if success:
            self.logger.info(f"Procesamiento completado exitosamente", {
                'session_id': session_id,
                'filename': session['filename'],
                'processing_time': processing_time,
                'results': results
            })
        else:
            self.logger.error(f"Procesamiento falló", {
                'session_id': session_id,
                'filename': session['filename'],
                'processing_time': processing_time,
                'error': error_message
            })
        
        # Métricas
        self.metrics.increment_counter('documents_processed', labels={
            'status': 'success' if success else 'error',
            'filename': session['filename']
        })
        
        self.metrics.record_histogram('processing_time_seconds', processing_time, labels={
            'filename': session['filename']
        })
        
        if results:
            self.metrics.set_gauge('last_processed_chunks', results.get('num_chunks', 0))
            self.metrics.set_gauge('last_processed_words', results.get('total_words', 0))
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de procesamiento."""
        active_sessions = {k: v for k, v in self.processing_sessions.items() 
                          if v['status'] == 'started'}
        
        completed_sessions = {k: v for k, v in self.processing_sessions.items() 
                             if v['status'] in ['completed', 'failed']}
        
        return {
            'active_sessions': len(active_sessions),
            'completed_sessions': len(completed_sessions),
            'total_sessions': len(self.processing_sessions),
            'sessions': self.processing_sessions
        }


# Decorador para monitorear funciones
def monitor_function(logger: DrCecimLogger, metrics: MetricsCollector):
    """
    Decorador para monitorear funciones.
    
    Args:
        logger (DrCecimLogger): Logger a usar
        metrics (MetricsCollector): Colector de métricas
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            function_name = func.__name__
            start_time = time.time()
            
            logger.info(f"Iniciando función: {function_name}")
            metrics.increment_counter('function_calls', labels={'function': function_name})
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                logger.info(f"Función completada: {function_name}", {
                    'execution_time': execution_time
                })
                
                metrics.record_histogram('function_execution_time', execution_time, labels={
                    'function': function_name,
                    'status': 'success'
                })
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                
                logger.error(f"Error en función: {function_name}", {
                    'execution_time': execution_time,
                    'error': str(e)
                })
                
                metrics.increment_counter('function_errors', labels={
                    'function': function_name
                })
                
                metrics.record_histogram('function_execution_time', execution_time, labels={
                    'function': function_name,
                    'status': 'error'
                })
                
                raise
        
        return wrapper
    return decorator


# Instancias globales
logger = DrCecimLogger()
metrics = MetricsCollector()
processing_monitor = ProcessingMonitor(logger, metrics)


# Funciones de conveniencia
def get_logger(name: str = None) -> DrCecimLogger:
    """Obtiene un logger."""
    if name:
        return DrCecimLogger(name)
    return logger


def get_metrics() -> MetricsCollector:
    """Obtiene el colector de métricas."""
    return metrics


def get_processing_monitor() -> ProcessingMonitor:
    """Obtiene el monitor de procesamiento."""
    return processing_monitor


def log_system_info():
    """Registra información del sistema."""
    logger.info("Sistema DrCecim Upload iniciado", {
        'environment': ENVIRONMENT,
        'debug': DEBUG,
        'log_level': LOG_LEVEL,
        'timestamp': datetime.now().isoformat()
    }) 