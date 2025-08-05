"""
Configuración central para el sistema DrCecim Upload usando Pydantic.
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env
load_dotenv()


class GoogleCloudSettings(BaseSettings):
    """Configuración de Google Cloud Services."""
    
    # Google Cloud Storage
    gcs_bucket_name: str = Field(default='drcecim-chatbot-storage', env='GCS_BUCKET_NAME')
    gcs_credentials_path: Optional[str] = Field(default=None, env='GCS_CREDENTIALS_PATH')
    
    # Google Cloud Functions
    gcf_region: str = Field(default='us-central1', env='GCF_REGION')
    gcf_project_id: Optional[str] = Field(default=None, env='GCF_PROJECT_ID')
    
    # Estructura de carpetas en GCS optimizada
    gcs_uploads_prefix: str = 'uploads/'
    gcs_temp_prefix: str = 'temp/'
    # DEPRECATED: embeddings/, metadata/, processed/ - Todo migrado a PostgreSQL
    
    # Nombres de archivos en GCS
    gcs_metadata_name: str = 'metadata.csv'
    gcs_metadata_summary_name: str = 'metadata_summary.csv'
    gcs_config_name: str = 'config.json'

    class Config:
        env_prefix = ''
    



class OpenAISettings(BaseSettings):
    """Configuración de OpenAI API."""
    
    openai_api_key: Optional[str] = Field(default=None, env='OPENAI_API_KEY')
    embedding_model: str = Field(default='text-embedding-3-small', env='EMBEDDING_MODEL')
    api_timeout: int = Field(default=30, env='API_TIMEOUT')
    
    # Configuración de generación de texto
    max_output_tokens: int = Field(default=2048, env='MAX_OUTPUT_TOKENS')
    temperature: float = Field(default=0.7, env='TEMPERATURE')
    top_p: float = Field(default=1.0, env='TOP_P')

    class Config:
        env_prefix = ''




class ProcessingSettings(BaseSettings):
    """Configuración de procesamiento de documentos."""
    
    # Configuración de chunking
    chunk_size: int = Field(default=250, env='CHUNK_SIZE')
    chunk_overlap: int = Field(default=50, env='CHUNK_OVERLAP')
    
    # Directorios - usar rutas relativas más seguras por defecto
    temp_dir: str = Field(default='./temp', env='TEMP_DIR')
    processed_dir: str = Field(default='./data/processed', env='PROCESSED_DIR')
    embeddings_dir: str = Field(default='./data/embeddings', env='EMBEDDINGS_DIR')
    
    # Configuración del dispositivo
    device: str = Field(default='cpu', env='DEVICE')

    class Config:
        env_prefix = ''




class StreamlitSettings(BaseSettings):
    """Configuración de la aplicación Streamlit."""
    
    title: str = Field(default='DrCecim - Carga de Documentos', env='STREAMLIT_TITLE')
    description: str = Field(
        default='Sistema de carga y procesamiento de documentos PDF para el chatbot DrCecim',
        env='STREAMLIT_DESCRIPTION'
    )
    max_file_size_mb: int = Field(default=50, env='MAX_FILE_SIZE_MB')
    allowed_file_types: List[str] = ['pdf']

    class Config:
        env_prefix = ''


class ServerSettings(BaseSettings):
    """Configuración del servidor."""
    
    host: str = Field(default='0.0.0.0', env='HOST')
    port: int = Field(default=8080, env='PORT')

    class Config:
        env_prefix = ''


class LoggingSettings(BaseSettings):
    """Configuración de logging."""
    
    log_level: str = Field(default='INFO', env='LOG_LEVEL')
    log_format: str = Field(
        default='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        env='LOG_FORMAT'
    )

    class Config:
        env_prefix = ''


class DatabaseSettings(BaseSettings):
    """Configuración de Cloud SQL Database."""
    
    db_user: str = Field(default='raguser', env='DB_USER')
    db_pass: str = Field(default='DrCecim2024@', env='DB_PASS')
    db_name: str = Field(default='ragdb', env='DB_NAME')
    cloud_sql_connection_name: str = Field(
        default='drcecim-465823:southamerica-east1:drcecim-cloud-sql', 
        env='CLOUD_SQL_CONNECTION_NAME'
    )
    db_private_ip: bool = Field(default=False, env='DB_PRIVATE_IP')

    class Config:
        env_prefix = ''


class MonitoringSettings(BaseSettings):
    """Configuración de monitoreo."""
    
    enabled: bool = Field(default=True, env='ENABLE_MONITORING')
    interval: int = Field(default=60, env='MONITORING_INTERVAL')  # segundos

    class Config:
        env_prefix = ''


class AppSettings(BaseSettings):
    """Configuración general de la aplicación."""
    
    debug: bool = Field(default=False, env='DEBUG')
    environment: str = Field(default='development', env='ENVIRONMENT')

    class Config:
        env_prefix = ''




class DrCecimConfig(BaseSettings):
    """Configuración principal que agrupa todas las configuraciones."""
    
    # Subsecciones de configuración
    google_cloud: GoogleCloudSettings = GoogleCloudSettings()
    openai: OpenAISettings = OpenAISettings()
    processing: ProcessingSettings = ProcessingSettings()
    streamlit: StreamlitSettings = StreamlitSettings()
    server: ServerSettings = ServerSettings()
    logging: LoggingSettings = LoggingSettings()
    monitoring: MonitoringSettings = MonitoringSettings()
    database: DatabaseSettings = DatabaseSettings()
    app: AppSettings = AppSettings()

    class Config:
        env_prefix = ''

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._adjust_development_settings()
        self._create_directories()

    def _adjust_development_settings(self):
        """Ajustar configuraciones específicas para desarrollo."""
        if self.app.environment == 'development':
            # Usar directorios locales para desarrollo
            self.processing.temp_dir = './temp'
            self.processing.processed_dir = './data/processed'
            self.processing.embeddings_dir = './data/embeddings'

    def _create_directories(self):
        """Crear los directorios necesarios para el funcionamiento del sistema."""
        # Solo crear directorios si no estamos en Cloud Functions
        import os
        if os.getenv("LOG_TO_DISK") == "false":
            # En Cloud Functions, solo usar /tmp
            return
            
        dirs_to_create = [
            self.processing.temp_dir,
            self.processing.processed_dir,
            self.processing.embeddings_dir,
        ]
        
        for dir_path in dirs_to_create:
            try:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError) as e:
                # Log pero no fallar en Cloud Functions
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"No se pudo crear directorio {dir_path}: {e}")
                pass

    def validate_config(self):
        """Valida que todas las variables de entorno críticas estén configuradas."""
        missing_vars = []
        
        # Variables críticas para el frontend
        if not self.google_cloud.gcs_bucket_name:
            missing_vars.append('GCS_BUCKET_NAME')
        
        if not self.google_cloud.gcf_project_id:
            missing_vars.append('GCF_PROJECT_ID')
        
        # OpenAI API es opcional para el frontend (solo se usa en Cloud Functions)
        # if not self.openai.openai_api_key:
        #     missing_vars.append('OPENAI_API_KEY')
        
        if missing_vars:
            raise ValueError(f"Las siguientes variables de entorno son requeridas: {', '.join(missing_vars)}")
        
        return True

    def to_dict(self):
        """Convierte la configuración a un diccionario para compatibilidad."""
        return {
            'gcs': {
                'bucket_name': self.google_cloud.gcs_bucket_name,
                'credentials_path': self.google_cloud.gcs_credentials_path,
                'project_id': self.google_cloud.gcf_project_id,
                'region': self.google_cloud.gcf_region,
                'uploads_prefix': self.google_cloud.gcs_uploads_prefix,
                'temp_prefix': self.google_cloud.gcs_temp_prefix,
            },
                 'openai': {
                 'api_key': self.openai.openai_api_key,
                 'embedding_model': self.openai.embedding_model,
                 'api_timeout': self.openai.api_timeout,
                 'max_output_tokens': self.openai.max_output_tokens,
                 'temperature': self.openai.temperature,
                 'top_p': self.openai.top_p,
             },
            'rag': {
                'chunk_size': self.processing.chunk_size,
                'chunk_overlap': self.processing.chunk_overlap,
            },
            'processing': {
                'temp_dir': self.processing.temp_dir,
                'processed_dir': self.processing.processed_dir,
                'embeddings_dir': self.processing.embeddings_dir,
                'device': self.processing.device,
            },
            'streamlit': {
                'title': self.streamlit.title,
                'description': self.streamlit.description,
                'max_file_size_mb': self.streamlit.max_file_size_mb,
                'allowed_file_types': self.streamlit.allowed_file_types,
            },
            'monitoring': {
                'enabled': self.monitoring.enabled,
                'interval': self.monitoring.interval,
            },
            'database': {
                'db_user': self.database.db_user,
                'db_pass': self.database.db_pass,
                'db_name': self.database.db_name,
                'cloud_sql_connection_name': self.database.cloud_sql_connection_name,
                'db_private_ip': self.database.db_private_ip,
            },
            'app': {
                'debug': self.app.debug,
                'environment': self.app.environment,
                'log_level': self.logging.log_level,
                'log_format': self.logging.log_format,
            }
        }


# Instancia global de configuración
config = DrCecimConfig()

# Variables de compatibilidad para código existente
GCS_BUCKET_NAME = config.google_cloud.gcs_bucket_name
GCS_CREDENTIALS_PATH = config.google_cloud.gcs_credentials_path
GCF_REGION = config.google_cloud.gcf_region
GCF_PROJECT_ID = config.google_cloud.gcf_project_id

# Variables de base de datos
DB_USER = config.database.db_user
DB_PASS = config.database.db_pass
DB_NAME = config.database.db_name
CLOUD_SQL_CONNECTION_NAME = config.database.cloud_sql_connection_name
DB_PRIVATE_IP = config.database.db_private_ip

OPENAI_API_KEY = config.openai.openai_api_key
EMBEDDING_MODEL = config.openai.embedding_model
API_TIMEOUT = config.openai.api_timeout
MAX_OUTPUT_TOKENS = config.openai.max_output_tokens
TEMPERATURE = config.openai.temperature
TOP_P = config.openai.top_p

CHUNK_SIZE = config.processing.chunk_size
CHUNK_OVERLAP = config.processing.chunk_overlap
TEMP_DIR = config.processing.temp_dir
PROCESSED_DIR = config.processing.processed_dir
EMBEDDINGS_DIR = config.processing.embeddings_dir
DEVICE = config.processing.device

HOST = config.server.host
PORT = config.server.port

STREAMLIT_TITLE = config.streamlit.title
STREAMLIT_DESCRIPTION = config.streamlit.description
MAX_FILE_SIZE_MB = config.streamlit.max_file_size_mb
ALLOWED_FILE_TYPES = config.streamlit.allowed_file_types

LOG_LEVEL = config.logging.log_level
LOG_FORMAT = config.logging.log_format

ENABLE_MONITORING = config.monitoring.enabled
MONITORING_INTERVAL = config.monitoring.interval

DEBUG = config.app.debug
ENVIRONMENT = config.app.environment

# GCS constants optimizados
GCS_UPLOADS_PREFIX = config.google_cloud.gcs_uploads_prefix
GCS_TEMP_PREFIX = config.google_cloud.gcs_temp_prefix

# DEPRECATED: Migrando todo a PostgreSQL
# GCS_EMBEDDINGS_PREFIX = 'embeddings/'  # NO USAR - Todo en PostgreSQL
# GCS_METADATA_PREFIX = 'metadata/'      # NO USAR - Todo en PostgreSQL  
# GCS_PROCESSED_PREFIX = 'processed/'    # NO USAR - Todo en PostgreSQL

GCS_METADATA_NAME = config.google_cloud.gcs_metadata_name
GCS_METADATA_SUMMARY_NAME = config.google_cloud.gcs_metadata_summary_name
GCS_CONFIG_NAME = config.google_cloud.gcs_config_name

# Diccionario de configuración para compatibilidad
CONFIG = config.to_dict()

# Funciones de compatibilidad
def validate_config():
    """Función de compatibilidad para validar configuración."""
    return config.validate_config()

def create_directories():
    """Función de compatibilidad para crear directorios."""
    return config._create_directories()

# Ejecutar validación al importar
if __name__ != '__main__':
    validate_config() 