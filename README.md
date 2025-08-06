# DrCecim Upload - Sistema RAG para Chatbot Médico

🤖 **Sistema de procesamiento de documentos PDF para el chatbot DrCecim de la Facultad de Medicina UBA**. Convierte documentos médicos en embeddings vectoriales para búsqueda semántica usando RAG (Retrieval-Augmented Generation).

## 🎯 Descripción

**DrCecim Upload** es un pipeline automatizado que:
1. **Recibe** documentos PDF médicos vía interfaz Streamlit
2. **Procesa** PDFs con Marker (PDF→Markdown→Chunks) 
3. **Genera** embeddings vectoriales con OpenAI text-embedding-3-small
4. **Almacena** vectores en PostgreSQL + pgvector para búsqueda semántica
5. **Alimenta** el sistema RAG del chatbot DrCecim con conocimiento médico actualizado

## 🏗️ Arquitectura Completa

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamlit     │───▶│  Google Cloud   │───▶│ Cloud Functions │
│   Frontend      │    │    Storage      │    │   (Gen 2)       │
│   (Upload UI)   │    │   (PDF Store)   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                │              ┌────────┴────────┐
                                │              ▼                 ▼
                                │    ┌─────────────────┐ ┌─────────────────┐
                                │    │ process-pdf-to- │ │create-embeddings│
                                │    │    chunks       │ │  -from-chunks   │
                                │    │   (Marker)      │ │   (OpenAI)      │
                                │    └─────────────────┘ └─────────────────┘
                                │                                 │
                                ▼                                 ▼
                       ┌─────────────────┐                ┌─────────────────┐
                       │   Status &      │                │   PostgreSQL    │
                       │   Monitoring    │                │   + pgvector    │
                       │                 │                │  (Vector DB)    │
                       └─────────────────┘                └─────────────────┘
```

### 🛠️ Stack Tecnológico

- **Frontend**: Streamlit para interfaz de usuario  
- **Document Processing**: Marker-PDF (1.8.2+) para conversión PDF→Markdown
- **Vector Generation**: OpenAI text-embedding-3-small (1536 dims)
- **Compute**: Google Cloud Functions Gen2 (Python 3.11)
- **Storage**: Google Cloud Storage para archivos + PostgreSQL para vectores
- **Vector DB**: PostgreSQL 14+ con extensión pgvector
- **Infrastructure**: Google Cloud Platform (GCP)

## 🚀 Instalación y Configuración

### 1. Prerequisitos del Sistema
```bash
# macOS (Homebrew recomendado)
brew install python@3.11 postgresql@14 pgvector
brew install --cask google-cloud-sdk

# Ubuntu/Debian
sudo apt-get install python3.11 postgresql-14 postgresql-14-pgvector
# Instalar Google Cloud SDK desde https://cloud.google.com/sdk/docs/install
```

### 2. Setup del Proyecto
```bash
# Clonar repositorio
git clone <repo-url>
cd drcecim_upload

# Configurar variables de entorno
cp cloud_functions/.env.example cloud_functions/.env
# ⚠️ EDITAR cloud_functions/.env con tus credenciales

# Configurar credenciales GCP
gcloud auth login
gcloud config set project TU-PROJECT-ID
```

### 3. Variables de Entorno Críticas
Editar `cloud_functions/.env`:
```bash
# === GOOGLE CLOUD (REQUERIDO) ===
GCS_BUCKET_NAME=tu-bucket-drcecim
GCF_PROJECT_ID=tu-project-id
SERVICE_ACCOUNT=tu-service-account@proyecto.iam.gserviceaccount.com

# === DATABASE ===
DB_USER=raguser
DB_PASS=tu-password-seguro
DB_NAME=ragdb
CLOUD_SQL_CONNECTION_NAME=proyecto:region:instancia
```

### 4. Testing Local COMPLETO (RECOMENDADO)
```bash
cd cloud_functions

# 1. Entorno virtual para testing
python3 -m venv test_env
source test_env/bin/activate
pip install -r requirements.txt

# 2. PostgreSQL local + pgvector
brew services start postgresql@15
createdb ragdb
psql ragdb -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql ragdb -c "CREATE USER raguser WITH PASSWORD 'DrCecim2024@';"

# 3. Ejecutar prueba end-to-end ✅
python3 test_simple.py

# ✅ Si todo funciona → listo para deploy
# ❌ Si hay errores → revisar configuración
```

### 5. Deployment Cloud Functions
```bash
# Solo después de que test_simple.py funcione ✅
./deploy_event_driven.sh
```

### 6. Streamlit Frontend (Opcional)
```bash
# Entorno separado para frontend
python3 -m venv streamlit_env
source streamlit_env/bin/activate
pip install -r requirements.txt

# Ejecutar interfaz web
streamlit run streamlit_app.py
```

## 📁 Estructura del Proyecto

```
drcecim_upload/
├── cloud_functions/                 # 🎯 CORE: Cloud Functions + Testing
│   ├── main.py                      # Entry points: process_pdf_to_chunks, create_embeddings_from_chunks
│   ├── requirements.txt             # Dependencias para deployment
│   ├── test_simple.py               # ✅ Testing end-to-end local
│   ├── test_env/                    # Entorno virtual para pruebas
│   ├── common/                      # Código compartido
│   │   ├── config/                  # Configuración (settings.py, logging)
│   │   ├── db/                      # PostgreSQL + pgvector (models, connection)
│   │   ├── services/                # Lógica de negocio (processing, embeddings, gcs)
│   │   └── credentials/             # service-account.json
│   └── deploy_event_driven.sh       # Script de deployment automatizado
├── config/                          # Configuración para Streamlit
├── services/                        # Servicios duplicados para Streamlit  
├── ui/                              # Interfaz Streamlit
├── streamlit_app.py                 # Frontend web
└── requirements.txt                 # Dependencias Streamlit
```

## 🔧 Configuración Avanzada

### Optimización de Chunks
```bash
# En cloud_functions/.env
CHUNK_SIZE=500          # Tamaño de chunks (caracteres)
CHUNK_OVERLAP=100       # Overlap entre chunks 
```

### Modelo de Embeddings Alternativo
```bash
# En cloud_functions/.env  
EMBEDDING_MODEL=text-embedding-3-large  # Mayor precisión, más costo
# EMBEDDING_MODEL=text-embedding-3-small # Menor costo (default)
```

### Configuración de Performance
```bash
# Memory y timeout para Cloud Functions
--memory=2048MB --timeout=540s  # process-pdf-to-chunks
--memory=1024MB --timeout=300s  # create-embeddings-from-chunks
```

## 🚢 Deployment en Producción

### 1. Google Cloud Infrastructure Setup
```bash
# Configurar proyecto GCP
gcloud auth login
gcloud config set project TU-PROJECT-ID

# Habilitar APIs necesarias
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable sqladmin.googleapis.com  
gcloud services enable storage.googleapis.com

# Crear bucket GCS
gsutil mb gs://tu-bucket-drcecim

# Crear instancia Cloud SQL + pgvector
gcloud sql instances create drcecim-cloud-sql \
  --database-version=POSTGRES_14 \
  --region=southamerica-east1 \
  --tier=db-f1-micro

# Configurar pgvector en Cloud SQL
gcloud sql databases create ragdb --instance=drcecim-cloud-sql
gcloud sql users create raguser --instance=drcecim-cloud-sql --password=PASSWORD
```

### 2. Deploy Cloud Functions
```bash
cd cloud_functions

# ⚠️ IMPORTANTE: Solo deploy después de test_simple.py ✅
./deploy_event_driven.sh

# Verificar deployment
gcloud functions list --regions=southamerica-east1
```

### 3. Deploy Frontend Streamlit (Opcional)
```bash
# Streamlit Cloud: Configurar secrets.toml con variables de entorno
# O deploy local:
streamlit run streamlit_app.py
```

## 🧪 Testing & Validación

### Testing Local End-to-End (RECOMENDADO)
```bash
cd cloud_functions
python3 test_simple.py

# ✅ Verifica TODA la funcionalidad antes del deploy:
# - PDF Processing (Marker)
# - Database Connection (PostgreSQL + pgvector)  
# - OpenAI API (Embeddings)
# - Vector Storage
```

### Testing en Producción
```bash
# Subir PDF de prueba
gsutil cp test.pdf gs://tu-bucket-drcecim/

# Verificar logs de Cloud Functions
gcloud functions logs read process-pdf-to-chunks --region=southamerica-east1 --follow

# Verificar base de datos
gcloud sql connect drcecim-cloud-sql --user=raguser --database=ragdb
SELECT COUNT(*) FROM embeddings;
```

## 📊 Monitoreo en Producción

### Logs y Debugging
```bash
# Ver logs de Cloud Functions en tiempo real
gcloud functions logs read process-pdf-to-chunks --region=southamerica-east1 --follow
gcloud functions logs read create-embeddings-from-chunks --region=southamerica-east1 --follow

# Status de procesamiento
gcloud sql connect drcecim-cloud-sql --user=raguser --database=ragdb
SELECT filename, processing_status, upload_timestamp FROM documents ORDER BY upload_timestamp DESC LIMIT 10;
```

### Métricas Importantes
- **Tiempo de procesamiento PDF**: ~2-5 minutos por documento
- **Generación de embeddings**: ~30 segundos por documento  
- **Dimensión vectores**: 1536 (OpenAI text-embedding-3-small)
- **Rate limits OpenAI**: 3 RPM (tier gratuito), 3000 RPM (tier pagado)

## 🔒 Seguridad y Best Practices

- ✅ **Testing local obligatorio** antes de deployment
- ✅ **Service Account** con permisos mínimos necesarios  
- ✅ **API Keys** gestionadas via variables de entorno (no hardcoded)
- ✅ **Rate limiting** automático para OpenAI API
- ✅ **Validación de uploads** de archivos PDF
- ✅ **Logging estructurado** para auditoría y debugging
- ✅ **Conexiones seguras** a Cloud SQL con SSL

## 🐛 Troubleshooting

### Problemas Frecuentes

**❌ test_simple.py falla**
```bash
# 1. Verificar PostgreSQL local
brew services restart postgresql@14
psql ragdb -c "SELECT version();"

# 2. Verificar extensión pgvector
psql ragdb -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**❌ Cloud Functions health check falla**
```bash
# Siempre ejecutar test local ANTES del deploy
cd cloud_functions && python3 test_simple.py

# Solo deploy si test_simple.py ✅ pasa completamente
```

**❌ Error "Cannot connect to Cloud SQL"**
```bash
# Verificar service account tiene permisos
gcloud projects add-iam-policy-binding PROJECT-ID \
  --member="serviceAccount:SERVICE-ACCOUNT" \
  --role="roles/cloudsql.client"
```

**❌ OpenAI rate limit excedido**
- **Problema**: Tier gratuito de OpenAI (3 RPM)
- **Solución**: Actualizar a tier pagado o ajustar `API_TIMEOUT`

### Logs Útiles para Debugging
```bash
# Cloud Functions (Producción)
gcloud functions logs read process-pdf-to-chunks --region=southamerica-east1 --limit=20

# PostgreSQL local (Testing)
tail -f /opt/homebrew/var/log/postgresql@14.log

# Testing local completo
cd cloud_functions && python3 test_simple.py 2>&1 | tee debug.log
```

## 📚 Documentación Adicional

- **Cloud Functions**: [`cloud_functions/README.md`](cloud_functions/README.md) - Documentación técnica detallada
- **Streamlit Deployment**: [`STREAMLIT_DEPLOYMENT_GUIDE.md`](STREAMLIT_DEPLOYMENT_GUIDE.md) - Guía de deployment frontend  
- **Flujo Completo**: [`FLUJO_COMPLETO_SISTEMA.md`](FLUJO_COMPLETO_SISTEMA.md) - Arquitectura end-to-end

## 📝 Changelog

### v2.0.0 (Latest)
- 🎯 **Testing local end-to-end** obligatorio pre-deployment
- 🚀 **PostgreSQL + pgvector** configuración local automatizada  
- ⚡ **Marker-PDF 1.8.2+** corrigiendo incompatibilidades de dependencias
- 🗄️ **Base de datos dual**: Cloud SQL (prod) + PostgreSQL local (testing)
- 📊 **Logging mejorado** compatible con Cloud Functions read-only filesystem
- 🔧 **Configuración unificada** en `cloud_functions/.env`
- ✅ **Pipeline validado** completamente antes de cualquier deployment

### v1.0.0 (Anterior)
- ✅ Arquitectura modular con servicios compartidos
- ✅ Cloud Functions Gen2 + Google Cloud Storage
- ✅ OpenAI embeddings + configuración básica

---

🎓 **Desarrollado para la Facultad de Medicina UBA**  
🤖 **Sistema RAG para chatbot DrCecim** 