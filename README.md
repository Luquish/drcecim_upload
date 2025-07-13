# DrCecim Upload - Sistema de Procesamiento de Documentos

Sistema completo para cargar, procesar y almacenar documentos PDF para el chatbot DrCecim de la Facultad de Medicina UBA.

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamlit     │    │  Cloud Function │    │  Google Cloud   │
│   Frontend      │───▶│   Processing    │───▶│    Storage      │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   OpenAI API    │
                       │   Embeddings    │
                       └─────────────────┘
```

### Componentes Principales

1. **Streamlit Frontend** - Interfaz web para subir archivos PDF
2. **Google Cloud Function** - Procesamiento serverless de documentos
3. **Document Processor** - Convierte PDF a Markdown usando Marker
4. **Embedding Service** - Genera embeddings usando OpenAI
5. **GCS Service** - Almacena datos en Google Cloud Storage
6. **OpenAI Integration** - API para generación de embeddings

## 🚀 Características

- ✅ **Procesamiento Automático**: PDF → Markdown → Chunks → Embeddings → GCS
- ✅ **Interfaz Moderna**: Web UI con Streamlit
- ✅ **Arquitectura Serverless**: Google Cloud Functions
- ✅ **Almacenamiento Escalable**: Google Cloud Storage
- ✅ **Embeddings de Calidad**: OpenAI text-embedding-3-small
- ✅ **Búsqueda Vectorial**: Índices FAISS optimizados
- ✅ **Monitoreo**: Logs y métricas integradas

## 📁 Estructura del Proyecto

```
drcecim_upload/
├── config/
│   ├── __init__.py
│   └── settings.py              # Configuración central
├── services/
│   ├── __init__.py
│   ├── processing_service.py    # Procesamiento PDF
│   ├── embeddings_service.py    # Generación embeddings
│   └── gcs_service.py          # Google Cloud Storage
├── models/
│   ├── __init__.py
│   ├── base_model.py           # Clase base
│   └── openai_model.py         # Modelo OpenAI
├── cloud_functions/
│   ├── __init__.py
│   ├── main.py                 # Cloud Function principal
│   ├── requirements.txt        # Dependencias CF
│   ├── deployment_config.yaml  # Configuración deployment
│   └── deploy.sh              # Script de deployment
├── utils/
│   └── __init__.py
├── .streamlit/
│   ├── config.toml            # Configuración Streamlit
│   └── secrets.toml           # Secrets (no commitear)
├── streamlit_app.py           # Aplicación Streamlit
├── requirements.txt           # Dependencias principales
├── env.example               # Ejemplo variables entorno
├── .gitignore               # Archivos a ignorar
└── README.md               # Este archivo
```

## ⚙️ Instalación y Configuración

### 1. Requisitos Previos

- Python 3.11+
- Google Cloud SDK (`gcloud`)
- Cuenta de Google Cloud con facturación habilitada
- API Key de OpenAI
- Marker PDF instalado (`pip install marker-pdf`)

### 2. Configuración del Entorno

```bash
# Clonar el repositorio
git clone <repository-url>
cd drcecim_upload

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Configuración de Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp env.example .env

# Editar .env con tus valores
nano .env
```

Variables requeridas:
```bash
# Google Cloud
GCS_BUCKET_NAME=tu-bucket-name
GCS_CREDENTIALS_PATH=path/to/credentials.json
GCF_PROJECT_ID=tu-project-id
GCF_REGION=us-central1

# OpenAI
OPENAI_API_KEY=tu-api-key
EMBEDDING_MODEL=text-embedding-3-small

# Procesamiento
MAX_FILE_SIZE_MB=50
CHUNK_SIZE=250
CHUNK_OVERLAP=50
```

### 4. Configuración de Google Cloud

```bash
# Autenticarse con Google Cloud
gcloud auth login

# Configurar proyecto
gcloud config set project tu-project-id

# Crear bucket de GCS
gsutil mb gs://tu-bucket-name

# Habilitar APIs necesarias
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable storage.googleapis.com
```

## 🚀 Deployment

### 1. Desplegar Cloud Function

```bash
# Ir al directorio de Cloud Functions
cd cloud_functions

# Configurar variables de entorno
export OPENAI_API_KEY="tu-api-key"
export GCS_BUCKET_NAME="tu-bucket-name"
export GCF_PROJECT_ID="tu-project-id"

# Ejecutar script de deployment
./deploy.sh
```

### 2. Configurar Streamlit

```bash
# Editar secrets de Streamlit
nano .streamlit/secrets.toml

# Agregar URL de la Cloud Function
CLOUD_FUNCTION_URL = "https://us-central1-tu-project.cloudfunctions.net/drcecim-process-document"
```

### 3. Ejecutar Streamlit

```bash
# Ejecutar aplicación
streamlit run streamlit_app.py
```

## 📖 Uso

### 1. Subir Documento

1. Abrir la aplicación Streamlit en `http://localhost:8501`
2. Seleccionar un archivo PDF (máximo 50MB)
3. Verificar que el archivo sea válido
4. Hacer clic en "Procesar Documento"

### 2. Monitorear Procesamiento

El sistema mostrará el progreso en tiempo real:
- 🔄 Convirtiendo PDF a Markdown
- 🤖 Generando embeddings con OpenAI
- ☁️ Subiendo datos a Google Cloud Storage

### 3. Revisar Resultados

Una vez completado, verás:
- ✅ Estado del procesamiento
- 📊 Estadísticas del documento
- 📄 Información de chunks generados
- ☁️ Archivos almacenados en GCS

## 🔧 Configuración Avanzada

### Personalizar Chunk Size

```python
# En config/settings.py
CHUNK_SIZE = 500  # Palabras por chunk
CHUNK_OVERLAP = 100  # Solapamiento entre chunks
```

### Configurar Memory/Timeout de Cloud Function

```bash
# En cloud_functions/deploy.sh
MEMORY="2048Mi"
TIMEOUT="900s"  # 15 minutos
```

### Cambiar Modelo de Embeddings

```python
# En config/settings.py
EMBEDDING_MODEL = "text-embedding-3-large"  # Más preciso, más caro
```

## 📊 Monitoreo y Logs

### Cloud Function Logs

```bash
# Ver logs de la función
gcloud functions logs read drcecim-process-document --region=us-central1
```

### Streamlit Logs

Los logs aparecen en la terminal donde ejecutas Streamlit.

### Google Cloud Storage

```bash
# Listar archivos procesados
gsutil ls gs://tu-bucket-name/embeddings/
gsutil ls gs://tu-bucket-name/metadata/
```

## 🐛 Troubleshooting

### Problemas Comunes

1. **Error de autenticación de Google Cloud**
   ```bash
   gcloud auth application-default login
   ```

2. **Timeout en Cloud Function**
   - Aumentar timeout en deploy.sh
   - Verificar tamaño del archivo PDF

3. **Error de API Key de OpenAI**
   - Verificar que la API Key sea válida
   - Revisar límites de uso

4. **Marker PDF no funciona**
   ```bash
   pip install marker-pdf
   # Verificar que marker_single esté en PATH
   ```

### Logs Útiles

```bash
# Logs de Cloud Function
gcloud functions logs read drcecim-process-document

# Logs de Cloud Build
gcloud builds log <BUILD_ID>

# Status de APIs
gcloud services list --enabled
```

## 🔒 Seguridad

### Variables Sensibles

- ❌ **Nunca commites** archivos `.env` o `secrets.toml`
- ✅ **Usa** service accounts para producción
- ✅ **Restringe** acceso a buckets de GCS
- ✅ **Rota** API keys regularmente

### Acceso a Cloud Function

```bash
# Restringir acceso (para producción)
gcloud functions deploy drcecim-process-document \
  --no-allow-unauthenticated
```

## 🤝 Contribuir

1. Fork el repositorio
2. Crear feature branch (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push branch (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📚 Documentación Adicional

- [Google Cloud Functions](https://cloud.google.com/functions/docs)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Marker PDF](https://github.com/VikParuchuri/marker)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)

## 📝 Licencia

Este proyecto está bajo la licencia MIT. Ver `LICENSE` para más detalles.

## 🆘 Soporte

Para soporte técnico:
- 📧 Email: tu-email@dominio.com
- 💬 Issues: GitHub Issues
- 📚 Wiki: GitHub Wiki

---

**Desarrollado con ❤️ para la Facultad de Medicina UBA** 