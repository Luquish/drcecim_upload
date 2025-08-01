# Cloud Functions - Estructura Optimizada

## Descripción

Este directorio contiene las Google Cloud Functions para el sistema DrCecim, organizadas siguiendo las mejores prácticas para evitar duplicación de código y mantener una estructura clara y eficiente.

## Estructura del Proyecto

```
cloud_functions/
├── common/                          # Código compartido entre funciones
│   ├── config/                      # Configuraciones compartidas
│   ├── services/                    # Servicios compartidos
│   ├── utils/                       # Utilidades compartidas
│   ├── models/                      # Modelos compartidos
│   ├── credentials/                 # Credenciales compartidas
│   └── requirements.txt             # Dependencias comunes
├── process_pdf/                     # Cloud Function para procesar PDFs
│   ├── main.py                      # Entry point de la función
│   └── requirements.txt             # Dependencias específicas
├── create_embeddings/               # Cloud Function para generar embeddings
│   ├── main.py                      # Entry point de la función
│   └── requirements.txt             # Dependencias específicas
├── .gcloudignore                    # Archivos excluidos del deployment
└── deploy_event_driven.sh          # Script de deployment
```

## Mejoras Implementadas

### ✅ Eliminación de Duplicación
- **Antes**: Cada Cloud Function tenía su propia copia de `config/`, `services/`, `utils/`, y `models/`
- **Después**: Todo el código compartido está en el directorio `common/`

### ✅ Gestión de Dependencias Optimizada
- **Dependencias comunes**: Centralizadas en `common/requirements.txt`
- **Dependencias específicas**: Cada función solo incluye sus dependencias únicas
- **Referencias**: Los `requirements.txt` específicos incluyen las dependencias comunes con `-r ../common/requirements.txt`

### ✅ Imports Actualizados
- Todos los imports en `main.py` apuntan al directorio `common/`
- Mantiene compatibilidad con fallbacks para desarrollo local

## Cloud Functions

### 1. process_pdf
**Función**: Procesa documentos PDF y genera chunks de texto
**Trigger**: Cloud Storage (eventos de subida de archivos PDF)
**Dependencias específicas**: `marker-pdf`

### 2. create_embeddings
**Función**: Genera embeddings y los almacena en PostgreSQL
**Trigger**: Cloud Storage (eventos de archivos de chunks procesados)
**Dependencias específicas**: `openai`, `numpy`, `pgvector`, `sqlalchemy`

## Deployment

### Deployment Individual
```bash
# Deploy process_pdf
gcloud functions deploy process_pdf_to_chunks \
  --runtime python311 \
  --trigger-event google.storage.object.finalize \
  --trigger-resource YOUR_BUCKET \
  --source process_pdf/

# Deploy create_embeddings
gcloud functions deploy create_embeddings_from_chunks \
  --runtime python311 \
  --trigger-event google.storage.object.finalize \
  --trigger-resource YOUR_BUCKET \
  --source create_embeddings/
```

### Deployment con Script
```bash
./deploy_event_driven.sh
```

## Beneficios de la Nueva Estructura

1. **Mantenibilidad**: Cambios en código compartido se aplican a todas las funciones
2. **Consistencia**: Configuración y servicios uniformes entre funciones
3. **Eficiencia**: Menor tamaño de deployment y tiempos de build más rápidos
4. **Escalabilidad**: Fácil agregar nuevas Cloud Functions sin duplicar código
5. **Cumplimiento**: Sigue las mejores prácticas de Google Cloud Functions

## Configuración de Variables de Entorno

### 📁 Ubicación del Archivo .env
- **Ubicación**: `.env` está en el directorio raíz de `cloud_functions/`
- **Compartido**: Todas las Cloud Functions acceden al mismo archivo
- **Seguridad**: Excluido del deployment por `.gcloudignore`

### 🔧 Configuración
1. **Desarrollo local**: Copia `.env.example` a `.env` y configura tus valores
2. **Deployment**: Las variables se pasan como parámetros de entorno
3. **Producción**: Google Cloud Functions usa las variables configuradas

### 📋 Variables Requeridas
```bash
# Google Cloud
GCS_BUCKET_NAME=tu-bucket-name
GCF_REGION=us-central1
GCF_PROJECT_ID=tu-project-id

# OpenAI
OPENAI_API_KEY=sk-proj-tu-api-key-aqui
EMBEDDING_MODEL=text-embedding-3-small
API_TIMEOUT=30

# Procesamiento
CHUNK_SIZE=250
CHUNK_OVERLAP=50

# Logging
LOG_LEVEL=INFO
ENVIRONMENT=development
```

## Notas de Desarrollo

- El directorio `common/` se incluye automáticamente en el deployment
- Los imports usan rutas relativas para compatibilidad con diferentes entornos
- Se mantienen fallbacks para desarrollo local y testing
- El archivo `.env` está excluido del deployment por seguridad 