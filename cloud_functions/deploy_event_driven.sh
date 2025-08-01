#!/bin/bash

# =============================================================================
# SCRIPT DE DESPLIEGUE PARA ARQUITECTURA MONOREPO
# =============================================================================

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Funciones de Utilidad ---
print_message() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Cargar configuración desde archivo .env
load_config_from_env() {
    print_message "Cargando configuración desde archivo .env..."
    
    # Verificar que existe el archivo .env
    if [[ ! -f ".env" ]]; then
        print_error "Archivo .env no encontrado en el directorio actual"
        exit 1
    fi
    
    # Cargar variables desde .env (excluyendo comentarios y líneas vacías)
    while IFS='=' read -r key value; do
        # Ignorar comentarios y líneas vacías
        if [[ -n "$key" && ! "$key" =~ ^# && -n "$value" ]]; then
            export "$key=$value"
        fi
    done < ".env"
    
    print_success "Configuración cargada exitosamente desde .env"
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
    
    if [[ -z "${OPENAI_API_KEY}" ]]; then
        print_error "OPENAI_API_KEY no está configurado"
        exit 1
    fi
    
    print_success "Variables de entorno verificadas"
}

# Verificar estructura monorepo
check_monorepo_structure() {
    print_message "Verificando estructura monorepo..."
    
    # Verificar que existe el archivo main.py
    if [[ ! -f "main.py" ]]; then
        print_error "Archivo main.py no encontrado"
        exit 1
    fi
    
    # Verificar que existe el archivo requirements.txt
    if [[ ! -f "requirements.txt" ]]; then
        print_error "Archivo requirements.txt no encontrado"
        exit 1
    fi
    
    # Verificar que existe el directorio common
    if [[ ! -d "common" ]]; then
        print_error "Directorio common no encontrado"
        exit 1
    fi
    
    print_success "Estructura monorepo verificada"
}

# =============================================================================
# Verifica si una función existe y la borra si es necesario.
# =============================================================================
delete_if_exists() {
    local func_name=$1
    print_message "Verificando si la función '${func_name}' ya existe en la región ${GCF_REGION}..."

    # El comando 'describe' falla si la función no existe.
    # Redirigimos la salida para evitar mensajes de error en la consola.
    if gcloud functions describe "${func_name}" --region "${GCF_REGION}" --project "${GCF_PROJECT_ID}" > /dev/null 2>&1; then
        print_warning "La función '${func_name}' ya existe. Se procederá a eliminarla..."
        
        # El flag --quiet evita la confirmación interactiva (y/N).
        gcloud functions delete "${func_name}" \
          --region "${GCF_REGION}" \
          --project "${GCF_PROJECT_ID}" \
          --quiet

        if [[ $? -eq 0 ]]; then
            print_success "Función '${func_name}' eliminada exitosamente."
        else
            print_error "Ocurrió un error al eliminar la función '${func_name}'."
            exit 1
        fi
    else
        print_message "La función '${func_name}' no existe. Se procederá con la creación."
    fi
}

# Cargar configuración
load_config_from_env

# Configurar variables
ENTRY_BUCKET_NAME="${GCS_BUCKET_NAME}"
PROCESSED_BUCKET_NAME="${GCS_BUCKET_NAME}"  # Mismo bucket, diferentes prefijos
SERVICE_ACCOUNT="data-pipeline-serviceaccount@${GCF_PROJECT_ID}.iam.gserviceaccount.com"

print_message "==================================================================="
print_message "DESPLEGANDO ARQUITECTURA MONOREPO PARA DRCECIM UPLOAD"
print_message "==================================================================="
print_message "Proyecto: ${GCF_PROJECT_ID}"
print_message "Región: ${GCF_REGION}"
print_message "Bucket: ${GCS_BUCKET_NAME}"
print_message "Service Account: ${SERVICE_ACCOUNT}"
print_message "Estructura: Monorepo (main.py + requirements.txt)"
print_message "==================================================================="

# Verificar variables requeridas
check_required_vars

# Verificar estructura monorepo
check_monorepo_structure

# =============================================================================
# Función 1: Procesar PDFs a chunks
# Trigger: Solo para archivos .pdf en la carpeta 'uploads/'
# =============================================================================
print_message "Desplegando función 1: process-pdf-to-chunks..."

gcloud functions deploy process-pdf-to-chunks \
  --gen2 \
  --runtime=python311 \
  --region=${GCF_REGION} \
  --source=. \
  --entry-point=process_pdf_to_chunks \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=${GCS_BUCKET_NAME}" \
  --service-account=${SERVICE_ACCOUNT} \
  --memory=2048MB \
  --timeout=540s \
  --max-instances=1 \
  --set-env-vars="GCS_BUCKET_NAME=${GCS_BUCKET_NAME},GCF_PROJECT_ID=${GCF_PROJECT_ID},OPENAI_API_KEY=${OPENAI_API_KEY},EMBEDDING_MODEL=${EMBEDDING_MODEL},API_TIMEOUT=${API_TIMEOUT},CHUNK_SIZE=${CHUNK_SIZE},CHUNK_OVERLAP=${CHUNK_OVERLAP},ENVIRONMENT=${ENVIRONMENT},LOG_LEVEL=${LOG_LEVEL},LOG_TO_DISK=false,DB_USER=${DB_USER},DB_PASS=${DB_PASS},DB_NAME=${DB_NAME},CLOUD_SQL_CONNECTION_NAME=${CLOUD_SQL_CONNECTION_NAME},DB_PRIVATE_IP=${DB_PRIVATE_IP}" \
  --project=${GCF_PROJECT_ID}

if [[ $? -eq 0 ]]; then
    print_success "Función process-pdf-to-chunks desplegada exitosamente"
else
    print_error "Error al desplegar process-pdf-to-chunks"
    exit 1
fi

# =============================================================================
# Función 2: Generar embeddings
# Trigger: Solo para archivos .json en la carpeta 'processed/'
# =============================================================================
print_message "Desplegando función 2: create-embeddings-from-chunks..."

gcloud functions deploy create-embeddings-from-chunks \
  --gen2 \
  --runtime=python311 \
  --region=${GCF_REGION} \
  --source=. \
  --entry-point=create_embeddings_from_chunks \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=${GCS_BUCKET_NAME}" \
  --service-account=${SERVICE_ACCOUNT} \
  --memory=2048MB \
  --timeout=540s \
  --max-instances=1 \
  --set-env-vars="GCS_BUCKET_NAME=${GCS_BUCKET_NAME},GCF_PROJECT_ID=${GCF_PROJECT_ID},OPENAI_API_KEY=${OPENAI_API_KEY},EMBEDDING_MODEL=${EMBEDDING_MODEL},API_TIMEOUT=${API_TIMEOUT},CHUNK_SIZE=${CHUNK_SIZE},CHUNK_OVERLAP=${CHUNK_OVERLAP},ENVIRONMENT=${ENVIRONMENT},LOG_LEVEL=${LOG_LEVEL},LOG_TO_DISK=false,DB_USER=${DB_USER},DB_PASS=${DB_PASS},DB_NAME=${DB_NAME},CLOUD_SQL_CONNECTION_NAME=${CLOUD_SQL_CONNECTION_NAME},DB_PRIVATE_IP=${DB_PRIVATE_IP}" \
  --project=${GCF_PROJECT_ID}

if [[ $? -eq 0 ]]; then
    print_success "Función create-embeddings-from-chunks desplegada exitosamente"
else
    print_error "Error al desplegar create-embeddings-from-chunks"
    exit 1
fi