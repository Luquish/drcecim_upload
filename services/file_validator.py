"""
Servicio de validación de archivos PDF para seguridad.
"""
import os
import magic
import logging
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from io import BytesIO

logger = logging.getLogger(__name__)


class PDFSecurityValidator:
    """
    Validador de seguridad para archivos PDF.
    """
    
    # Firmas de archivo PDF válidas
    PDF_SIGNATURES = [
        b'%PDF-1.',  # PDF 1.x
        b'%PDF-2.',  # PDF 2.x
    ]
    
    # Tamaños máximos permitidos (en bytes)
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    MIN_FILE_SIZE = 100  # 100 bytes
    
    # Patrones sospechosos en archivos PDF
    SUSPICIOUS_PATTERNS = [
        b'/JavaScript',
        b'/JS',
        b'/OpenAction',
        b'/Launch',
        b'/EmbeddedFile',
        b'/XFA',
        b'<script',
        b'ActiveX',
        b'GetObject',
        b'WScript',
        b'eval('
    ]
    
    # Lista de hash conocidos de archivos maliciosos (ejemplo)
    MALICIOUS_HASHES = [
        # Agregar hashes MD5/SHA256 de archivos maliciosos conocidos
        # 'd41d8cd98f00b204e9800998ecf8427e',  # Ejemplo
    ]
    
    def __init__(self):
        """Inicializa el validador de seguridad."""
        self.magic_mime = None
        try:
            self.magic_mime = magic.Magic(mime=True)
            logger.info("Validador de archivos inicializado con libmagic")
        except Exception as e:
            logger.warning(f"No se pudo inicializar libmagic: {str(e)}")
    
    def validate_file(self, file_path: str = None, file_data: bytes = None) -> Dict[str, Any]:
        """
        Valida un archivo PDF completo.
        
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
        
        # Realizar todas las validaciones
        checks = {}
        
        # 1. Validar tamaño
        checks["size"] = self._validate_size(file_size)
        
        # 2. Validar extensión (si hay nombre)
        checks["extension"] = self._validate_extension(filename)
        
        # 3. Validar firma de archivo
        checks["signature"] = self._validate_pdf_signature(file_data)
        
        # 4. Validar tipo MIME
        checks["mime_type"] = self._validate_mime_type(file_data)
        
        # 5. Buscar patrones sospechosos
        checks["suspicious_content"] = self._check_suspicious_patterns(file_data)
        
        # 6. Verificar hash contra lista de malware conocido
        checks["malware_hash"] = self._check_malicious_hash(file_data)
        
        # 7. Validación básica de estructura PDF
        checks["pdf_structure"] = self._validate_pdf_structure(file_data)
        
        # Determinar si el archivo es válido
        is_valid = all([
            checks["size"]["valid"],
            checks["extension"]["valid"],
            checks["signature"]["valid"],
            checks["mime_type"]["valid"],
            checks["suspicious_content"]["valid"],
            checks["malware_hash"]["valid"],
            checks["pdf_structure"]["valid"]
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
    
    def _validate_mime_type(self, file_data: bytes) -> Dict[str, Any]:
        """Valida el tipo MIME del archivo."""
        if not self.magic_mime:
            return {
                "valid": True,
                "warning": "Validación MIME no disponible (libmagic no instalado)"
            }
        
        try:
            mime_type = self.magic_mime.from_buffer(file_data)
            
            if mime_type == 'application/pdf':
                return {
                    "valid": True,
                    "mime_type": mime_type
                }
            else:
                return {
                    "valid": False,
                    "error": f"Tipo MIME no válido: {mime_type} (esperado: application/pdf)"
                }
        
        except Exception as e:
            return {
                "valid": False,
                "error": f"Error verificando tipo MIME: {str(e)}"
            }
    
    def _check_suspicious_patterns(self, file_data: bytes) -> Dict[str, Any]:
        """Busca patrones sospechosos en el contenido del archivo."""
        found_patterns = []
        
        for pattern in self.SUSPICIOUS_PATTERNS:
            if pattern in file_data:
                found_patterns.append(pattern.decode('utf-8', errors='ignore'))
        
        if found_patterns:
            return {
                "valid": False,
                "error": f"Patrones sospechosos encontrados: {', '.join(found_patterns)}",
                "patterns": found_patterns
            }
        
        return {
            "valid": True,
            "patterns": []
        }
    
    def _check_malicious_hash(self, file_data: bytes) -> Dict[str, Any]:
        """Verifica el hash del archivo contra una lista de malware conocido."""
        file_md5 = hashlib.md5(file_data).hexdigest()
        file_sha256 = hashlib.sha256(file_data).hexdigest()
        
        if file_md5 in self.MALICIOUS_HASHES or file_sha256 in self.MALICIOUS_HASHES:
            return {
                "valid": False,
                "error": "Archivo coincide con hash de malware conocido",
                "md5": file_md5,
                "sha256": file_sha256
            }
        
        return {
            "valid": True,
            "md5": file_md5,
            "sha256": file_sha256
        }
    
    def _validate_pdf_structure(self, file_data: bytes) -> Dict[str, Any]:
        """Valida la estructura básica del archivo PDF."""
        try:
            # Verificar presencia de elementos básicos de PDF
            if b'%%EOF' not in file_data:
                return {
                    "valid": False,
                    "error": "PDF no contiene marcador de final (%%EOF)"
                }
            
            if b'trailer' not in file_data:
                return {
                    "valid": False,
                    "error": "PDF no contiene trailer"
                }
            
            # Contar objetos PDF básicos
            obj_count = file_data.count(b'obj')
            endobj_count = file_data.count(b'endobj')
            
            if obj_count != endobj_count:
                return {
                    "valid": False,
                    "error": f"Estructura PDF inconsistente: {obj_count} obj vs {endobj_count} endobj"
                }
            
            return {
                "valid": True,
                "objects": obj_count,
                "structure": "básica_válida"
            }
        
        except Exception as e:
            return {
                "valid": False,
                "error": f"Error validando estructura PDF: {str(e)}"
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
        
        # Verificar patrones críticos
        critical_patterns = [b'/JavaScript', b'/JS', b'<script']
        for pattern in critical_patterns:
            if pattern in file_data:
                return False, f"Contenido sospechoso detectado: {pattern.decode('utf-8', errors='ignore')}"
        
        return True, "Archivo válido"


# Instancia global del validador
pdf_validator = PDFSecurityValidator() 