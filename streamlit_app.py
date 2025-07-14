"""
Aplicación Streamlit para cargar y procesar documentos PDF usando DrCecim.
"""
import streamlit as st
import time
from typing import Dict, Any, Optional
from pathlib import Path
import os
from datetime import datetime

# Configurar la página
st.set_page_config(
    page_title="DrCecim - Carga de Documentos",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Importar configuración
try:
    from config.settings import (
        STREAMLIT_TITLE,
        STREAMLIT_DESCRIPTION,
        MAX_FILE_SIZE_MB,
        ALLOWED_FILE_TYPES,
        GCS_BUCKET_NAME
    )
except ImportError:
    # Valores por defecto si no se puede importar
    STREAMLIT_TITLE = "DrCecim - Carga de Documentos"
    STREAMLIT_DESCRIPTION = "Sistema de carga y procesamiento de documentos PDF"
    MAX_FILE_SIZE_MB = 50
    ALLOWED_FILE_TYPES = ['pdf']
    GCS_BUCKET_NAME = "drcecim-chatbot-storage"

# =============================================================================
# CONFIGURACIÓN Y ESTADO
# =============================================================================

# URL de la Cloud Function (configurar según tu deployment)
CLOUD_FUNCTION_URL = st.secrets.get("CLOUD_FUNCTION_URL", "")

# Inicializar estado de la sesión
if 'processing_history' not in st.session_state:
    st.session_state.processing_history = []

if 'current_processing' not in st.session_state:
    st.session_state.current_processing = None

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def format_file_size(size_bytes: int) -> str:
    """Formatea el tamaño del archivo de manera legible."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

def validate_file(uploaded_file) -> Dict[str, Any]:
    """Valida que el archivo sea válido para procesamiento."""
    if not uploaded_file:
        return {'valid': False, 'error': 'No se seleccionó ningún archivo'}
    
    # Verificar extensión
    file_extension = Path(uploaded_file.name).suffix.lower().lstrip('.')
    if file_extension not in ALLOWED_FILE_TYPES:
        return {
            'valid': False,
            'error': f'Tipo de archivo no permitido. Solo se permiten: {", ".join(ALLOWED_FILE_TYPES)}'
        }
    
    # Verificar tamaño
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return {
            'valid': False,
            'error': f'El archivo excede el tamaño máximo de {MAX_FILE_SIZE_MB}MB'
        }
    
    return {'valid': True}

def upload_file_to_gcs(file_data: bytes, filename: str) -> Dict[str, Any]:
    """Sube el archivo directamente a Google Cloud Storage."""
    try:
        # Importar servicio GCS
        from services.gcs_service import GCSService
        
        # Inicializar servicio GCS
        gcs_service = GCSService()
        
        # Crear archivo temporal
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file_data)
            tmp_file_path = tmp_file.name
        
        try:
            # Subir archivo al bucket (esto activará automáticamente el pipeline)
            gcs_path = filename  # Subir directamente al root del bucket
            success = gcs_service.upload_file(tmp_file_path, gcs_path)
            
            if success:
                return {
                    'success': True, 
                    'filename': filename,
                    'gcs_path': gcs_path,
                    'message': 'Archivo subido exitosamente. El procesamiento comenzará automáticamente.'
                }
            else:
                return {'success': False, 'error': 'Error al subir archivo a Google Cloud Storage'}
                
        finally:
            # Limpiar archivo temporal
            if os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)
    
    except Exception as e:
        return {'success': False, 'error': f'Error al subir archivo: {str(e)}'}

def add_to_history(filename: str, result: Dict[str, Any]):
    """Agrega un resultado al historial de procesamiento."""
    history_item = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'filename': filename,
        'result': result
    }
    st.session_state.processing_history.insert(0, history_item)
    
    # Mantener solo los últimos 10 items
    if len(st.session_state.processing_history) > 10:
        st.session_state.processing_history = st.session_state.processing_history[:10]

# =============================================================================
# COMPONENTES DE LA INTERFAZ
# =============================================================================

def render_header():
    """Renderiza el encabezado de la aplicación."""
    st.title(STREAMLIT_TITLE)
    st.markdown(f"**{STREAMLIT_DESCRIPTION}**")
    
    # Información del sistema
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tamaño máximo", f"{MAX_FILE_SIZE_MB} MB")
    with col2:
        st.metric("Tipos permitidos", ", ".join(ALLOWED_FILE_TYPES).upper())
    with col3:
        st.metric("Bucket GCS", GCS_BUCKET_NAME)
    
    st.divider()

def render_file_uploader():
    """Renderiza el componente de carga de archivos."""
    st.subheader("📁 Subir Documento PDF")
    
    # Instrucciones
    with st.expander("📋 Instrucciones", expanded=False):
        st.markdown("""
        **Pasos para cargar un documento:**
        
        1. **Selecciona un archivo PDF** usando el botón de abajo
        2. **Verifica** que el archivo sea válido (tamaño y tipo)
        3. **Haz clic en "Subir Documento"** para enviarlo al sistema
        4. **El procesamiento comenzará automáticamente** en segundo plano:
           - Conversión del PDF a chunks de texto
           - Generación de embeddings con OpenAI
           - Actualización del índice FAISS
        5. **El documento aparecerá en el sistema** en unos minutos
        
        **Notas importantes:**
        - El procesamiento es completamente asíncrono - no necesitas esperar
        - Los documentos se procesan usando OpenAI para generar embeddings
        - Los resultados se almacenan en Google Cloud Storage para uso del chatbot
        - El sistema usa una arquitectura orientada a eventos para mayor robustez
        """)
    
    # Subir archivo
    uploaded_file = st.file_uploader(
        "Selecciona un archivo PDF",
        type=['pdf'],
        help=f"Archivo PDF de máximo {MAX_FILE_SIZE_MB}MB"
    )
    
    if uploaded_file:
        # Mostrar información del archivo
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"📄 **Archivo:** {uploaded_file.name}")
            st.info(f"📊 **Tamaño:** {format_file_size(uploaded_file.size)}")
        
        with col2:
            # Validar archivo
            validation = validate_file(uploaded_file)
            if validation['valid']:
                st.success("✅ Archivo válido")
            else:
                st.error(f"❌ {validation['error']}")
                return None
        
        return uploaded_file
    
    return None

def render_processing_button(uploaded_file):
    """Renderiza el botón de procesamiento."""
    if uploaded_file is None:
        st.warning("⚠️ Primero selecciona un archivo PDF")
        return False
    
    # Botón de carga
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📤 Subir Documento", type="primary", use_container_width=True):
            return True
    
    return False

def render_processing_status():
    """Renderiza el estado del procesamiento actual."""
    if st.session_state.current_processing:
        st.subheader("📤 Subiendo archivo...")
        
        # Spinner simple
        with st.spinner("Subiendo archivo a Google Cloud Storage..."):
            time.sleep(1)  # Breve pausa para mostrar el spinner
        
        return True
    
    return False

def render_results(result: Dict[str, Any]):
    """Renderiza los resultados del procesamiento."""
    st.subheader("📊 Resultado de la Carga")
    
    if result.get('success', False):
        st.success("✅ ¡Éxito! Archivo subido correctamente")
        
        # Información del archivo subido
        st.info(f"📄 **Archivo:** {result.get('filename', 'N/A')}")
        st.info(f"💬 **Mensaje:** {result.get('message', 'N/A')}")
        
        # Información sobre el procesamiento automático
        st.markdown("### 🔄 ¿Qué sigue?")
        st.write("El archivo se está procesando automáticamente en segundo plano:")
        st.write("1. ✅ **Paso 1**: Conversión de PDF a chunks de texto")
        st.write("2. ⏳ **Paso 2**: Generación de embeddings con OpenAI")
        st.write("3. ⏳ **Paso 3**: Actualización del índice FAISS")
        st.write("")
        st.write("📋 **El documento aparecerá en el sistema en unos minutos.**")
        
        # Archivos en GCS
        gcs_path = result.get('gcs_path')
        if gcs_path:
            st.write(f"📁 **Ubicación:** `{gcs_path}`")
    
    else:
        st.error("❌ Error al subir archivo")
        error_msg = result.get('error', 'Error desconocido')
        st.write(f"**Error:** {error_msg}")
        
        # Sugerencias de solución
        st.subheader("💡 Sugerencias")
        st.write("- Verifica que el archivo PDF no esté dañado")
        st.write("- Asegúrate de que el archivo tenga contenido de texto")
        st.write("- Intenta con un archivo más pequeño")
        st.write("- Verifica la configuración de Google Cloud Storage")

def render_history():
    """Renderiza el historial de carga de documentos."""
    if not st.session_state.processing_history:
        st.info("📝 No hay historial de cargas")
        return
    
    st.subheader("📚 Historial de Cargas")
    
    for i, item in enumerate(st.session_state.processing_history):
        with st.expander(f"📄 {item['filename']} - {item['timestamp']}", expanded=i==0):
            result = item['result']
            if result.get('success', False):
                st.success("✅ Procesado exitosamente")
                stats = result.get('stats', {})
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Chunks", stats.get('num_chunks', 0))
                with col2:
                    st.metric("Palabras", stats.get('total_words', 0))
                with col3:
                    st.metric("Vectores", stats.get('num_vectors', 0))
            else:
                st.error("❌ Error en procesamiento")
                st.error(result.get('error', 'Error desconocido'))

def render_sidebar():
    """Renderiza la barra lateral con información adicional."""
    st.sidebar.header("🔧 Configuración")
    
    # Configuración de la Cloud Function
    st.sidebar.subheader("☁️ Cloud Function")
    if CLOUD_FUNCTION_URL:
        st.sidebar.success("✅ Configurada")
        st.sidebar.text(f"URL: {CLOUD_FUNCTION_URL[:50]}...")
    else:
        st.sidebar.error("❌ No configurada")
        st.sidebar.text("Configura CLOUD_FUNCTION_URL en secrets")
    
    # Información del sistema
    st.sidebar.subheader("📊 Sistema")
    st.sidebar.info(f"Bucket: {GCS_BUCKET_NAME}")
    st.sidebar.info(f"Tamaño máx: {MAX_FILE_SIZE_MB}MB")
    st.sidebar.info(f"Tipos: {', '.join(ALLOWED_FILE_TYPES)}")
    
    # Botón para limpiar historial
    st.sidebar.subheader("🧹 Mantenimiento")
    if st.sidebar.button("Limpiar historial", help="Elimina el historial de procesamiento"):
        st.session_state.processing_history = []
        st.sidebar.success("Historial limpiado")

# =============================================================================
# APLICACIÓN PRINCIPAL
# =============================================================================

def main():
    """Función principal de la aplicación."""
    # Renderizar componentes
    render_header()
    render_sidebar()
    
    # Área principal
    uploaded_file = render_file_uploader()
    
    # Botón de procesamiento
    if render_processing_button(uploaded_file):
        st.session_state.current_processing = True
        
        # Mostrar estado de procesamiento
        if render_processing_status():
            # Subir archivo a GCS
            try:
                file_data = uploaded_file.read()
                result = upload_file_to_gcs(file_data, uploaded_file.name)
                
                # Agregar al historial
                add_to_history(uploaded_file.name, result)
                
                # Mostrar resultados
                render_results(result)
                
            except Exception as e:
                st.error(f"Error inesperado: {str(e)}")
                result = {'success': False, 'error': str(e)}
                add_to_history(uploaded_file.name, result)
            
            finally:
                st.session_state.current_processing = None
                st.rerun()
    
    # Historial
    st.divider()
    render_history()

if __name__ == "__main__":
    main() 