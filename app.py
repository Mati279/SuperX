# app.py
import streamlit as st
import extra_streamlit_components as stx

# Imports corregidos
from ui.state import initialize_session_state, is_logged_in, is_registering
from ui.auth_page import render_auth_page
from ui.registration_wizard import render_registration_wizard
from ui.main_game_page import render_main_game_page
from data.player_repository import get_player_by_session_token
from config.app_constants import SESSION_COOKIE_NAME, TIMEZONE_NAME
import os

# Configuración de página
st.set_page_config(
    page_title="SuperX",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Cookie Manager
cookie_manager = stx.CookieManager()

# Inicialización
initialize_session_state()

# --- Lógica de Ruteo ---
if is_logged_in():
    render_main_game_page(cookie_manager)
elif is_registering():
    render_registration_wizard(cookie_manager)
else:
    # Intento de Login con Cookie
    token = cookie_manager.get(SESSION_COOKIE_NAME)
    if token and not is_logged_in():
        player = get_player_by_session_token(token)
        if player:
            from ui.state import login_user
            login_user(player, cookie_manager)
            st.rerun()
    
    render_auth_page(cookie_manager)