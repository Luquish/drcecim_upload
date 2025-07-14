#!/usr/bin/env python3
"""
Script para migrar variables de entorno a Google Secret Manager.
"""
import os
import sys
import argparse
from pathlib import Path

# Agregar el directorio padre al path para importar módulos
sys.path.append(str(Path(__file__).parent.parent))

from services.secrets_service import SecureConfigManager
from config.settings import GCF_PROJECT_ID


def main():
    """Función principal del script de migración."""
    parser = argparse.ArgumentParser(description="Migrar variables de entorno a Google Secret Manager")
    parser.add_argument("--project-id", help="ID del proyecto de Google Cloud")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar qué se migraría sin hacer cambios")
    parser.add_argument("--force", action="store_true", help="Forzar migración incluso si hay errores")
    
    args = parser.parse_args()
    
    # Determinar project ID
    project_id = args.project_id or GCF_PROJECT_ID
    if not project_id:
        print("❌ ERROR: Debe especificar --project-id o configurar GCF_PROJECT_ID")
        sys.exit(1)
    
    print(f"🚀 Migrando secretos para proyecto: {project_id}")
    print("=" * 50)
    
    # Variables críticas para migrar
    variables_to_migrate = [
        'OPENAI_API_KEY',
        'GCS_CREDENTIALS_PATH',
        'GCS_BUCKET_NAME',
        'GCF_PROJECT_ID',
        'GCF_REGION',
        'EMBEDDING_MODEL',
        'API_TIMEOUT',
        'MAX_OUTPUT_TOKENS',
        'TEMPERATURE',
        'TOP_P',
        'CHUNK_SIZE',
        'CHUNK_OVERLAP',
        'TEMP_DIR',
        'PROCESSED_DIR',
        'EMBEDDINGS_DIR',
        'DEVICE',
        'HOST',
        'PORT',
        'MAX_FILE_SIZE_MB',
        'LOG_LEVEL',
        'DEBUG',
        'ENVIRONMENT',
        'DATABASE_URL',
        'JWT_SECRET',
        'WEBHOOK_SECRET'
    ]
    
    # Verificar que variables existen
    print("📋 Verificando variables de entorno...")
    available_vars = []
    for var in variables_to_migrate:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {'*' * min(len(value), 20)}...")
            available_vars.append(var)
        else:
            print(f"  ⚠️  {var}: No encontrada")
    
    if not available_vars:
        print("\n❌ No se encontraron variables de entorno para migrar")
        sys.exit(1)
    
    print(f"\n📦 Variables para migrar: {len(available_vars)}")
    
    if args.dry_run:
        print("\n🔍 MODO DRY RUN - No se harán cambios reales")
        for var in available_vars:
            secret_name = var.lower().replace("_", "-")
            print(f"  Migraría: {var} → {secret_name}")
        return
    
    # Confirmar migración
    if not args.force:
        response = input(f"\n¿Continuar con la migración de {len(available_vars)} variables? (y/N): ")
        if response.lower() != 'y':
            print("❌ Migración cancelada")
            sys.exit(0)
    
    # Realizar migración
    try:
        config_manager = SecureConfigManager(project_id)
        
        print("\n🔄 Iniciando migración...")
        results = config_manager.migrate_env_to_secrets(available_vars)
        
        # Mostrar resultados
        successful = sum(1 for success in results.values() if success)
        failed = len(results) - successful
        
        print(f"\n📊 Resultados de migración:")
        print(f"  ✅ Exitosas: {successful}")
        print(f"  ❌ Fallidas: {failed}")
        
        for var, success in results.items():
            status = "✅" if success else "❌"
            secret_name = var.lower().replace("_", "-")
            print(f"  {status} {var} → {secret_name}")
        
        if failed > 0:
            print(f"\n⚠️  {failed} secretos fallaron. Revisa los logs para detalles.")
            if not args.force:
                sys.exit(1)
        else:
            print("\n🎉 ¡Migración completada exitosamente!")
            print("\n💡 Pasos siguientes:")
            print("1. Verifica que los secretos estén en Secret Manager")
            print("2. Actualiza las configuraciones de tus Cloud Functions")
            print("3. Considera remover las variables de entorno locales")
    
    except Exception as e:
        print(f"\n❌ Error durante la migración: {str(e)}")
        sys.exit(1)


def list_current_secrets():
    """Lista los secretos actuales en Secret Manager."""
    try:
        config_manager = SecureConfigManager()
        if not config_manager.secrets_service:
            print("❌ Secret Manager no está disponible")
            return
        
        secrets_info = config_manager.secrets_service.list_secrets()
        secrets = secrets_info['secrets']
        
        print(f"📋 Secretos actuales en Secret Manager ({len(secrets)}):")
        for secret in secrets:
            print(f"  • {secret['name']} (creado: {secret['created']})")
    
    except Exception as e:
        print(f"❌ Error listando secretos: {str(e)}")


def verify_migration():
    """Verifica que los secretos migrados funcionen correctamente."""
    print("🔍 Verificando secretos migrados...")
    
    try:
        config_manager = SecureConfigManager()
        
        # Probar obtener algunos secretos clave
        test_secrets = ['openai-api-key', 'database-url']
        
        for secret_name in test_secrets:
            value = config_manager.get_config_value(secret_name, env_fallback=False)
            if value:
                print(f"  ✅ {secret_name}: {'*' * 20}...")
            else:
                print(f"  ❌ {secret_name}: No encontrado")
    
    except Exception as e:
        print(f"❌ Error verificando secretos: {str(e)}")


if __name__ == "__main__":
    # Verificar argumentos especiales
    if len(sys.argv) > 1:
        if sys.argv[1] == "list":
            list_current_secrets()
            sys.exit(0)
        elif sys.argv[1] == "verify":
            verify_migration()
            sys.exit(0)
    
    main() 