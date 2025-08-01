#!/usr/bin/env python3
"""
Script de prueba simplificado para las Cloud Functions
Enfocado en probar paso a paso cada componente.

CONFIGURACIÓN:
Las variables se cargan automáticamente desde settings.py, que lee de:
1. Archivo .env (si existe) 
2. Variables de entorno del sistema
3. Valores por defecto

Para configurar tus propias variables, crear un archivo .env con:
```
# REQUERIDO
OPENAI_API_KEY=sk-proj-tu-nueva-api-key
GCS_BUCKET_NAME=tu-bucket-name
GCF_PROJECT_ID=tu-project-id

# OPCIONAL (tienen defaults)
TEST_PDF_PATH=/ruta/a/tu/archivo.pdf
DB_HOST=localhost
DB_USER=raguser
DB_PASS=tu-password
CHUNK_SIZE=250
EMBEDDING_MODEL=text-embedding-3-small
```
"""

import os
import sys
import json
from pathlib import Path

# Agregar el directorio actual al path para importaciones
sys.path.insert(0, str(Path(__file__).parent))

# Configurar credenciales GCP
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(Path(__file__).parent / "common" / "credentials" / "service-account.json")

# Configurar overrides específicos para testing local
TEST_LOCAL_OVERRIDES = {
    'LOG_TO_DISK': 'true',          # Habilitar logging local
    'ENVIRONMENT': 'development',    # Modo desarrollo
    'DB_HOST': 'localhost',         # PostgreSQL local
    'DB_PORT': '5432',              # Puerto local
    'CLOUD_SQL_CONNECTION_NAME': '', # Vacío para forzar conexión local
}

# Aplicar overrides para testing local
os.environ.update(TEST_LOCAL_OVERRIDES)

# Cargar configuración centralizada
try:
    from common.config.settings import config
    print("✅ Configuración cargada desde settings.py")
    
    # Mostrar configuración relevante para testing
    print(f"   - OpenAI Model: {config.openai.embedding_model}")
    print(f"   - Database: {config.database.db_user}@{config.database.db_host}:{config.database.db_port}/{config.database.db_name}")
    print(f"   - GCS Bucket: {config.google_cloud.gcs_bucket_name}")
    print(f"   - Chunk Size: {config.processing.chunk_size}")
    
except Exception as e:
    print(f"❌ Error cargando configuración: {e}")
    sys.exit(1)

print("🧪 INICIANDO PRUEBAS SIMPLES")
print("=" * 50)

# ========================
# PASO 1: PRUEBAS DE IMPORTACIÓN
# ========================
print("📦 Probando importaciones...")

try:
    from common.config.logging_config import setup_logging, get_logger
    print("✅ Logging config importado")
except Exception as e:
    print(f"❌ Error importando logging: {e}")
    sys.exit(1)

try:
    setup_logging(log_level="INFO", enable_file_logging=True, enable_console_logging=True)
    logger = get_logger(__name__)
    print("✅ Logging configurado")
except Exception as e:
    print(f"❌ Error configurando logging: {e}")
    sys.exit(1)

try:
    from main import process_pdf_document
    print("✅ Función process_pdf_document importada")
except Exception as e:
    print(f"❌ Error importando main: {e}")
    sys.exit(1)

# ========================
# PASO 2: PRUEBA PROCESAMIENTO PDF
# ========================
def test_pdf_simple():
    # Obtener ruta del PDF desde variable de entorno o usar default
    pdf_path = os.getenv('TEST_PDF_PATH', '/Users/lucamazzarello_/Desktop/Regimen_Disciplinario.pdf')
    
    print(f"\n📄 PROBANDO PROCESAMIENTO DE PDF:")
    print(f"   - Archivo: {pdf_path}")
    print(f"   - Configurar TEST_PDF_PATH en .env para cambiar la ruta")
    
    if not os.path.exists(pdf_path):
        print(f"❌ Archivo no encontrado: {pdf_path}")
        print(f"   Configurar TEST_PDF_PATH=/ruta/a/tu/archivo.pdf en .env")
        return False
    
    filename = Path(pdf_path).name
    print(f"   - Procesando: {filename}")
    
    try:
        result = process_pdf_document(pdf_path, filename)
        
        print(f"✅ PDF procesado exitosamente:")
        print(f"   - Chunks: {result.get('num_chunks', 0)}")
        print(f"   - Palabras: {result.get('total_words', 0)}")
        print(f"   - Método: {result.get('processing_method', 'unknown')}")
        
        # Guardar resultado para inspección
        output_file = Path("./test_temp/simple_chunks.json")
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Resultado guardado en: {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error procesando PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# ========================
# PASO 3: PRUEBAS DE CONECTIVIDAD
# ========================
def test_database_simple():
    print(f"\n🔌 PROBANDO CONEXIÓN A BASE DE DATOS...")
    
    try:
        from common.services.vector_db_service import VectorDBService
        vector_db = VectorDBService()
        
        # Intentar una consulta simple
        stats = vector_db.get_database_stats()
        print(f"✅ PostgreSQL conectado:")
        print(f"   - Embeddings: {stats.get('total_embeddings', 0)}")
        print(f"   - Documentos: {stats.get('unique_documents', 0)}")
        return True
        
    except Exception as e:
        print(f"❌ Error de base de datos: {str(e)}")
        return False

def test_openai_simple():
    print(f"\n🤖 PROBANDO CONEXIÓN A OPENAI...")
    
    try:
        from common.services.embeddings_service import EmbeddingService
        embedding_service = EmbeddingService()
        
        # Probar con texto simple
        test_embeddings = embedding_service._generate_embeddings_with_batch_api(["Hola mundo"])
        print(f"✅ OpenAI conectado:")
        print(f"   - Embedding test: {len(test_embeddings)} vectores")
        return True
        
    except Exception as e:
        print(f"❌ Error OpenAI: {str(e)}")
        return False

# ========================
# FUNCIÓN PRINCIPAL
# ========================
def main():
    print(f"\n🚀 EJECUTANDO PRUEBAS...")
    
    results = {}
    
    # Prueba 1: Procesamiento PDF
    results['pdf'] = test_pdf_simple()
    
    # Prueba 2: Base de datos (opcional)
    results['database'] = test_database_simple()
    
    # Prueba 3: OpenAI (opcional)
    results['openai'] = test_openai_simple()
    
    # Resumen
    print(f"\n📊 RESUMEN:")
    print(f"   - PDF Processing: {'✅' if results['pdf'] else '❌'}")
    print(f"   - Database: {'✅' if results['database'] else '❌'}")
    print(f"   - OpenAI: {'✅' if results['openai'] else '❌'}")
    
    if results['pdf']:
        print(f"\n🎯 SIGUIENTE PASO:")
        print(f"   - El procesamiento básico funciona")
        print(f"   - Revisar el archivo de chunks generado")
        print(f"   - Si todo se ve bien, proceder con el despliegue")
    
    return all(results.values())

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)