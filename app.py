# app.py
import streamlit as st
import extra_streamlit_components as stx  # Importar la librería de cookies
from ui.state import initialize_session_state, login_user
from ui.auth_page import render_auth_page
from ui.registration_wizard import render_registration_wizard
from ui.main_game_page import render_main_game_page
from data.player_repository import get_player_by_session_token
from data.character_repository import get_commander_by_player_id
from config.app_constants import SESSION_COOKIE_NAME

st.set_page_config(page_title="SuperX Engine", layout="wide")

# 1. Inicializar Cookie Manager (Debe ser al inicio)
cookie_manager = stx.CookieManager()

# 2. Inicializar Estado
initialize_session_state()

# 3. Lógica de Auto-Login (Persistencia)
if not st.session_state.logged_in:
    # Intentar leer la cookie
    cookie_token = cookie_manager.get(cookie=SESSION_COOKIE_NAME)

    if cookie_token:
        # Validar el token contra la base de datos
        player = get_player_by_session_token(cookie_token)
        if player:
            commander = get_commander_by_player_id(player['id'])
            if commander:
                login_user(player, commander)
                st.rerun() # Recargar para mostrar el dashboard inmediatamente

# 4. Enrutador
if not st.session_state.logged_in:
    if st.session_state.is_registering:
        render_registration_wizard()
    else:
        # Pasamos el cookie_manager para poder guardar la cookie al loguearse
        render_auth_page(cookie_manager)
else:
    # Pasamos el cookie_manager para poder borrar la cookie al salir
    render_main_game_page(cookie_manager)