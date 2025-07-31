#!/bin/bash

# =============================================================================
# SCRIPT DE PRUEBA LOCAL PARA CLOUD FUNCTIONS
# =============================================================================

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_message() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

print_message "==================================================================="
print_message "PRUEBA LOCAL DE CLOUD FUNCTIONS - DRCECIM UPLOAD"
print_message "==================================================================="

# Verificar que estamos en el directorio correcto
if [[ ! -f "main.py" ]]; then
    print_error "Archivo main.py no encontrado. Ejecutar desde el directorio cloud_functions/"
    exit 1
fi

# Verificar que existe requirements.txt
if [[ ! -f "requirements.txt" ]]; then
    print_error "Archivo requirements.txt no encontrado"
    exit 1
fi

# Verificar que existe el archivo .env
if [[ ! -f ".env" ]]; then
    print_warning "Archivo .env no encontrado. Asegúrate de configurar las variables de entorno."
fi

print_message "Iniciando función process_pdf_to_chunks en puerto 8080..."
print_message "Para probar, envía una petición POST a http://localhost:8080"
print_message "Presiona Ctrl+C para detener"

# Ejecutar la función localmente
functions-framework --target process_pdf_to_chunks --port 8080 