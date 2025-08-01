# 🔄 Flujo Completo del Sistema DrCecim

## 📋 Resumen del Flujo

Este documento describe el recorrido completo de un chunk desde que el usuario sube un archivo PDF hasta que se almacena como embedding en la tabla PostgreSQL.

## 🎯 Flujo Detallado

### **Paso 1: Subida del Archivo (Streamlit)**
```
Usuario → Streamlit UI → GCS Bucket
```

**1.1. Interfaz de Usuario (Streamlit)**
- **Archivo**: `streamlit_app.py` → `ui/streamlit_ui.py`
- **Acción**: Usuario sube archivo PDF
- **Validación**: `ui/streamlit_utils.py` valida tipo y tamaño

**1.2. Lógica de Procesamiento (Streamlit)**
- **Archivo**: `ui/streamlit_logic.py`
- **Función**: `upload_file_to_bucket()`
- **Acción**: Sube archivo a GCS en carpeta `uploads/`
- **Formato**: `uploads/YYYYMMDD_HHMMSS_nombre_archivo.pdf`

**1.3. Registro de Estado**
- **Archivo**: `ui/streamlit_logic.py`
- **Función**: `register_document_status()`
- **Acción**: Registra documento en sistema de estado
- **Estado**: `UPLOADED`

---

### **Paso 2: Procesamiento de PDF (Cloud Function #1)**
```
GCS Event → process_pdf_to_chunks → Chunks JSON
```

**2.1. Trigger de Cloud Function**
- **Archivo**: `cloud_functions/main.py`
- **Función**: `process_pdf_to_chunks()`
- **Trigger**: Evento `google.cloud.storage.object.v1.finalized`
- **Filtro**: Solo archivos en `uploads/` con extensión `.pdf`

**2.2. Descarga y Procesamiento**
- **Archivo**: `cloud_functions/main.py`
- **Función**: `process_pdf_document()`
- **Acción**: 
  - Descarga PDF de GCS
  - Procesa con `marker-pdf`
  - Genera chunks de texto
  - Crea metadatos

**2.3. Generación de Chunks**
- **Archivo**: `cloud_functions/common/services/processing_service.py`
- **Clase**: `DocumentProcessor`
- **Método**: `split_into_chunks()`
- **Configuración**: 
  - `CHUNK_SIZE=250` (palabras)
  - `CHUNK_OVERLAP=50` (palabras)

**2.4. Subida de Chunks**
- **Archivo**: `cloud_functions/main.py`
- **Acción**: Sube chunks como JSON a GCS
- **Ruta**: `processed/YYYYMMDD_HHMMSS_nombre_archivo_chunks.json`
- **Contenido**: 
  ```json
  {
    "filename": "documento.pdf",
    "chunks": ["chunk1", "chunk2", ...],
    "metadata": {...},
    "num_chunks": 15,
    "total_words": 3750
  }
  ```

---

### **Paso 3: Generación de Embeddings (Cloud Function #2)**
```
Chunks JSON → create_embeddings_from_chunks → PostgreSQL
```

**3.1. Trigger de Segunda Cloud Function**
- **Archivo**: `cloud_functions/main.py`
- **Función**: `create_embeddings_from_chunks()`
- **Trigger**: Evento `google.cloud.storage.object.v1.finalized`
- **Filtro**: Solo archivos en `processed/` con `_chunks.json`

**3.2. Descarga de Chunks**
- **Archivo**: `cloud_functions/main.py`
- **Función**: `_download_and_load_chunks()`
- **Acción**: Descarga JSON de chunks desde GCS

**3.3. Generación de Embeddings**
- **Archivo**: `cloud_functions/common/services/embeddings_service.py`
- **Clase**: `EmbeddingService`
- **Método**: `generate_embeddings()`
- **Proceso**:
  1. Preprocesa textos
  2. Genera embeddings con OpenAI API
  3. Usa modelo `text-embedding-3-small` (1536 dimensiones)
  4. Maneja reintentos automáticos

**3.4. Almacenamiento en PostgreSQL**
- **Archivo**: `cloud_functions/common/services/embeddings_service.py`
- **Método**: `store_embeddings_in_db()`
- **Archivo**: `cloud_functions/common/services/vector_db_service.py`
- **Clase**: `VectorDBService`
- **Método**: `store_embeddings()`

**3.5. Inserción en Base de Datos**
- **Tabla**: `embeddings`
- **Estructura**:
  ```sql
  INSERT INTO embeddings (
      document_id,
      chunk_id,
      text_content,
      embedding_vector,
      metadata,
      created_at
  ) VALUES (
      'documento',
      'documento_chunk_0',
      'texto del chunk...',
      '[0.1, 0.2, ...]',
      '{"filename": "documento.pdf", ...}',
      NOW()
  );
  ```

---

### **Paso 4: Gestión de Estado y Metadatos**
```
PostgreSQL → Status Service → GCS Metadata
```

**4.1. Actualización de Estado**
- **Archivo**: `cloud_functions/main.py`
- **Función**: `_update_document_status_completed()`
- **Archivo**: `cloud_functions/common/services/status_service.py`
- **Estado**: `COMPLETED`

**4.2. Almacenamiento de Metadatos**
- **Archivo**: `cloud_functions/common/services/embeddings_service.py`
- **Método**: `create_metadata_summary()`
- **Acción**: Crea resumen de metadatos
- **Almacenamiento**: En tabla `documents` (opcional)

---

## 🗂️ Estructura de Datos Final

### **Tabla `embeddings`**
```sql
CREATE TABLE embeddings (
    id BIGSERIAL PRIMARY KEY,
    document_id TEXT NOT NULL,           -- 'documento'
    chunk_id TEXT NOT NULL,              -- 'documento_chunk_0'
    text_content TEXT NOT NULL,          -- Texto del chunk
    embedding_vector vector(1536) NOT NULL, -- Vector de OpenAI
    metadata JSONB,                      -- Metadatos adicionales
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### **Tabla `documents` (Opcional)**
```sql
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    document_id TEXT UNIQUE NOT NULL,    -- 'documento'
    filename TEXT NOT NULL,              -- 'documento.pdf'
    file_size BIGINT,                    -- Tamaño en bytes
    upload_date TIMESTAMP DEFAULT NOW(),
    processing_status TEXT DEFAULT 'completed',
    num_chunks BIGINT DEFAULT 0,         -- Número de chunks
    metadata JSONB,                      -- Metadatos del documento
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🔍 Ejemplo de Recorrido Completo

### **Entrada**: Usuario sube `documento.pdf`

### **Paso 1**: Streamlit
```
documento.pdf → uploads/20250801_143022_documento.pdf
```

### **Paso 2**: Cloud Function #1
```
uploads/20250801_143022_documento.pdf → 
processed/20250801_143022_documento_chunks.json
```

### **Paso 3**: Cloud Function #2
```
processed/20250801_143022_documento_chunks.json → 
PostgreSQL embeddings table
```

### **Resultado Final**:
```sql
-- 15 registros insertados en embeddings
SELECT * FROM embeddings WHERE document_id = 'documento';
-- Resultado: 15 filas con embeddings de cada chunk
```

---

## 📊 Métricas del Proceso

### **Tiempos Estimados**
- **Subida**: 2-5 segundos
- **Procesamiento PDF**: 30-60 segundos
- **Generación embeddings**: 60-120 segundos
- **Almacenamiento DB**: 5-10 segundos

### **Volúmenes Típicos**
- **PDF de 10 páginas**: ~15 chunks
- **Cada chunk**: ~250 palabras
- **Cada embedding**: 1536 dimensiones
- **Tamaño total**: ~2-5MB de embeddings

### **Monitoreo**
- **Logs**: Cloud Logging
- **Métricas**: Cloud Monitoring
- **Estado**: Status Service en GCS
- **Base de datos**: PostgreSQL logs

---

## 🔧 Configuración de Índices

### **Índices Optimizados**
```sql
-- Búsqueda de similitud vectorial
CREATE INDEX idx_embeddings_vector_cosine 
ON embeddings USING ivfflat (embedding_vector vector_cosine_ops) 
WITH (lists = 100);

-- Consultas por documento
CREATE INDEX idx_embeddings_document_id ON embeddings(document_id);

-- Consultas por chunk
CREATE INDEX idx_embeddings_chunk_id ON embeddings(chunk_id);
```

---

## 🚀 Ventajas del Nuevo Flujo

### **Antes (FAISS)**
- Embeddings en memoria
- Archivos binarios en GCS
- Pérdida de datos en reinicios
- Escalabilidad limitada

### **Ahora (PostgreSQL)**
- Embeddings persistentes
- Base de datos relacional
- Consultas SQL complejas
- Escalabilidad ilimitada
- Backup automático

---

**Fecha**: 2025-08-01
**Versión**: 2.0 (PostgreSQL)
**Estado**: ✅ Implementado 