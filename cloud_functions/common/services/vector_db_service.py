"""
Servicio de base de datos vectorial usando PostgreSQL con pgvector.

Este servicio reemplaza las funcionalidades de FAISS para:
1. Almacenar embeddings en PostgreSQL
2. Realizar búsquedas de similitud vectorial
3. Gestionar metadatos de documentos
4. Proporcionar operaciones CRUD para vectores
"""
import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from sqlalchemy import text, func
from datetime import datetime

from common.db.connection import get_engine, get_session
from common.db.models import EmbeddingModel, create_tables, get_table_info

logger = logging.getLogger(__name__)


class VectorDBService:
    """
    Servicio para gestionar operaciones de base de datos vectorial.
    """
    
    def __init__(self):
        """Inicializa el servicio de base de datos vectorial."""
        self.engine = get_engine()
        self._ensure_tables_exist()
        logger.info("VectorDBService inicializado")
    
    def _ensure_tables_exist(self):
        """Asegura que las tablas necesarias existan."""
        try:
            create_tables(self.engine)
            logger.info("Tablas verificadas/creadas exitosamente")
        except Exception as e:
            logger.error(f"Error al verificar/crear tablas: {str(e)}")
            raise
    
    def store_embeddings(self, embeddings: np.ndarray, metadata_df: pd.DataFrame) -> bool:
        """
        Almacena embeddings en la base de datos.
        
        Args:
            embeddings (np.ndarray): Array de embeddings
            metadata_df (pd.DataFrame): DataFrame con metadatos
            
        Returns:
            bool: True si se almacenaron exitosamente
        """
        try:
            if len(embeddings) != len(metadata_df):
                raise ValueError("El número de embeddings no coincide con el número de registros de metadatos")
            
            # Convertir embeddings a lista para pgvector
            embedding_list = embeddings.tolist()
            
            # Preparar datos para inserción
            records = []
            for i, (_, row) in enumerate(metadata_df.iterrows()):
                record = {
                    'document_id': row.get('document_id', 'unknown'),
                    'chunk_id': row.get('chunk_id', f'chunk_{i}'),
                    'text_content': row.get('text', ''),
                    'embedding_vector': embedding_list[i],
                    'document_metadata': row.to_dict() if hasattr(row, 'to_dict') else {}
                }
                records.append(record)
            
            # Insertar en lotes para mejor rendimiento
            batch_size = 100
            with get_session() as session:
                # Primero, guardar información del documento en la tabla documents
                if records:
                    first_record = records[0]
                    filename = metadata_df.iloc[0].get('filename', 'unknown')
                    
                    # Obtener información del archivo original desde uploads/
                    file_size = 0
                    upload_date = datetime.now()
                    
                    try:
                        from common.services.gcs_service import GCSService
                        gcs_service = GCSService()
                        
                        # Construir ruta del archivo original
                        original_file_path = f"uploads/{filename}"
                        
                        if gcs_service.file_exists(original_file_path):
                            # Obtener metadatos del archivo original
                            file_metadata = gcs_service.get_file_metadata(original_file_path)
                            file_size = file_metadata.get('size', 0)
                            
                            # Obtener fecha de creación del archivo
                            created_str = file_metadata.get('created')
                            if created_str:
                                upload_date = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                            
                            logger.info(f"Metadatos del archivo original obtenidos: {filename}, size: {file_size}, created: {upload_date}")
                        else:
                            logger.warning(f"Archivo original no encontrado: {original_file_path}")
                            
                    except Exception as e:
                        logger.warning(f"No se pudieron obtener metadatos del archivo original: {str(e)}")
                    
                    document_info = {
                        'document_id': first_record['document_id'],
                        'filename': filename,
                        'file_size': file_size,
                        'upload_date': upload_date,
                        'processing_status': 'completed',
                        'num_chunks': len(records),
                        'document_metadata': {
                            'total_words': sum(metadata_df.get('word_count', [0])),
                            'total_chars': sum(metadata_df.get('text_length', [0])),
                            'chunk_count': len(records),
                            'processed_at': datetime.now().isoformat(),
                            'original_filename': filename,
                            'embedding_model': 'OpenAI text-embedding-3-small',
                            'vector_dimension': 1536
                        }
                    }
                    
                    # Usar upsert para evitar duplicados
                    from sqlalchemy.dialects.postgresql import insert
                    from common.db.models import DocumentModel
                    
                    stmt = insert(DocumentModel).values(**document_info)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['document_id'],
                        set_={
                            'filename': document_info['filename'],
                            'file_size': document_info['file_size'],
                            'upload_date': document_info['upload_date'],
                            'processing_status': document_info['processing_status'],
                            'num_chunks': document_info['num_chunks'],
                            'document_metadata': document_info['document_metadata'],
                            'updated_at': datetime.now()
                        }
                    )
                    session.execute(stmt)
                
                # Luego, insertar embeddings
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    embedding_models = [EmbeddingModel(**record) for record in batch]
                    session.add_all(embedding_models)
                
                session.commit()
            
            logger.info(f"Almacenados {len(records)} embeddings y información del documento en la base de datos")
            return True
            
        except Exception as e:
            logger.error(f"Error al almacenar embeddings: {str(e)}")
            return False
    
    def similarity_search(self, query_embedding: np.ndarray, k: int = 5, 
                         document_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Realiza búsqueda de similitud vectorial.
        
        Args:
            query_embedding (np.ndarray): Embedding de la consulta
            k (int): Número de resultados a retornar
            document_id (Optional[str]): Filtrar por documento específico
            
        Returns:
            List[Dict[str, Any]]: Lista de resultados con similitud
        """
        try:
            # Convertir embedding a lista para pgvector
            embedding_list = query_embedding.tolist()
            
            # Construir query SQL
            if document_id:
                sql = text("""
                    SELECT 
                        text_content,
                        document_id,
                        chunk_id,
                        document_metadata,
                        embedding_vector <-> :query_embedding as distance
                    FROM embeddings
                    WHERE document_id = :document_id
                    ORDER BY embedding_vector <-> :query_embedding
                    LIMIT :k
                """)
                params = {
                    "query_embedding": embedding_list,
                    "document_id": document_id,
                    "k": k
                }
            else:
                sql = text("""
                    SELECT 
                        text_content,
                        document_id,
                        chunk_id,
                        document_metadata,
                        embedding_vector <-> :query_embedding as distance
                    FROM embeddings
                    ORDER BY embedding_vector <-> :query_embedding
                    LIMIT :k
                """)
                params = {
                    "query_embedding": embedding_list,
                    "k": k
                }
            
            with self.engine.connect() as conn:
                result = conn.execute(sql, params)
                rows = result.fetchall()
                
                # Convertir a lista de diccionarios
                results = []
                for row in rows:
                    result_dict = {
                        'text_content': row.text_content,
                        'document_id': row.document_id,
                        'chunk_id': row.chunk_id,
                        'metadata': row.document_metadata,
                        'distance': float(row.distance)
                    }
                    results.append(result_dict)
                
                logger.info(f"Búsqueda de similitud completada: {len(results)} resultados")
                return results
                
        except Exception as e:
            logger.error(f"Error en búsqueda de similitud: {str(e)}")
            return []
    
    def get_document_embeddings(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Obtiene todos los embeddings de un documento específico.
        
        Args:
            document_id (str): ID del documento
            
        Returns:
            List[Dict[str, Any]]: Lista de embeddings del documento
        """
        try:
            with get_session() as session:
                embeddings = session.query(EmbeddingModel).filter(
                    EmbeddingModel.document_id == document_id
                ).all()
                
                results = []
                for embedding in embeddings:
                    result_dict = {
                        'id': embedding.id,
                        'document_id': embedding.document_id,
                        'chunk_id': embedding.chunk_id,
                        'text_content': embedding.text_content,
                        'metadata': embedding.document_metadata,
                        'created_at': embedding.created_at.isoformat() if embedding.created_at else None
                    }
                    results.append(result_dict)
                
                logger.info(f"Obtenidos {len(results)} embeddings para documento {document_id}")
                return results
                
        except Exception as e:
            logger.error(f"Error al obtener embeddings del documento: {str(e)}")
            return []
    
    def delete_document_embeddings(self, document_id: str) -> bool:
        """
        Elimina todos los embeddings de un documento específico.
        
        Args:
            document_id (str): ID del documento
            
        Returns:
            bool: True si se eliminaron exitosamente
        """
        try:
            with get_session() as session:
                deleted_count = session.query(EmbeddingModel).filter(
                    EmbeddingModel.document_id == document_id
                ).delete()
                
                session.commit()
                logger.info(f"Eliminados {deleted_count} embeddings del documento {document_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error al eliminar embeddings del documento: {str(e)}")
            return False
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de la base de datos.
        
        Returns:
            Dict[str, Any]: Estadísticas de la base de datos
        """
        try:
            table_info = get_table_info(self.engine)
            
            with get_session() as session:
                # Contar total de embeddings
                total_embeddings = session.query(func.count(EmbeddingModel.id)).scalar()
                
                # Contar documentos únicos
                unique_documents = session.query(func.count(func.distinct(EmbeddingModel.document_id))).scalar()
                
                # Obtener documentos más recientes
                recent_documents = session.query(
                    EmbeddingModel.document_id,
                    func.count(EmbeddingModel.id).label('chunk_count'),
                    func.max(EmbeddingModel.created_at).label('last_updated')
                ).group_by(EmbeddingModel.document_id).order_by(
                    func.max(EmbeddingModel.created_at).desc()
                ).limit(10).all()
                
                stats = {
                    'total_embeddings': total_embeddings,
                    'unique_documents': unique_documents,
                    'recent_documents': [
                        {
                            'document_id': doc.document_id,
                            'chunk_count': doc.chunk_count,
                            'last_updated': doc.last_updated.isoformat() if doc.last_updated else None
                        }
                        for doc in recent_documents
                    ],
                    'table_info': table_info
                }
                
                logger.info(f"Estadísticas obtenidas: {total_embeddings} embeddings, {unique_documents} documentos")
                return stats
                
        except Exception as e:
            logger.error(f"Error al obtener estadísticas: {str(e)}")
            return {}
    
    def create_index(self) -> bool:
        """
        Crea índices para optimizar las búsquedas.
        
        Returns:
            bool: True si se crearon exitosamente
        """
        try:
            with self.engine.connect() as conn:
                # Índice para búsquedas de similitud (coseno)
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_vector_cosine 
                    ON embeddings USING ivfflat (embedding_vector vector_cosine_ops) 
                    WITH (lists = 100);
                """))
                
                # Índices adicionales para consultas por documento
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_document_id 
                    ON embeddings(document_id);
                """))
                
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id 
                    ON embeddings(chunk_id);
                """))
                
                conn.commit()
                logger.info("Índices creados exitosamente")
                return True
                
        except Exception as e:
            logger.error(f"Error al crear índices: {str(e)}")
            return False
    
    def test_connection(self) -> bool:
        """
        Prueba la conexión a la base de datos.
        
        Returns:
            bool: True si la conexión es exitosa
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info("Conexión a la base de datos probada exitosamente")
                return True
        except Exception as e:
            logger.error(f"Error al probar conexión: {str(e)}")
            return False


# Función de conveniencia
def get_vector_db_service() -> VectorDBService:
    """
    Obtiene una instancia del servicio de base de datos vectorial.
    
    Returns:
        VectorDBService: Instancia del servicio
    """
    return VectorDBService() 