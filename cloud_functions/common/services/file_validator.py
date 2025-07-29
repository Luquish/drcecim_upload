"""
Servicio de validación de archivos PDF simplificado.
"""
import os
import logging
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from io import BytesIO

logger = logging.getLogger(__name__)


class PDFSecurityValidator:
    """
    Validador simplificado para archivos PDF.
    """
    
    # Firmas de archivo PDF válidas
    PDF_SIGNATURES = [
        b'%PDF-1.',  # PDF 1.x
        b'%PDF-2.',  # PDF 2.x
    ]
    
    # Tamaños máximos permitidos (en bytes)
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    MIN_FILE_SIZE = 100  # 100 bytes
    
    def __init__(self):
        """Inicializa el validador simplificado."""
        logger.info("Validador de archivos simplificado inicializado")
    
    def validate_file(self, file_path: str = None, file_data: bytes = None) -> Dict[str, Any]:
        """
        Valida un archivo PDF con validaciones básicas únicamente.
        
        Args:
            file_path (str): Ruta del archivo (opcional)
            file_data (bytes): Datos del archivo (opcional)
            
        Returns:
            Dict: Resultado completo de la validación
        """
        if not file_path and not file_data:
            return {
                "valid": False,
                "error": "Debe proporcionar file_path o file_data",
                "checks": {}
            }
        
        # Obtener datos del archivo
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                file_size = os.path.getsize(file_path)
                filename = Path(file_path).name
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"Error leyendo archivo: {str(e)}",
                    "checks": {}
                }
        else:
            file_size = len(file_data)
            filename = "uploaded_file.pdf"
        
        # Realizar solo validaciones básicas
        checks = {}
        
        # 1. Validar tamaño
        checks["size"] = self._validate_size(file_size)
        
        # 2. Validar extensión (si hay nombre)
        checks["extension"] = self._validate_extension(filename)
        
        # 3. Validar firma de archivo (básica)
        checks["signature"] = self._validate_pdf_signature(file_data)
        
        # Determinar si el archivo es válido
        is_valid = all([
            checks["size"]["valid"],
            checks["extension"]["valid"],
            checks["signature"]["valid"]
        ])
        
        # Recopilar errores
        errors = []
        for check_name, check_result in checks.items():
            if not check_result["valid"]:
                errors.append(f"{check_name}: {check_result.get('error', 'Falló')}")
        
        return {
            "valid": is_valid,
            "error": "; ".join(errors) if errors else None,
            "checks": checks,
            "file_info": {
                "size": file_size,
                "filename": filename,
                "md5": hashlib.md5(file_data).hexdigest(),
                "sha256": hashlib.sha256(file_data).hexdigest()
            }
        }
    
    def _validate_size(self, file_size: int) -> Dict[str, Any]:
        """Valida el tamaño del archivo."""
        if file_size < self.MIN_FILE_SIZE:
            return {
                "valid": False,
                "error": f"Archivo demasiado pequeño: {file_size} bytes (mínimo: {self.MIN_FILE_SIZE})"
            }
        
        if file_size > self.MAX_FILE_SIZE:
            return {
                "valid": False,
                "error": f"Archivo demasiado grande: {file_size} bytes (máximo: {self.MAX_FILE_SIZE})"
            }
        
        return {
            "valid": True,
            "size": file_size
        }
    
    def _validate_extension(self, filename: str) -> Dict[str, Any]:
        """Valida la extensión del archivo."""
        if not filename.lower().endswith('.pdf'):
            return {
                "valid": False,
                "error": f"Extensión no válida: {Path(filename).suffix}"
            }
        
        return {
            "valid": True,
            "extension": ".pdf"
        }
    
    def _validate_pdf_signature(self, file_data: bytes) -> Dict[str, Any]:
        """Valida la firma/cabecera del archivo PDF."""
        if len(file_data) < 8:
            return {
                "valid": False,
                "error": "Archivo demasiado pequeño para verificar firma"
            }
        
        header = file_data[:8]
        
        for signature in self.PDF_SIGNATURES:
            if header.startswith(signature):
                return {
                    "valid": True,
                    "signature": signature.decode('utf-8', errors='ignore')
                }
        
        return {
            "valid": False,
            "error": f"Firma PDF no válida: {header[:8]}"
        }
    
    def quick_validate(self, file_data: bytes) -> Tuple[bool, str]:
        """
        Validación rápida para casos donde solo necesitas saber si es válido.
        
        Args:
            file_data (bytes): Datos del archivo
            
        Returns:
            Tuple[bool, str]: (es_válido, mensaje_error)
        """
        # Validaciones críticas más rápidas
        if len(file_data) < self.MIN_FILE_SIZE:
            return False, "Archivo demasiado pequeño"
        
        if len(file_data) > self.MAX_FILE_SIZE:
            return False, "Archivo demasiado grande"
        
        # Verificar firma PDF
        if not any(file_data.startswith(sig) for sig in self.PDF_SIGNATURES):
            return False, "No es un archivo PDF válido"
        
        return True, "Validación rápida exitosa"


# Instancia global del validador
pdf_validator = PDFSecurityValidator() 