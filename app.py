# app.py (Completo)
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
from ui.planet_surface_view import render_planet_surface  # Importamos la vista de superficie
from data.player_repository import get_player_by_session_token
from data.character_repository import get_commander_by_player_id
from data.database import get_service_container, get_supabase  # Necesitamos get_supabase para la consulta rápida
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
        # --- BARRA LATERAL DE HERRAMIENTAS (DEBUG/ADMIN) ---
        with st.sidebar:
            st.divider()
            st.subheader("🔧 Herramientas Admin")
            
            # Botón para forzar navegación a superficie
            if st.button("🏗️ Ir a Superficie (Test)", help="Carga el primer planeta disponible o activa modo omnisciencia"):
                try:
                    db = get_supabase()
                    player_id = st.session_state.player_id
                    
                    # 1. Intentar buscar un asset propio
                    my_asset = db.table("planet_assets").select("planet_id").eq("player_id", player_id).limit(1).execute()
                    
                    target_id = None
                    if my_asset.data:
                        target_id = my_asset.data[0]['planet_id']
                        st.session_state.debug_omniscience = False
                    else:
                        # 2. Fallback: Cualquier planeta (Modo Omnisciencia)
                        any_planet = db.table("planets").select("id").limit(1).execute()
                        if any_planet.data:
                            target_id = any_planet.data[0]['id']
                            st.session_state.debug_omniscience = True # Flag usado en planet_surface_view
                            st.toast("Modo Omnisciencia Activado (Sin colonias detectadas)")
                    
                    if target_id:
                        st.session_state.view_mode = "planet_surface"
                        st.session_state.selected_planet_id = target_id
                        st.rerun()
                    else:
                        st.error("No se encontraron planetas en la base de datos.")
                        
                except Exception as e:
                    st.error(f"Error al navegar: {e}")

            # Botón de retorno (solo visible si estamos en una vista alternativa)
            if st.session_state.get("view_mode") == "planet_surface":
                if st.button("⬅️ Volver al Comando", use_container_width=True):
                    st.session_state.view_mode = "main"
                    st.session_state.debug_omniscience = False
                    st.rerun()

        # --- LÓGICA DE RENDERIZADO CONDICIONAL ---
        # Si la variable de estado 'view_mode' es 'planet_surface', mostramos esa vista.
        # De lo contrario, mostramos la página principal del juego.
        if st.session_state.get("view_mode") == "planet_surface" and st.session_state.get("selected_planet_id"):
            render_planet_surface(st.session_state.selected_planet_id)
        else:
            render_main_game_page(cookie_manager)


if __name__ == "__main__":
    main()