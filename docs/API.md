# API Documentation - DrCecim Upload

Documentación completa de la API de Google Cloud Functions para el sistema DrCecim Upload.

## 📡 Base URL

```
https://us-central1-[PROJECT_ID].cloudfunctions.net/drcecim-process-document
```

## 🔗 Endpoints

### 1. Procesar Documento

**Endpoint principal para procesar archivos PDF.**

```http
POST /
```

#### Headers

| Header | Valor | Requerido |
|--------|--------|-----------|
| Content-Type | multipart/form-data | ✅ |

#### Request Body

| Campo | Tipo | Descripción | Requerido |
|-------|------|-------------|-----------|
| file | File | Archivo PDF a procesar | ✅ |

#### Validaciones

- **Tipo de archivo**: Solo PDF
- **Tamaño máximo**: 50MB
- **Nombre**: Debe tener extensión .pdf

#### Response Success (200)

```json
{
  "success": true,
  "message": "Documento procesado exitosamente",
  "filename": "documento.pdf",
  "stats": {
    "num_chunks": 45,
    "total_words": 2150,
    "embedding_dimension": 1536,
    "num_vectors": 45
  },
  "gcs_files": {
    "faiss_index": "gs://bucket/embeddings/faiss_index.bin",
    "metadata": "gs://bucket/metadata/metadata.csv",
    "config": "gs://bucket/metadata/config.json"
  },
  "processing_time": "completado",
  "session_id": "proc_1672531200"
}
```

#### Response Error (400)

```json
{
  "error": "Tipo de archivo no permitido. Solo se permiten: pdf"
}
```

#### Response Error (500)

```json
{
  "error": "Error al procesar documento: mensaje específico del error"
}
```

### 2. Health Check

**Endpoint para verificar el estado de la función.**

```http
GET /health
```

#### Response Success (200)

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00.000Z",
  "services": {
    "document_processor": "available",
    "embedding_service": "available",
    "gcs_service": "available"
  },
  "config": {
    "bucket_name": "drcecim-chatbot-storage",
    "max_file_size_mb": 50,
    "allowed_file_types": ["pdf"]
  }
}
```

#### Response Error (500)

```json
{
  "status": "unhealthy",
  "error": "mensaje de error específico"
}
```

### 3. Métricas

**Endpoint para obtener métricas del sistema.**

```http
GET /metrics
```

#### Response Success (200)

```json
{
  "system": {
    "metrics": {
      "documents_processing_started": {
        "type": "counter",
        "value": 25,
        "labels": {}
      },
      "documents_processed": {
        "type": "counter", 
        "value": 23,
        "labels": {"status": "success"}
      },
      "processing_time_seconds": {
        "type": "histogram",
        "values": [
          {"value": 45.2, "timestamp": 1672531200},
          {"value": 38.1, "timestamp": 1672531260}
        ],
        "labels": {}
      }
    },
    "system": {
      "uptime": 3600,
      "timestamp": "2024-01-01T12:00:00.000Z"
    }
  },
  "processing": {
    "active_sessions": 1,
    "completed_sessions": 23,
    "total_sessions": 24,
    "sessions": {
      "proc_1672531200": {
        "filename": "documento.pdf",
        "start_time": 1672531200,
        "status": "completed",
        "steps": [...]
      }
    }
  },
  "health": "healthy",
  "timestamp": "2024-01-01T12:00:00.000Z"
}
```

## 📊 Códigos de Estado

| Código | Descripción |
|--------|-------------|
| 200 | Éxito |
| 400 | Error en la solicitud (archivo inválido, etc.) |
| 405 | Método no permitido |
| 500 | Error interno del servidor |

## 🔧 Ejemplos de Uso

### cURL

```bash
# Procesar documento
curl -X POST \
  -F "file=@documento.pdf" \
  https://us-central1-[PROJECT_ID].cloudfunctions.net/drcecim-process-document

# Health check
curl -X GET \
  https://us-central1-[PROJECT_ID].cloudfunctions.net/drcecim-process-document/health

# Métricas
curl -X GET \
  https://us-central1-[PROJECT_ID].cloudfunctions.net/drcecim-process-document/metrics
```

### Python (requests)

```python
import requests

# Procesar documento
url = "https://us-central1-[PROJECT_ID].cloudfunctions.net/drcecim-process-document"
files = {'file': open('documento.pdf', 'rb')}

response = requests.post(url, files=files)
result = response.json()

if response.status_code == 200:
    print(f"Procesado exitosamente: {result['stats']['num_chunks']} chunks")
else:
    print(f"Error: {result.get('error', 'Error desconocido')}")
```

### JavaScript (fetch)

```javascript
// Procesar documento
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('https://us-central1-[PROJECT_ID].cloudfunctions.net/drcecim-process-document', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  if (data.success) {
    console.log(`Procesado: ${data.stats.num_chunks} chunks`);
  } else {
    console.error(`Error: ${data.error}`);
  }
});
```

## 🔒 Autenticación

### Desarrollo

Por defecto, la función permite acceso público (`--allow-unauthenticated`).

### Producción

Para restringir acceso:

```bash
# Quitar acceso público
gcloud functions remove-iam-policy-binding drcecim-process-document \
  --member="allUsers" \
  --role="roles/cloudfunctions.invoker"

# Agregar usuario específico
gcloud functions add-iam-policy-binding drcecim-process-document \
  --member="user:usuario@dominio.com" \
  --role="roles/cloudfunctions.invoker"
```

Para usar con autenticación:

```bash
# Obtener token
gcloud auth print-identity-token

# Usar token en request
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -F "file=@documento.pdf" \
  https://us-central1-[PROJECT_ID].cloudfunctions.net/drcecim-process-document
```

## ⚡ Límites y Consideraciones

### Límites de Cloud Functions

| Recurso | Límite |
|---------|--------|
| Timeout máximo | 9 minutos |
| Memoria máxima | 8GB |
| Tamaño máximo request | 32MB |
| Instancias concurrentes | 1000 |

### Límites del Sistema

| Recurso | Límite |
|---------|--------|
| Tamaño archivo PDF | 50MB |
| Tipos de archivo | Solo PDF |
| Procesamiento concurrente | 1 por instancia |

### Recomendaciones

- **Archivos grandes**: Dividir en chunks más pequeños
- **Alto volumen**: Considerar usar Cloud Run para mayor concurrencia
- **Latencia**: Usar mínimo de instancias calientes en producción

## 📈 Monitoreo

### Métricas Disponibles

| Métrica | Tipo | Descripción |
|---------|------|-------------|
| `documents_processing_started` | Counter | Documentos que iniciaron procesamiento |
| `documents_processed` | Counter | Documentos completados (success/error) |
| `processing_time_seconds` | Histogram | Tiempo de procesamiento |
| `function_calls` | Counter | Llamadas a funciones internas |
| `function_errors` | Counter | Errores en funciones |

### Logs Estructurados

Todos los logs incluyen:

```json
{
  "severity": "INFO",
  "timestamp": "2024-01-01T12:00:00.000Z",
  "message": "Mensaje del log",
  "context": {
    "session_id": "proc_1672531200",
    "filename": "documento.pdf",
    "step": "pdf_processing"
  }
}
```

## 🐛 Troubleshooting

### Errores Comunes

1. **"Tipo de archivo no permitido"**
   - Verificar que el archivo sea .pdf
   - Revisar Content-Type del request

2. **"Timeout"**
   - Reducir tamaño del archivo
   - Verificar configuración de timeout

3. **"Error al procesar documento"**
   - Revisar logs detallados
   - Verificar que el PDF no esté corrupto

4. **"Error interno del servidor"**
   - Revisar métricas de la función
   - Verificar configuración de variables de entorno

### Debug

```bash
# Ver logs en tiempo real
gcloud functions logs tail drcecim-process-document

# Ver métricas específicas
curl https://[FUNCTION_URL]/metrics | jq '.processing'
```

---

**Nota**: Reemplaza `[PROJECT_ID]` con tu ID de proyecto de Google Cloud. 