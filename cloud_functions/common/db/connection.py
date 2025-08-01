"""
Conexión a Cloud SQL PostgreSQL usando Cloud SQL Python Connector.
"""
import os
import logging
from google.cloud.sql.connector import Connector
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Variable global para el connector
_connector = None

def get_connector():
    """
    Obtiene una instancia singleton del Cloud SQL Connector.
    
    Returns:
        Connector: Instancia del connector
    """
    global _connector
    if _connector is None:
        _connector = Connector()
        logger.info("Cloud SQL Connector inicializado")
    return _connector

def get_connection():
    """
    Obtiene una conexión directa a PostgreSQL.
    
    Returns:
        Connection: Conexión a la base de datos
    """
    connector = get_connector()
    
    try:
        conn = connector.connect(
            os.getenv("CLOUD_SQL_CONNECTION_NAME"),
            "pg8000",
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            db=os.getenv("DB_NAME"),
        )
        logger.info("Conexión a Cloud SQL establecida")
        return conn
    except Exception as e:
        logger.error(f"Error al conectar a Cloud SQL: {str(e)}")
        raise

def get_engine():
    """
    Obtiene un engine de SQLAlchemy para Cloud SQL.
    
    Returns:
        Engine: Engine de SQLAlchemy
    """
    connector = get_connector()
    
    def getconn():
        return connector.connect(
            os.getenv("CLOUD_SQL_CONNECTION_NAME"),
            "pg8000",
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            db=os.getenv("DB_NAME"),
        )
    
    engine = create_engine(
        "postgresql+pg8000://",
        creator=getconn,
        pool_size=5,
        max_overflow=2,
        pool_timeout=30,
        pool_recycle=3600,
        echo=False  # Set to True for debugging SQL queries
    )
    
    logger.info("Engine de SQLAlchemy creado para Cloud SQL")
    return engine

def get_session():
    """
    Obtiene una sesión de SQLAlchemy.
    
    Returns:
        Session: Sesión de SQLAlchemy
    """
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def test_connection():
    """
    Prueba la conexión a la base de datos.
    
    Returns:
        bool: True si la conexión es exitosa
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(sqlalchemy.text("SELECT 1"))
            logger.info("Conexión a Cloud SQL probada exitosamente")
            return True
    except Exception as e:
        logger.error(f"Error al probar conexión: {str(e)}")
        return False

def close_connector():
    """
    Cierra el connector de Cloud SQL.
    """
    global _connector
    if _connector:
        _connector.close()
        _connector = None
        logger.info("Cloud SQL Connector cerrado")

# Context manager para conexiones
class DatabaseConnection:
    """Context manager para conexiones a la base de datos."""
    
    def __init__(self):
        self.engine = None
        self.connection = None
    
    def __enter__(self):
        self.engine = get_engine()
        self.connection = self.engine.connect()
        return self.connection
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()
        if self.engine:
            self.engine.dispose()

# Función de conveniencia para usar con context manager
def with_connection():
    """
    Función de conveniencia para usar con context manager.
    
    Returns:
        DatabaseConnection: Context manager para conexiones
    """
    return DatabaseConnection()
