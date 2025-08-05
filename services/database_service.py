"""
Servicio de base de datos para la aplicación Streamlit de DrCecim Upload.
Conecta directamente a Cloud SQL PostgreSQL para mostrar datos en tiempo real.
"""
import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Importar configuración centralizada
from config.settings import config
from config.logging_config import get_streamlit_logger

logger = get_streamlit_logger(__name__)


class StreamlitDatabaseService:
    """
    Servicio de base de datos optimizado para Streamlit.
    Conecta directamente a Cloud SQL PostgreSQL para datos en tiempo real.
    """
    
    def __init__(self):
        """Inicializa el servicio de base de datos."""
        self.conn = None
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Inicializa la conexión a Cloud SQL PostgreSQL usando Streamlit secrets."""
        try:
            logger.info("🔄 Iniciando conexión a Cloud SQL...")
            
            # Obtener configuración desde Streamlit secrets
            db_config = st.secrets["connections"]["postgresql"]
            
            logger.info(f"Configuración: {db_config['username']}@{db_config['host']}:{db_config['port']}")
            
            # Crear conexión usando la configuración de Streamlit secrets
            self.conn = psycopg2.connect(
                host=db_config['host'],
                port=db_config['port'],
                database=db_config['database'],
                user=db_config['username'],
                password=db_config['password'],
                cursor_factory=RealDictCursor
            )
            logger.info("✅ Conexión a Cloud SQL inicializada exitosamente")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando conexión a Cloud SQL: {str(e)}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            st.error(f"Error de conexión a la base de datos: {str(e)}")
            self.conn = None
    
    def get_documents_history(self) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de documentos desde Cloud SQL en tiempo real.
        
        Returns:
            List[Dict]: Lista de documentos con su información completa
        """
        logger.info("🔄 Obteniendo documentos desde Cloud SQL...")
        
        if not self.conn:
            logger.error("❌ No hay conexión a la base de datos")
            st.error("No hay conexión a la base de datos")
            return []
        
        try:
            # Query para obtener documentos ordenados por fecha de creación
            query = """
                SELECT 
                    document_id,
                    filename,
                    file_size,
                    upload_date,
                    processing_status,
                    num_chunks,
                    created_at,
                    updated_at,
                    chunk_count,
                    total_chars,
                    total_words,
                    processed_at,
                    embedding_model,
                    vector_dimension,
                    original_filename
                FROM documents 
                ORDER BY created_at DESC
            """
            
            # Ejecutar query directamente con psycopg2
            with self.conn.cursor() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
            
            # Convertir resultados a lista de diccionarios
            documents = []
            for row in results:
                doc = {
                    'document_id': row['document_id'],
                    'filename': row['filename'],
                    'file_size': row['file_size'],
                    'upload_date': row['upload_date'],
                    'processing_status': row['processing_status'],
                    'num_chunks': row['num_chunks'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'chunk_count': row['chunk_count'],
                    'total_chars': row['total_chars'],
                    'total_words': row['total_words'],
                    'processed_at': row['processed_at'],
                    'embedding_model': row['embedding_model'],
                    'vector_dimension': row['vector_dimension'],
                    'original_filename': row['original_filename']
                }
                documents.append(doc)
            
            logger.info(f"✅ Obtenidos {len(documents)} documentos desde Cloud SQL")
            return documents
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo documentos desde Cloud SQL: {str(e)}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            st.error(f"Error cargando documentos: {str(e)}")
            return []
    

    
    def get_documents_summary(self) -> Dict[str, Any]:
        """
        Obtiene un resumen estadístico de los documentos desde Cloud SQL.
        
        Returns:
            Dict: Resumen con estadísticas relevantes para empleadores
        """
        logger.info("🔄 Obteniendo resumen de documentos desde Cloud SQL...")
        
        if not self.conn:
            logger.error("❌ No hay conexión a la base de datos")
            return {
                'total_documents': 0,
                'completed_documents': 0,
                'processing_documents': 0,
                'error_documents': 0
            }
        
        try:
            # Query para obtener estadísticas básicas
            query = """
                SELECT 
                    COUNT(*) as total_documents,
                    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed_documents,
                    COUNT(CASE WHEN processing_status = 'processing' THEN 1 END) as processing_documents,
                    COUNT(CASE WHEN processing_status = 'error' THEN 1 END) as error_documents
                FROM documents
            """
            
            # Ejecutar query directamente con psycopg2
            with self.conn.cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchone()
            
            if result:
                return {
                    'total_documents': int(result['total_documents']),
                    'completed_documents': int(result['completed_documents']),
                    'processing_documents': int(result['processing_documents']),
                    'error_documents': int(result['error_documents'])
                }
            
            logger.info("✅ Resumen obtenido exitosamente")
            return {
                'total_documents': 0,
                'completed_documents': 0,
                'processing_documents': 0,
                'error_documents': 0
            }
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo resumen desde Cloud SQL: {str(e)}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            return {
                'total_documents': 0,
                'completed_documents': 0,
                'processing_documents': 0,
                'error_documents': 0
            }
    
    def get_recent_documents(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene los documentos más recientes.
        
        Args:
            limit (int): Número máximo de documentos a retornar
            
        Returns:
            List[Dict]: Lista de documentos recientes
        """
        if not self.conn:
            return []
        
        try:
            query = """
                SELECT 
                    document_id,
                    filename,
                    file_size,
                    upload_date,
                    processing_status,
                    num_chunks,
                    created_at
                FROM documents 
                ORDER BY created_at DESC
                LIMIT :limit
            """
            
            df = self.conn.query(query, params={"limit": limit}, ttl="2m")
            
            documents = []
            for _, row in df.iterrows():
                doc = {
                    'document_id': row.document_id,
                    'filename': row.filename,
                    'file_size': row.file_size,
                    'upload_date': row.upload_date,
                    'processing_status': row.processing_status,
                    'num_chunks': row.num_chunks,
                    'created_at': row.created_at
                }
                documents.append(doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"Error obteniendo documentos recientes: {str(e)}")
            return []
    
    def test_connection(self) -> bool:
        """
        Prueba la conexión a Cloud SQL.
        
        Returns:
            bool: True si la conexión es exitosa
        """
        logger.info("🔍 Probando conexión a Cloud SQL...")
        
        if not self.conn:
            logger.error("❌ No hay conexión disponible")
            return False
        
        try:
            # Query simple para probar la conexión
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
            
            success = result is not None
            logger.info(f"✅ Prueba de conexión a Cloud SQL: {'EXITOSA' if success else 'FALLIDA'}")
            return success
        except Exception as e:
            logger.error(f"❌ Error en prueba de conexión a Cloud SQL: {str(e)}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            return False


# Instancia global del servicio
@st.cache_resource
def get_database_service():
    """Obtiene una instancia del servicio de base de datos con caché."""
    return StreamlitDatabaseService() 