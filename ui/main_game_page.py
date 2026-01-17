# ui/main_game_page.py
import streamlit as st
from .state import logout_user, get_player, get_commander
from data.log_repository import get_recent_logs, log_event, clear_player_logs
from services.gemini_service import resolve_player_action

# --- Imports para STRT (Sistema de Tiempo) ---
from core.time_engine import get_world_status_display, check_and_trigger_tick, debug_force_tick
from data.world_repository import get_pending_actions_count, get_commander_location_display
from data.player_repository import get_player_finances, delete_player_account

# --- Importar las vistas del juego ---
from .faction_roster import show_faction_roster, render_character_card
from .recruitment_center import show_recruitment_center
from .galaxy_map_page import show_galaxy_map_page
from .ship_status_page import show_ship_status_page


def render_main_game_page(cookie_manager):
    """
    Página principal del juego con HUD superior FIXED y navegación lateral.
    """
    
    # --- STRT: Trigger de Tiempo ---
    try:
        check_and_trigger_tick()
    except Exception as e:
        print(f"Advertencia de tiempo: {e}")

    player = get_player()
    commander = get_commander()

    if not player or not commander:
        st.error("❌ ERROR CRÍTICO: No se pudieron cargar los datos del jugador. Reinicia sesión.")
        if st.button("Volver al Login"):
            logout_user(cookie_manager)
        return

    # --- 1. RENDERIZAR HUD SUPERIOR (Siempre visible) ---
    _render_sticky_top_hud(player, commander)

    # --- 2. Renderizar Sidebar (Solo Navegación e Identidad) ---
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Puente de Mando"
        
    _render_navigation_sidebar(player, commander, cookie_manager)

    # --- 3. Renderizar la página seleccionada ---
    PAGES = {
        "Puente de Mando": _render_war_room_page,
        "Ficha del Comandante": _render_commander_sheet_page,
        "Comando de Facción": show_faction_roster,
        "Centro de Reclutamiento": show_recruitment_center,
        "Mapa de la Galaxia": show_galaxy_map_page,
        "Estado de la Nave": show_ship_status_page,
    }
    
    # Contenedor principal con margen superior para no quedar bajo el HUD
    with st.container():
        st.write("") # Espaciador
        st.write("") 
        render_func = PAGES.get(st.session_state.current_page, _render_war_room_page)
        render_func()


def _render_sticky_top_hud(player, commander):
    """
    Renderiza la barra superior STICKY (siempre visible).
    Layout: Recursos (Izquierda/Centro) + Ubicación (Derecha).
    """
    finances = get_player_finances(player.id)
    location_data = get_commander_location_display(commander.id)

    # Helper para evitar crash por NoneType
    def safe_val(key):
        val = finances.get(key) if finances else None
        return val if val is not None else 0

    # Preparar valores para el HTML
    creditos = f"{safe_val('creditos'):,}"
    materiales = f"{safe_val('materiales'):,}"
    componentes = f"{safe_val('componentes'):,}"
    celulas = f"{safe_val('celulas_energia'):,}"
    influencia = f"{safe_val('influencia'):,}"
    
    # Datos de Ubicación
    loc_system = location_data.get("system", "Desconocido")
    loc_planet = location_data.get("planet", "---")
    loc_base = location_data.get("base", "---")

    # CSS separado para mayor claridad
    hud_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700&family=Source+Code+Pro:wght@400;600&display=swap');

    .top-hud-sticky {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 60px;
        z-index: 999999;
        background: linear-gradient(180deg, #1e2129 0%, #262730 100%);
        border-bottom: 2px solid #444;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.6);
    }

    /* Recursos */
    .hud-left-panel {
        display: flex;
        gap: 30px;
        align-items: center;
    }

    .hud-metric {
        display: flex;
        align-items: center;
        gap: 8px;
        cursor: help;
        transition: transform 0.2s;
    }

    .hud-metric:hover {
        transform: translateY(-2px);
    }

    .hud-icon {
        font-size: 1.2em;
    }

    .hud-value {
        font-family: 'Source Code Pro', monospace;
        font-weight: 600;
        color: #e0e0e0;
        font-size: 1em;
    }

    /* Ubicación */
    .hud-right-panel {
        display: flex;
        align-items: center;
        background: rgba(0, 0, 0, 0.3);
        padding: 5px 15px;
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    .loc-container {
        font-family: 'Orbitron', sans-serif;
        font-size: 0.85em;
        color: #8ab4f8;
        display: flex;
        align-items: center;
        gap: 12px;
        letter-spacing: 1px;
    }

    .loc-item {
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .loc-separator {
        color: #444;
        font-weight: 300;
    }
    
    .loc-icon-small {
        font-size: 1.1em;
        filter: drop-shadow(0 0 2px rgba(138, 180, 248, 0.5));
    }

    @media (max-width: 900px) {
        .top-hud-sticky { padding: 0 10px; height: auto; flex-wrap: wrap; justify-content: center; gap: 5px; padding-bottom: 5px; }
        .hud-left-panel { gap: 15px; margin-bottom: 5px; }
        .hud-value { font-size: 0.85em; }
        .hud-icon { font-size: 1em; }
        .loc-container { font-size: 0.75em; }
    }
    </style>
    """

    # HTML
    hud_html = f"""
    <div class="top-hud-sticky">
        <div class="hud-left-panel">
            <div class="hud-metric" title="Créditos Estándar">
                <span class="hud-icon">💳</span>
                <span class="hud-value">{creditos}</span>
            </div>
            <div class="hud-metric" title="Materiales de Construcción">
                <span class="hud-icon">📦</span>
                <span class="hud-value">{materiales}</span>
            </div>
            <div class="hud-metric" title="Componentes Tecnológicos">
                <span class="hud-icon">🧩</span>
                <span class="hud-value">{componentes}</span>
            </div>
            <div class="hud-metric" title="Células de Energía">
                <span class="hud-icon">⚡</span>
                <span class="hud-value">{celulas}</span>
            </div>
            <div class="hud-metric" title="Influencia Política">
                <span class="hud-icon">👑</span>
                <span class="hud-value">{influencia}</span>
            </div>
        </div>

        <div class="hud-right-panel">
            <div class="loc-container">
                <div class="loc-item" title="Sistema Actual">
                    <span class="loc-icon-small">☀</span> {loc_system}
                </div>
                <span class="loc-separator">|</span>
                <div class="loc-item" title="Cuerpo Celeste">
                    <span class="loc-icon-small">🪐</span> {loc_planet}
                </div>
                <span class="loc-separator">|</span>
                <div class="loc-item" title="Base / Nave Asignada">
                    <span class="loc-icon-small">🏛</span> {loc_base}
                </div>
            </div>
        </div>
    </div>

    <div style="height: 70px;"></div>
    """

    st.markdown(hud_css + hud_html, unsafe_allow_html=True)


def _render_navigation_sidebar(player, commander, cookie_manager):
    """Sidebar con reloj galáctico, identidad y menú de navegación."""
    status = get_world_status_display()

    with st.sidebar:

        # --- RELOJ GALÁCTICO + DEBUG ---
        clock_time = str(status.get('time', '00:00'))
        clock_tick = str(status.get('tick', 0))

        if status.get("is_frozen"):
            time_color = "#ff6b6b"
            status_icon = "❄️"
            status_text = "CONGELADO"
        elif status.get("is_lock_in"):
            time_color = "#f9ca24"
            status_icon = "⚠️"
            status_text = "BLOQUEO"
        else:
            time_color = "#56d59f"
            status_icon = "🟢"
            status_text = "NOMINAL"

        clock_css = f"""
        <style>
        @import url("https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700&display=swap");
        .sidebar-clock-panel {{
            background: linear-gradient(135deg, rgba(20,25,35,0.9) 0%, rgba(30,40,55,0.9) 100%);
            border: 1px solid rgba(86, 213, 159, 0.3);
            border-radius: 10px;
            padding: 12px 15px;
            margin-bottom: 10px;
        }}
        .clock-time {{
            font-family: 'Orbitron', monospace;
            font-size: 1.8em;
            font-weight: 700;
            color: {time_color};
            text-align: center;
            letter-spacing: 3px;
        }}
        </style>
        <div class="sidebar-clock-panel">
            <div style="display: flex; justify-content: space-between; font-size: 0.7em; color: #888;">
                <span>Ciclo Galáctico</span>
                <span style="color: {time_color};">{status_icon} {status_text}</span>
            </div>
            <div class="clock-time">{clock_time}</div>
            <div style="text-align: center; font-size: 0.7em; color: #666;">TICK #{clock_tick}</div>
        </div>
        """
        st.markdown(clock_css, unsafe_allow_html=True)

        if st.button("🔄 Forzar Tick", use_container_width=True):
            debug_force_tick()
            st.rerun()

        st.divider()

        # --- SECCIÓN: IDENTIDAD ---
        st.header(f"{player.faccion_nombre}")
        if player.banner_url:
            st.image(player.banner_url, use_container_width=True)

        st.caption(f"Comandante {commander.nombre}")

        # --- SECCIÓN: NAVEGACIÓN ---
        st.divider()
        
        pages = ["Puente de Mando", "Mapa de la Galaxia", "Estado de la Nave", 
                 "Ficha del Comandante", "Comando de Facción", "Centro de Reclutamiento"]
        
        for p in pages:
            if st.button(p, use_container_width=True, type="primary" if st.session_state.current_page == p else "secondary"):
                st.session_state.current_page = p
                st.rerun()

        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            logout_user(cookie_manager)
            st.rerun()

        # --- BOTÓN DE DEBUG: HARD RESET ---
        # Ubicado al final de la sidebar para ser fácilmente localizable
        st.write("")
        st.write("")
        st.markdown("---")
        st.caption("🛠️ ZONA DE PRUEBAS")
        if st.button("🔥 ELIMINAR CUENTA (DEBUG)", type="secondary", use_container_width=True, help="Elimina permanentemente al jugador y sus datos para reiniciar el Génesis."):
            if delete_player_account(player.id):
                st.success("Cuenta eliminada.")
                logout_user(cookie_manager)
                st.rerun()
            else:
                st.error("Error al eliminar.")


def _render_commander_sheet_page():
    """Renderiza la ficha específica del Comandante."""
    st.title("Ficha de Servicio: Comandante")
    player = get_player()
    commander = get_commander()
    if player and commander:
        render_character_card(commander, player.id, is_commander=True)


def _render_war_room_page():
    """Página del Puente de Mando con CHAT."""
    player = get_player()
    commander = get_commander()
    if not player: return

    st.markdown("### 📟 Enlace Neuronal de Mando")
    
    chat_box = st.container(height=500, border=True)
    logs = get_recent_logs(player.id, limit=30) 

    with chat_box:
        for log in reversed(logs):
            mensaje = log.get('evento_texto', '')
            if "[PLAYER]" in mensaje:
                with st.chat_message("user"): st.write(mensaje.replace("[PLAYER] ", ""))
            else:
                with st.chat_message("assistant"): st.write(mensaje)

    action = st.chat_input("Escriba sus órdenes...")
    if action:
        log_event(f"[PLAYER] {action}", player.id)
        resolve_player_action(action, player.id)
        st.rerun()