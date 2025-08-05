#!/usr/bin/env python3
"""
Script de prueba completo para simular el flujo de producción de Cloud Functions
Diseñado para identificar TODOS los errores antes del deployment.

FLUJO COMPLETO QUE SIMULA:
1. 📄 PDF → Chunks (process_pdf_to_chunks)
2. 📦 Chunks → JSON (upload a GCS)  
3. 🤖 JSON → Embeddings (create_embeddings_from_chunks)
4. 🗄️ Embeddings → PostgreSQL
5. 📊 Medición de memoria en tiempo real

ERRORES QUE DETECTA:
- ❌ 'dict' object has no attribute 'split' (chunks mal formateados)
- ❌ 'processed_successfully' faltante en JSON
- ❌ Problemas de conectividad (PostgreSQL, OpenAI)
- ❌ Errores de memoria y timeout
- ❌ Problemas de estructura de datos entre funciones

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
import psutil
import time
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
# FUNCIÓN PARA MEDIR MEMORIA
# ========================
def monitor_memory_usage(func, *args, **kwargs):
    """Ejecuta una función monitoreando el uso de memoria."""
    process = psutil.Process()
    
    # Memoria inicial
    memory_info_start = process.memory_info()
    memory_start_mb = memory_info_start.rss / 1024 / 1024
    
    print(f"   📊 Memoria inicial: {memory_start_mb:.1f} MB")
    
    # Variables para tracking
    max_memory_mb = memory_start_mb
    memory_samples = []
    
    def memory_monitor():
        nonlocal max_memory_mb, memory_samples
        while True:
            try:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_samples.append(current_memory)
                max_memory_mb = max(max_memory_mb, current_memory)
                time.sleep(0.5)  # Muestrear cada 0.5 segundos
            except:
                break
    
    # Iniciar monitoreo en thread separado
    import threading
    monitor_thread = threading.Thread(target=memory_monitor, daemon=True)
    monitor_thread.start()
    
    try:
        # Ejecutar función
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        # Detener monitoreo
        time.sleep(1)  # Dar tiempo para última muestra
        
        # Memoria final
        memory_info_end = process.memory_info()
        memory_end_mb = memory_info_end.rss / 1024 / 1024
        
        # Estadísticas
        duration = end_time - start_time
        memory_increase = max_memory_mb - memory_start_mb
        
        print(f"   📊 Memoria máxima: {max_memory_mb:.1f} MB")
        print(f"   📊 Incremento: +{memory_increase:.1f} MB")
        print(f"   ⏱️  Duración: {duration:.1f}s")
        
        return result, {
            'start_mb': memory_start_mb,
            'max_mb': max_memory_mb,
            'end_mb': memory_end_mb,
            'increase_mb': memory_increase,
            'duration_s': duration,
            'samples': len(memory_samples)
        }
        
    except Exception as e:
        print(f"   ❌ Error durante monitoreo: {e}")
        raise

# ========================
# PASO 2: PRUEBA PROCESAMIENTO PDF
# ========================
def test_pdf_with_memory(pdf_path):
    """Procesa un PDF midiendo el consumo de memoria."""
    print(f"\n📄 PROBANDO: {Path(pdf_path).name}")
    print(f"   - Ruta: {pdf_path}")
    
    if not os.path.exists(pdf_path):
        print(f"❌ Archivo no encontrado: {pdf_path}")
        return False, None
    
    filename = Path(pdf_path).name
    
    def process_with_monitoring():
        return process_pdf_document(pdf_path, filename)
    
    try:
        result, memory_stats = monitor_memory_usage(process_with_monitoring)
        
        print(f"✅ PDF procesado exitosamente:")
        print(f"   - Chunks: {result.get('num_chunks', 0)}")
        print(f"   - Palabras: {result.get('total_words', 0)}")
        print(f"   - Método: {result.get('processing_method', 'unknown')}")
        
        return True, memory_stats
        
    except Exception as e:
        print(f"❌ Error procesando PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None

def test_both_pdfs():
    """Prueba ambos PDFs y retorna las estadísticas de memoria."""
    pdfs_to_test = [
        '/Users/lucamazzarello_/Desktop/Condiciones_Regularidad.pdf',
        '/Users/lucamazzarello_/Desktop/Regimen_Disciplinario.pdf'
    ]
    
    memory_results = {}
    
    for pdf_path in pdfs_to_test:
        if os.path.exists(pdf_path):
            success, memory_stats = test_pdf_with_memory(pdf_path)
            if success and memory_stats:
                memory_results[Path(pdf_path).name] = memory_stats
        else:
            print(f"⚠️  Archivo no encontrado: {pdf_path}")
    
    return memory_results

def calculate_optimal_memory(memory_results):
    """Calcula la memoria óptima basada en los resultados."""
    if not memory_results:
        print("❌ No hay resultados de memoria para calcular")
        return None
    
    print(f"\n📊 ANÁLISIS DE MEMORIA:")
    print("=" * 50)
    
    max_memory_needed = 0
    max_file = ""
    
    for filename, stats in memory_results.items():
        max_mb = stats['max_mb']
        increase_mb = stats['increase_mb']
        duration = stats['duration_s']
        
        print(f"📄 {filename}:")
        print(f"   - Memoria máxima: {max_mb:.1f} MB")
        print(f"   - Incremento: +{increase_mb:.1f} MB")
        print(f"   - Duración: {duration:.1f}s")
        
        if max_mb > max_memory_needed:
            max_memory_needed = max_mb
            max_file = filename
    
    # Agregar buffer de seguridad (25%)
    buffer_factor = 1.25
    recommended_mb = max_memory_needed * buffer_factor
    
    # Redondear a múltiplos de 512MB
    recommended_mb_rounded = ((recommended_mb // 512) + 1) * 512
    
    print(f"\n🎯 RECOMENDACIÓN:")
    print(f"   - Archivo más pesado: {max_file}")
    print(f"   - Memoria máxima medida: {max_memory_needed:.1f} MB")
    print(f"   - Con buffer 25%: {recommended_mb:.1f} MB")
    print(f"   - Recomendado para Cloud Functions: {int(recommended_mb_rounded)} MB")
    
    return int(recommended_mb_rounded)

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
# PASO 4: PRUEBA FLUJO COMPLETO END-TO-END
# ========================
def test_full_pipeline_simulation(pdf_path):
    """
    Simula el flujo completo de producción:
    1. PDF → Chunks (process_pdf_document)
    2. Chunks → JSON (simular GCS)  
    3. JSON → Embeddings (process_document_embeddings)
    4. Embeddings → PostgreSQL
    """
    print(f"\n🔄 SIMULANDO FLUJO COMPLETO: {Path(pdf_path).name}")
    print("=" * 60)
    
    if not os.path.exists(pdf_path):
        print(f"❌ Archivo no encontrado: {pdf_path}")
        return False
    
    filename = Path(pdf_path).name
    
    try:
        # PASO 1: PDF → Chunks (simula process_pdf_to_chunks)
        print("📄 PASO 1: PDF → Chunks")
        result = process_pdf_document(pdf_path, filename)
        
        if not result.get('processed_successfully', False):
            print(f"❌ Error en procesamiento PDF: {result.get('error', 'Unknown')}")
            return False
            
        print(f"✅ PDF procesado: {result['num_chunks']} chunks, {result['total_words']} palabras")
        
        # PASO 2: Simular estructura JSON como en GCS (simula el upload a GCS)
        print("\n📦 PASO 2: Chunks → JSON (simular GCS)")
        chunks_data = {
            'filename': result['filename'],
            'chunks': result['chunks'],
            'metadata': result['metadata'],
            'num_chunks': result['num_chunks'],
            'total_words': result['total_words'],
            'processing_timestamp': result['processing_timestamp'],
            'source_file': filename,
            'processed_successfully': True  # ¡Este campo causó el primer error!
        }
        
        print(f"✅ JSON creado: {len(chunks_data['chunks'])} chunks")
        print(f"   - processed_successfully: {chunks_data.get('processed_successfully')}")
        print(f"   - Estructura chunks[0]: {type(chunks_data['chunks'][0])}")
        
        # PASO 3: JSON → Embeddings (simula create_embeddings_from_chunks)
        print("\n🤖 PASO 3: JSON → Embeddings")
        from common.services.embeddings_service import EmbeddingService
        
        embedding_service = EmbeddingService()
        embeddings_result = embedding_service.process_document_embeddings(chunks_data)
        
        if not embeddings_result.get('processed_successfully', False):
            error_msg = embeddings_result.get('error', 'Unknown')
            print(f"❌ Error en embeddings: {error_msg}")
            return False
            
        print(f"✅ Embeddings generados:")
        print(f"   - Vectores: {embeddings_result.get('config', {}).get('num_vectors', 0)}")
        print(f"   - Dimensión: {embeddings_result.get('config', {}).get('dimension', 0)}")
        print(f"   - Almacenado en PostgreSQL: {embeddings_result.get('storage_success', False)}")
        
        # PASO 4: Verificar PostgreSQL
        print("\n🗄️ PASO 4: Verificar PostgreSQL")
        from common.services.vector_db_service import VectorDBService
        vector_db = VectorDBService()
        stats = vector_db.get_database_stats()
        
        print(f"✅ Base de datos actualizada:")
        print(f"   - Total embeddings: {stats.get('total_embeddings', 0)}")
        print(f"   - Documentos únicos: {stats.get('unique_documents', 0)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en flujo completo: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_pipeline_with_both_pdfs():
    """Prueba el flujo completo con ambos PDFs."""
    pdfs_to_test = [
        '/Users/lucamazzarello_/Desktop/Condiciones_Regularidad.pdf',
        '/Users/lucamazzarello_/Desktop/Regimen_Disciplinario.pdf'
    ]
    
    results = {}
    
    for pdf_path in pdfs_to_test:
        if os.path.exists(pdf_path):
            success = test_full_pipeline_simulation(pdf_path)
            results[Path(pdf_path).name] = success
        else:
            print(f"⚠️  Archivo no encontrado: {pdf_path}")
            results[Path(pdf_path).name] = False
    
    return results

# ========================
# FUNCIÓN PRINCIPAL
# ========================
def main():
    print(f"\n🚀 EJECUTANDO PRUEBAS COMPLETAS CON SIMULACIÓN DE PRODUCCIÓN...")
    
    # Prueba 1: Análisis de memoria con ambos PDFs
    print(f"\n📊 PASO 1: ANÁLISIS DE MEMORIA")
    memory_results = test_both_pdfs()
    
    optimal_memory_mb = None
    if memory_results:
        optimal_memory_mb = calculate_optimal_memory(memory_results)
    
    # Prueba 2: Base de datos (opcional)
    print(f"\n🔌 PASO 2: CONECTIVIDAD")
    database_ok = test_database_simple()
    
    # Prueba 3: OpenAI (opcional)
    openai_ok = test_openai_simple()
    
    # NUEVA Prueba 4: Flujo completo END-TO-END
    print(f"\n🔄 PASO 4: SIMULACIÓN COMPLETA DE PRODUCCIÓN")
    pipeline_results = test_pipeline_with_both_pdfs()
    pipeline_ok = all(pipeline_results.values())
    
    # Resumen final
    print(f"\n📊 RESUMEN FINAL:")
    print("=" * 50)
    print(f"   - PDFs procesados (memoria): {len(memory_results)}/{2}")
    print(f"   - Database: {'✅' if database_ok else '❌'}")
    print(f"   - OpenAI: {'✅' if openai_ok else '❌'}")
    print(f"   - Pipeline completo: {'✅' if pipeline_ok else '❌'}")
    
    if not pipeline_ok:
        print(f"\n❌ ERRORES EN PIPELINE:")
        for pdf_name, success in pipeline_results.items():
            if not success:
                print(f"   - {pdf_name}: FALLÓ")
    
    if optimal_memory_mb:
        print(f"\n🎯 RECOMENDACIÓN PARA CLOUD FUNCTIONS:")
        print(f"   - Memoria recomendada: {optimal_memory_mb} MB")
        print(f"   - Actualizar deploy_event_driven.sh con --memory={optimal_memory_mb}MB")
        
        # Guardar recomendación en archivo
        recommendation_file = Path("./memory_recommendation.txt")
        with open(recommendation_file, 'w') as f:
            f.write(f"# Recomendación de memoria basada en pruebas locales\n")
            f.write(f"RECOMMENDED_MEMORY_MB={optimal_memory_mb}\n")
            f.write(f"\n# Resultados detallados:\n")
            for filename, stats in memory_results.items():
                f.write(f"# {filename}: {stats['max_mb']:.1f} MB máx, {stats['duration_s']:.1f}s\n")
            f.write(f"\n# Pipeline E2E: {'PASSED' if pipeline_ok else 'FAILED'}\n")
            for pdf_name, success in pipeline_results.items():
                f.write(f"# {pdf_name}: {'✅' if success else '❌'}\n")
        
        print(f"   - Guardado en: {recommendation_file}")
        
        return pipeline_ok and database_ok and openai_ok, optimal_memory_mb
    else:
        print(f"\n❌ No se pudo determinar memoria óptima")
        return False, None

if __name__ == "__main__":
    success, recommended_memory = main()
    
    if success and recommended_memory:
        print(f"\n✅ Pruebas completadas. Memoria recomendada: {recommended_memory} MB")
    
    sys.exit(0 if success else 1)