"""
Constantes para la aplicación Streamlit de DrCecim Upload.
Centraliza todos los valores configurables y constantes utilizadas en la interfaz.
"""

# =============================================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# =============================================================================

# Configuración de la página
PAGE_TITLE = "DrCecim - Carga de Documentos"
PAGE_ICON = "📚"
PAGE_LAYOUT = "wide"
SIDEBAR_STATE = "expanded"

# Información de la aplicación
APP_TITLE = "DrCecim - Carga de Documentos"
APP_DESCRIPTION = "Sistema de carga y procesamiento de documentos PDF"
APP_VERSION = "1.2.0"

# =============================================================================
# LÍMITES Y RESTRICCIONES DE ARCHIVOS
# =============================================================================

# Tamaños de archivo
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Tipos de archivo permitidos
ALLOWED_FILE_TYPES = ['pdf']
ALLOWED_EXTENSIONS = ['.pdf']

# =============================================================================
# CONFIGURACIÓN DE PROCESAMIENTO
# =============================================================================

# Timeouts
PROCESSING_TIMEOUT_SECONDS = 900  # 15 minutos
UPLOAD_TIMEOUT_SECONDS = 300     # 5 minutos

# Límites de chunks
MAX_CHUNKS_PER_DOCUMENT = 1000
MIN_CHUNK_SIZE_WORDS = 10

# Límites de nombres de archivo
MAX_FILENAME_LENGTH = 100
SAFE_FILENAME_LENGTH = 90

# =============================================================================
# MENSAJES DE LA INTERFAZ
# =============================================================================

# Mensajes de error
ERROR_NO_FILE_SELECTED = "No se seleccionó ningún archivo"
ERROR_FILE_TOO_LARGE = f"El archivo excede el tamaño máximo de {MAX_FILE_SIZE_MB}MB"
ERROR_INVALID_FILE_TYPE = f"Tipo de archivo no permitido. Solo se permiten: {', '.join(ALLOWED_FILE_TYPES)}"
ERROR_UPLOAD_FAILED = "Error al subir el archivo para procesamiento"
ERROR_VALIDATION_FAILED = "Error de validación del archivo"
ERROR_CONNECTION_FAILED = "Error de conectividad"
ERROR_PROCESSING_FAILED = "Error en el procesamiento del documento"

# Mensajes de éxito
SUCCESS_FILE_UPLOADED = "¡Éxito! El archivo ha sido enviado para procesamiento."
SUCCESS_VALIDATION_PASSED = "✅ Archivo válido"

# Mensajes informativos
INFO_PROCESSING_STARTED = "⏳ Subiendo archivo para procesamiento..."
INFO_PROCESSING_ASYNC = "El procesamiento es completamente asíncrono"
INFO_NO_WAIT_REQUIRED = "No necesitas esperar en esta pantalla"
INFO_CHECK_STATUS = "Puedes consultar el estado en la pestaña 'Estado de Documentos'"
INFO_CLOSE_BROWSER = "Puedes cerrar el navegador y volver después"

# Warnings
WARNING_CONNECTIVITY_ISSUE = "⚠️ Error de conectividad al registrar estado"
WARNING_DATA_ISSUE = "⚠️ Error en datos al registrar estado"
WARNING_UNEXPECTED_ERROR = "⚠️ Error inesperado al registrar en el sistema de estado"

# =============================================================================
# CONFIGURACIÓN DE INTERFAZ
# =============================================================================

# Columnas
UPLOAD_COLUMNS = [1, 2, 1]  # Proporción de columnas para el botón de upload
INFO_COLUMNS = 2  # Número de columnas para mostrar información del archivo

# Iconos
ICON_FILE = "📄"
ICON_SIZE = "📊"
ICON_SUCCESS = "✅"
ICON_ERROR = "❌"
ICON_WARNING = "⚠️"
ICON_PROCESSING = "🚀"
ICON_INFO = "📋"
ICON_ID = "🆔"
ICON_TIP = "💡"

# =============================================================================
# TEXTOS DE AYUDA
# =============================================================================

HELP_FILE_UPLOAD = f"Archivo PDF de máximo {MAX_FILE_SIZE_MB}MB"

INSTRUCTIONS_TEXT = """
### 📋 **Instrucciones de Uso**

Para procesar un documento PDF:

1. **Selecciona un archivo PDF** usando el selector de archivos
2. **Verifica** que el archivo sea válido y no exceda el límite de tamaño
3. **Haz clic en "Procesar Documento"** para iniciar el procesamiento
4. **El sistema automáticamente:**
   - Convierte el PDF a Markdown
   - Genera chunks de texto
   - Crea embeddings con OpenAI
   - Sube los datos a Google Cloud Storage
5. **Revisa los resultados** en la sección de resultados

**Notas importantes:**
- El procesamiento puede tomar varios minutos dependiendo del tamaño del documento
- Los documentos se procesan usando OpenAI para generar embeddings
- Los resultados se almacenan en Google Cloud Storage para uso del chatbot
"""

IMPORTANT_INFO_TEXT = """
- El archivo aparecerá en el sistema en **unos minutos**
- El procesamiento es completamente **asíncrono**
- No necesitas esperar en esta pantalla
- Puedes consultar el estado en la pestaña "Estado de Documentos"
- Puedes cerrar el navegador y volver después
"""

# =============================================================================
# CONFIGURACIÓN DE LOGS Y DEBUGGING
# =============================================================================

# Niveles de log para diferentes operaciones
LOG_LEVEL_UPLOAD = "INFO"
LOG_LEVEL_VALIDATION = "INFO"
LOG_LEVEL_PROCESSING = "INFO"
LOG_LEVEL_ERROR = "ERROR"

# Prefijos para logs
LOG_PREFIX_UPLOAD = "[UPLOAD]"
LOG_PREFIX_VALIDATION = "[VALIDATION]"
LOG_PREFIX_PROCESSING = "[PROCESSING]"
LOG_PREFIX_ERROR = "[ERROR]" 