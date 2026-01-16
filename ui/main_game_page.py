# ui/main_game_page.py
import streamlit as st
import time
from .state import logout_user, get_player, get_commander
from data.log_repository import get_recent_logs
from services.gemini_service import resolve_player_action

# Nuevos imports para STRT
from core.time_engine import check_and_trigger_tick, get_world_status_display
from data.world_repository import get_pending_actions_count

# Imports de vistas existentes
from .faction_roster import show_faction_roster
from .recruitment_center import show_recruitment_center
from .galaxy_map_page import show_galaxy_map_page
from .ship_status_page import show_ship_status_page


def render_main_game_page(cookie_manager):
    """
    Página principal del juego.
    """
    
    # --- STRT: LAZY TICK TRIGGER ---
    # Cada vez que alguien carga esta página, verificamos si hay que pasar de día.
    try:
        check_and_trigger_tick()
    except Exception as e:
        st.error(f"Error de sincronización temporal: {e}")
    # -------------------------------

    player = get_player()
    commander = get_commander()

    if not player or not commander:
        st.error("Error de sesión. Reinicia.")
        return

    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Puente de Mando"
        
    _render_navigation_sidebar(player, commander, cookie_manager)

    # Renderizar página seleccionada
    PAGES = {
        "Puente de Mando": _render_war_room_page,
        "Ficha del Comandante": _render_commander_sheet_page,
        "Comando de Facción": show_faction_roster,
        "Centro de Reclutamiento": show_recruitment_center,
        "Mapa de la Galaxia": show_galaxy_map_page,
        "Estado de la Nave": show_ship_status_page,
    }
    
    render_func = PAGES.get(st.session_state.current_page, _render_war_room_page)
    render_func()


def _render_navigation_sidebar(player, commander, cookie_manager):
    """Sidebar con info del jugador y RELOJ STRT."""
    with st.sidebar:
        # --- WIDGET DE TIEMPO GALÁCTICO ---
        world_status = get_world_status_display()
        
        # Color del reloj según estado
        clock_color = "green"
        if world_status["is_frozen"]: clock_color = "blue"
        elif world_status["is_lock_in"]: clock_color = "orange"
        
        st.markdown(f"""
        <div style="padding:10px; border:1px solid #333; border-radius:5px; background-color:#0e1117; text-align:center; margin-bottom:15px;">
            <small style="color:#aaa;">TIEMPO ESTÁNDAR (GMT-3)</small><br>
            <strong style="font-size:1.4em; color:{clock_color};">{world_status['time']}</strong><br>
            <span style="font-size:0.8em; color:#ddd;">ESTADO: {world_status['status']}</span><br>
            <span style="font-size:0.8em; color:#888;">CICLO: {world_status['tick']}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Alerta de acciones encoladas
        pending_count = get_pending_actions_count(player['id'])
        if pending_count > 0:
            st.warning(f"📩 {pending_count} Órdenes en cola de espera.")
        # -----------------------------------

        st.header(f"Facción: {player['faccion_nombre']}")
        if player.get('banner_url'):
            st.image(player['banner_url'], use_column_width='auto')

        st.subheader(f"Cmdt. {commander['nombre']}")
        
        st.divider()
        st.header("Navegación")

        if st.button("Puente de Mando", use_container_width=True, type="primary" if st.session_state.current_page == "Puente de Mando" else "secondary"):
            st.session_state.current_page = "Puente de Mando"
            st.rerun()

        if st.button("Mapa de la Galaxia", use_container_width=True, type="primary" if st.session_state.current_page == "Mapa de la Galaxia" else "secondary"):
            st.session_state.current_page = "Mapa de la Galaxia"
            st.rerun()

        if st.button("Estado de la Nave", use_container_width=True, type="primary" if st.session_state.current_page == "Estado de la Nave" else "secondary"):
            st.session_state.current_page = "Estado de la Nave"
            st.rerun()

        st.divider()
        st.header("Gestión")

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

# --- Funciones de renderizado de páginas ---

def _render_war_room_page():
    st.title("Puente de Mando")
    
    # Info de estado STRT en el header
    status = get_world_status_display()
    if status['is_lock_in']:
        st.warning("⚠️ VENTANA DE BLOQUEO ACTIVA: Las órdenes emitidas ahora se ejecutarán al inicio del próximo ciclo.")
    if status['is_frozen']:
        st.info("❄️ SISTEMA CONGELADO: El tiempo está detenido.")

    st.subheader("Bitácora de Misión")
    
    player_id = get_player()['id']
    commander_name = get_commander()['nombre']
    
    # Container para chat
    log_container = st.container(height=350)
    logs = get_recent_logs(player_id)
    
    for log in reversed(logs):
        if "ERROR" not in log['evento_texto']:
            avatar = "📜"
            if "VENTANA DE BLOQUEO" in log['evento_texto']:
                avatar = "⏳"
            elif "CONGELADO" in log['evento_texto']:
                avatar = "❄️"
            log_container.chat_message("assistant", avatar=avatar).write(log['evento_texto'])
            
    # Input de acción
    placeholder = f"¿Órdenes, Comandante {commander_name}?"
    if status['is_frozen']:
        placeholder = "Sistemas congelados. Entrada deshabilitada."
        
    action = st.chat_input(placeholder, disabled=status['is_frozen'])
    
    if action:
        with st.spinner("Transmitiendo..."):
            try:
                resolve_player_action(action, player_id)
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ Error: {e}")

def _render_commander_sheet_page():
    st.title("Ficha de Servicio")
    commander = get_commander()
    stats = commander.get('stats_json', {})
    st.header(f"{commander['nombre']}")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Biografía")
        st.write(stats.get('bio', {}))
    with col2:
        st.subheader("Atributos")
        st.json(stats.get('atributos', {}))
    st.subheader("Habilidades")
    st.json(stats.get('habilidades', {}))