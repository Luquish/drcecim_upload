"""
Aplicación Streamlit para cargar y procesar documentos PDF usando DrCecim.
"""
import streamlit as st
import requests
import json
import time
from typing import Dict, Any, Optional
from pathlib import Path
import os
from datetime import datetime
import tempfile

# Importar servicio GCS
from services.gcs_service import GCSService

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

# Inicializar estado de la sesión
if 'processing_history' not in st.session_state:
    st.session_state.processing_history = []

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

def upload_file_to_bucket(file_data: bytes, filename: str) -> Dict[str, Any]:
    """Sube el archivo directamente al bucket de GCS para procesamiento asíncrono."""
    try:
        # Inicializar servicio GCS
        gcs_service = GCSService()
        
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(file_data)
            temp_file_path = temp_file.name
        
        try:
            # Subir archivo al bucket (directamente en la raíz para activar el trigger)
            gcs_path = filename
            success = gcs_service.upload_file(
                local_path=temp_file_path,
                gcs_path=gcs_path,
                content_type='application/pdf'
            )
            
            if success:
                return {
                    'success': True,
                    'filename': filename,
                    'message': f'Archivo {filename} subido exitosamente para procesamiento asíncrono'
                }
            else:
                return {
                    'success': False,
                    'error': 'Error al subir el archivo al bucket'
                }
        finally:
            # Limpiar archivo temporal
            os.unlink(temp_file_path)
            
    except Exception as e:
        return {'success': False, 'error': f'Error inesperado: {str(e)}'}

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
        **Pasos para procesar un documento:**
        
        1. **Selecciona un archivo PDF** usando el botón de abajo
        2. **Verifica** que el archivo sea válido (tamaño y tipo)
        3. **Haz clic en "Procesar Documento"** para iniciar el procesamiento
        4. **Espera** mientras el sistema:
           - Convierte el PDF a Markdown
           - Genera chunks de texto
           - Crea embeddings con OpenAI
           - Sube los datos a Google Cloud Storage
        5. **Revisa los resultados** en la sección de resultados
        
        **Notas importantes:**
        - El procesamiento puede tomar varios minutos dependiendo del tamaño del documento
        - Los documentos se procesan usando OpenAI para generar embeddings
        - Los resultados se almacenan en Google Cloud Storage para uso del chatbot
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
    """Renderiza el botón de procesamiento y maneja la subida al bucket."""
    if uploaded_file is None:
        st.warning("⚠️ Primero selecciona un archivo PDF")
        return
    
    # Botón de procesamiento
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Procesar Documento", type="primary", use_container_width=True):
            # Validar archivo
            validation = validate_file(uploaded_file)
            if not validation['valid']:
                st.error(f"❌ Error de validación: {validation['error']}")
                return
            
            # Mostrar mensaje de procesamiento
            with st.spinner("⏳ Subiendo archivo para procesamiento..."):
                # Subir archivo al bucket
                file_data = uploaded_file.read()
                result = upload_file_to_bucket(file_data, uploaded_file.name)
                
                # Agregar al historial
                add_to_history(uploaded_file.name, result)
                
                # Mostrar resultado
                if result['success']:
                    st.success(f"✅ ¡Éxito! El archivo **{uploaded_file.name}** ha sido enviado para procesamiento.")
                    st.info("📋 **Información importante:**")
                    st.markdown("""
                    - El archivo aparecerá en el sistema en **unos minutos**
                    - El procesamiento es completamente **asíncrono**
                    - No necesitas esperar en esta pantalla
                    - Puedes cerrar el navegador y volver después
                    """)
                else:
                    st.error(f"❌ Error al subir el archivo: {result.get('error', 'Error desconocido')}")
                    
                # Limpiar el archivo del uploader
                if 'uploaded_file' in st.session_state:
                    del st.session_state['uploaded_file']

def render_processing_status():
    """Renderiza el estado del procesamiento actual (simplificado para arquitectura asíncrona)."""
    # Esta función ya no es necesaria con la nueva arquitectura asíncrona
    pass

def render_results(result: Dict[str, Any]):
    """Renderiza los resultados del procesamiento (simplificado para arquitectura asíncrona)."""
    # Esta función ya no es necesaria con la nueva arquitectura asíncrona
    # Los resultados se muestran directamente en render_processing_button
    pass

def render_history():
    """Renderiza el historial de procesamiento."""
    if not st.session_state.processing_history:
        st.info("📝 No hay historial de procesamiento")
        return
    
    st.subheader("📚 Historial de Procesamiento")
    
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
    """Función principal de la aplicación (simplificada para arquitectura asíncrona)."""
    # Renderizar componentes
    render_header()
    render_sidebar()
    
    # Área principal
    uploaded_file = render_file_uploader()
    
    # Botón de procesamiento (ahora maneja toda la lógica internamente)
    render_processing_button(uploaded_file)
    
    # Historial
    st.divider()
    render_history()

if __name__ == "__main__":
    main() 