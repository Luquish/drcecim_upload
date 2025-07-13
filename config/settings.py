"""
Configuración central para el sistema DrCecim Upload.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env
load_dotenv()

# =============================================================================
# CONFIGURACIÓN DE GOOGLE CLOUD
# =============================================================================

# Google Cloud Storage
GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'drcecim-chatbot-storage')
GCS_CREDENTIALS_PATH = os.getenv('GCS_CREDENTIALS_PATH')  # Ruta al archivo de credenciales

# Google Cloud Functions
GCF_REGION = os.getenv('GCF_REGION', 'us-central1')
GCF_PROJECT_ID = os.getenv('GCF_PROJECT_ID')

# =============================================================================
# CONFIGURACIÓN DE OPENAI
# =============================================================================

# API Keys y Modelos
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PRIMARY_MODEL = os.getenv('PRIMARY_MODEL', 'gpt-4o-mini')
FALLBACK_MODEL = os.getenv('FALLBACK_MODEL', 'gpt-4.1-nano')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')

# Parámetros de generación
TEMPERATURE = float(os.getenv('TEMPERATURE', 0.7))
TOP_P = float(os.getenv('TOP_P', 0.9))
TOP_K = int(os.getenv('TOP_K', 50))
MAX_OUTPUT_TOKENS = int(os.getenv('MAX_OUTPUT_TOKENS', 300))
API_TIMEOUT = int(os.getenv('API_TIMEOUT', 30))

# =============================================================================
# CONFIGURACIÓN DE RAG
# =============================================================================

# Parámetros de RAG
RAG_NUM_CHUNKS = int(os.getenv('RAG_NUM_CHUNKS', 3))
SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', 0.3))

# Configuración de chunking
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', 250))
CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', 50))

# =============================================================================
# CONFIGURACIÓN DE PROCESAMIENTO
# =============================================================================

# Directorio temporal para procesamiento
TEMP_DIR = os.getenv('TEMP_DIR', '/tmp/drcecim_processing')
PROCESSED_DIR = os.getenv('PROCESSED_DIR', 'data/processed')
EMBEDDINGS_DIR = os.getenv('EMBEDDINGS_DIR', 'data/embeddings')

# Configuración del dispositivo (auto, cuda, cpu, mps)
DEVICE = os.getenv('DEVICE', 'cpu')

# Configuración del servidor
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 8080))

# =============================================================================
# CONFIGURACIÓN DE STREAMLIT
# =============================================================================

# Configuración de la aplicación Streamlit
STREAMLIT_TITLE = os.getenv('STREAMLIT_TITLE', 'DrCecim - Carga de Documentos')
STREAMLIT_DESCRIPTION = os.getenv('STREAMLIT_DESCRIPTION', 'Sistema de carga y procesamiento de documentos PDF para el chatbot DrCecim')

# Límites de archivo
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', 50))
ALLOWED_FILE_TYPES = ['pdf']

# =============================================================================
# CONFIGURACIÓN DE LOGGING
# =============================================================================

# Configuración de logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# =============================================================================
# VALIDACIÓN DE CONFIGURACIÓN
# =============================================================================

def validate_config():
    """
    Valida que todas las variables de entorno críticas estén configuradas.
    """
    missing_vars = []
    
    # Variables críticas
    if not OPENAI_API_KEY:
        missing_vars.append('OPENAI_API_KEY')
    
    if not GCS_BUCKET_NAME:
        missing_vars.append('GCS_BUCKET_NAME')
    
    if not GCF_PROJECT_ID:
        missing_vars.append('GCF_PROJECT_ID')
    
    if missing_vars:
        raise ValueError(f"Las siguientes variables de entorno son requeridas: {', '.join(missing_vars)}")
    
    return True

# =============================================================================
# CONFIGURACIÓN DE PATHS
# =============================================================================

# Crear directorios necesarios
def create_directories():
    """
    Crea los directorios necesarios para el funcionamiento del sistema.
    """
    dirs_to_create = [
        TEMP_DIR,
        PROCESSED_DIR,
        EMBEDDINGS_DIR,
    ]
    
    for dir_path in dirs_to_create:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

# =============================================================================
# CONFIGURACIÓN DE GOOGLE CLOUD STORAGE
# =============================================================================

# Estructura de carpetas en GCS
GCS_EMBEDDINGS_PREFIX = 'embeddings/'
GCS_METADATA_PREFIX = 'metadata/'
GCS_PROCESSED_PREFIX = 'processed/'
GCS_TEMP_PREFIX = 'temp/'

# Nombres de archivos en GCS
GCS_FAISS_INDEX_NAME = 'faiss_index.bin'
GCS_METADATA_NAME = 'metadata.csv'
GCS_METADATA_SUMMARY_NAME = 'metadata_summary.csv'
GCS_CONFIG_NAME = 'config.json'

# =============================================================================
# CONFIGURACIÓN DE LOGGING
# =============================================================================

# Configuración de logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# =============================================================================
# CONFIGURACIÓN DE MONITOREO
# =============================================================================

# Configuración de monitoreo y alertas
ENABLE_MONITORING = os.getenv('ENABLE_MONITORING', 'True').lower() == 'true'
MONITORING_INTERVAL = int(os.getenv('MONITORING_INTERVAL', 60))  # segundos

# =============================================================================
# CONFIGURACIÓN DE DESARROLLO
# =============================================================================

# Modo de desarrollo
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

# Configuración específica para desarrollo
if ENVIRONMENT == 'development':
    # Usar directorios locales para desarrollo
    TEMP_DIR = './temp'
    PROCESSED_DIR = './data/processed'
    EMBEDDINGS_DIR = './data/embeddings'

# =============================================================================
# EXPORT DE CONFIGURACIÓN
# =============================================================================

# Diccionario con toda la configuración para fácil acceso
CONFIG = {
    'gcs': {
        'bucket_name': GCS_BUCKET_NAME,
        'credentials_path': GCS_CREDENTIALS_PATH,
        'project_id': GCF_PROJECT_ID,
        'region': GCF_REGION,
        'embeddings_prefix': GCS_EMBEDDINGS_PREFIX,
        'metadata_prefix': GCS_METADATA_PREFIX,
        'processed_prefix': GCS_PROCESSED_PREFIX,
        'temp_prefix': GCS_TEMP_PREFIX,
    },
    'openai': {
        'api_key': OPENAI_API_KEY,
        'primary_model': PRIMARY_MODEL,
        'fallback_model': FALLBACK_MODEL,
        'embedding_model': EMBEDDING_MODEL,
        'temperature': TEMPERATURE,
        'top_p': TOP_P,
        'top_k': TOP_K,
        'max_output_tokens': MAX_OUTPUT_TOKENS,
        'api_timeout': API_TIMEOUT,
    },
    'rag': {
        'num_chunks': RAG_NUM_CHUNKS,
        'similarity_threshold': SIMILARITY_THRESHOLD,
        'chunk_size': CHUNK_SIZE,
        'chunk_overlap': CHUNK_OVERLAP,
    },
    'processing': {
        'temp_dir': TEMP_DIR,
        'processed_dir': PROCESSED_DIR,
        'embeddings_dir': EMBEDDINGS_DIR,
        'device': DEVICE,
    },
    'streamlit': {
        'title': STREAMLIT_TITLE,
        'description': STREAMLIT_DESCRIPTION,
        'max_file_size_mb': MAX_FILE_SIZE_MB,
        'allowed_file_types': ALLOWED_FILE_TYPES,
    },
    'monitoring': {
        'enabled': ENABLE_MONITORING,
        'interval': MONITORING_INTERVAL,
    },
    'app': {
        'debug': DEBUG,
        'environment': ENVIRONMENT,
        'log_level': LOG_LEVEL,
        'log_format': LOG_FORMAT,
    }
}

# Ejecutar validación al importar
if __name__ != '__main__':
    validate_config()
    if ENVIRONMENT == 'development':
        create_directories() 