"""
Lógica de negocio para la aplicación Streamlit de DrCecim Upload.
Contiene las funciones de procesamiento, upload y manejo de estado.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

# Imports con manejo de errores
try:
    from services.gcs_service import GCSService
except ImportError as e:
    import logging
    logging.error(f"Error importando GCSService: {e}")
    raise ImportError("No se pudo importar GCSService. Verificar instalación del paquete.")

try:
    from services.status_service import StatusService, DocumentStatus
except ImportError as e:
    import logging
    logging.error(f"Error importando StatusService: {e}")
    raise ImportError("No se pudo importar StatusService. Verificar instalación del paquete.")

try:
    from config.streamlit_constants import (
        SUCCESS_FILE_UPLOADED,
        ERROR_UPLOAD_FAILED,
        ERROR_CONNECTION_FAILED,
        WARNING_CONNECTIVITY_ISSUE,
        WARNING_DATA_ISSUE,
        WARNING_UNEXPECTED_ERROR,
        IMPORTANT_INFO_TEXT
    )
except ImportError as e:
    import logging
    logging.error(f"Error importando constantes: {e}")
    # Valores por defecto en caso de error
    SUCCESS_FILE_UPLOADED = "¡Éxito! El archivo ha sido enviado para procesamiento."
    ERROR_UPLOAD_FAILED = "Error al subir el archivo para procesamiento"
    ERROR_CONNECTION_FAILED = "Error de conectividad"
    WARNING_CONNECTIVITY_ISSUE = "⚠️ Error de conectividad al registrar estado"
    WARNING_DATA_ISSUE = "⚠️ Error en datos al registrar estado"
    WARNING_UNEXPECTED_ERROR = "⚠️ Error inesperado al registrar en el sistema de estado"
    IMPORTANT_INFO_TEXT = """
    - El archivo aparecerá en el sistema en **unos minutos**
    - El procesamiento es completamente **asíncrono**
    - No necesitas esperar en esta pantalla
    - Puedes cerrar el navegador y volver después
    """

# Configuración de logging
import logging
logger = logging.getLogger(__name__)


def upload_file_to_bucket(file_data: bytes, filename: str) -> Dict[str, Any]:
    """
    Sube un archivo al bucket de GCS para procesamiento.
    
    Args:
        file_data (bytes): Datos del archivo
        filename (str): Nombre del archivo
        
    Returns:
        Dict con 'success' (bool) y información del resultado
        
    Raises:
        ConnectionError: Si hay problemas de conectividad con GCS
        ValueError: Si los datos del archivo son inválidos
        PermissionError: Si no hay permisos para escribir en GCS
    """
    try:
        # Importar configuración de bucket (lazy import para manejo de errores)
        from config.settings import GCS_BUCKET_NAME
        
        # Inicializar servicio GCS con el bucket configurado
        # Esto establecerá la conexión con Google Cloud Storage
        gcs_service = GCSService(bucket_name=GCS_BUCKET_NAME)
        
        # Usar nombre original del archivo sin timestamp
        # Esto permite mejor identificación y evita duplicados innecesarios
        unique_filename = f"uploads/{filename}"
        
        # Subir archivo al bucket usando el servicio GCS
        # upload_bytes es un método que maneja la subida de datos binarios
        upload_success = gcs_service.upload_bytes(
            file_data, 
            unique_filename
        )
        
        if upload_success:
            logger.info(f"Archivo subido exitosamente: {unique_filename}")
            return {
                'success': True,
                'filename': unique_filename,
                'original_filename': filename,
                'uploaded_at': datetime.now().isoformat(),
                'size': len(file_data)
            }
        else:
            logger.error(f"Error subiendo archivo: {filename}")
            return {
                'success': False,
                'error': ERROR_UPLOAD_FAILED,
                'filename': filename
            }
            
    except ConnectionError as e:
        logger.error(f"Error de conectividad subiendo archivo: {str(e)}")
        raise ConnectionError(f"Error de conectividad con GCS: {str(e)}")
    except ValueError as e:
        logger.error(f"Datos de archivo inválidos: {str(e)}")
        raise ValueError(f"Datos del archivo inválidos: {str(e)}")
    except PermissionError as e:
        logger.error(f"Sin permisos para subir archivo: {str(e)}")
        raise PermissionError(f"Sin permisos para GCS: {str(e)}")
    except Exception as e:
        logger.error(f"Error inesperado subiendo archivo: {str(e)}")
        return {
            'success': False,
            'error': f"Error inesperado: {str(e)}",
            'filename': filename
        }


def register_document_status(filename: str) -> Optional[str]:
    """
    Registra un documento en el sistema de estado.
    
    Args:
        filename (str): Nombre del archivo
        
    Returns:
        Optional[str]: ID del documento registrado, None si hay error
        
    Raises:
        ConnectionError: Si hay problemas de conectividad
        ValueError: Si los datos son inválidos
    """
    try:
        status_service = StatusService()
        document_id = status_service.register_document(filename)
        logger.info(f"Documento registrado con ID: {document_id}")
        return document_id
        
    except ConnectionError as e:
        logger.error(f"Error de conectividad registrando documento: {str(e)}")
        raise ConnectionError(str(e))
    except ValueError as e:
        logger.error(f"Error en datos registrando documento: {str(e)}")
        raise ValueError(str(e))
    except Exception as e:
        logger.error(f"Error inesperado registrando documento: {str(e)}")
        raise Exception(str(e))


def add_to_processing_history(filename: str, result: Dict[str, Any]) -> None:
    """
    Agrega un resultado al historial de procesamiento de la sesión.
    
    Args:
        filename (str): Nombre del archivo procesado
        result (Dict[str, Any]): Resultado del procesamiento
    """
    import streamlit as st
    
    # Inicializar historial si no existe
    if 'processing_history' not in st.session_state:
        st.session_state.processing_history = []
    
    # Agregar entrada al historial
    history_entry = {
        'filename': filename,
        'timestamp': datetime.now().isoformat(),
        'success': result.get('success', False),
        'result': result
    }
    
    st.session_state.processing_history.append(history_entry)
    
    # Limitar historial a últimos 50 elementos
    if len(st.session_state.processing_history) > 50:
        st.session_state.processing_history = st.session_state.processing_history[-50:]


def process_document_upload(file_data: bytes, filename: str) -> Dict[str, Any]:
    """
    Procesa la carga completa de un documento.
    
    Args:
        file_data (bytes): Datos del archivo
        filename (str): Nombre del archivo
        
    Returns:
        Dict con el resultado completo del procesamiento
    """
    try:
        # PASO 1: Subir archivo al bucket de GCS
        # Este paso almacena el archivo en Google Cloud Storage donde será
        # procesado por las Cloud Functions de manera asíncrona
        upload_result = upload_file_to_bucket(file_data, filename)
        
        # Si falló la subida, retornar inmediatamente el error
        if not upload_result['success']:
            return upload_result
        
        # PASO 2: Registrar documento en el sistema de estado
        # Este paso permite rastrear el progreso del procesamiento
        # Se maneja de forma independiente para que el upload no falle
        # si hay problemas con el sistema de estado
        try:
            document_id = register_document_status(filename)
            upload_result['document_id'] = document_id
            upload_result['status_registered'] = True
            
        except ConnectionError as e:
            # El upload fue exitoso pero falló el registro de estado por conectividad
            # Esto no es crítico - el archivo se procesará igual
            upload_result['status_registered'] = False
            upload_result['status_error'] = WARNING_CONNECTIVITY_ISSUE
            upload_result['status_error_detail'] = str(e)
            
        except ValueError as e:
            # Error en los datos para el registro de estado
            upload_result['status_registered'] = False
            upload_result['status_error'] = WARNING_DATA_ISSUE
            upload_result['status_error_detail'] = str(e)
            
        except Exception as e:
            upload_result['status_registered'] = False
            upload_result['status_error'] = WARNING_UNEXPECTED_ERROR
            upload_result['status_error_detail'] = str(e)
        
        return upload_result
        
    except (ConnectionError, ValueError, PermissionError) as e:
        # Errores específicos que se propagan
        return {
            'success': False,
            'error': str(e),
            'filename': filename,
            'error_type': type(e).__name__
        }
    except Exception as e:
        # Error inesperado
        logger.error(f"Error inesperado en procesamiento completo: {str(e)}")
        return {
            'success': False,
            'error': f"Error inesperado: {str(e)}",
            'filename': filename,
            'error_type': 'UnexpectedError'
        }


def get_processing_summary(result: Dict[str, Any]) -> Dict[str, str]:
    """
    Genera un resumen de procesamiento para mostrar en la UI.
    
    Args:
        result (Dict[str, Any]): Resultado del procesamiento
        
    Returns:
        Dict con mensaje principal y detalles para la UI
    """
    if not result.get('success', False):
        return {
            'main_message': f"❌ Error: {result.get('error', 'Error desconocido')}",
            'message_type': 'error',
            'details': None
        }
    
    filename = result.get('original_filename', result.get('filename', 'archivo'))
    main_message = f"✅ {SUCCESS_FILE_UPLOADED.replace('**{uploaded_file.name}**', f'**{filename}**')}"
    
    details = []
    
    # Información del documento
    if result.get('document_id'):
        details.append(f"🆔 **ID del documento:** `{result['document_id']}`")
    
    # Estado del registro
    if not result.get('status_registered', True):
        details.append(f"{result.get('status_error', WARNING_UNEXPECTED_ERROR)}")
    
    # Información importante
    details.append(f"📋 **Información importante:**")
    details.append(IMPORTANT_INFO_TEXT)
    
    # Consejo sobre el ID
    if result.get('document_id'):
        details.append(f"💡 **Consejo:** Copia este ID para consultar el estado: `{result['document_id']}`")
    
    return {
        'main_message': main_message,
        'message_type': 'success',
        'details': details
    }


def validate_cloud_function_url() -> bool:
    """
    Valida que la URL de Cloud Function esté configurada.
    
    Returns:
        bool: True si la URL está configurada
    """
    try:
        import streamlit as st
        url = st.secrets.get("CLOUD_FUNCTION_URL")
        return url is not None and url.strip() != ""
    except Exception:
        return False 

def get_documents_history_from_db() -> List[Dict[str, Any]]:
    """
    Obtiene el historial de documentos desde la base de datos PostgreSQL.
    
    Returns:
        List[Dict]: Lista de documentos con su información completa
    """
    try:
        from services.database_service import get_database_service
        db_service = get_database_service()
        return db_service.get_documents_history()
    except Exception as e:
        logger.error(f"Error obteniendo historial desde DB: {str(e)}")
        return []

 