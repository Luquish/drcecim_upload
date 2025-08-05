"""
Modelos de SQLAlchemy para la base de datos de embeddings.
"""
import logging
from datetime import datetime
from sqlalchemy import Table, Column, BigInteger, Text, DateTime, MetaData, Integer, String
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector

logger = logging.getLogger(__name__)

# Crear base declarativa
Base = declarative_base()

# Metadata para las tablas
db_metadata = MetaData()

class EmbeddingModel(Base):
    """
    Modelo para la tabla de embeddings usando pgvector.
    """
    __tablename__ = "embeddings"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    document_id = Column(Text, nullable=False, index=True)
    chunk_id = Column(Text, nullable=False, index=True)
    text_content = Column(Text, nullable=False)
    embedding_vector = Column(Vector(1536), nullable=False)  # OpenAI text-embedding-3-small
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<EmbeddingModel(id={self.id}, document_id='{self.document_id}', chunk_id='{self.chunk_id}')>"

class DocumentModel(Base):
    """
    Modelo para la tabla de documentos (opcional).
    """
    __tablename__ = "documents"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    document_id = Column(Text, unique=True, nullable=False, index=True)
    filename = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    processing_status = Column(Text, default='pending', nullable=False)
    num_chunks = Column(BigInteger, default=0, nullable=False)
    # Nuevas columnas extraídas del JSON document_metadata
    chunk_count = Column(Integer, nullable=True)
    total_chars = Column(Integer, nullable=True)
    total_words = Column(Integer, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    embedding_model = Column(String(100), nullable=True)
    vector_dimension = Column(Integer, nullable=True)
    original_filename = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<DocumentModel(id={self.id}, document_id='{self.document_id}', filename='{self.filename}')>"

# Tabla de embeddings usando Table (alternativa a declarative)
embeddings_table = Table(
    "embeddings",
    db_metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("document_id", Text, nullable=False, index=True),
    Column("chunk_id", Text, nullable=False, index=True),
    Column("text_content", Text, nullable=False),
    Column("embedding_vector", Vector(1536), nullable=False),
    Column("created_at", DateTime, default=datetime.utcnow, nullable=False),
    Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
)

# Tabla de documentos usando Table (alternativa a declarative)
documents_table = Table(
    "documents",
    db_metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("document_id", Text, unique=True, nullable=False, index=True),
    Column("filename", Text, nullable=False),
    Column("file_size", BigInteger, nullable=True),
    Column("upload_date", DateTime, default=datetime.utcnow, nullable=False),
    Column("processing_status", Text, default='pending', nullable=False),
    Column("num_chunks", BigInteger, default=0, nullable=False),
    # Nuevas columnas extraídas del JSON document_metadata
    Column("chunk_count", Integer, nullable=True),
    Column("total_chars", Integer, nullable=True),
    Column("total_words", Integer, nullable=True),
    Column("processed_at", DateTime, nullable=True),
    Column("embedding_model", String(100), nullable=True),
    Column("vector_dimension", Integer, nullable=True),
    Column("original_filename", Text, nullable=True),
    Column("created_at", DateTime, default=datetime.utcnow, nullable=False),
    Column("updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
)

def create_tables(engine):
    """
    Crea todas las tablas en la base de datos.
    
    Args:
        engine: Engine de SQLAlchemy
    """
    try:
        # Crear extensión pgvector si no existe
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
            logger.info("Extensión pgvector verificada/creada")
        
        # Crear tablas
        Base.metadata.create_all(engine)
        logger.info("Tablas creadas exitosamente")
        
    except Exception as e:
        logger.error(f"Error al crear tablas: {str(e)}")
        raise

def drop_tables(engine):
    """
    Elimina todas las tablas de la base de datos.
    
    Args:
        engine: Engine de SQLAlchemy
    """
    try:
        Base.metadata.drop_all(engine)
        logger.info("Tablas eliminadas exitosamente")
        
    except Exception as e:
        logger.error(f"Error al eliminar tablas: {str(e)}")
        raise

def get_table_info(engine):
    """
    Obtiene información sobre las tablas existentes.
    
    Args:
        engine: Engine de SQLAlchemy
        
    Returns:
        dict: Información de las tablas
    """
    try:
        with engine.connect() as conn:
            # Verificar si existe la extensión vector
            vector_ext = conn.execute("SELECT * FROM pg_extension WHERE extname = 'vector';").fetchone()
            
            # Verificar si existen las tablas
            embeddings_exists = conn.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'embeddings'
                );
            """).fetchone()[0]
            
            documents_exists = conn.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'documents'
                );
            """).fetchone()[0]
            
            # Contar registros si las tablas existen
            embeddings_count = 0
            documents_count = 0
            
            if embeddings_exists:
                embeddings_count = conn.execute("SELECT COUNT(*) FROM embeddings;").fetchone()[0]
            
            if documents_exists:
                documents_count = conn.execute("SELECT COUNT(*) FROM documents;").fetchone()[0]
            
            return {
                "vector_extension": vector_ext is not None,
                "embeddings_table_exists": embeddings_exists,
                "documents_table_exists": documents_exists,
                "embeddings_count": embeddings_count,
                "documents_count": documents_count
            }
            
    except Exception as e:
        logger.error(f"Error al obtener información de tablas: {str(e)}")
        return None
