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

def call_cloud_function(file_data: bytes, filename: str) -> Dict[str, Any]:
    """Llama a la Cloud Function para procesar el archivo."""
    if not CLOUD_FUNCTION_URL:
        return {'success': False, 'error': 'URL de Cloud Function no configurada'}
    
    try:
        files = {'file': (filename, file_data, 'application/pdf')}
        
        response = requests.post(
            CLOUD_FUNCTION_URL,
            files=files,
            timeout=600  # 10 minutos timeout
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            error_msg = f"Error HTTP {response.status_code}"
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_msg = error_data['error']
            except:
                error_msg = response.text
            
            return {'success': False, 'error': error_msg}
    
    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'Timeout: El procesamiento tomó demasiado tiempo'}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'error': 'Error de conexión: No se pudo conectar con el servidor'}
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
    """Renderiza el botón de procesamiento."""
    if uploaded_file is None:
        st.warning("⚠️ Primero selecciona un archivo PDF")
        return False
    
    # Botón de procesamiento
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Procesar Documento", type="primary", use_container_width=True):
            return True
    
    return False

def render_processing_status():
    """Renderiza el estado del procesamiento actual."""
    if st.session_state.current_processing:
        st.subheader("⏳ Procesando...")
        
        # Barra de progreso indeterminada
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Simular progreso
        for i in range(100):
            progress_bar.progress(i + 1)
            if i < 30:
                status_text.text("🔄 Convirtiendo PDF a Markdown...")
            elif i < 70:
                status_text.text("🤖 Generando embeddings con OpenAI...")
            else:
                status_text.text("☁️ Subiendo datos a Google Cloud Storage...")
            time.sleep(0.1)
        
        return True
    
    return False

def render_results(result: Dict[str, Any]):
    """Renderiza los resultados del procesamiento."""
    st.subheader("📊 Resultados del Procesamiento")
    
    if result.get('success', False):
        st.success("✅ Documento procesado exitosamente")
        
        # Información del archivo procesado
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📄 Información del Documento")
            st.write(f"**Archivo:** {result.get('filename', 'N/A')}")
            st.write(f"**Mensaje:** {result.get('message', 'N/A')}")
            
        with col2:
            st.subheader("📈 Estadísticas")
            stats = result.get('stats', {})
            st.metric("Chunks generados", stats.get('num_chunks', 0))
            st.metric("Palabras totales", stats.get('total_words', 0))
            st.metric("Dimensión embeddings", stats.get('embedding_dimension', 0))
            st.metric("Vectores creados", stats.get('num_vectors', 0))
        
        # Archivos en GCS
        gcs_files = result.get('gcs_files', {})
        if gcs_files:
            st.subheader("☁️ Archivos en Google Cloud Storage")
            for file_type, file_url in gcs_files.items():
                st.write(f"**{file_type.title()}:** `{file_url}`")
    
    else:
        st.error("❌ Error en el procesamiento")
        error_msg = result.get('error', 'Error desconocido')
        st.error(f"**Error:** {error_msg}")

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
            # Procesar archivo
            try:
                file_data = uploaded_file.read()
                result = call_cloud_function(file_data, uploaded_file.name)
                
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