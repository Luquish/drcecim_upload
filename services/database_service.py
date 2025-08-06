"""
Servicio de base de datos para la aplicación Streamlit de DrCecim Upload.
Conecta directamente a Cloud SQL PostgreSQL para mostrar datos en tiempo real.
"""
import streamlit as st
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import time
from functools import wraps

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
        self.last_connection_time = 0
        # Configuraciones desde variables de entorno o valores por defecto
        self.connection_timeout = int(st.secrets.get('DB_CONNECTION_TIMEOUT', 3600))  # 1 hora por defecto
        self.max_retries = int(st.secrets.get('DB_MAX_RETRIES', 3))
        self.keepalives_idle = int(st.secrets.get('DB_KEEPALIVES_IDLE', 600))  # 10 minutos
        self.keepalives_interval = int(st.secrets.get('DB_KEEPALIVES_INTERVAL', 30))  # 30 segundos
        self.keepalives_count = int(st.secrets.get('DB_KEEPALIVES_COUNT', 3))  # 3 intentos
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Inicializa la conexión a Cloud SQL PostgreSQL usando Streamlit secrets."""
        try:
            logger.info("🔄 Iniciando conexión a Cloud SQL...")
            
            # Obtener configuración desde Streamlit secrets (variables de entorno)
            db_host = st.secrets.get('DB_HOST', '34.95.166.187')
            db_port = st.secrets.get('DB_PORT', 5432)
            db_name = st.secrets.get('DB_NAME', 'ragdb')
            db_user = st.secrets.get('DB_USER', 'raguser')
            db_pass = st.secrets.get('DB_PASS', 'DrCecim2024@')
            
            logger.info(f"Configuración: {db_user}@{db_host}:{db_port}")
            
            # Crear conexión usando la configuración de Streamlit secrets con timeouts optimizados
            self.conn = psycopg2.connect(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_pass,
                cursor_factory=RealDictCursor,
                connect_timeout=10,  # Timeout de conexión de 10 segundos
                keepalives_idle=self.keepalives_idle,  # Enviar keepalive configurado
                keepalives_interval=self.keepalives_interval,  # Intervalo entre keepalives configurado
                keepalives_count=self.keepalives_count  # Número de keepalives configurado
            )
            self.last_connection_time = time.time()
            logger.info("✅ Conexión a Cloud SQL inicializada exitosamente")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando conexión a Cloud SQL: {str(e)}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            st.error(f"Error de conexión a la base de datos: {str(e)}")
            self.conn = None
    
    def _is_connection_valid(self) -> bool:
        """
        Verifica si la conexión está activa y válida.
        
        Returns:
            bool: True si la conexión es válida
        """
        if not self.conn:
            return False
        
        try:
            # Verificar si la conexión está cerrada
            if self.conn.closed != 0:
                return False
            
            # Verificar timeout manual
            current_time = time.time()
            if (current_time - self.last_connection_time) > self.connection_timeout:
                logger.warning("🕒 Conexión expirada por timeout, necesita reconexión")
                return False
            
            # Probar con un query simple
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            return True
            
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            logger.warning(f"⚠️ Conexión inválida detectada: {str(e)}")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Error verificando conexión: {str(e)}")
            return False
    
    def _ensure_connection(self) -> bool:
        """
        Asegura que hay una conexión válida, reconectando si es necesario.
        
        Returns:
            bool: True si se logró establecer una conexión válida
        """
        if self._is_connection_valid():
            return True
        
        logger.info("🔄 Reconectando a Cloud SQL...")
        
        # Cerrar conexión existente si la hay
        if self.conn:
            try:
                self.conn.close()
            except:
                pass
            self.conn = None
        
        # Intentar reconectar con reintentos
        for attempt in range(self.max_retries):
            try:
                self._initialize_connection()
                if self.conn:
                    logger.info(f"✅ Reconexión exitosa en intento {attempt + 1}")
                    return True
            except Exception as e:
                logger.warning(f"⚠️ Intento de reconexión {attempt + 1} falló: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Backoff exponencial
        
        logger.error("❌ No se pudo reconectar después de múltiples intentos")
        return False
    
    def _with_retry(func):
        """Decorador para ejecutar funciones con reintentos automáticos."""
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not self._ensure_connection():
                logger.error("❌ No se pudo establecer conexión a la base de datos")
                return None if 'get_' in func.__name__ else False
            
            try:
                return func(self, *args, **kwargs)
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                logger.warning(f"⚠️ Error de conexión detectado, reintentando: {str(e)}")
                
                # Intentar reconectar y ejecutar de nuevo
                if self._ensure_connection():
                    try:
                        return func(self, *args, **kwargs)
                    except Exception as retry_e:
                        logger.error(f"❌ Error en reintento: {str(retry_e)}")
                
                return None if 'get_' in func.__name__ else False
        return wrapper
    
    @_with_retry
    def get_documents_history(self) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de documentos desde Cloud SQL en tiempo real.
        
        Returns:
            List[Dict]: Lista de documentos con su información completa
        """
        logger.info("🔄 Obteniendo documentos desde Cloud SQL...")
        
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
    

    
    @_with_retry
    def get_documents_summary(self) -> Dict[str, Any]:
        """
        Obtiene un resumen estadístico de los documentos desde Cloud SQL.
        
        Returns:
            Dict: Resumen con estadísticas relevantes para empleadores
        """
        logger.info("🔄 Obteniendo resumen de documentos desde Cloud SQL...")
        
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
        """
        Prueba la conexión usando el método _is_connection_valid() que ya maneja reconexión.
        """
        logger.info("🔍 Probando conexión a Cloud SQL...")
        
        # Usar el método de validación que incluye reconexión automática
        is_valid = self._is_connection_valid()
        
        if not is_valid:
            # Intentar reconectar si la validación falló
            is_valid = self._ensure_connection()
        
        logger.info(f"✅ Prueba de conexión a Cloud SQL: {'EXITOSA' if is_valid else 'FALLIDA'}")
        return is_valid


# Instancia global del servicio
@st.cache_resource
def get_database_service():
    """Obtiene una instancia del servicio de base de datos con caché."""
    return StreamlitDatabaseService() 