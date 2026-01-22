# app.py
"""
SuperX Engine - Punto de Entrada Principal.
Juego de estrategia espacial persistente con IA narrativa.
"""

import streamlit as st
import extra_streamlit_components as stx

from ui.state import initialize_session_state, login_user, is_logged_in
from ui.auth_page import render_auth_page
from ui.registration_wizard import render_registration_wizard
from ui.main_game_page import render_main_game_page
from data.player_repository import get_player_by_session_token
from data.character_repository import get_commander_by_player_id
from data.database import get_service_container
from config.app_constants import SESSION_COOKIE_NAME


def check_database_connection() -> bool:
    """
    Verifica la conexión a la base de datos.

    Returns:
        True si la conexión está disponible
    """
    container = get_service_container()
    return container.is_supabase_available()


def try_auto_login(cookie_manager) -> bool:
    """
    Intenta realizar auto-login usando la cookie de sesión.

    Args:
        cookie_manager: Gestor de cookies de Streamlit

    Returns:
        True si el auto-login fue exitoso
    """
    try:
        cookie_token = cookie_manager.get(cookie=SESSION_COOKIE_NAME)

        if not cookie_token:
            return False

        # Validar token contra la base de datos
        player = get_player_by_session_token(cookie_token)
        if not player:
            return False

        # Obtener comandante
        commander = get_commander_by_player_id(player['id'])
        if not commander:
            return False

        # Login exitoso
        login_user(player, commander)
        return True

    except Exception:
        return False


def render_error_page(error_message: str) -> None:
    """
    Renderiza una página de error.

    Args:
        error_message: Mensaje de error a mostrar
    """
    st.error("⚠️ Error de Conexión")
    st.markdown(f"""
    ### No se pudo conectar a los servicios del juego

    **Detalle:** {error_message}

    Por favor, verifica:
    - Tu conexión a internet
    - Que las credenciales de Supabase estén configuradas
    - Que el servidor de base de datos esté disponible

    Recarga la página para reintentar.
    """)


def main():
    """Función principal de la aplicación."""

    # Configuración de página
    st.set_page_config(
        page_title="SuperX Engine",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Verificar conexión a DB
    if not check_database_connection():
        container = get_service_container()
        render_error_page(container.status.supabase_error or "Error desconocido")
        return

    # Inicializar Cookie Manager (debe ser al inicio)
    cookie_manager = stx.CookieManager()

    # Inicializar Estado de Sesión
    initialize_session_state()

    # Lógica de Auto-Login (Persistencia)
    if not is_logged_in():
        if try_auto_login(cookie_manager):
            st.rerun()

    # Enrutador Principal
    if not is_logged_in():
        if st.session_state.get('is_registering', False):
            render_registration_wizard()
        else:
            render_auth_page(cookie_manager)
    else:
        render_main_game_page(cookie_manager)


if __name__ == "__main__":
    main()