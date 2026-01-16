# ui/main_game_page.py
import streamlit as st
from .state import logout_user, get_player, get_commander
from data.log_repository import get_recent_logs
from services.gemini_service import resolve_player_action

# --- Nuevos imports para STRT (Sistema de Tiempo) ---
from core.time_engine import get_world_status_display, check_and_trigger_tick, debug_force_tick
from data.world_repository import get_pending_actions_count
from data.player_repository import get_player_finances # Importamos el nuevo getter

# --- Importar las vistas del juego ---
from .faction_roster import show_faction_roster
from .recruitment_center import show_recruitment_center
from .galaxy_map_page import show_galaxy_map_page
from .ship_status_page import show_ship_status_page


def render_main_game_page(cookie_manager):
    """
    Página principal del juego con navegación por sidebar.
    """
    
    # --- STRT: Trigger de Tiempo ---
    try:
        check_and_trigger_tick()
    except Exception as e:
        print(f"Advertencia de tiempo: {e}")

    player = get_player()
    commander = get_commander()

    if not player or not commander:
        st.error("No se pudieron cargar los datos del jugador o comandante. Por favor, reinicia la sesión.")
        return

    # --- Renderizar el Sidebar de Navegación ---
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Puente de Mando"
        
    _render_navigation_sidebar(player, commander, cookie_manager)

    # --- Renderizar la página seleccionada ---
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
    """Dibuja el sidebar con el RELOJ GALÁCTICO, INVENTARIO y la navegación."""
    with st.sidebar:
        
        # --- BOTÓN DEBUG ---
        if st.button("🚨 DEBUG: FORZAR TICK", width='stretch', type="secondary"):
            with st.spinner("Forzando salto temporal..."):
                debug_force_tick()
            st.rerun()
        
        st.write("") 
        
        # --- WIDGET DE RELOJ STRT ---
        status = get_world_status_display()
        color = "#56d59f"  # Verde (Nominal)
        status_text = status['status']
        if status["is_lock_in"]: color = "#f6c45b"
        if status["is_frozen"]: color = "#f06464"

        st.markdown(f"""
            <div style="background-color: #0e1117; padding: 15px; border: 1px solid #333; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                <p style="margin: 0; color: #888; font-size: 0.75em; letter-spacing: 1px;">TIEMPO ESTÁNDAR (GMT-3)</p>
                <h2 style="margin: 5px 0; color: {color}; font-family: monospace; font-size: 2em;">{status['time']}</h2>
                <div style="display: flex; justify-content: space-between; font-size: 0.8em; margin-top: 8px; color: #ccc;">
                    <span>CICLO: <b>{status['tick']}</b></span>
                    <span style="color: {color}; font-weight: bold;">{status_text}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        pending = get_pending_actions_count(player['id'])
        if pending > 0:
            st.info(f"📩 {pending} orden(es) en cola.")

        # --- SECCIÓN: IDENTIDAD ---
        st.header(f"Facción: {player['faccion_nombre']}")
        if player.get('banner_url'):
            st.image(player['banner_url'], width='stretch')

        st.subheader(f"Cmdt. {commander['nombre']}")

        # --- SECCIÓN: INVENTARIO MMFR ---
        st.divider()
        st.subheader("📦 Inventario Logístico")
        
        # Obtener recursos frescos de la DB
        finances = get_player_finances(player['id'])
        
        # Usamos CSS Grid simple para mostrar los recursos en 2 columnas
        c1, c2 = st.columns(2)
        c1.metric("Créditos", f"{finances.get('creditos',0)} C")
        c2.metric("Influencia", finances.get('influencia',0), help="Poder político para el Consejo.")
        
        c3, c4 = st.columns(2)
        c3.metric("Materiales", finances.get('materiales',0), help="Reparación y construcción física.")
        c4.metric("Componentes", finances.get('componentes',0), help="Electrónica y armas avanzadas.")
        
        st.metric("Células de Energía", finances.get('celulas_energia',0), help="Combustible para escudos y saltos.")

        # --- SECCIÓN: NAVEGACIÓN ---
        st.divider()
        st.header("Navegación")

        if st.button("Puente de Mando", width='stretch', type="primary" if st.session_state.current_page == "Puente de Mando" else "secondary"):
            st.session_state.current_page = "Puente de Mando"
            st.rerun()

        if st.button("Mapa de la Galaxia", width='stretch', type="primary" if st.session_state.current_page == "Mapa de la Galaxia" else "secondary"):
            st.session_state.current_page = "Mapa de la Galaxia"
            st.rerun()

        if st.button("Estado de la Nave", width='stretch', type="primary" if st.session_state.current_page == "Estado de la Nave" else "secondary"):
            st.session_state.current_page = "Estado de la Nave"
            st.rerun()

        st.divider()
        st.header("Gestión de Facción")

        if st.button("Ficha del Comandante", width='stretch', type="primary" if st.session_state.current_page == "Ficha del Comandante" else "secondary"):
            st.session_state.current_page = "Ficha del Comandante"
            st.rerun()

        if st.button("Comando de Facción", width='stretch', type="primary" if st.session_state.current_page == "Comando de Facción" else "secondary"):
            st.session_state.current_page = "Comando de Facción"
            st.rerun()

        if st.button("Centro de Reclutamiento", width='stretch', type="primary" if st.session_state.current_page == "Centro de Reclutamiento" else "secondary"):
            st.session_state.current_page = "Centro de Reclutamiento"
            st.rerun()

        st.divider()
        if st.button("Cerrar Sesión", width='stretch'):
            logout_user(cookie_manager)
            st.rerun()


# --- Vistas Internas ---

def _render_war_room_page():
    """Página del Puente de Mando con integración STRT."""
    st.title("Puente de Mando")
    
    status = get_world_status_display()
    
    if status['is_lock_in']:
        st.warning("⚠️ VENTANA DE BLOQUEO ACTIVA: Las órdenes se ejecutarán al iniciar el próximo ciclo.")
    if status['is_frozen']:
        st.error("❄️ ALERTA: El flujo temporal está detenido (FREEZE). Sistemas tácticos en espera.")

    st.subheader("Bitácora de Misión")
    
    player_id = get_player()['id']
    commander_name = get_commander()['nombre']
    
    log_container = st.container(height=300)
    logs = get_recent_logs(player_id)
    for log in reversed(logs):
        if "ERROR" not in log['evento_texto']:
            icon = "📜"
            if "VENTANA DE BLOQUEO" in log['evento_texto']: icon = "⏳"
            if "CONGELADO" in log['evento_texto']: icon = "❄️"
            if "DEBUG" in log['evento_texto']: icon = "🛠️"
            if "Misión EXITOSA" in log['evento_texto']: icon = "✅"
            if "Misión FALLIDA" in log['evento_texto']: icon = "❌"
            
            log_container.chat_message("assistant", avatar=icon).write(log['evento_texto'])
            
    input_placeholder = f"¿Órdenes, Comandante {commander_name}?"
    if status['is_frozen']:
        input_placeholder = "Sistemas congelados. Entrada deshabilitada."
        
    action = st.chat_input(input_placeholder, disabled=status['is_frozen'])
    
    if action:
        with st.spinner("Transmitiendo órdenes..."):
            try:
                result = resolve_player_action(action, player_id)
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ Error: {e}")

def _render_commander_sheet_page():
    """Página de la Ficha del Comandante."""
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