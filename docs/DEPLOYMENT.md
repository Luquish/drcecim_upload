# Guía de Deployment - DrCecim Upload

Esta guía detalla el proceso completo de deployment del sistema DrCecim Upload.

## 🚀 Pre-requisitos

### 1. Herramientas Requeridas

- **Python 3.11+**
- **Google Cloud SDK (gcloud)**
- **Git**
- **Terminal/Command Line**

### 2. Cuentas y Permisos

- **Cuenta de Google Cloud** con facturación habilitada
- **Permisos de administrador** en el proyecto de Google Cloud
- **API Key de OpenAI** válida

### 3. Configuración Inicial

Asegúrate de tener las siguientes APIs habilitadas en Google Cloud:

```bash
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable storage.googleapis.com
```

## 📋 Pasos de Deployment

### Paso 1: Preparación del Entorno

```bash
# Clonar el repositorio
git clone <repository-url>
cd drcecim_upload

# Ejecutar configuración automática
chmod +x setup.sh
./setup.sh
```

El script de setup te guiará a través de la configuración inicial.

### Paso 2: Configuración Manual (Opcional)

Si prefieres configurar manualmente:

```bash
# Crear archivo .env
cp env.example .env

# Editar variables
nano .env
```

Variables importantes:
```bash
GCS_BUCKET_NAME=tu-bucket-name
GCF_PROJECT_ID=tu-project-id
OPENAI_API_KEY=tu-api-key
```

### Paso 3: Deployment de Cloud Function

```bash
# Ir al directorio de Cloud Functions
cd cloud_functions

# Configurar variables de entorno para deployment
export OPENAI_API_KEY="tu-openai-api-key"
export GCS_BUCKET_NAME="tu-bucket-name"
export GCF_PROJECT_ID="tu-project-id"

# Ejecutar deployment
chmod +x deploy.sh
./deploy.sh
```

### Paso 4: Configurar Streamlit

```bash
# Volver al directorio principal
cd ..

# Editar secrets de Streamlit
nano .streamlit/secrets.toml

# Actualizar con la URL de la Cloud Function
CLOUD_FUNCTION_URL = "https://us-central1-TU-PROJECT.cloudfunctions.net/drcecim-process-document"
```

### Paso 5: Ejecutar Streamlit

```bash
# Activar entorno virtual
source venv/bin/activate

# Ejecutar Streamlit
streamlit run streamlit_app.py
```

## 🏭 Deployment en Producción

### 1. Streamlit Cloud

Para deployar en Streamlit Cloud:

1. **Fork el repositorio** en GitHub
2. **Conectar con Streamlit Cloud**
3. **Configurar secrets** en la interfaz web:
   ```toml
   CLOUD_FUNCTION_URL = "https://..."
   ```

### 2. Google Cloud Run

Para deployar Streamlit en Cloud Run:

```bash
# Crear Dockerfile para Streamlit
cat > Dockerfile << EOF
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0"]
EOF

# Construir y deployar
gcloud builds submit --tag gcr.io/TU-PROJECT/drcecim-upload
gcloud run deploy drcecim-upload --image gcr.io/TU-PROJECT/drcecim-upload --platform managed
```

## 🔒 Configuración de Seguridad

### 1. Restringir Acceso a Cloud Function

```bash
# Quitar acceso público
gcloud functions remove-iam-policy-binding drcecim-process-document \
  --member="allUsers" \
  --role="roles/cloudfunctions.invoker"

# Agregar acceso específico
gcloud functions add-iam-policy-binding drcecim-process-document \
  --member="user:tu-email@dominio.com" \
  --role="roles/cloudfunctions.invoker"
```

### 2. Configurar VPC (Opcional)

```bash
# Crear VPC connector
gcloud compute networks vpc-access connectors create drcecim-connector \
  --network default \
  --region us-central1 \
  --range 10.8.0.0/28

# Deployar con VPC
gcloud functions deploy drcecim-process-document \
  --vpc-connector drcecim-connector
```

## 📊 Monitoreo

### 1. Logs de Cloud Function

```bash
# Ver logs en tiempo real
gcloud functions logs tail drcecim-process-document

# Ver logs históricos
gcloud functions logs read drcecim-process-document --limit 50
```

### 2. Métricas

Accede a las métricas en:
- **Cloud Function**: `https://tu-function-url/metrics`
- **Google Cloud Console**: Monitoring > Metrics Explorer

### 3. Alertas

Configura alertas para:
- Errores en Cloud Function
- Latencia alta
- Uso excesivo de recursos

## 🐛 Troubleshooting

### Errores Comunes

1. **Error de autenticación**
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

2. **Timeout en Cloud Function**
   - Aumentar timeout en `deploy.sh`
   - Verificar tamaño del archivo

3. **Error de permisos en GCS**
   ```bash
   gsutil iam ch user:tu-email@dominio.com:admin gs://tu-bucket
   ```

4. **Marker PDF no funciona**
   ```bash
   pip uninstall marker-pdf
   pip install marker-pdf
   ```

### Verificación Post-Deployment

```bash
# Test de Cloud Function
curl -X POST "https://tu-function-url/health"

# Test de métricas
curl -X GET "https://tu-function-url/metrics"

# Test de Streamlit
curl -I http://localhost:8501
```

## 📝 Checklist de Deployment

- [ ] Configuración inicial completada
- [ ] Variables de entorno configuradas
- [ ] APIs de Google Cloud habilitadas
- [ ] Bucket de GCS creado
- [ ] Cloud Function desplegada
- [ ] Streamlit configurado
- [ ] Tests básicos pasados
- [ ] Monitoreo configurado
- [ ] Documentación actualizada

## 🔄 Actualizaciones

Para actualizar el sistema:

```bash
# Actualizar código
git pull origin main

# Re-deployar Cloud Function
cd cloud_functions
./deploy.sh

# Reiniciar Streamlit
# (automático en Streamlit Cloud)
```

## 📞 Soporte

Si encuentras problemas:

1. **Revisar logs** de Cloud Function
2. **Verificar configuración** en `.env`
3. **Consultar troubleshooting** arriba
4. **Crear issue** en GitHub
5. **Contactar soporte** técnico

---

**Nota**: Esta guía asume un environment de producción. Para desarrollo, algunos pasos pueden simplificarse. 