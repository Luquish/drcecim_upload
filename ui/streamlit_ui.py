"""
Componentes de interfaz de usuario para la aplicación Streamlit de DrCecim Upload.
Contiene las funciones de renderizado y componentes de UI reutilizables.
"""
import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional

from ui.streamlit_utils import validate_file, extract_file_info
from ui.streamlit_logic import process_document_upload, add_to_processing_history, get_processing_summary
from config.streamlit_constants import (
    # Configuración de página
    PAGE_TITLE, PAGE_ICON, PAGE_LAYOUT, SIDEBAR_STATE,
    
    # Información de la aplicación
    APP_TITLE, APP_DESCRIPTION, APP_VERSION,
    
    # Constantes de UI
    UPLOAD_COLUMNS, INFO_COLUMNS,
    ICON_FILE, ICON_SIZE, ICON_SUCCESS, ICON_ERROR, ICON_PROCESSING,
    
    # Mensajes
    ERROR_NO_FILE_SELECTED, SUCCESS_VALIDATION_PASSED,
    INFO_PROCESSING_STARTED, INSTRUCTIONS_TEXT, HELP_FILE_UPLOAD
)


def setup_page_config() -> None:
    """
    Configura la página de Streamlit con los parámetros correctos.
    """
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout=PAGE_LAYOUT,
        initial_sidebar_state=SIDEBAR_STATE
    )


def render_header() -> None:
    """
    Renderiza el encabezado principal de la aplicación.
    """
    st.title(f"{PAGE_ICON} {APP_TITLE}")
    st.markdown(f"**{APP_DESCRIPTION}** (v{APP_VERSION})")
    st.markdown("---")


def render_sidebar() -> None:
    """
    Renderiza la barra lateral con información adicional.
    """
    with st.sidebar:
        st.header("📋 Información")
        
        st.markdown("""
        ### 🎯 Propósito
        Esta aplicación permite cargar documentos PDF para el chatbot DrCecim de la Facultad de Medicina UBA.
        
        ### 🔄 Proceso
        1. **Subida** - El PDF se sube a Google Cloud Storage
        2. **Conversión** - Se convierte a texto usando Marker
        3. **Chunking** - Se divide en fragmentos procesables
        4. **Embeddings** - Se generan con OpenAI
        5. **Almacenamiento** - Se guarda para el chatbot
        
        ### ⚙️ Configuración
        - **Tamaño máximo:** 50MB
        - **Formatos:** Solo PDF
        - **Procesamiento:** Asíncrono
        - **Embeddings:** OpenAI text-embedding-3-small
        """)
        
        st.markdown("---")
        
        # Mostrar información desde la base de datos
        try:
            from services.database_service import get_database_service
            
            db_service = get_database_service()
            
            # Probar conexión primero
            if db_service.test_connection():
                summary = db_service.get_documents_summary()
                # Mostrar estado de conexión
                st.success("🟢 Base de datos conectada")
            else:
                st.error("🔴 Error de conexión a BD")
                st.metric("📄 Documentos", "N/A")
        except Exception as e:
            st.error(f"🔴 Error: {str(e)}")
            st.metric("📄 Documentos", "N/A")
        
        st.markdown("---")
        
        st.markdown("""
        ### 🆘 Soporte
        - **Email:** drcecim@gmail.com
        - **Docs:** [Wiki del proyecto](https://github.com/medicina-uba/drcecim)
        """)


def render_instructions() -> None:
    """
    Renderiza las instrucciones de uso.
    """
    with st.expander("📖 **Instrucciones de Uso**", expanded=False):
        st.markdown(INSTRUCTIONS_TEXT)


def render_file_uploader() -> Optional[Any]:
    """
    Renderiza el componente de subida de archivos con validación.
    
    Returns:
        Optional[Any]: Archivo subido si es válido, None en caso contrario
    """
    st.markdown("### 📁 **Seleccionar Archivo**")
    
    # Mostrar instrucciones
    render_instructions()
    
    # Subir archivo
    uploaded_file = st.file_uploader(
        "Selecciona un archivo PDF",
        type=['pdf'],
        help=HELP_FILE_UPLOAD
    )
    
    if uploaded_file:
        return render_file_validation(uploaded_file)
    
    return None


def render_file_validation(uploaded_file: Any) -> Optional[Any]:
    """
    Renderiza la validación del archivo subido.
    
    Args:
        uploaded_file: Archivo subido por Streamlit
        
    Returns:
        Optional[Any]: Archivo si es válido, None en caso contrario
    """
    # Extraer información del archivo
    file_info = extract_file_info(uploaded_file)
    
    # Mostrar información del archivo
    col1, col2 = st.columns(INFO_COLUMNS)
    with col1:
        st.info(f"{ICON_FILE} **Archivo:** {file_info['name']}")
        st.info(f"{ICON_SIZE} **Tamaño:** {file_info['size_formatted']}")
    
    with col2:
        # Validar archivo
        validation = validate_file(uploaded_file)
        if validation['valid']:
            st.success(SUCCESS_VALIDATION_PASSED)
            return uploaded_file
        else:
            st.error(f"{ICON_ERROR} {validation['error']}")
            return None


def render_processing_button(uploaded_file: Optional[Any]) -> None:
    """
    Renderiza el botón de procesamiento y maneja la lógica de upload.
    
    Args:
        uploaded_file: Archivo validado listo para procesar
    """
    if uploaded_file is None:
        st.warning(f"⚠️ {ERROR_NO_FILE_SELECTED}")
        return
    
    # Botón de procesamiento
    col1, col2, col3 = st.columns(UPLOAD_COLUMNS)
    with col2:
        if st.button(f"{ICON_PROCESSING} Procesar Documento", type="primary", use_container_width=True):
            process_file_upload(uploaded_file)


def process_file_upload(uploaded_file: Any) -> None:
    """
    Procesa la subida del archivo con feedback en tiempo real.
    
    Args:
        uploaded_file: Archivo a procesar
    """
    # Mostrar mensaje de procesamiento
    with st.spinner(INFO_PROCESSING_STARTED):
        try:
            # Validar archivo nuevamente
            validation = validate_file(uploaded_file)
            if not validation['valid']:
                st.error(f"{ICON_ERROR} Error de validación: {validation['error']}")
                return
            
            # Procesar upload
            file_data = validation['file_data']
            result = process_document_upload(file_data, uploaded_file.name)
            
            # Agregar al historial
            add_to_processing_history(uploaded_file.name, result)
            
            # Mostrar resultado
            render_processing_result(result)
            
        except Exception as e:
            st.error(f"{ICON_ERROR} Error inesperado: {str(e)}")


def render_processing_result(result: Dict[str, Any]) -> None:
    """
    Renderiza el resultado del procesamiento.
    
    Args:
        result: Diccionario con el resultado del procesamiento
    """
    summary = get_processing_summary(result)
    
    if summary['message_type'] == 'success':
        st.success(summary['main_message'])
        
        # Mostrar detalles adicionales
        if summary['details']:
            for detail in summary['details']:
                if detail.startswith('🆔'):
                    st.info(detail)
                elif detail.startswith('⚠️'):
                    st.warning(detail)
                elif detail.startswith('📋'):
                    st.info(detail)
                elif detail.startswith('💡'):
                    st.markdown(f"**{detail}**")
                else:
                    st.markdown(detail)
    else:
        st.error(summary['main_message'])


def render_processing_history() -> None:
    """
    Renderiza el historial de documentos desde la base de datos.
    """
    try:
        from services.database_service import get_database_service
        
        st.markdown("---")
        st.markdown("### 📊 **Historial de Documentos**")
        
        # Obtener servicio de base de datos
        db_service = get_database_service()
        
        # Probar conexión
        if not db_service.test_connection():
            st.error("🔴 No se pudo conectar a la base de datos")
            st.info("📝 Verifica la configuración de conexión en .streamlit/secrets.toml")
            return
        
        # Obtener documentos desde la base de datos
        documents = db_service.get_documents_history()
        
        if not documents:
            st.info("📝 No hay documentos procesados aún.")
            return
        
        # Crear DataFrame para mostrar el historial
        history_data = []
        for doc in documents:
            # Formatear fecha
            created_date = doc['created_at'].strftime('%d/%m/%Y %H:%M') if doc['created_at'] else 'N/A'
            
            # Determinar estado
            status_icon = "✅" if doc['processing_status'] == 'completed' else "⏳" if doc['processing_status'] == 'processing' else "❌"
            status_text = "Completado" if doc['processing_status'] == 'completed' else "Procesando" if doc['processing_status'] == 'processing' else "Error"
            
            history_data.append({
                '📄 Documento': doc['filename'].replace('uploads/', ''),
                '📅 Fecha de Subida': created_date,
                '✅ Estado': f"{status_icon} {status_text}"
            })
        
        if history_data:
            df = pd.DataFrame(history_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
                
    except Exception as e:
        st.error(f"Error cargando historial: {str(e)}")
        st.info("📝 No se pudo cargar el historial desde la base de datos.")


def render_main_interface() -> None:
    """
    Renderiza la interfaz principal de la aplicación.
    """
    # Renderizar componentes principales
    uploaded_file = render_file_uploader()
    
    # Separador visual
    st.markdown("---")
    
    # Botón de procesamiento
    render_processing_button(uploaded_file)
    
    # Historial de procesamiento
    render_processing_history()


def render_footer() -> None:
    """
    Renderiza el pie de página con información adicional.
    """
    st.markdown("---")
    st.markdown(
        f"""
        <div style="text-align: center; color: #666; margin-top: 2rem;">
            <small>
                {APP_TITLE} v{APP_VERSION} | Desarrollado para la Facultad de Medicina UBA<br/>
                Procesamiento seguro con Google Cloud Storage y OpenAI
            </small>
        </div>
        """,
        unsafe_allow_html=True
    )


def show_error_page(error_message: str) -> None:
    """
    Muestra una página de error cuando hay problemas de configuración.
    
    Args:
        error_message: Mensaje de error a mostrar
    """
    st.error(f"🚨 Error de Configuración")
    st.markdown(f"**Error:** {error_message}")
    
    st.markdown("""
    ### 🔧 Posibles soluciones:
    
    1. **Verificar variables de entorno**
       - Revisar que estén configuradas las variables necesarias
       - Verificar el archivo `.streamlit/secrets.toml`
    
    2. **Verificar permisos de Google Cloud**
       - Confirmar que las credenciales están configuradas
       - Verificar acceso al bucket de GCS
    
    3. **Contactar soporte**
       - Email: drcecim@gmail.com
       - Incluir el mensaje de error completo
    """)


def main_app() -> None:
    """
    Función principal que orquesta toda la aplicación.
    """
    try:
        # Configurar página
        setup_page_config()
        
        # Renderizar interfaz
        render_header()
        render_sidebar()
        render_main_interface()
        render_footer()
        
    except ImportError as e:
        show_error_page(f"Error importando dependencias: {str(e)}")
    except Exception as e:
        show_error_page(f"Error inesperado: {str(e)}") 