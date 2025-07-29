#!/usr/bin/env python3
"""
Script de verificación para validar la estructura optimizada de Cloud Functions.
Verifica que no haya duplicación de código y que los imports estén correctos.
"""

import os
import sys
from pathlib import Path

def check_structure():
    """Verifica que la estructura esté correcta."""
    print("🔍 Verificando estructura de Cloud Functions...")
    
    # Verificar que el directorio common existe
    common_dir = Path("common")
    if not common_dir.exists():
        print("❌ Error: Directorio 'common' no encontrado")
        return False
    
    # Verificar directorios compartidos
    shared_dirs = ["config", "services", "utils", "models", "credentials"]
    for dir_name in shared_dirs:
        shared_path = common_dir / dir_name
        if not shared_path.exists():
            print(f"❌ Error: Directorio compartido '{dir_name}' no encontrado en common/")
            return False
    
    # Verificar que las Cloud Functions no tengan directorios duplicados
    cloud_functions = ["process_pdf", "create_embeddings"]
    for cf in cloud_functions:
        cf_dir = Path(cf)
        if not cf_dir.exists():
            print(f"❌ Error: Cloud Function '{cf}' no encontrada")
            return False
        
        # Verificar que no haya directorios duplicados
        for dir_name in shared_dirs:
            duplicate_path = cf_dir / dir_name
            if duplicate_path.exists():
                print(f"❌ Error: Directorio duplicado '{dir_name}' encontrado en {cf}/")
                return False
    
    print("✅ Estructura de directorios correcta")
    return True

def check_requirements():
    """Verifica que los requirements.txt estén correctos."""
    print("\n📦 Verificando requirements.txt...")
    
    # Verificar requirements.txt común
    common_req = Path("common/requirements.txt")
    if not common_req.exists():
        print("❌ Error: common/requirements.txt no encontrado")
        return False
    
    # Verificar que las Cloud Functions incluyan las dependencias comunes
    cloud_functions = ["process_pdf", "create_embeddings"]
    for cf in cloud_functions:
        cf_req = Path(cf) / "requirements.txt"
        if not cf_req.exists():
            print(f"❌ Error: requirements.txt no encontrado en {cf}/")
            return False
        
        # Verificar que incluya la referencia a dependencias comunes
        with open(cf_req, 'r') as f:
            content = f.read()
            if "-r ../common/requirements.txt" not in content:
                print(f"❌ Error: {cf}/requirements.txt no incluye dependencias comunes")
                return False
    
    print("✅ Requirements.txt correctos")
    return True

def check_imports():
    """Verifica que los imports apunten al directorio common."""
    print("\n📥 Verificando imports...")
    
    # Verificar imports específicos para cada Cloud Function
    cloud_functions_imports = {
        "process_pdf": {
            "required": ["from common.config import"],
            "services_optional": True  # process_pdf no necesita servicios
        },
        "create_embeddings": {
            "required": ["from common.config import", "from common.services."],
            "services_optional": False  # create_embeddings necesita servicios
        }
    }
    
    for cf, imports_config in cloud_functions_imports.items():
        main_py = Path(cf) / "main.py"
        if not main_py.exists():
            print(f"❌ Error: main.py no encontrado en {cf}/")
            return False
        
        with open(main_py, 'r') as f:
            content = f.read()
            
            # Verificar imports requeridos
            for required_import in imports_config["required"]:
                if required_import not in content:
                    print(f"❌ Error: {cf}/main.py no tiene el import requerido: {required_import}")
                    return False
            
            # Verificar imports de servicios según la función
            if not imports_config["services_optional"]:
                # Si los servicios no son opcionales, debe tener imports de servicios
                if "from common.services." not in content:
                    print(f"❌ Error: {cf}/main.py debe importar servicios desde common.services")
                    return False
    
    print("✅ Imports correctos")
    return True

def main():
    """Función principal de verificación."""
    print("🚀 Iniciando verificación de estructura de Cloud Functions\n")
    
    checks = [
        check_structure,
        check_requirements,
        check_imports
    ]
    
    all_passed = True
    for check in checks:
        if not check():
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("🎉 ¡Todas las verificaciones pasaron! La estructura está optimizada.")
        print("✅ No hay duplicación de código")
        print("✅ Dependencias organizadas correctamente")
        print("✅ Imports actualizados")
        return 0
    else:
        print("❌ Algunas verificaciones fallaron. Revisa los errores arriba.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 