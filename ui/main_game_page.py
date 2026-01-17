# ui/main_game_page.py
import streamlit as st
from .state import logout_user, get_player, get_commander
from data.log_repository import get_recent_logs, log_event, clear_player_logs
from services.gemini_service import resolve_player_action

# --- Imports para STRT (Sistema de Tiempo) ---
from core.time_engine import get_world_status_display, check_and_trigger_tick, debug_force_tick
from data.world_repository import get_pending_actions_count
from data.player_repository import get_player_finances

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
    @import url("https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700&display=swap");

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

    with st.sidebar:

        # --- RELOJ GALÁCTICO + DEBUG ---
        clock_time = str(status.get('time', '00:00'))
        clock_tick = str(status.get('tick', 0))

        # Color según estado del sistema
        if status.get("is_frozen"):
            time_color = "#ff6b6b"  # Rojo congelado
            status_icon = "❄️"
            status_text = "CONGELADO"
        elif status.get("is_lock_in"):
            time_color = "#f9ca24"  # Amarillo bloqueo
            status_icon = "⚠️"
            status_text = "BLOQUEO"
        else:
            time_color = "#56d59f"  # Verde nominal
            status_icon = "🟢"
            status_text = "NOMINAL"

        # CSS para el reloj elegante
        clock_css = f"""
        <style>
        @import url("https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700&display=swap");

        .sidebar-clock-panel {{
            background: linear-gradient(135deg, rgba(20,25,35,0.9) 0%, rgba(30,40,55,0.9) 100%);
            border: 1px solid rgba(86, 213, 159, 0.3);
            border-radius: 10px;
            padding: 12px 15px;
            margin-bottom: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05);
        }}

        .clock-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}

        .clock-label {{
            font-family: 'Orbitron', monospace;
            font-size: 0.7em;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 2px;
        }}

        .clock-status {{
            font-size: 0.65em;
            color: {time_color};
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        .clock-time {{
            font-family: 'Orbitron', monospace;
            font-size: 1.8em;
            font-weight: 700;
            color: {time_color};
            text-align: center;
            letter-spacing: 3px;
            text-shadow: 0 0 10px {time_color}40;
            margin: 5px 0;
        }}

        .clock-tick {{
            font-family: 'Orbitron', monospace;
            font-size: 0.7em;
            color: #666;
            text-align: center;
            letter-spacing: 1px;
        }}
        </style>

        <div class="sidebar-clock-panel">
            <div class="clock-header">
                <span class="clock-label">Ciclo Galáctico</span>
                <span class="clock-status">{status_icon} {status_text}</span>
            </div>
            <div class="clock-time">{clock_time}</div>
            <div class="clock-tick">TICK #{clock_tick}</div>
        </div>
        """
        st.markdown(clock_css, unsafe_allow_html=True)

        # Botón de debug debajo del reloj
        if st.button("🔄 Forzar Tick", help="Avanzar tiempo manualmente (Debug)", use_container_width=True):
            with st.spinner("⏳ Procesando tick..."):
                debug_force_tick()
            st.rerun()

        st.divider()

        # --- SECCIÓN: IDENTIDAD ---
        st.header(f"{player.faccion_nombre}")
        if player.banner_url:
            st.image(player.banner_url, use_container_width=True)

        st.caption(f"Comandante {commander.nombre}")

        pending = get_pending_actions_count(player.id)
        if pending > 0:
            st.info(f"📩 {pending} orden(es) en cola.")

        # --- SECCIÓN: NAVEGACIÓN ---
        st.divider()
        st.subheader("Navegación")

        # Botones de menú
        nav_options = [
            ("Puente de Mando", "primary" if st.session_state.current_page == "Puente de Mando" else "secondary"),
            ("Mapa de la Galaxia", "primary" if st.session_state.current_page == "Mapa de la Galaxia" else "secondary"),
            ("Estado de la Nave", "primary" if st.session_state.current_page == "Estado de la Nave" else "secondary"),
            ("Ficha del Comandante", "primary" if st.session_state.current_page == "Ficha del Comandante" else "secondary"),
            ("Comando de Facción", "primary" if st.session_state.current_page == "Comando de Facción" else "secondary"),
            ("Centro de Reclutamiento", "primary" if st.session_state.current_page == "Centro de Reclutamiento" else "secondary"),
        ]

        for label, btn_type in nav_options:
            if st.button(label, width='stretch', type=btn_type):
                st.session_state.current_page = label
                st.rerun()

        st.divider()
        if st.button("Cerrar Sesión", width='stretch'):
            logout_user(cookie_manager)
            st.rerun()


def _render_commander_sheet_page():
    """Renderiza la ficha específica del Comandante."""
    st.title("Ficha de Servicio: Comandante")
    player = get_player()
    commander = get_commander()
    
    if player and commander:
        render_character_card(commander, player.id, is_commander=True)
    else:
        st.error("Datos del comandante no disponibles.")


def _render_war_room_styles():
    """Estilos visuales para el Puente de Mando."""
    st.markdown(
        """
        <style>
        @import url("https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700&family=Share+Tech+Mono&display=swap");

        .war-room-title {
            font-family: "Orbitron", sans-serif;
            font-size: 24px;
            font-weight: 700;
            color: #dff6ff;
            text-transform: uppercase;
            margin-bottom: 10px;
        }

        /* --- ESTILOS DE CHAT --- */
        div[data-testid="stChatMessage"] {
            border-radius: 8px;
            border: 1px solid rgba(80, 170, 220, 0.2);
            background: rgba(10, 20, 32, 0.6);
            padding: 10px;
            margin-bottom: 8px;
        }
        /* Fuente monoespaciada para mensajes */
        div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] {
            font-family: "Share Tech Mono", monospace;
            color: #e0e0e0 !important; 
            font-size: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_war_room_page():
    """Página del Puente de Mando con CHAT COMPACTO."""
    _render_war_room_styles()
    
    player = get_player()
    commander = get_commander()
    if not player or not commander:
        st.error("Datos no disponibles.")
        return
    player_id = player.id
    commander_name = commander.nombre
    status = get_world_status_display()

    # Título más compacto con botón de limpiar
    col_title, col_clear = st.columns([4, 1])
    with col_title:
        st.markdown('<div class="war-room-title">📟 Enlace Neuronal de Mando</div>', unsafe_allow_html=True)
    with col_clear:
        if st.button("🗑️ Limpiar", help="Borrar historial del chat"):
            clear_player_logs(player_id)
            st.rerun()

    if status['is_lock_in']:
        st.warning("⚠️ VENTANA DE BLOQUEO ACTIVA")
    
    # --- CONTENEDOR DE CHAT (SCROLLABLE) ---
    # Usamos st.container con altura fija para crear la "caja" contenida
    chat_box = st.container(height=500, border=True)

    logs = get_recent_logs(player_id, limit=30) 

    with chat_box:
        if not logs:
            st.info(f"Conexión establecida. Esperando órdenes, Comandante {commander_name}...")
        
        # Logs en orden cronológico inverso visual (Chat Style)
        for log in reversed(logs):
            mensaje = log.get('evento_texto', log.get('message', ''))
            
            if "[DEBUG]" in mensaje: continue

            if mensaje.startswith("[PLAYER]"):
                clean_msg = mensaje.replace("[PLAYER] ", "")
                with st.chat_message("user", avatar="👤"):
                    st.write(clean_msg)
            else:
                icon = "🤖"
                if "EXITOSA" in mensaje: icon = "✅"
                elif "FALLIDA" in mensaje: icon = "❌"
                
                clean_msg = mensaje
                for p in ["[GM] ", "🤖 [ASISTENTE] ", "🤖 "]:
                    clean_msg = clean_msg.replace(p, "")

                with st.chat_message("assistant", avatar=icon):
                    st.write(clean_msg)

    # --- INPUT AREA (Fuera del scroll, siempre visible abajo) ---
    st.write("") 
    input_placeholder = f"Escriba sus órdenes, Cmdt. {commander_name}..."
    if status['is_frozen']:
        input_placeholder = "SISTEMAS CONGELADOS."
        
    action = st.chat_input(input_placeholder, disabled=status['is_frozen'])

    if action:
        log_event(f"[PLAYER] {action}", player_id)
        with st.spinner("Transmitiendo..."):
            try:
                resolve_player_action(action, player_id)
                st.rerun()
            except Exception as e:
                st.error(f"Error de transmisión: {e}")