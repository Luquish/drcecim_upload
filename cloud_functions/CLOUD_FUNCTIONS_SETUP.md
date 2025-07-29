# 🚀 Implementación de Cloud Functions - DrCecim Upload

## 📋 Resumen de lo que estamos haciendo

### 🎯 Objetivo Principal
Estamos implementando las **Cloud Functions de Google Cloud** para automatizar el procesamiento de PDFs. Esto solucionará los warnings que aparecen:

```
WARN[0000] The "CLOUD_FUNCTION_URL" variable is not set. Defaulting to a blank string. 
WARN[0000] The "EMBEDDINGS_FUNCTION_URL" variable is not set. Defaulting to a blank string.
```

### 🏗️ Arquitectura que estamos desplegando

1. **`process-pdf-to-chunks`**: Se activa cuando subes un PDF al bucket
   - Convierte PDF → Chunks de texto
   - Guarda chunks en `processed/archivo_chunks.json`

2. **`create-embeddings-from-chunks`**: Se activa cuando aparecen chunks
   - Convierte chunks → Embeddings (vectores)
   - Actualiza el índice FAISS
   - Guarda metadata

### ❌ Problema Actual
El deployment falló porque el servicio **Eventarc** (que maneja los triggers) no tiene permisos para acceder al bucket `drcecim-chatbot-storage`.

**Error específico:**
```
Permission "storage.buckets.get" denied on "Bucket \"drcecim-chatbot-storage\""
```

## 🔧 Solución

### Paso 1: Dar permisos al servicio Eventarc

**Opción A: Comando automático (Recomendado)**
```bash
gcloud projects add-iam-policy-binding drcecim-465823 --member="serviceAccount:service-1096862351778@gcp-sa-eventarc.iam.gserviceaccount.com" --role="roles/storage.objectViewer"
```

**Opción B: Manual desde Google Cloud Console**
1. Ve a [Google Cloud Console](https://console.cloud.google.com)
2. Navega a **IAM & Admin** → **IAM**
3. Busca la cuenta `service-1096862351778@gcp-sa-eventarc.iam.gserviceaccount.com`
4. Agrega el rol **Storage Object Viewer**

### Paso 2: Desplegar las Cloud Functions
```bash
cd cloud_functions
./deploy_event_driven.sh
```

### Paso 3: Actualizar variables de entorno
Después del deployment exitoso, actualiza tu archivo `.env` con las URLs generadas:

```bash
# URLs de Cloud Functions (se generan después del deployment)
CLOUD_FUNCTION_URL=https://us-central1-drcecim-465823.cloudfunctions.net/process-pdf-to-chunks
EMBEDDINGS_FUNCTION_URL=https://us-central1-drcecim-465823.cloudfunctions.net/create-embeddings-from-chunks
```

## ✅ Resultado Final

- Los warnings desaparecerán
- El sistema será completamente automático
- Subirás PDFs y se procesarán automáticamente
- Los chunks y vectores se guardarán en GCS automáticamente

## 🔄 Flujo Automático

1. **Subir PDF** → Bucket GCS
2. **Trigger automático** → `process-pdf-to-chunks`
3. **Generar chunks** → `processed/archivo_chunks.json`
4. **Trigger automático** → `create-embeddings-from-chunks`
5. **Generar embeddings** → Actualizar FAISS index
6. **Listo para usar** → Chatbot puede usar los nuevos datos

## 📁 Estructura de archivos en GCS

```
drcecim-chatbot-storage/
├── processed/
│   └── archivo_chunks.json
├── embeddings/
│   ├── faiss_index.bin
│   └── metadata.csv
└── metadata/
    └── config.json
```

## 🛠️ Comandos útiles

### Verificar estado de las funciones
```bash
gcloud functions describe process-pdf-to-chunks --region=us-central1 --project=drcecim-465823
gcloud functions describe create-embeddings-from-chunks --region=us-central1 --project=drcecim-465823
```

### Ver logs de las funciones
```bash
gcloud functions logs read process-pdf-to-chunks --region=us-central1 --project=drcecim-465823
gcloud functions logs read create-embeddings-from-chunks --region=us-central1 --project=drcecim-465823
```

### Eliminar funciones (si necesitas redeployar)
```bash
gcloud functions delete process-pdf-to-chunks --region=us-central1 --project=drcecim-465823
gcloud functions delete create-embeddings-from-chunks --region=us-central1 --project=drcecim-465823
```

## 🔐 Variables de entorno requeridas

```bash
# Google Cloud (REQUERIDO)
GCF_PROJECT_ID=drcecim-465823
GCS_BUCKET_NAME=drcecim-chatbot-storage
GCF_REGION=us-central1

# OpenAI (REQUERIDO)
OPENAI_API_KEY=sk-proj-tu-api-key-aqui

# URLs de Cloud Functions (se generan después del deployment)
CLOUD_FUNCTION_URL=https://us-central1-drcecim-465823.cloudfunctions.net/process-pdf-to-chunks
EMBEDDINGS_FUNCTION_URL=https://us-central1-drcecim-465823.cloudfunctions.net/create-embeddings-from-chunks
```

## 📝 Notas importantes

- Las Cloud Functions usan la cuenta de servicio `chatbot-pipeline-sa@drcecim-465823.iam.gserviceaccount.com`
- No necesitas configurar `GCS_CREDENTIALS_PATH` en producción
- Las funciones se activan automáticamente cuando se suben archivos al bucket
- El procesamiento es asíncrono y puede tomar varios minutos
- Los logs se pueden ver en Google Cloud Console → Cloud Functions → Logs 