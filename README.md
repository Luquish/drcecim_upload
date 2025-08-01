# DrCecim Upload - Sistema de Procesamiento de Documentos

🤖 Sistema de carga y procesamiento de documentos PDF para el chatbot DrCecim de la Facultad de Medicina UBA.

## 🎯 Descripción

DrCecim Upload convierte documentos PDF en embeddings vectoriales para alimentar el sistema de RAG (Retrieval-Augmented Generation) del chatbot DrCecim. El sistema procesa automáticamente documentos, los convierte a texto usando Marker, genera embeddings con OpenAI y los almacena en Google Cloud Storage.

## 🏗️ Arquitectura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamlit     │───▶│  Cloud Function │───▶│  Google Cloud   │
│   Frontend      │    │   Processing    │    │    Storage      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   OpenAI API    │
                       │   Embeddings    │
                       └─────────────────┘
```

### Componentes

- **Frontend Streamlit**: Interfaz web para subida de PDFs
- **Document Processor**: Convierte PDF a Markdown con Marker
- **Embedding Service**: Genera embeddings usando OpenAI
- **Cloud Functions**: Procesamiento serverless en Google Cloud
- **Vector Store**: Base de datos PostgreSQL con pgvector para búsquedas vectoriales

## 🚀 Instalación Rápida

### 1. Requisitos
- Python 3.9+
- Google Cloud SDK
- API Key de OpenAI

### 2. Configuración

```bash
# Clonar repositorio
git clone <repo-url>
cd drcecim_upload

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -e .[all]

# Configurar variables de entorno
cp env.example .env
# Editar .env con tus valores
```

### 3. Variables de Entorno Críticas

```bash
# Google Cloud (REQUERIDO)
GCS_BUCKET_NAME=tu-bucket-name
GCF_PROJECT_ID=tu-project-id

# OpenAI (REQUERIDO)
OPENAI_API_KEY=sk-tu-api-key

# Opcional
GCS_CREDENTIALS_PATH=./cloud_functions/credentials/service-account.json
```

### 4. Ejecutar

```bash
# Aplicación Streamlit
streamlit run streamlit_app.py

# Tests
pytest

# Linting
pre-commit run --all-files
```

## 📁 Estructura del Proyecto

```
drcecim_upload/
├── config/              # Configuración centralizada
├── services/            # Lógica de negocio
├── models/              # Modelos de datos
├── ui/                  # Interfaz Streamlit
├── utils/               # Utilidades
├── cloud_functions/     # Google Cloud Functions
├── tests/               # Pruebas unitarias
└── requirements.txt     # Dependencias
```

## 🔧 Configuración Avanzada

### Personalizar Chunk Size
```python
# En .env
CHUNK_SIZE=500
CHUNK_OVERLAP=100
```

### Cambiar Modelo de Embeddings
```python
# En .env
EMBEDDING_MODEL=text-embedding-3-large
```

### Cloud Functions
```bash
cd cloud_functions
./deploy_event_driven.sh
```

## 🚢 Deployment

### Google Cloud Setup
```bash
# Autenticar
gcloud auth login

# Crear bucket
gsutil mb gs://tu-bucket-name

# Habilitar APIs
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable storage.googleapis.com
```

### Streamlit Cloud
Configura `secrets.toml` con las variables de entorno requeridas.

## 🧪 Testing

```bash
# Ejecutar todos los tests
pytest

# Con coverage
pytest --cov=services --cov=config --cov=models

# Tests específicos
pytest tests/test_processing_service.py
```

## 📊 Monitoreo

```bash
# Logs de Cloud Function
gcloud functions logs read drcecim-process-document

# Status de archivos procesados
python -c "from services.status_service import StatusService; print(StatusService().get_all_documents())"
```

## 🔒 Seguridad

- ✅ Rate limiting automático para OpenAI
- ✅ Validación robusta de API keys
- ✅ Pre-commit hooks para security scanning
- ✅ Secrets management con Google Secret Manager
- ✅ Validación de uploads de archivos

## 🤝 Desarrollo

### Setup para Desarrollo
```bash
# Instalar dependencias de desarrollo
pip install -e .[dev]

# Configurar pre-commit
pre-commit install

# Ejecutar linting
black .
isort .
flake8 .
```

### Estructura de Dependencias
- **Producción**: Solo dependencias core
- **UI**: + Streamlit
- **Dev**: + Testing, linting, security tools
- **Cloud**: + Functions framework
- **PDF**: + Marker para procesamiento PDF

## 🐛 Troubleshooting

### Problemas Comunes

**Error de autenticación GCP**
```bash
gcloud auth application-default login
```

**Marker PDF no funciona**
```bash
pip install marker-pdf
```

**Rate limit de OpenAI**
- Configurar `OPENAI_RATE_LIMIT` en `.env`
- Verificar límites en tu cuenta OpenAI

### Logs Útiles
```bash
# Cloud Function logs
gcloud functions logs read drcecim-process-document --region=us-central1

# Streamlit logs
# Aparecen en la terminal donde ejecutas streamlit
```

## 📚 Documentación

- [Configuración detallada](docs/configuration.md)
- [API Reference](docs/api.md)
- [Deployment Guide](docs/deployment.md)

## 📝 Changelog

### v1.0.0
- ✅ Refactorización completa con arquitectura modular
- ✅ Rate limiting para OpenAI
- ✅ Validaciones robustas de configuración
- ✅ Tests mejorados con cleanup apropiado
- ✅ Pre-commit hooks para calidad de código
- ✅ Documentación simplificada

---

**Desarrollado con ❤️ para la Facultad de Medicina UBA** 