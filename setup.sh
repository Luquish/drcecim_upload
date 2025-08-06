#!/bin/bash

# =============================================================================
# SCRIPT DE CONFIGURACIÓN INICIAL PARA DRCECIM UPLOAD
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

header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Función para leer input del usuario
read_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    
    if [ -n "$default" ]; then
        read -p "$prompt [$default]: " input
        input=${input:-$default}
    else
        read -p "$prompt: " input
    fi
    
    eval "$var_name='$input'"
}

# Función para validar comando
check_command() {
    if ! command -v "$1" &> /dev/null; then
        error "$1 no está instalado"
        return 1
    fi
    log "✓ $1 está instalado"
    return 0
}

# Función para validar API key
validate_api_key() {
    local api_key="$1"
    if [[ ${#api_key} -lt 20 ]]; then
        error "API key parece inválida (muy corta)"
        return 1
    fi
    return 0
}

# Función principal
main() {
    header "CONFIGURACIÓN INICIAL DE DRCECIM UPLOAD"
    
    log "Este script te ayudará a configurar el proyecto DrCecim Upload"
    log "Asegúrate de tener los siguientes requisitos:"
    log "- Python 3.11+"
    log "- Google Cloud SDK (gcloud)"
    log "- Cuenta de Google Cloud con facturación"
    echo
    
    # Verificar requisitos
    header "VERIFICANDO REQUISITOS"
    
    # Verificar Python
    if ! check_command python3; then
        error "Python 3 es requerido"
        exit 1
    fi
    
    # Verificar versión de Python
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if [[ $(echo "$PYTHON_VERSION < 3.11" | bc -l) -eq 1 ]]; then
        error "Python 3.11+ es requerido. Versión actual: $PYTHON_VERSION"
        exit 1
    fi
    log "✓ Python $PYTHON_VERSION"
    
    # Verificar gcloud
    if ! check_command gcloud; then
        error "Google Cloud SDK es requerido"
        error "Instálalo desde: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    # Verificar pip
    if ! check_command pip3; then
        error "pip3 es requerido"
        exit 1
    fi
    
    # Verificar git
    if ! check_command git; then
        error "git es requerido"
        exit 1
    fi
    
    # Verificar gsutil
    if ! check_command gsutil; then
        error "gsutil es requerido (parte de Google Cloud SDK)"
        exit 1
    fi
    
    # Configuración de variables de entorno
    header "CONFIGURACIÓN DE VARIABLES DE ENTORNO"
    
    # Leer configuración
    read_input "Google Cloud Project ID" "" "PROJECT_ID"
    read_input "Google Cloud Region" "us-central1" "REGION"
    read_input "GCS Bucket Name" "drcecim-chatbot-storage" "BUCKET_NAME"
    read_input "Tamaño máximo de archivo (MB)" "50" "MAX_FILE_SIZE"
    read_input "Tamaño de chunk" "250" "CHUNK_SIZE"
    read_input "Overlap de chunk" "50" "CHUNK_OVERLAP"
    
    # Crear archivo .env
    header "CREANDO ARCHIVO .env"
    
    cat > .env << EOF
# =============================================================================
# CONFIGURACIÓN GENERADA POR SETUP.SH
# =============================================================================

# Google Cloud
GCS_BUCKET_NAME=$BUCKET_NAME
GCF_PROJECT_ID=$PROJECT_ID
GCF_REGION=$REGION

# Procesamiento
MAX_FILE_SIZE_MB=$MAX_FILE_SIZE
CHUNK_SIZE=$CHUNK_SIZE
CHUNK_OVERLAP=$CHUNK_OVERLAP

# Configuración adicional
ENVIRONMENT=development
DEBUG=False
LOG_LEVEL=INFO
TEMP_DIR=/tmp/drcecim_processing
USE_GCS=true
GCS_AUTO_REFRESH=true
EOF
    
    log "✓ Archivo .env creado"
    
    # Configurar Google Cloud
    header "CONFIGURANDO GOOGLE CLOUD"
    
    log "Configurando proyecto de Google Cloud..."
    gcloud config set project "$PROJECT_ID"
    
    log "Verificando autenticación..."
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        warn "No hay cuenta activa. Iniciando proceso de autenticación..."
        gcloud auth login
    fi
    
    log "Habilitando APIs necesarias..."
    gcloud services enable cloudfunctions.googleapis.com
    gcloud services enable cloudbuild.googleapis.com
    gcloud services enable storage.googleapis.com
    
    log "Verificando/creando bucket de GCS..."
    if ! gsutil ls "gs://$BUCKET_NAME" &> /dev/null; then
        log "Creando bucket: gs://$BUCKET_NAME"
        gsutil mb "gs://$BUCKET_NAME"
    else
        log "✓ Bucket ya existe: gs://$BUCKET_NAME"
    fi
    
    # Configurar entorno Python
    header "CONFIGURANDO ENTORNO PYTHON"
    
    log "Creando entorno virtual..."
    python3 -m venv venv
    
    log "Activando entorno virtual..."
    source venv/bin/activate
    
    log "Actualizando pip..."
    pip install --upgrade pip
    
    log "Instalando dependencias..."
    pip install -r requirements.txt
    
    # Configurar Streamlit
    header "CONFIGURANDO STREAMLIT"
    
    log "Creando configuración de Streamlit..."
    mkdir -p .streamlit
    
    cat > .streamlit/secrets.toml << EOF
# URL de la Cloud Function (actualizar después del deployment)
CLOUD_FUNCTION_URL = "https://$REGION-$PROJECT_ID.cloudfunctions.net/drcecim-process-document"
EOF
    
    log "✓ Configuración de Streamlit creada"
    
    # Verificar marker-pdf
    header "VERIFICANDO MARKER-PDF"
    
    if ! pip show marker-pdf &> /dev/null; then
        log "Instalando marker-pdf..."
        pip install marker-pdf
    fi
    
    if ! command -v marker_single &> /dev/null; then
        warn "marker_single no está en PATH. Reinstalando marker-pdf..."
        pip uninstall marker-pdf -y
        pip install marker-pdf
    fi
    
    # Finalizar
    header "CONFIGURACIÓN COMPLETADA"
    
    log "✅ Configuración inicial completada exitosamente"
    echo
    log "Próximos pasos:"
    log "1. Revisar el archivo .env y ajustar si es necesario"
    log "2. Activar el entorno virtual: source venv/bin/activate"
    log "3. Deployar Cloud Function: cd cloud_functions && ./deploy.sh"
    log "4. Ejecutar Streamlit: streamlit run streamlit_app.py"
    echo
    log "Para más información, consulta el README.md"
    
    # Mostrar resumen
    echo
    log "=== RESUMEN DE CONFIGURACIÓN ==="
    log "Proyecto: $PROJECT_ID"
    log "Región: $REGION"
    log "Bucket: $BUCKET_NAME"
    log "Tamaño máx: ${MAX_FILE_SIZE}MB"
    log "==============================="
}

# Ejecutar función principal
main "$@" 