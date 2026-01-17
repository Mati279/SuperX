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
        "Flota": show_ship_status_page,
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
    Layout: Recursos CENTRADOS.
    """
    finances = get_player_finances(player.id)

    # Helper para evitar crash por NoneType
    def safe_val(key):
        val = finances.get(key) if finances else None
        return val if val is not None else 0

    # Preparar valores para el HTML (evita problemas de interpolación)
    creditos = f"{safe_val('creditos'):,}"
    materiales = f"{safe_val('materiales'):,}"
    componentes = f"{safe_val('componentes'):,}"
    celulas = f"{safe_val('celulas_energia'):,}"
    influencia = f"{safe_val('influencia'):,}"

    # CSS separado para mayor claridad
    hud_css = """
    <style>
    .top-hud-sticky {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 50px;
        z-index: 999999;
        background-color: #262730;
        border-bottom: 1px solid #444;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    }

    .hud-resource-group {
        display: flex;
        gap: 40px;
        align-items: center;
        height: 100%;
    }

    .hud-metric {
        display: flex;
        align-items: center;
        gap: 6px;
        cursor: help;
        padding: 2px 8px;
        border-radius: 4px;
    }

    .hud-metric:hover {
        background-color: rgba(255,255,255,0.05);
    }

    .hud-icon {
        font-size: 1.1em;
        line-height: 1;
        opacity: 0.8;
    }

    .hud-value {
        font-family: 'Source Code Pro', monospace;
        font-weight: 600;
        color: #e0e0e0 !important;
        font-size: 0.95em;
        white-space: nowrap;
    }

    @media (max-width: 800px) {
        .hud-value { font-size: 0.8em; }
        .hud-icon { font-size: 1.0em; }
        .top-hud-sticky { padding-left: 60px; }
        .hud-resource-group { gap: 15px; }
    }
    </style>
    """

    # HTML con valores ya interpolados
    hud_html = f"""
    <div class="top-hud-sticky">
        <div class="hud-resource-group">
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
    </div>

    <div style="height: 60px;"></div>
    """

    st.markdown(hud_css + hud_html, unsafe_allow_html=True)


def _render_navigation_sidebar(player, commander, cookie_manager):
    """Sidebar con reloj galáctico, identidad y menú de navegación."""
    status = get_world_status_display()
    
    # Obtener ubicación real (Base Principal)
    loc_data = get_commander_location_display(commander.id)
    loc_system = loc_data.get("system", "Desconocido")
    loc_planet = loc_data.get("planet", "---")
    
    # El label de "Base" aquí lo uso como título de la sección o nombre del activo,
    # según tu requerimiento de "El sistema y el planeta en donde está a planet asset".
    # Incluyo el nombre de la base también para contexto completo.
    loc_base_name = loc_data.get("base", "Base Principal")

    with st.sidebar:
        
        # --- PANEL DE UBICACIÓN (ARRIBA DEL RELOJ) ---
        location_css = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700&display=swap');
        .sidebar-loc-panel {
            background: rgba(30, 33, 40, 0.6);
            border-left: 3px solid #8ab4f8;
            padding: 10px;
            margin-bottom: 15px;
            font-family: 'Orbitron', sans-serif;
            color: #e0e0e0;
        }
        .loc-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 6px;
            font-size: 0.85em;
        }
        .loc-row:last-child { margin-bottom: 0; }
        .loc-icon { color: #8ab4f8; width: 20px; text-align: center; }
        .loc-label { color: #888; font-size: 0.7em; text-transform: uppercase; margin-right: 5px; font-weight: 600; }
        </style>
        """
        
        location_html = f"""
        <div class="sidebar-loc-panel">
            <div class="loc-row" title="Sistema Estelar">
                <span class="loc-icon">☀</span>
                <div>
                    <div class="loc-label">SISTEMA</div>
                    {loc_system}
                </div>
            </div>
            <div class="loc-row" title="Cuerpo Celeste">
                <span class="loc-icon">🪐</span>
                 <div>
                    <div class="loc-label">PLANETA</div>
                    {loc_planet}
                </div>
            </div>
            <div class="loc-row" title="Asentamiento">
                <span class="loc-icon">🏛</span>
                 <div>
                    <div class="loc-label">BASE</div>
                    {loc_base_name}
                </div>
            </div>
        </div>
        """
        st.markdown(location_css + location_html, unsafe_allow_html=True)

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
        
        pages = ["Puente de Mando", "Mapa de la Galaxia", 
                 "Ficha del Comandante", "Comando de Facción", "Centro de Reclutamiento", "Flota"]
        
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