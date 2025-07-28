"""
Aplicación Streamlit para cargar y procesar documentos PDF usando DrCecim.
Versión refactorizada con arquitectura modular mejorada.

Esta aplicación permite a los usuarios:
1. Subir archivos PDF
2. Validar archivos automáticamente
3. Procesar documentos de manera asíncrona
4. Monitorear el estado del procesamiento

Arquitectura:
- ui/streamlit_ui.py: Componentes de interfaz de usuario
- ui/streamlit_logic.py: Lógica de negocio y procesamiento
- ui/streamlit_utils.py: Utilidades y validaciones
- config/streamlit_constants.py: Constantes y configuración
"""

import logging
from typing import Optional

# Configurar logging básico para la aplicación
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main() -> None:
    """
    Función principal de la aplicación Streamlit.
    
    Maneja la importación y ejecución de la interfaz principal,
    con manejo robusto de errores de configuración.
    """
    try:
        # Importar la aplicación principal
        from ui.streamlit_ui import main_app
        
        # Ejecutar la aplicación
        main_app()
        
    except ImportError as e:
        # Error de importación - posiblemente dependencias faltantes
        logger.error(f"Error de importación: {str(e)}")
        _show_import_error(str(e))
        
    except ModuleNotFoundError as e:
        # Módulo no encontrado - posiblemente configuración incorrecta
        logger.error(f"Módulo no encontrado: {str(e)}")
        _show_module_error(str(e))
        
    except Exception as e:
        # Error inesperado
        logger.error(f"Error inesperado en aplicación principal: {str(e)}")
        _show_unexpected_error(str(e))


def _show_import_error(error_message: str) -> None:
    """
    Muestra página de error para problemas de importación.
    
    Args:
        error_message: Mensaje de error de importación
    """
    import streamlit as st
    
    st.set_page_config(
        page_title="DrCecim - Error de Configuración",
        page_icon="🚨",
        layout="wide"
    )
    
    st.error("🚨 Error de Importación")
    st.markdown(f"**Error:** {error_message}")
    
    st.markdown("""
    ### 🔧 Posibles soluciones:
    
    1. **Instalar dependencias faltantes**
       ```bash
       pip install -r requirements.txt
       ```
    
    2. **Verificar estructura del proyecto**
       - Confirmar que existen los directorios `ui/`, `config/`, `services/`
       - Verificar que todos los archivos `__init__.py` están presentes
    
    3. **Reinstalar el paquete**
       ```bash
       pip install -e .
       ```
    """)


def _show_module_error(error_message: str) -> None:
    """
    Muestra página de error para módulos no encontrados.
    
    Args:
        error_message: Mensaje de error de módulo
    """
    import streamlit as st
    
    st.set_page_config(
        page_title="DrCecim - Módulo No Encontrado",
        page_icon="📦",
        layout="wide"
    )
    
    st.error("📦 Módulo No Encontrado")
    st.markdown(f"**Error:** {error_message}")
    
    st.markdown("""
    ### 🔧 Posibles soluciones:
    
    1. **Verificar instalación del paquete**
       ```bash
       pip install -e .
       ```
    
    2. **Verificar estructura de directorios**
       - Confirmar que el directorio actual es la raíz del proyecto
       - Verificar que existen los archivos de configuración
    
    3. **Configurar PYTHONPATH**
       ```bash
       export PYTHONPATH="${PYTHONPATH}:$(pwd)"
       ```
    """)


def _show_unexpected_error(error_message: str) -> None:
    """
    Muestra página de error para errores inesperados.
    
    Args:
        error_message: Mensaje de error inesperado
    """
    import streamlit as st
    
    st.set_page_config(
        page_title="DrCecim - Error Inesperado",
        page_icon="⚠️",
        layout="wide"
    )
    
    st.error("⚠️ Error Inesperado")
    st.markdown(f"**Error:** {error_message}")
    
    st.markdown("""
    ### 🔧 Posibles soluciones:
    
    1. **Reiniciar la aplicación**
       - Detener Streamlit (Ctrl+C)
       - Volver a ejecutar: `streamlit run streamlit_app.py`
    
    2. **Verificar logs**
       - Revisar la consola para errores adicionales
       - Verificar archivos de log si están configurados
    
    3. **Contactar soporte**
       - Email: soporte@medicina.uba.ar
       - Incluir el mensaje de error completo
       - Incluir información del entorno (Python, OS, etc.)
    """)


# Ejecutar aplicación si se ejecuta directamente
if __name__ == "__main__":
    main() 