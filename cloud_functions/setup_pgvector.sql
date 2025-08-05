-- =============================================================================
-- SCRIPT DE CONFIGURACIÓN PARA PGVECTOR
-- =============================================================================

-- 1. Crear extensión pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Crear tabla de embeddings
CREATE TABLE IF NOT EXISTS embeddings (
    id BIGSERIAL PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    text_content TEXT NOT NULL,
    embedding_vector vector(1536) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Crear tabla de documentos (opcional)
CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    document_id TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    file_size BIGINT,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_status TEXT DEFAULT 'pending',
    num_chunks BIGINT DEFAULT 0,
    -- Columnas individuales para metadatos del documento
    chunk_count INTEGER,
    total_chars INTEGER,
    total_words INTEGER,
    processed_at TIMESTAMP,
    embedding_model VARCHAR(100),
    vector_dimension INTEGER,
    original_filename TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Crear índices para optimizar búsquedas
-- Índice para búsquedas de similitud vectorial (coseno)
CREATE INDEX IF NOT EXISTS idx_embeddings_vector_cosine 
ON embeddings USING ivfflat (embedding_vector vector_cosine_ops) 
WITH (lists = 100);

-- Índices para consultas por documento y chunk
CREATE INDEX IF NOT EXISTS idx_embeddings_document_id ON embeddings(document_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id ON embeddings(chunk_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_created_at ON embeddings(created_at);

-- Índices para la tabla de documentos
CREATE INDEX IF NOT EXISTS idx_documents_document_id ON documents(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status);

-- 5. Conceder permisos al usuario raguser
GRANT ALL PRIVILEGES ON TABLE embeddings TO raguser;
GRANT ALL PRIVILEGES ON TABLE documents TO raguser;
GRANT USAGE, SELECT ON SEQUENCE embeddings_id_seq TO raguser;
GRANT USAGE, SELECT ON SEQUENCE documents_id_seq TO raguser;

-- 6. Verificar la instalación
SELECT 
    'pgvector extension' as component,
    CASE 
        WHEN EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') 
        THEN 'INSTALLED' 
        ELSE 'NOT INSTALLED' 
    END as status;

SELECT 
    'embeddings table' as component,
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'embeddings') 
        THEN 'CREATED' 
        ELSE 'NOT CREATED' 
    END as status;

SELECT 
    'documents table' as component,
    CASE 
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents') 
        THEN 'CREATED' 
        ELSE 'NOT CREATED' 
    END as status; 