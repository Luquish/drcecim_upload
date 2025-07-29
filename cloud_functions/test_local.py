#!/usr/bin/env python3
"""
Script de prueba local para las Cloud Functions
Simula eventos de Cloud Storage para probar las funciones
"""

import json
import os
import tempfile
from pathlib import Path

# Simular evento de Cloud Storage para process_pdf_to_chunks
def create_storage_event(bucket_name: str, file_name: str) -> dict:
    """Crea un evento simulado de Cloud Storage."""
    return {
        "bucket": bucket_name,
        "name": file_name,
        "eventType": "OBJECT_FINALIZE",
        "timeCreated": "2024-01-01T00:00:00.000Z",
        "updated": "2024-01-01T00:00:00.000Z",
        "generation": "1234567890",
        "metageneration": "1",
        "contentType": "application/pdf",
        "size": "1024",
        "md5Hash": "d41d8cd98f00b204e9800998ecf8427e",
        "storageClass": "STANDARD",
        "timeStorageClassUpdated": "2024-01-01T00:00:00.000Z",
        "etag": "Cj0KGAoGdGVzdGVy",
        "owner": {
            "entity": "user-123456789012345678901",
            "entityId": "123456789012345678901"
        }
    }

# Simular evento de Cloud Storage para create_embeddings_from_chunks
def create_chunks_event(bucket_name: str, file_name: str) -> dict:
    """Crea un evento simulado para archivos de chunks."""
    return {
        "bucket": bucket_name,
        "name": f"processed/{file_name}_chunks.json",
        "eventType": "OBJECT_FINALIZE",
        "timeCreated": "2024-01-01T00:00:00.000Z",
        "updated": "2024-01-01T00:00:00.000Z",
        "generation": "1234567890",
        "metageneration": "1",
        "contentType": "application/json",
        "size": "1024",
        "md5Hash": "d41d8cd98f00b204e9800998ecf8427e",
        "storageClass": "STANDARD",
        "timeStorageClassUpdated": "2024-01-01T00:00:00.000Z",
        "etag": "Cj0KGAoGdGVzdGVy",
        "owner": {
            "entity": "user-123456789012345678901",
            "entityId": "123456789012345678901"
        }
    }

def test_health_checks():
    """Prueba los endpoints de health check."""
    print("🔍 Probando health checks...")
    
    # Simular request HTTP
    class MockRequest:
        def __init__(self):
            self.method = "GET"
            self.headers = {}
            self.url = "http://localhost:8080"
    
    try:
        from main import health_check_process_pdf, health_check_create_embeddings
        
        # Probar health check de process_pdf
        request = MockRequest()
        result = health_check_process_pdf(request)
        print(f"✅ Health check process_pdf: {result}")
        
        # Probar health check de create_embeddings
        result = health_check_create_embeddings(request)
        print(f"✅ Health check create_embeddings: {result}")
        
    except Exception as e:
        print(f"❌ Error en health checks: {e}")

def test_functions_framework():
    """Prueba que functions-framework funciona correctamente."""
    print("🔍 Probando functions-framework...")
    
    try:
        import functions_framework
        print("✅ functions-framework importado correctamente")
        
        # Verificar que las funciones están disponibles
        from main import process_pdf_to_chunks, create_embeddings_from_chunks
        print("✅ Funciones importadas correctamente")
        
    except Exception as e:
        print(f"❌ Error con functions-framework: {e}")

def test_dependencies():
    """Prueba que todas las dependencias están disponibles."""
    print("🔍 Probando dependencias...")
    
    dependencies = [
        "functions_framework",
        "google.cloud.storage",
        "google.cloud.logging", 
        "pydantic",
        "pydantic_settings",
        "dotenv",
        "tenacity",
        "openai",
        "numpy",
        "faiss",
        "pandas",
        "tqdm"
    ]
    
    for dep in dependencies:
        try:
            __import__(dep.replace("-", "_"))
            print(f"✅ {dep}")
        except ImportError as e:
            print(f"❌ {dep}: {e}")

def test_marker_pdf_alternative():
    """Prueba alternativas a marker-pdf."""
    print("🔍 Probando alternativas a marker-pdf...")
    
    alternatives = [
        "PyPDF2",
        "pdfplumber", 
        "pymupdf",
        "pdf2image"
    ]
    
    for alt in alternatives:
        try:
            __import__(alt.lower())
            print(f"✅ {alt} disponible")
        except ImportError:
            print(f"❌ {alt} no disponible")

if __name__ == "__main__":
    print("🚀 Iniciando pruebas locales...")
    print("=" * 50)
    
    test_dependencies()
    print()
    
    test_functions_framework()
    print()
    
    test_health_checks()
    print()
    
    test_marker_pdf_alternative()
    print()
    
    print("=" * 50)
    print("✅ Pruebas completadas") 