# ui/main_game_page.py
import streamlit as st
from .state import logout_user, get_player, get_commander
from data.log_repository import get_recent_logs
from services.gemini_service import resolve_player_action

# --- Importar las nuevas vistas ---
from .faction_roster import show_faction_roster
from .recruitment_center import show_recruitment_center
from .galaxy_map_page import show_galaxy_map_page


def render_main_game_page(cookie_manager):
    """
    Página principal del juego con navegación por sidebar.
    """
    player = get_player()
    commander = get_commander()

    if not player or not commander:
        st.error("No se pudieron cargar los datos del jugador o comandante. Por favor, reinicia la sesión.")
        return

    # --- Renderizar el Sidebar de Navegación ---
    # Usamos st.session_state para guardar la página actual
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Puente de Mando"
        
    _render_navigation_sidebar(player, commander, cookie_manager)

    # --- Renderizar la página seleccionada ---
    # Mapeo de nombres de página a funciones que las renderizan
    PAGES = {
        "Puente de Mando": _render_war_room_page,
        "Ficha del Comandante": _render_commander_sheet_page,
        "Comando de Facción": show_faction_roster,
        "Centro de Reclutamiento": show_recruitment_center,
        "Mapa de la Galaxia": show_galaxy_map_page,
    }
    
    # Llama a la función correspondiente a la página seleccionada
    render_func = PAGES.get(st.session_state.current_page, _render_war_room_page)
    render_func()


def _render_navigation_sidebar(player, commander, cookie_manager):
    """Dibuja el sidebar con la información y los botones de navegación."""
    with st.sidebar:
        st.header(f"Facción: {player['faccion_nombre']}")
        if player.get('banner_url'):
            st.image(player['banner_url'], use_column_width=True)

        st.subheader(f"Comandante: {commander['nombre']}")
        
        st.divider()
        st.header("Navegación")

        # Botones para cambiar de página
        if st.button("Puente de Mando", use_container_width=True, type="primary" if st.session_state.current_page == "Puente de Mando" else "secondary"):
            st.session_state.current_page = "Puente de Mando"
            st.rerun()

        if st.button("Mapa de la Galaxia", use_container_width=True, type="primary" if st.session_state.current_page == "Mapa de la Galaxia" else "secondary"):
            st.session_state.current_page = "Mapa de la Galaxia"
            st.rerun()

        st.divider()
        st.header("Gestión de Facción")

        if st.button("Ficha del Comandante", use_container_width=True, type="primary" if st.session_state.current_page == "Ficha del Comandante" else "secondary"):
            st.session_state.current_page = "Ficha del Comandante"
            st.rerun()

        if st.button("Comando de Facción", use_container_width=True, type="primary" if st.session_state.current_page == "Comando de Facción" else "secondary"):
            st.session_state.current_page = "Comando de Facción"
            st.rerun()

        if st.button("Centro de Reclutamiento", use_container_width=True, type="primary" if st.session_state.current_page == "Centro de Reclutamiento" else "secondary"):
            st.session_state.current_page = "Centro de Reclutamiento"
            st.rerun()

        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            logout_user(cookie_manager)
            st.rerun()


# --- Adaptaciones de las vistas originales a funciones de página completas ---

def _render_war_room_page():
    """Página del Puente de Mando (antes tab 'Sala de Guerra')."""
    st.title("Puente de Mando")
    st.subheader("Bitácora de Misión")
    
    player_id = get_player()['id']
    commander_name = get_commander()['nombre']
    
    log_container = st.container(height=300)
    logs = get_recent_logs(player_id) # Asegurarse de pasar el player_id si es necesario
    for log in reversed(logs):
        if "ERROR" not in log['evento_texto']:
            log_container.chat_message("assistant", avatar="📜").write(log['evento_texto'])
            
    action = st.chat_input(f"¿Órdenes, Comandante {commander_name}?")
    if action:
        with st.spinner("Transmitiendo órdenes..."):
            try:
                resolve_player_action(action, player_id)
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ Error: {e}")

def _render_commander_sheet_page():
    """Página de la Ficha del Comandante (antes tab 'Datos')."""
    st.title("Ficha de Servicio del Comandante")
    
    commander = get_commander()
    stats = commander.get('stats_json', {})
    
    st.header(f"Informe de {commander['nombre']}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Biografía")
        st.write(stats.get('bio', {}))

    with col2:
        st.subheader("Atributos")
        st.json(stats.get('atributos', {}))

    st.subheader("Habilidades")
    st.json(stats.get('habilidades', {}))