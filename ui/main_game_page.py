# ui/main_game_page.py
import streamlit as st
from .state import logout_user
from data.log_repository import get_recent_logs
from services.gemini_service import resolve_player_action

def render_main_game_page(cookie_manager): # <--- Recibe el cookie_manager
    # ... (Resto del código igual) ...
    player = st.session_state.player_data
    commander = st.session_state.commander_data
    
    stats = commander.get('stats_json', {}) if commander else {}
    bio = stats.get('bio', {})
    nombre_comandante = bio.get('nombre', 'Desconocido')

    st.markdown(f"## Facción: {player['faccion_nombre']} | Comandante: {nombre_comandante}")
    if player.get('banner_url'):
        st.image(player['banner_url'], width=150)

    _render_sidebar(bio, cookie_manager) # Pasamos el manager al sidebar
    
    tab_guerra, tab_datos = st.tabs(["Sala de Guerra", "Datos del Comandante"])
    # ... (Resto de tabs igual) ...
    with tab_guerra:
        _render_war_room(nombre_comandante, player['id'])

    with tab_datos:
        _render_commander_sheet(stats)

def _render_sidebar(bio: dict, cookie_manager):
    st.sidebar.header("Terminal de Mando")
    st.sidebar.success(f"Líder: {bio.get('nombre', 'N/A')}")
    st.sidebar.info(f"Clase: {bio.get('clase', 'N/A')} | Raza: {bio.get('raza', 'N/A')}")
    
    if st.sidebar.button("Cerrar Sesión"):
        logout_user(cookie_manager) # <--- Usamos el manager para borrar cookie
        
    st.sidebar.divider()

# ... (El resto de funciones auxiliares _render_war_room y _render_commander_sheet siguen igual)
def _render_war_room(nombre_comandante: str, player_id: int):
    st.subheader("Bitácora de Misión")
    log_container = st.container(height=300)
    logs = get_recent_logs()
    for log in reversed(logs):
        if "ERROR" not in log['evento_texto']:
            log_container.chat_message("assistant", avatar="📜").write(log['evento_texto'])
    action = st.chat_input(f"¿Órdenes, Comandante {nombre_comandante}?")
    if action:
        with st.spinner("Transmitiendo órdenes..."):
            try:
                resolve_player_action(action, player_id)
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ Error: {e}")

def _render_commander_sheet(stats: dict):
    st.subheader("Hoja de Servicio")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Atributos")
        st.json(stats.get('atributos', {}))
    with col2:
        st.markdown("### Habilidades")
        st.json(stats.get('habilidades', {}))
    st.markdown("### Biografía")
    st.write(stats.get('bio', {}))