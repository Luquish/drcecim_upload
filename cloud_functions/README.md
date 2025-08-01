# Cloud Functions - Sistema de Procesamiento DrCecim

## 🎯 Descripción

Sistema de Google Cloud Functions 2ª generación que procesa documentos PDF y genera embeddings vectoriales para el chatbot DrCecim. Utiliza PostgreSQL con pgvector como base de datos vectorial y OpenAI para generación de embeddings.

## 🏗️ Arquitectura

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│   PDF Upload    │───▶│  process-pdf-to-     │───▶│   PostgreSQL    │
│   (GCS Bucket)  │    │     chunks           │    │   + pgvector    │
└─────────────────┘    └──────────────────────┘    └─────────────────┘
                                │                           ▲
                                ▼                           │
                       ┌──────────────────────┐            │
                       │ create-embeddings-   │────────────┘
                       │   from-chunks        │
                       └──────────────────────┘
                                │
                                ▼
                       ┌──────────────────────┐
                       │     OpenAI API       │
                       │   (Embeddings)       │
                       └──────────────────────┘
```

## 📁 Estructura del Proyecto

```
cloud_functions/
├── main.py                          # Entry points de ambas funciones
├── requirements.txt                 # Todas las dependencias
├── common/                          # Código compartido
│   ├── config/                      # Configuración centralizada
│   │   ├── settings.py              # Variables de entorno
│   │   └── logging_config.py        # Sistema de logging
│   ├── db/                          # Base de datos
│   │   ├── connection.py            # Conexión Cloud SQL/Local
│   │   └── models.py                # Modelos SQLAlchemy
│   ├── services/                    # Servicios de negocio
│   │   ├── processing_service.py    # Procesamiento PDF
│   │   ├── embeddings_service.py    # Generación embeddings
│   │   ├── vector_db_service.py     # Base de datos vectorial
│   │   ├── gcs_service.py           # Google Cloud Storage
│   │   └── status_service.py        # Tracking de estado
│   └── credentials/                 # Credenciales GCP
│       └── service-account.json     # Service account
├── test_simple.py                   # Script de pruebas locales
├── test_env/                        # Entorno virtual para tests
└── deploy_event_driven.sh           # Script de deployment
```

## 🚀 Cloud Functions

### 1. `process-pdf-to-chunks`
**🎯 Propósito**: Procesa documentos PDF y los convierte en chunks de texto estructurado
- **Trigger**: Subida de archivos PDF a Google Cloud Storage
- **Tecnología**: Marker-PDF para conversión PDF→Markdown
- **Output**: Chunks de texto optimizados para RAG
- **Tiempo**: ~2-5 minutos por documento (dependiendo del tamaño)

### 2. `create-embeddings-from-chunks`  
**🎯 Propósito**: Genera embeddings vectoriales y los almacena en PostgreSQL
- **Trigger**: Procesamiento de chunks completado
- **Tecnología**: OpenAI text-embedding-3-small
- **Output**: Vectores de 1536 dimensiones en pgvector
- **Tiempo**: ~30 segundos por documento

## 🗄️ Base de Datos - PostgreSQL + pgvector

### Configuración Cloud SQL
```sql
-- Habilitar extensión pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabla de documentos
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_status VARCHAR(50) DEFAULT 'uploaded',
    document_metadata JSONB,
    total_chunks INTEGER,
    total_words INTEGER
);

-- Tabla de embeddings vectoriales  
CREATE TABLE embeddings (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),  -- OpenAI embeddings dimension
    document_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índice para búsquedas vectoriales eficientes
CREATE INDEX idx_embeddings_vector ON embeddings 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);
```

### Configuración de Conexión
```python
# Cloud SQL (Producción)
CLOUD_SQL_CONNECTION_NAME=proyecto:region:instancia
DB_PRIVATE_IP=false  # IP pública/privada

# PostgreSQL Local (Testing)  
DB_HOST=localhost
DB_PORT=5432
```

## 🚀 Deployment

### Pre-requisitos
```bash
# Habilitar APIs necesarias
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable storage.googleapis.com

# Configurar autenticación
gcloud auth login
gcloud config set project TU-PROJECT-ID
```

### Deployment Completo
```bash
# Usar el script automatizado (RECOMENDADO)
./deploy_event_driven.sh
```

### Deployment Manual (Opciones Avanzadas)
```bash
# Function 1: Procesamiento PDF
gcloud functions deploy process-pdf-to-chunks \
  --gen2 \
  --runtime=python311 \
  --region=southamerica-east1 \
  --source=. \
  --entry-point=process_pdf_to_chunks \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=TU-BUCKET" \
  --memory=2048MB \
  --timeout=540s \
  --max-instances=1

# Function 2: Generación de Embeddings  
gcloud functions deploy create-embeddings-from-chunks \
  --gen2 \
  --runtime=python311 \
  --region=southamerica-east1 \
  --source=. \
  --entry-point=create_embeddings_from_chunks \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=TU-BUCKET" \
  --memory=1024MB \
  --timeout=300s \
  --max-instances=3
```

## 🧪 Testing Local (RECOMENDADO)

### Configuración del Entorno de Pruebas
```bash
# 1. Crear entorno virtual
python3 -m venv test_env
source test_env/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar PostgreSQL local
brew install postgresql@14 pgvector
brew services start postgresql@14
createdb ragdb
psql ragdb -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql ragdb -c "CREATE USER raguser WITH PASSWORD 'DrCecim2024@';"
psql ragdb -c "GRANT ALL PRIVILEGES ON DATABASE ragdb TO raguser;"

# 4. Ejecutar pruebas completas
python3 test_simple.py
```

### ✅ Validación End-to-End
El script `test_simple.py` verifica:
- ✅ **PDF Processing**: Marker convierte PDF → chunks de texto
- ✅ **Database Connection**: PostgreSQL + pgvector funcionando  
- ✅ **OpenAI API**: Generación de embeddings exitosa
- ✅ **Vector Storage**: Almacenamiento en base vectorial
- ✅ **Configuración Centralizada**: Variables cargadas desde `settings.py` y `.env`

### 🔧 Configuración de Variables (.env)
```bash
# Crear archivo .env en cloud_functions/
# REQUERIDO
OPENAI_API_KEY=sk-proj-tu-nueva-api-key
GCS_BUCKET_NAME=tu-bucket-name
GCF_PROJECT_ID=tu-project-id

# OPCIONAL (testing local)
TEST_PDF_PATH=/ruta/a/tu/archivo.pdf  # Para test_simple.py
DB_HOST=localhost                     # PostgreSQL local
DB_USER=raguser
DB_PASS=tu-password
```

### 📋 Variables de Entorno

```bash
# === GOOGLE CLOUD ===
GCS_BUCKET_NAME=drcecim-chatbot-storage
GCF_PROJECT_ID=tu-project-id  
GCF_REGION=southamerica-east1
SERVICE_ACCOUNT=tu-service-account@project.iam.gserviceaccount.com

# === OPENAI ===
OPENAI_API_KEY=sk-proj-tu-nueva-api-key
EMBEDDING_MODEL=text-embedding-3-small
API_TIMEOUT=30

# === DATABASE ===
# Cloud SQL (Producción)
CLOUD_SQL_CONNECTION_NAME=proyecto:region:instancia
DB_USER=raguser
DB_PASS=tu-password
DB_NAME=ragdb
DB_PRIVATE_IP=false

# PostgreSQL Local (Testing)
DB_HOST=localhost
DB_PORT=5432

# === PROCESAMIENTO ===
CHUNK_SIZE=250
CHUNK_OVERLAP=50
LOG_LEVEL=INFO
LOG_TO_DISK=false  # Cloud Functions compatible
ENVIRONMENT=production
```

## 🔍 Monitoreo y Troubleshooting

### Logs de Cloud Functions
```bash
# Ver logs en tiempo real
gcloud functions logs read process-pdf-to-chunks --region=southamerica-east1 --follow

# Logs de una función específica
gcloud functions logs read create-embeddings-from-chunks --region=southamerica-east1 --limit=50
```

### Verificar Estado de la Base de Datos
```sql
-- Conectar a Cloud SQL
gcloud sql connect tu-instancia --user=raguser --database=ragdb

-- Verificar datos
SELECT COUNT(*) as total_documentos FROM documents;
SELECT COUNT(*) as total_embeddings FROM embeddings;

-- Ver último documento procesado
SELECT filename, processing_status, upload_timestamp 
FROM documents 
ORDER BY upload_timestamp DESC 
LIMIT 5;
```

### Problemas Comunes

**❌ Error: Health check failed**
- **Causa**: Archivo `main.py` con errores de sintaxis
- **Solución**: Ejecutar `test_simple.py` antes del deploy

**❌ Error: Cannot connect to Cloud SQL**  
- **Causa**: Service account sin permisos
- **Solución**: Agregar rol `Cloud SQL Client` al service account

**❌ Error: OpenAI rate limit**
- **Causa**: Límites de API superados  
- **Solución**: Configurar `API_TIMEOUT` más alto o usar tier pagado

**❌ Error: pgvector extension not found**
- **Causa**: Extensión no habilitada en Cloud SQL
- **Solución**: `CREATE EXTENSION IF NOT EXISTS vector;` 