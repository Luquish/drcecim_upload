#!/usr/bin/env python3
"""
Script para ejecutar las pruebas del sistema DrCecim Upload.
"""
import sys
import subprocess
import argparse
from pathlib import Path

# Configurar logging usando el sistema existente
from config.logging_config import setup_development_logging, get_logger

setup_development_logging()
logger = get_logger(__name__)


def run_command(command: list, description: str = "") -> bool:
    """Ejecutar un comando y manejar errores."""
    if description:
        logger.info(f"🔄 {description}")
        logger.info("=" * 50)
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        if result.stdout:
            logger.info(result.stdout)
        if result.stderr:
            logger.warning(f"Advertencias: {result.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error ejecutando: {' '.join(command)}")
        logger.error(f"Código de salida: {e.returncode}")
        if e.stdout:
            logger.error(f"Stdout: {e.stdout}")
        if e.stderr:
            logger.error(f"Stderr: {e.stderr}")
        return False


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(description="Ejecutar pruebas del sistema DrCecim Upload")
    parser.add_argument("--unit", action="store_true", help="Ejecutar solo pruebas unitarias")
    parser.add_argument("--integration", action="store_true", help="Ejecutar solo pruebas de integración")
    parser.add_argument("--coverage", action="store_true", help="Generar reporte de cobertura")
    parser.add_argument("--verbose", "-v", action="store_true", help="Salida verbose")
    parser.add_argument("--file", "-f", help="Ejecutar solo un archivo de pruebas específico")
    
    args = parser.parse_args()
    
    # Verificar que estamos en el directorio correcto
    if not Path("tests").exists():
        logger.error("❌ No se encontró el directorio 'tests'. Ejecuta desde la raíz del proyecto.")
        sys.exit(1)
    
    # Construir comando pytest (usar python3 explícitamente)
    pytest_cmd = ["python3", "-m", "pytest"]
    
    if args.verbose:
        pytest_cmd.append("-vv")
    
    if args.coverage:
        pytest_cmd.extend([
            "--cov=services",
            "--cov=models", 
            "--cov=utils",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    
    if args.unit:
        pytest_cmd.extend(["-m", "unit"])
        description = "Ejecutando pruebas unitarias"
    elif args.integration:
        pytest_cmd.extend(["-m", "integration"])
        description = "Ejecutando pruebas de integración"
    elif args.file:
        pytest_cmd.append(f"tests/{args.file}")
        description = f"Ejecutando pruebas en {args.file}"
    else:
        description = "Ejecutando todas las pruebas"
    
    # Ejecutar pruebas
    success = run_command(pytest_cmd, description)
    
    if success:
        logger.info("✅ ¡Todas las pruebas pasaron!")
        
        if args.coverage:
            logger.info("📊 Reporte de cobertura generado en htmlcov/index.html")
    else:
        logger.error("❌ Algunas pruebas fallaron.")
        sys.exit(1)


if __name__ == "__main__":
    main() 