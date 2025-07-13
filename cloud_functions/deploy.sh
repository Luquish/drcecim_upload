#!/bin/bash

# =============================================================================
# SCRIPT DE DEPLOYMENT PARA GOOGLE CLOUD FUNCTIONS
# =============================================================================

set -e  # Salir en caso de error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para logging
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuración (editables)
FUNCTION_NAME="drcecim-process-document"
ENTRY_POINT="process_document"
RUNTIME="python312"
REGION="us-central1"
MEMORY="1024Mi"
TIMEOUT="540s"
MAX_INSTANCES="10"
MIN_INSTANCES="0"

# Verificar que estamos en el directorio correcto
if [ ! -f "main.py" ] || [ ! -f "requirements.txt" ]; then
    error "Este script debe ejecutarse desde el directorio cloud_functions/"
    error "Archivos requeridos: main.py, requirements.txt"
    exit 1
fi

# Verificar que gcloud esté instalado
if ! command -v gcloud &> /dev/null; then
    error "gcloud CLI no está instalado"
    error "Instala gcloud CLI desde: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Verificar que el usuario esté autenticado
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    error "No hay una cuenta activa en gcloud"
    error "Ejecuta: gcloud auth login"
    exit 1
fi

# Obtener el proyecto actual
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    error "No hay un proyecto configurado en gcloud"
    error "Ejecuta: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

log "Proyecto actual: $PROJECT_ID"

# Verificar que las APIs estén habilitadas
log "Verificando APIs necesarias..."
APIS=("cloudfunctions.googleapis.com" "cloudbuild.googleapis.com" "storage.googleapis.com")

for API in "${APIS[@]}"; do
    if gcloud services list --enabled --filter="name:$API" --format="value(name)" | grep -q "$API"; then
        log "✓ API habilitada: $API"
    else
        warn "API no habilitada: $API"
        log "Habilitando API: $API"
        gcloud services enable "$API"
    fi
done

# Verificar variables de entorno requeridas
log "Verificando variables de entorno..."
REQUIRED_VARS=("OPENAI_API_KEY" "GCS_BUCKET_NAME" "GCF_PROJECT_ID")
MISSING_VARS=()

for VAR in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!VAR}" ]; then
        MISSING_VARS+=("$VAR")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    error "Variables de entorno faltantes:"
    for VAR in "${MISSING_VARS[@]}"; do
        error "  - $VAR"
    done
    error "Configura las variables de entorno antes del deployment"
    exit 1
fi

# Verificar que el bucket existe
log "Verificando bucket de GCS: $GCS_BUCKET_NAME"
if ! gsutil ls "gs://$GCS_BUCKET_NAME" &> /dev/null; then
    error "El bucket gs://$GCS_BUCKET_NAME no existe o no tienes permisos"
    error "Crea el bucket con: gsutil mb gs://$GCS_BUCKET_NAME"
    exit 1
fi

# Crear directorio de deployment temporal
TEMP_DIR=$(mktemp -d)
log "Directorio temporal: $TEMP_DIR"

# Función de limpieza
cleanup() {
    log "Limpiando archivos temporales..."
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# Copiar archivos necesarios
log "Preparando archivos para deployment..."
cp -r ../config "$TEMP_DIR/"
cp -r ../services "$TEMP_DIR/"
cp -r ../models "$TEMP_DIR/"
cp -r ../utils "$TEMP_DIR/"
cp main.py "$TEMP_DIR/"
cp requirements.txt "$TEMP_DIR/"

# Crear archivo .gcloudignore
cat > "$TEMP_DIR/.gcloudignore" << EOF
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
env*/
venv*/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
logs/
*.log

# Temporary files
temp/
tmp/
*.tmp

# Documentation
*.md
docs/

# Tests
test/
tests/
*_test.py
test_*.py

# Environment files
.env
.env.local
.env.*.local

# Git
.git/
.gitignore
EOF

# Construir comando de deployment
DEPLOY_CMD="gcloud functions deploy $FUNCTION_NAME"
DEPLOY_CMD+=" --gen2"
DEPLOY_CMD+=" --runtime=$RUNTIME"
DEPLOY_CMD+=" --region=$REGION"
DEPLOY_CMD+=" --source=$TEMP_DIR"
DEPLOY_CMD+=" --entry-point=$ENTRY_POINT"
DEPLOY_CMD+=" --memory=$MEMORY"
DEPLOY_CMD+=" --timeout=$TIMEOUT"
DEPLOY_CMD+=" --max-instances=$MAX_INSTANCES"
DEPLOY_CMD+=" --min-instances=$MIN_INSTANCES"
DEPLOY_CMD+=" --trigger-http"
DEPLOY_CMD+=" --allow-unauthenticated"
DEPLOY_CMD+=" --set-env-vars="
DEPLOY_CMD+="OPENAI_API_KEY=$OPENAI_API_KEY,"
DEPLOY_CMD+="GCS_BUCKET_NAME=$GCS_BUCKET_NAME,"
DEPLOY_CMD+="GCF_PROJECT_ID=$GCF_PROJECT_ID,"
DEPLOY_CMD+="ENVIRONMENT=production,"
DEPLOY_CMD+="LOG_LEVEL=INFO,"
DEPLOY_CMD+="MAX_FILE_SIZE_MB=50,"
DEPLOY_CMD+="CHUNK_SIZE=250,"
DEPLOY_CMD+="CHUNK_OVERLAP=50,"
DEPLOY_CMD+="EMBEDDING_MODEL=text-embedding-3-small,"
DEPLOY_CMD+="TEMP_DIR=/tmp/drcecim_processing"

# Mostrar información del deployment
log "=== INFORMACIÓN DEL DEPLOYMENT ==="
log "Función: $FUNCTION_NAME"
log "Proyecto: $PROJECT_ID"
log "Región: $REGION"
log "Runtime: $RUNTIME"
log "Memoria: $MEMORY"
log "Timeout: $TIMEOUT"
log "Bucket: $GCS_BUCKET_NAME"
log "================================="

# Confirmar deployment
read -p "¿Proceder con el deployment? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log "Deployment cancelado por el usuario"
    exit 0
fi

# Ejecutar deployment
log "Iniciando deployment de Cloud Function..."
eval "$DEPLOY_CMD"

if [ $? -eq 0 ]; then
    log "✓ Deployment completado exitosamente"
    
    # Obtener URL de la función
    FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" --region="$REGION" --format="value(serviceConfig.uri)")
    
    log "=== DEPLOYMENT COMPLETADO ==="
    log "URL de la función: $FUNCTION_URL"
    log "Health check: $FUNCTION_URL/health"
    log "Región: $REGION"
    log "Proyecto: $PROJECT_ID"
    log "============================="
    
    # Test básico de health check
    log "Probando health check..."
    if curl -s -f "$FUNCTION_URL/health" > /dev/null; then
        log "✓ Health check exitoso"
    else
        warn "Health check falló - verifica los logs"
    fi
    
else
    error "Deployment falló"
    exit 1
fi

log "Deployment completado. Revisa los logs en Google Cloud Console si hay problemas." 