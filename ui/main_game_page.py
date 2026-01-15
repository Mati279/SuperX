# ui/main_game_page.py
import streamlit as st
from .state import logout_user
from data.log_repository import get_recent_logs
from services.gemini_service import resolve_player_action

def render_main_game_page():
    """
    Renderiza la interfaz principal del juego para un jugador autenticado.
    """
    player = st.session_state.player_data
    commander = st.session_state.commander_data
    
    stats = commander.get('stats_json', {}) if commander else {}
    bio = stats.get('bio', {})
    nombre_comandante = bio.get('nombre', 'Desconocido')

    st.markdown(f"## Facción: {player['faccion_nombre']} | Comandante: {nombre_comandante}")
    if player.get('banner_url'):
        st.image(player['banner_url'], width=150)

    _render_sidebar(bio)
    
    tab_guerra, tab_datos = st.tabs(["Sala de Guerra", "Datos del Comandante"])

    with tab_guerra:
        _render_war_room(nombre_comandante, player['id'])

    with tab_datos:
        _render_commander_sheet(stats)

def _render_sidebar(bio: dict):
    """Renderiza la barra lateral con información del comandante y botón de logout."""
    st.sidebar.header("Terminal de Mando")
    st.sidebar.success(f"Líder: {bio.get('nombre', 'N/A')}")
    st.sidebar.info(f"Clase: {bio.get('clase', 'N/A')} | Raza: {bio.get('raza', 'N/A')}")
    
    if st.sidebar.button("Cerrar Sesión"):
        logout_user()
        
    st.sidebar.divider()

def _render_war_room(nombre_comandante: str, player_id: int):
    """Renderiza la pestaña 'Sala de Guerra' con logs y el input de acción."""
    st.subheader("Bitácora de Misión")
    log_container = st.container(height=300)
    
    # Obtenemos logs desde el repositorio
    logs = get_recent_logs()
    for log in reversed(logs):
        if "ERROR" not in log['evento_texto']:
            log_container.chat_message("assistant", avatar="📜").write(log['evento_texto'])

    # Input para la acción del jugador
    action = st.chat_input(f"¿Órdenes, Comandante {nombre_comandante}?")
    if action:
        with st.spinner("Transmitiendo órdenes al alto mando..."):
            try:
                # La acción se resuelve a través del servicio de IA
                resolve_player_action(action, player_id)
                st.rerun() # Recargamos para ver el nuevo log y posibles cambios
            except Exception as e:
                st.error(f"⚠️ Error de Comunicación: {e}")

def _render_commander_sheet(stats: dict):
    """Renderiza la pestaña 'Datos del Comandante' con sus estadísticas."""
    st.subheader("Hoja de Servicio del Comandante")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Atributos")
        st.json(stats.get('atributos', {}))
    with col2:
        st.markdown("### Habilidades")
        st.json(stats.get('habilidades', {}))
    
    st.markdown("### Biografía y Expediente")
    st.write(stats.get('bio', {}))
