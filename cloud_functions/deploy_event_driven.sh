#!/bin/bash

# =============================================================================
# SCRIPT DE DESPLIEGUE PARA ARQUITECTURA ORIENTADA A EVENTOS
# =============================================================================

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para imprimir mensajes coloreados
print_message() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar variables de entorno requeridas
check_required_vars() {
    print_message "Verificando variables de entorno..."
    
    if [[ -z "${GCF_PROJECT_ID}" ]]; then
        print_error "GCF_PROJECT_ID no está configurado"
        exit 1
    fi
    
    if [[ -z "${GCS_BUCKET_NAME}" ]]; then
        print_error "GCS_BUCKET_NAME no está configurado"
        exit 1
    fi
    
    print_success "Variables de entorno verificadas"
}

# Configurar variables
GCF_REGION=${GCF_REGION:-"us-central1"}
ENTRY_BUCKET_NAME="${GCS_BUCKET_NAME}"
PROCESSED_BUCKET_NAME="${GCS_BUCKET_NAME}"  # Mismo bucket, diferentes prefijos
SERVICE_ACCOUNT="chatbot-pipeline-sa@${GCF_PROJECT_ID}.iam.gserviceaccount.com"

print_message "==================================================================="
print_message "DESPLEGANDO ARQUITECTURA ORIENTADA A EVENTOS PARA DRCECIM UPLOAD"
print_message "==================================================================="
print_message "Proyecto: ${GCF_PROJECT_ID}"
print_message "Región: ${GCF_REGION}"
print_message "Bucket: ${GCS_BUCKET_NAME}"
print_message "Service Account: ${SERVICE_ACCOUNT}"
print_message "==================================================================="

# Verificar variables requeridas
check_required_vars

# Función 1: Procesar PDFs a chunks
print_message "Desplegando función 1: process-pdf-to-chunks..."

gcloud functions deploy process-pdf-to-chunks \
  --gen2 \
  --runtime=python311 \
  --region=${GCF_REGION} \
  --source=. \
  --entry-point=process_pdf_to_chunks \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=${ENTRY_BUCKET_NAME}" \
  --trigger-event-filters-path-pattern="*.pdf" \
  --service-account=${SERVICE_ACCOUNT} \
  --memory=1024MB \
  --timeout=540s \
  --max-instances=10 \
  --set-env-vars="GCS_BUCKET_NAME=${GCS_BUCKET_NAME},GCF_PROJECT_ID=${GCF_PROJECT_ID},ENVIRONMENT=production" \
  --project=${GCF_PROJECT_ID}

if [[ $? -eq 0 ]]; then
    print_success "Función process-pdf-to-chunks desplegada exitosamente"
else
    print_error "Error al desplegar process-pdf-to-chunks"
    exit 1
fi

# Función 2: Generar embeddings
print_message "Desplegando función 2: create-embeddings-from-chunks..."

gcloud functions deploy create-embeddings-from-chunks \
  --gen2 \
  --runtime=python311 \
  --region=${GCF_REGION} \
  --source=. \
  --entry-point=create_embeddings_from_chunks \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=${PROCESSED_BUCKET_NAME}" \
  --trigger-event-filters-path-pattern="processed/*_chunks.json" \
  --service-account=${SERVICE_ACCOUNT} \
  --memory=2048MB \
  --timeout=900s \
  --max-instances=5 \
  --set-env-vars="GCS_BUCKET_NAME=${GCS_BUCKET_NAME},GCF_PROJECT_ID=${GCF_PROJECT_ID},ENVIRONMENT=production" \
  --project=${GCF_PROJECT_ID}

if [[ $? -eq 0 ]]; then
    print_success "Función create-embeddings-from-chunks desplegada exitosamente"
else
    print_error "Error al desplegar create-embeddings-from-chunks"
    exit 1
fi

print_message "==================================================================="
print_success "DESPLIEGUE COMPLETADO"
print_message "==================================================================="

print_message "Funciones desplegadas:"
print_message "1. process-pdf-to-chunks: Se activa cuando se sube un PDF al bucket"
print_message "2. create-embeddings-from-chunks: Se activa cuando aparecen chunks procesados"
print_message ""
print_message "Para usar el nuevo sistema:"
print_message "1. Sube archivos PDF directamente al bucket: ${GCS_BUCKET_NAME}"
print_message "2. La función 1 los procesará automáticamente a chunks"
print_message "3. La función 2 generará embeddings y actualizará el índice FAISS"
print_message ""
print_warning "IMPORTANTE: Las funciones usan la cuenta de servicio asignada."
print_warning "No necesitas configurar GCS_CREDENTIALS_PATH en producción."
print_message ""
print_message "Para verificar el estado de las funciones:"
print_message "gcloud functions describe process-pdf-to-chunks --region=${GCF_REGION} --project=${GCF_PROJECT_ID}"
print_message "gcloud functions describe create-embeddings-from-chunks --region=${GCF_REGION} --project=${GCF_PROJECT_ID}" 