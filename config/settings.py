"""
Configuración específica para la aplicación Streamlit.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class StreamlitSettings(BaseSettings):
    """
    Configuración específica para la aplicación Streamlit.
    """
    
    # =============================================================================
    # CONFIGURACIÓN DE STREAMLIT
    # =============================================================================
    
    # Configuración de la aplicación
    STREAMLIT_TITLE: str = Field(
        default="DrCecim - Carga de Documentos",
        description="Título de la aplicación Streamlit"
    )
    STREAMLIT_DESCRIPTION: str = Field(
        default="Sistema de carga y procesamiento de documentos PDF para el chatbot DrCecim",
        description="Descripción de la aplicación"
    )
    
    # Límites de archivo
    MAX_FILE_SIZE_MB: int = Field(
        default=50,
        description="Tamaño máximo de archivo en MB"
    )
    
    # Configuración de la interfaz
    PAGE_ICON: str = Field(
        default="📚",
        description="Icono de la página"
    )
    LAYOUT: str = Field(
        default="wide",
        description="Layout de la aplicación"
    )
    
    # =============================================================================
    # CONFIGURACIÓN DE GOOGLE CLOUD
    # =============================================================================
    
    # Google Cloud Storage
    GCS_BUCKET_NAME: str = Field(
        default="drcecim-chatbot-storage",
        description="Nombre del bucket de Google Cloud Storage"
    )
    GCS_CREDENTIALS_PATH: Optional[str] = Field(
        default=None,
        description="Ruta a las credenciales de GCS"
    )
    
    # Prefijos de GCS
    GCS_EMBEDDINGS_PREFIX: str = Field(
        default="embeddings/",
        description="Prefijo para archivos de embeddings en GCS"
    )
    GCS_METADATA_PREFIX: str = Field(
        default="metadata/",
        description="Prefijo para archivos de metadatos en GCS"
    )
    GCS_PROCESSED_PREFIX: str = Field(
        default="processed/",
        description="Prefijo para archivos procesados en GCS"
    )
    GCS_TEMP_PREFIX: str = Field(
        default="temp/",
        description="Prefijo para archivos temporales en GCS"
    )
    
    # Nombres de archivos en GCS
    GCS_FAISS_INDEX_NAME: str = Field(
        default="faiss_index.bin",
        description="Nombre del archivo de índice FAISS en GCS"
    )
    GCS_METADATA_NAME: str = Field(
        default="metadata.csv",
        description="Nombre del archivo de metadatos en GCS"
    )
    GCS_METADATA_SUMMARY_NAME: str = Field(
        default="metadata_summary.csv",
        description="Nombre del archivo de resumen de metadatos en GCS"
    )
    GCS_CONFIG_NAME: str = Field(
        default="config.json",
        description="Nombre del archivo de configuración en GCS"
    )
    
    # Google Cloud Functions
    GCF_REGION: str = Field(
        default="southamerica-east1",
        description="Región de Google Cloud Functions"
    )
    GCF_PROJECT_ID: str = Field(
        default="drcecim-465823",
        description="ID del proyecto de Google Cloud"
    )
    
    # =============================================================================
    # CONFIGURACIÓN DE OPENAI
    # =============================================================================
    
    # API Keys y Modelos
    OPENAI_API_KEY: str = Field(
        description="API Key de OpenAI"
    )
    PRIMARY_MODEL: str = Field(
        default="gpt-4o-mini",
        description="Modelo principal de OpenAI"
    )
    FALLBACK_MODEL: str = Field(
        default="gpt-4.1-nano",
        description="Modelo de respaldo"
    )
    EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="Modelo de embeddings"
    )
    
    # Parámetros de generación
    TEMPERATURE: float = Field(
        default=0.7,
        description="Temperatura para generación de texto"
    )
    TOP_P: float = Field(
        default=0.9,
        description="Top-p para generación de texto"
    )
    TOP_K: int = Field(
        default=50,
        description="Top-k para generación de texto"
    )
    MAX_OUTPUT_TOKENS: int = Field(
        default=300,
        description="Número máximo de tokens de salida"
    )
    API_TIMEOUT: int = Field(
        default=30,
        description="Timeout para llamadas a la API"
    )
    
    # =============================================================================
    # CONFIGURACIÓN DE RAG
    # =============================================================================
    
    # Parámetros de RAG
    RAG_NUM_CHUNKS: int = Field(
        default=3,
        description="Número de chunks para RAG"
    )
    SIMILARITY_THRESHOLD: float = Field(
        default=0.3,
        description="Umbral de similitud para RAG"
    )
    
    # Configuración de chunking
    CHUNK_SIZE: int = Field(
        default=250,
        description="Tamaño de chunks"
    )
    CHUNK_OVERLAP: int = Field(
        default=50,
        description="Solapamiento de chunks"
    )
    
    # =============================================================================
    # CONFIGURACIÓN DE PROCESAMIENTO
    # =============================================================================
    
    # Directorio temporal para procesamiento
    TEMP_DIR: str = Field(
        default="/tmp/drcecim_processing",
        description="Directorio temporal para procesamiento"
    )
    PROCESSED_DIR: str = Field(
        default="data/processed",
        description="Directorio de archivos procesados"
    )
    EMBEDDINGS_DIR: str = Field(
        default="data/embeddings",
        description="Directorio de embeddings"
    )
    
    # Configuración del dispositivo
    DEVICE: str = Field(
        default="cpu",
        description="Dispositivo para procesamiento (auto, cuda, cpu, mps)"
    )
    
    # =============================================================================
    # CONFIGURACIÓN DE LOGGING
    # =============================================================================
    
    # Configuración de logging
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Nivel de logging"
    )
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Formato de logging"
    )
    
    # =============================================================================
    # CONFIGURACIÓN DE MONITOREO
    # =============================================================================
    
    # Configuración de monitoreo y alertas
    ENABLE_MONITORING: bool = Field(
        default=True,
        description="Habilitar monitoreo"
    )
    MONITORING_INTERVAL: int = Field(
        default=60,
        description="Intervalo de monitoreo en segundos"
    )
    
    # =============================================================================
    # CONFIGURACIÓN DE DESARROLLO
    # =============================================================================
    
    # Modo de desarrollo
    DEBUG: bool = Field(
        default=False,
        description="Modo debug"
    )
    ENVIRONMENT: str = Field(
        default="development",
        description="Entorno de ejecución"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Instancia global de configuración
settings = StreamlitSettings()

# Variables de entorno para compatibilidad
GCS_BUCKET_NAME = settings.GCS_BUCKET_NAME
GCS_CREDENTIALS_PATH = settings.GCS_CREDENTIALS_PATH
GCS_EMBEDDINGS_PREFIX = settings.GCS_EMBEDDINGS_PREFIX
GCS_METADATA_PREFIX = settings.GCS_METADATA_PREFIX
GCS_PROCESSED_PREFIX = settings.GCS_PROCESSED_PREFIX
GCS_TEMP_PREFIX = settings.GCS_TEMP_PREFIX
GCS_FAISS_INDEX_NAME = settings.GCS_FAISS_INDEX_NAME
GCS_METADATA_NAME = settings.GCS_METADATA_NAME
GCS_METADATA_SUMMARY_NAME = settings.GCS_METADATA_SUMMARY_NAME
GCS_CONFIG_NAME = settings.GCS_CONFIG_NAME
GCF_REGION = settings.GCF_REGION
GCF_PROJECT_ID = settings.GCF_PROJECT_ID
OPENAI_API_KEY = settings.OPENAI_API_KEY
PRIMARY_MODEL = settings.PRIMARY_MODEL
FALLBACK_MODEL = settings.FALLBACK_MODEL
EMBEDDING_MODEL = settings.EMBEDDING_MODEL
TEMPERATURE = settings.TEMPERATURE
TOP_P = settings.TOP_P
TOP_K = settings.TOP_K
MAX_OUTPUT_TOKENS = settings.MAX_OUTPUT_TOKENS
API_TIMEOUT = settings.API_TIMEOUT
RAG_NUM_CHUNKS = settings.RAG_NUM_CHUNKS
SIMILARITY_THRESHOLD = settings.SIMILARITY_THRESHOLD
CHUNK_SIZE = settings.CHUNK_SIZE
CHUNK_OVERLAP = settings.CHUNK_OVERLAP
TEMP_DIR = settings.TEMP_DIR
PROCESSED_DIR = settings.PROCESSED_DIR
EMBEDDINGS_DIR = settings.EMBEDDINGS_DIR
DEVICE = settings.DEVICE
LOG_LEVEL = settings.LOG_LEVEL
LOG_FORMAT = settings.LOG_FORMAT
ENABLE_MONITORING = settings.ENABLE_MONITORING
MONITORING_INTERVAL = settings.MONITORING_INTERVAL
DEBUG = settings.DEBUG
ENVIRONMENT = settings.ENVIRONMENT
STREAMLIT_TITLE = settings.STREAMLIT_TITLE
STREAMLIT_DESCRIPTION = settings.STREAMLIT_DESCRIPTION
MAX_FILE_SIZE_MB = settings.MAX_FILE_SIZE_MB
PAGE_ICON = settings.PAGE_ICON
LAYOUT = settings.LAYOUT
