#!/usr/bin/env python3
"""
Script de prueba para verificar la estructura de despliegue de Cloud Functions - Monorepo.
Verifica que la estructura monorepo esté correctamente configurada.
"""

import os
import sys
import tempfile
from pathlib import Path


def test_monorepo_structure():
    """Prueba la estructura monorepo."""
    print("🧪 Probando estructura monorepo...")
    
    # Verificar que existe el archivo main.py
    if not os.path.exists("main.py"):
        print("❌ Error: Archivo 'main.py' no encontrado")
        return False
    
    # Verificar que existe el archivo requirements.txt
    if not os.path.exists("requirements.txt"):
        print("❌ Error: Archivo 'requirements.txt' no encontrado")
        return False
    
    # Verificar que existe el directorio common
    if not os.path.exists("common"):
        print("❌ Error: Directorio 'common' no encontrado")
        return False
    
    # Verificar que existen los subdirectorios importantes de common
    common_subdirs = ["config", "services", "utils", "models"]
    for subdir in common_subdirs:
        if not os.path.exists(f"common/{subdir}"):
            print(f"❌ Error: Directorio 'common/{subdir}' no encontrado")
            return False
    
    print("✅ Estructura monorepo verificada")
    return True


def test_main_py_imports():
    """Prueba que los imports en main.py funcionen correctamente."""
    print("\n🔍 Probando imports de main.py...")
    
    try:
        # Cambiar al directorio temporal para simular el entorno de Cloud Functions
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Copiar archivos necesarios al directorio temporal
            import shutil
            shutil.copy("main.py", temp_path)
            shutil.copytree("common", temp_path / "common")
            
            # Cambiar al directorio temporal
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                # Agregar el directorio temporal al path de Python
                sys.path.insert(0, str(temp_path))
                
                # Intentar importar el módulo main
                print("  📦 Probando import de main.py...")
                
                # Simular la importación que haría Google Cloud Functions
                import main
                print("    ✅ Import de main.py exitoso")
                
                # Verificar que las funciones están definidas
                if hasattr(main, 'process_pdf_to_chunks'):
                    print("    ✅ Función process_pdf_to_chunks encontrada")
                else:
                    print("    ❌ Función process_pdf_to_chunks no encontrada")
                    return False
                
                if hasattr(main, 'create_embeddings_from_chunks'):
                    print("    ✅ Función create_embeddings_from_chunks encontrada")
                else:
                    print("    ❌ Función create_embeddings_from_chunks no encontrada")
                    return False
                
                print("✅ Todas las funciones están definidas correctamente")
                return True
                
            except ImportError as e:
                print(f"    ❌ Error importando main.py: {e}")
                return False
            except Exception as e:
                print(f"    ❌ Error inesperado: {e}")
                return False
            finally:
                # Restaurar directorio original
                os.chdir(original_cwd)
                
    except Exception as e:
        print(f"❌ Error durante las pruebas: {e}")
        return False


def test_requirements_txt():
    """Prueba que el archivo requirements.txt contenga todas las dependencias necesarias."""
    print("\n📦 Probando requirements.txt...")
    
    try:
        with open("requirements.txt", "r") as f:
            requirements = f.read()
        
        # Verificar dependencias críticas
        critical_deps = [
            "functions-framework",
            "pydantic",
            "google-cloud-storage",
            "marker-pdf",
            "openai",
            "numpy",
            "faiss-cpu"
        ]
        
        missing_deps = []
        for dep in critical_deps:
            if dep not in requirements:
                missing_deps.append(dep)
        
        if missing_deps:
            print(f"    ❌ Dependencias faltantes: {', '.join(missing_deps)}")
            return False
        else:
            print("    ✅ Todas las dependencias críticas están incluidas")
        
        # Verificar que no hay dependencias duplicadas
        lines = requirements.strip().split('\n')
        dep_lines = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
        
        if len(dep_lines) != len(set(dep_lines)):
            print("    ⚠️  Posibles dependencias duplicadas detectadas")
        else:
            print("    ✅ No hay dependencias duplicadas")
        
        print("✅ requirements.txt verificado correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error verificando requirements.txt: {e}")
        return False


def test_deployment_script():
    """Prueba que el script de despliegue esté configurado para monorepo."""
    print("\n🚀 Probando script de despliegue...")
    
    try:
        with open("deploy_event_driven.sh", "r") as f:
            script_content = f.read()
        
        # Verificar que usa --source=.
        if "--source=." not in script_content:
            print("    ❌ Script no usa --source=.")
            return False
        else:
            print("    ✅ Script usa --source=.")
        
        # Verificar que usa --entry-point
        if "--entry-point=" not in script_content:
            print("    ❌ Script no usa --entry-point")
            return False
        else:
            print("    ✅ Script usa --entry-point")
        
        # Verificar que menciona monorepo
        if "monorepo" not in script_content.lower():
            print("    ⚠️  Script no menciona monorepo")
        else:
            print("    ✅ Script menciona monorepo")
        
        print("✅ Script de despliegue verificado")
        return True
        
    except Exception as e:
        print(f"❌ Error verificando script de despliegue: {e}")
        return False


def test_old_structure_cleanup():
    """Verifica que los directorios antiguos ya no son necesarios."""
    print("\n🧹 Verificando limpieza de estructura anterior...")
    
    old_dirs = ["process_pdf", "create_embeddings"]
    existing_old_dirs = []
    
    for old_dir in old_dirs:
        if os.path.exists(old_dir):
            existing_old_dirs.append(old_dir)
    
    if existing_old_dirs:
        print(f"    ⚠️  Directorios antiguos aún existen: {', '.join(existing_old_dirs)}")
        print("    💡 Puedes eliminarlos manualmente si ya no los necesitas")
    else:
        print("    ✅ No hay directorios antiguos (ya fueron eliminados)")
    
    return True


def main():
    """Función principal de pruebas."""
    print("=" * 60)
    print("🧪 PRUEBAS DE ESTRUCTURA MONOREPO - CLOUD FUNCTIONS")
    print("=" * 60)
    
    # Verificar que estamos en el directorio correcto
    if not os.path.exists("deploy_event_driven.sh"):
        print("❌ Error: Ejecuta este script desde el directorio cloud_functions/")
        return False
    
    tests = [
        ("Verificación de estructura monorepo", test_monorepo_structure),
        ("Pruebas de imports de main.py", test_main_py_imports),
        ("Verificación de requirements.txt", test_requirements_txt),
        ("Verificación de script de despliegue", test_deployment_script),
        ("Verificación de limpieza", test_old_structure_cleanup)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        if test_func():
            print(f"✅ {test_name}: PASÓ")
            passed += 1
        else:
            print(f"❌ {test_name}: FALLÓ")
    
    print("\n" + "=" * 60)
    print(f"📊 RESULTADOS: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡Todas las pruebas pasaron! La estructura monorepo está lista para despliegue.")
        print("\n🚀 Para desplegar:")
        print("   ./deploy_event_driven.sh")
        return True
    else:
        print("⚠️  Algunas pruebas fallaron. Revisa los errores antes del despliegue.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 