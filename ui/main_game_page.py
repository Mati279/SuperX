# ui/main_game_page.py
"""
Pagina Principal del Juego - Terminal de Comando Galactico.
HUD superior persistente, navegacion lateral y contenido dinamico.
"""

import streamlit as st
from .state import logout_user, get_player, get_commander
from .styles import (
    inject_global_styles,
    inject_world_state_styles,
    Colors,
    render_terminal_header
)
from data.log_repository import get_recent_logs, log_event
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
    Pagina principal del juego con HUD superior FIXED y navegacion lateral.
    Implementa el estilo Terminal de Comando Galactico.
    """

    # --- Inyectar Estilos Globales ---
    inject_global_styles()

    # --- STRT: Trigger de Tiempo ---
    try:
        check_and_trigger_tick()
    except Exception as e:
        print(f"Advertencia de tiempo: {e}")

    player = get_player()
    commander = get_commander()

    if not player or not commander:
        st.error("ERROR CRITICO: No se pudieron cargar los datos del jugador. Reinicia sesion.")
        if st.button("Volver al Login"):
            logout_user(cookie_manager)
        return

    # --- Obtener estado del mundo para estilos dinamicos ---
    status = get_world_status_display()
    inject_world_state_styles(
        is_frozen=status.get("is_frozen", False),
        is_lock_in=status.get("is_lock_in", False)
    )

    # --- 1. RENDERIZAR HUD SUPERIOR (Siempre visible) ---
    _render_command_hud(player, commander, status)

    # --- 2. Renderizar Sidebar (Solo Navegacion e Identidad) ---
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Puente de Mando"

    _render_navigation_sidebar(player, commander, cookie_manager, status)

    # --- 3. Renderizar la pagina seleccionada ---
    PAGES = {
        "Puente de Mando": _render_war_room_page,
        "Ficha del Comandante": _render_commander_sheet_page,
        "Comando de Faccion": show_faction_roster,
        "Centro de Reclutamiento": show_recruitment_center,
        "Mapa de la Galaxia": show_galaxy_map_page,
        "Estado de la Nave": show_ship_status_page,
    }

    # Contenedor principal con margen superior para no quedar bajo el HUD
    with st.container():
        st.write("")
        render_func = PAGES.get(st.session_state.current_page, _render_war_room_page)
        render_func()


def _render_command_hud(player, commander, status):
    """
    Renderiza la barra de comando superior STICKY.
    Muestra recursos criticos y estado del sistema.
    """
    finances = get_player_finances(player.id)

    def safe_val(key):
        val = finances.get(key) if finances else None
        return val if val is not None else 0

    # Determinar color segun estado del mundo
    if status.get("is_frozen"):
        state_color = Colors.FROZEN
        state_glow = f"0 0 20px {Colors.FROZEN}60"
    elif status.get("is_lock_in"):
        state_color = Colors.LOCK_IN
        state_glow = f"0 0 20px {Colors.LOCK_IN}60"
    else:
        state_color = Colors.NOMINAL
        state_glow = f"0 0 20px {Colors.NOMINAL}40"

    # Preparar valores
    creditos = f"{safe_val('creditos'):,}"
    materiales = f"{safe_val('materiales'):,}"
    componentes = f"{safe_val('componentes'):,}"
    celulas = f"{safe_val('celulas_energia'):,}"
    influencia = f"{safe_val('influencia'):,}"

    hud_html = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700&family=Share+Tech+Mono&display=swap');

    .command-hud {{
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 56px;
        z-index: 999999;
        background: linear-gradient(180deg, {Colors.BG_PANEL} 0%, {Colors.BG_DARK} 100%);
        border-bottom: 1px solid {state_color}40;
        box-shadow: {state_glow}, 0 4px 20px rgba(0,0,0,0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 20px;
    }}

    .hud-resources {{
        display: flex;
        gap: 24px;
        align-items: center;
    }}

    .hud-resource {{
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 12px;
        background: {Colors.BG_CARD};
        border: 1px solid {Colors.BORDER_DIM};
        border-radius: 4px;
        transition: all 0.2s ease;
    }}

    .hud-resource:hover {{
        border-color: {state_color};
        box-shadow: 0 0 10px {state_color}30;
    }}

    .hud-icon {{
        font-size: 1.1em;
        opacity: 0.9;
    }}

    .hud-value {{
        font-family: 'Share Tech Mono', monospace;
        font-weight: 600;
        color: {Colors.TEXT_PRIMARY};
        font-size: 0.9em;
    }}

    .hud-label {{
        font-family: 'Orbitron', sans-serif;
        font-size: 0.55em;
        color: {Colors.TEXT_DIM};
        text-transform: uppercase;
        letter-spacing: 1px;
    }}

    @media (max-width: 900px) {{
        .hud-resource {{ padding: 4px 8px; }}
        .hud-value {{ font-size: 0.8em; }}
        .hud-resources {{ gap: 12px; }}
        .hud-label {{ display: none; }}
    }}
    </style>

    <div class="command-hud">
        <div class="hud-resources">
            <div class="hud-resource" title="Creditos Estandar Galacticos">
                <span class="hud-icon">&#128179;</span>
                <div>
                    <div class="hud-label">Creditos</div>
                    <span class="hud-value">{creditos}</span>
                </div>
            </div>
            <div class="hud-resource" title="Materiales de Construccion">
                <span class="hud-icon">&#128230;</span>
                <div>
                    <div class="hud-label">Materiales</div>
                    <span class="hud-value">{materiales}</span>
                </div>
            </div>
            <div class="hud-resource" title="Componentes Tecnologicos">
                <span class="hud-icon">&#129513;</span>
                <div>
                    <div class="hud-label">Componentes</div>
                    <span class="hud-value">{componentes}</span>
                </div>
            </div>
            <div class="hud-resource" title="Celulas de Energia">
                <span class="hud-icon">&#9889;</span>
                <div>
                    <div class="hud-label">Energia</div>
                    <span class="hud-value">{celulas}</span>
                </div>
            </div>
            <div class="hud-resource" title="Influencia Politica">
                <span class="hud-icon">&#128081;</span>
                <div>
                    <div class="hud-label">Influencia</div>
                    <span class="hud-value">{influencia}</span>
                </div>
            </div>
        </div>
    </div>

    <div style="height: 66px;"></div>
    """

    st.markdown(hud_html, unsafe_allow_html=True)


def _render_navigation_sidebar(player, commander, cookie_manager, status):
    """Sidebar con reloj galactico, identidad y menu de navegacion."""

    # Obtener ubicacion real
    loc_data = get_commander_location_display(commander.id)
    loc_system = loc_data.get("system", "Desconocido")
    loc_planet = loc_data.get("planet", "---")
    loc_base_name = loc_data.get("base", "Base Principal")

    with st.sidebar:

        # --- PANEL DE UBICACION ---
        _render_location_panel(loc_system, loc_planet, loc_base_name)

        # --- RELOJ GALACTICO ---
        _render_galactic_clock(status)

        if st.button("Forzar Tick", use_container_width=True, help="DEBUG: Avanza el tiempo manualmente"):
            debug_force_tick()
            st.rerun()

        st.divider()

        # --- SECCION: IDENTIDAD ---
        _render_faction_identity(player, commander)

        st.divider()

        # --- SECCION: NAVEGACION ---
        _render_nav_menu()

        st.divider()

        if st.button("Cerrar Sesion", use_container_width=True):
            logout_user(cookie_manager)
            st.rerun()

        # --- ZONA DEBUG ---
        _render_debug_zone(player, cookie_manager)


def _render_location_panel(system: str, planet: str, base: str):
    """Panel de ubicacion actual del comandante."""
    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {Colors.BG_CARD} 0%, {Colors.BG_PANEL} 100%);
            border: 1px solid {Colors.BORDER_DIM};
            border-left: 3px solid {Colors.INFO};
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 16px;
        ">
            <div style="
                font-family: 'Orbitron', sans-serif;
                font-size: 0.6em;
                color: {Colors.TEXT_DIM};
                letter-spacing: 2px;
                margin-bottom: 8px;
            ">POSICION ACTUAL</div>

            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                <span style="color: {Colors.WARNING};">&#9728;</span>
                <div>
                    <div style="font-size: 0.65em; color: {Colors.TEXT_DIM}; text-transform: uppercase;">Sistema</div>
                    <div style="font-family: 'Share Tech Mono', monospace; color: {Colors.TEXT_PRIMARY}; font-size: 0.9em;">{system}</div>
                </div>
            </div>

            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                <span style="color: {Colors.INFO};">&#127760;</span>
                <div>
                    <div style="font-size: 0.65em; color: {Colors.TEXT_DIM}; text-transform: uppercase;">Planeta</div>
                    <div style="font-family: 'Share Tech Mono', monospace; color: {Colors.TEXT_PRIMARY}; font-size: 0.9em;">{planet}</div>
                </div>
            </div>

            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="color: {Colors.EPIC};">&#127963;</span>
                <div>
                    <div style="font-size: 0.65em; color: {Colors.TEXT_DIM}; text-transform: uppercase;">Base</div>
                    <div style="font-family: 'Share Tech Mono', monospace; color: {Colors.TEXT_PRIMARY}; font-size: 0.9em;">{base}</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)


def _render_galactic_clock(status):
    """Renderiza el reloj galactico con indicador de estado."""
    clock_time = str(status.get('time', '00:00'))
    clock_tick = str(status.get('tick', 0))

    if status.get("is_frozen"):
        time_color = Colors.FROZEN
        status_text = "CONGELADO"
        pulse_color = Colors.FROZEN
    elif status.get("is_lock_in"):
        time_color = Colors.LOCK_IN
        status_text = "BLOQUEO"
        pulse_color = Colors.LOCK_IN
    else:
        time_color = Colors.NOMINAL
        status_text = "NOMINAL"
        pulse_color = Colors.NOMINAL

    st.markdown(f"""
        <style>
        @keyframes pulse-glow {{
            0%, 100% {{ box-shadow: 0 0 5px {pulse_color}40; }}
            50% {{ box-shadow: 0 0 15px {pulse_color}60; }}
        }}
        </style>

        <div style="
            background: linear-gradient(135deg, {Colors.BG_CARD} 0%, {Colors.BG_DARK} 100%);
            border: 1px solid {time_color}40;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 12px;
            animation: pulse-glow 2s infinite;
        ">
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            ">
                <span style="
                    font-family: 'Orbitron', sans-serif;
                    font-size: 0.6em;
                    color: {Colors.TEXT_DIM};
                    letter-spacing: 1px;
                ">CICLO GALACTICO</span>
                <span style="
                    font-family: 'Orbitron', sans-serif;
                    font-size: 0.55em;
                    color: {time_color};
                    padding: 2px 6px;
                    background: {time_color}20;
                    border: 1px solid {time_color}40;
                    border-radius: 3px;
                ">{status_text}</span>
            </div>

            <div style="
                font-family: 'Orbitron', sans-serif;
                font-size: 2em;
                font-weight: 700;
                color: {time_color};
                text-align: center;
                letter-spacing: 4px;
                text-shadow: 0 0 20px {time_color}60;
            ">{clock_time}</div>

            <div style="
                text-align: center;
                font-family: 'Share Tech Mono', monospace;
                font-size: 0.7em;
                color: {Colors.TEXT_DIM};
                margin-top: 4px;
            ">TICK #{clock_tick}</div>
        </div>
    """, unsafe_allow_html=True)


def _render_faction_identity(player, commander):
    """Renderiza la identidad de la faccion."""
    st.markdown(f"""
        <div style="
            font-family: 'Orbitron', sans-serif;
            font-size: 1.1em;
            color: {Colors.TEXT_PRIMARY};
            margin-bottom: 8px;
        ">{player.faccion_nombre}</div>
    """, unsafe_allow_html=True)

    if player.banner_url:
        st.image(player.banner_url, use_container_width=True)

    st.markdown(f"""
        <div style="
            font-family: 'Rajdhani', sans-serif;
            font-size: 0.85em;
            color: {Colors.TEXT_SECONDARY};
        ">Comandante <span style="color: {Colors.NOMINAL};">{commander.nombre}</span></div>
    """, unsafe_allow_html=True)


def _render_nav_menu():
    """Menu de navegacion principal."""
    pages = [
        ("Puente de Mando", "&#128225;"),
        ("Mapa de la Galaxia", "&#127760;"),
        ("Estado de la Nave", "&#128640;"),
        ("Ficha del Comandante", "&#128100;"),
        ("Comando de Faccion", "&#128101;"),
        ("Centro de Reclutamiento", "&#127919;"),
    ]

    for page_name, icon in pages:
        is_active = st.session_state.current_page == page_name
        btn_type = "primary" if is_active else "secondary"

        if st.button(
            f"{page_name}",
            use_container_width=True,
            type=btn_type,
            key=f"nav_{page_name}"
        ):
            st.session_state.current_page = page_name
            st.rerun()


def _render_debug_zone(player, cookie_manager):
    """Zona de debug para desarrollo."""
    st.write("")
    st.markdown(f"""
        <div style="
            font-family: 'Orbitron', sans-serif;
            font-size: 0.6em;
            color: {Colors.TEXT_DIM};
            letter-spacing: 1px;
            text-align: center;
            margin: 10px 0;
        ">ZONA DE PRUEBAS</div>
    """, unsafe_allow_html=True)

    if st.button(
        "ELIMINAR CUENTA",
        type="secondary",
        use_container_width=True,
        help="DEBUG: Elimina permanentemente la cuenta"
    ):
        if delete_player_account(player.id):
            st.success("Cuenta eliminada.")
            logout_user(cookie_manager)
            st.rerun()
        else:
            st.error("Error al eliminar.")


def _render_commander_sheet_page():
    """Renderiza la ficha especifica del Comandante."""
    render_terminal_header(
        title="FICHA DE SERVICIO",
        subtitle="COMANDANTE // DATOS CLASIFICADOS",
        icon="&#128100;"
    )

    player = get_player()
    commander = get_commander()

    if player and commander:
        render_character_card(commander, player.id, is_commander=True)


def _render_war_room_page():
    """Pagina del Puente de Mando con interfaz de chat."""
    player = get_player()
    commander = get_commander()
    if not player:
        return

    render_terminal_header(
        title="ENLACE NEURONAL",
        subtitle="SISTEMA DE COMUNICACION TACTICA",
        icon="&#128225;"
    )

    # Contenedor de chat estilizado
    st.markdown(f"""
        <style>
        .chat-container {{
            background: {Colors.BG_DARK};
            border: 1px solid {Colors.BORDER_DIM};
            border-radius: 8px;
            padding: 4px;
        }}
        </style>
    """, unsafe_allow_html=True)

    chat_box = st.container(height=450, border=True)
    logs = get_recent_logs(player.id, limit=30)

    with chat_box:
        for log in reversed(logs):
            mensaje = log.get('evento_texto', '')
            if "[PLAYER]" in mensaje:
                with st.chat_message("user"):
                    st.write(mensaje.replace("[PLAYER] ", ""))
            else:
                with st.chat_message("assistant"):
                    st.write(mensaje)

    action = st.chat_input("Transmitir ordenes...")
    if action:
        log_event(f"[PLAYER] {action}", player.id)
        resolve_player_action(action, player.id)
        st.rerun()
