"""
Paquete UI para la aplicación Streamlit de DrCecim Upload.

Este paquete contiene los componentes de interfaz de usuario, lógica de negocio
y utilidades para la aplicación Streamlit.

Módulos:
- streamlit_ui: Componentes de interfaz de usuario
- streamlit_logic: Lógica de negocio y procesamiento
- streamlit_utils: Utilidades y validaciones

Para usar, importar directamente desde los módulos:
    from ui.streamlit_ui import main_app
    from ui.streamlit_utils import format_file_size
"""

# No hacer imports automáticos para evitar problemas con dependencias
__all__ = [
    'streamlit_ui',
    'streamlit_logic', 
    'streamlit_utils'
] 