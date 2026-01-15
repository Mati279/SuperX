# app.py - Punto de Entrada Principal
import streamlit as st
from ui.state import initialize_session_state
from ui.auth_page import render_auth_page
from ui.registration_wizard import render_registration_wizard
from ui.main_game_page import render_main_game_page

# --- Configuración de la Página ---
st.set_page_config(
    page_title="SuperX Engine",
    layout="wide",
    initial_sidebar_state="auto"
)

# 1. Inicializar el estado de la sesión
# Esta función asegura que todas las claves necesarias existan en st.session_state
initialize_session_state()

# 2. Enrutador Principal de la Aplicación
# Decide qué página o componente mostrar basándose en el estado actual.
if not st.session_state.logged_in:
    if st.session_state.is_registering:
        # Muestra el wizard de registro si el usuario está en ese flujo
        render_registration_wizard()
    else:
        # Muestra la página de login/registro por defecto
        render_auth_page()
else:
    # Si el usuario está logueado, muestra la interfaz principal del juego
    render_main_game_page()
