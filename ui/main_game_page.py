# ui/main_game_page.py
import streamlit as st
from .state import logout_user, get_player, get_commander
from data.log_repository import get_recent_logs, log_event
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
    Versión Robustecida: Manejo de nulos y Z-Index extremo.
    """
    
    finances = get_player_finances(player.id)
    status = get_world_status_display()

    # Función helper para evitar crash por NoneType en f-strings
    def safe_val(key):
        val = finances.get(key)
        return val if val is not None else 0

    # Colores de estado para el reloj
    time_color = "#56d59f"  # Verde nominal
    if status["is_lock_in"]: time_color = "#f9ca24" 
    if status["is_frozen"]: time_color = "#ff6b6b" 

    st.markdown(f"""
        <style>
        /* Contenedor principal Sticky */
        .top-hud-sticky {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 60px;
            z-index: 999999; /* Z-Index extremo para asegurar visibilidad */
            background-color: #262730; /* COLOR DE LA SIDEBAR */
            border-bottom: 1px solid #444;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px 0 80px; /* Padding izquierdo para no tapar menú hamburguesa */
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
        }}

        /* Grupo de Recursos */
        .hud-resource-group {{
            display: flex;
            gap: 20px;
            align-items: center;
            height: 100%;
        }}
        
        /* Métrica individual */
        .hud-metric {{
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: help;
            padding: 5px 10px;
            border-radius: 5px;
            height: 40px; /* Altura fija para evitar colapso */
        }}
        
        .hud-metric:hover {{
            background-color: rgba(255,255,255,0.1);
        }}

        .hud-icon {{ 
            font-size: 1.4em; 
            line-height: 1;
        }}
        
        .hud-value {{ 
            font-family: 'Source Code Pro', monospace; 
            font-weight: bold; 
            color: #ffffff !important; /* Color forzado */
            font-size: 1.1em;
            white-space: nowrap;
        }}

        /* Reloj */
        .hud-clock {{
            font-family: 'Orbitron', monospace;
            color: {time_color} !important;
            font-weight: bold;
            font-size: 1.2em;
            letter-spacing: 1px;
            background: rgba(0,0,0,0.3);
            padding: 5px 15px;
            border-radius: 4px;
            border: 1px solid #444;
            white-space: nowrap;
        }}
        
        /* Ajuste para móviles */
        @media (max-width: 800px) {{
            .hud-value {{ font-size: 0.9em; }}
            .hud-icon {{ font-size: 1.1em; }}
            .top-hud-sticky {{ padding-left: 60px; padding-right: 10px; gap: 10px; }}
            .hud-resource-group {{ gap: 10px; }}
        }}
        </style>

        <div class="top-hud-sticky">
            <div class="hud-resource-group">
                <div class="hud-metric" title="Créditos Estándar">
                    <span class="hud-icon">💳</span>
                    <span class="hud-value">{safe_val('creditos'):,}</span>
                </div>
                <div class="hud-metric" title="Materiales de Construcción">
                    <span class="hud-icon">📦</span>
                    <span class="hud-value">{safe_val('materiales'):,}</span>
                </div>
                <div class="hud-metric" title="Componentes Tecnológicos">
                    <span class="hud-icon">🧩</span>
                    <span class="hud-value">{safe_val('componentes'):,}</span>
                </div>
                <div class="hud-metric" title="Células de Energía">
                    <span class="hud-icon">⚡</span>
                    <span class="hud-value">{safe_val('celulas_energia'):,}</span>
                </div>
                <div class="hud-metric" title="Influencia Política">
                    <span class="hud-icon">👑</span>
                    <span class="hud-value">{safe_val('influencia'):,}</span>
                </div>
            </div>

            <div title="Ciclo Galáctico Actual: {status.get('tick', 0)}">
                <span class="hud-clock">{status.get('time', '00:00')}</span>
            </div>
        </div>
        
        <div style="height: 60px;"></div>
    """, unsafe_allow_html=True)


def _render_navigation_sidebar(player, commander, cookie_manager):
    """Sidebar limpia: Solo identidad y menú."""
    with st.sidebar:
        
        # --- BOTÓN DEBUG (Restaurado) ---
        col_dbg_txt, col_dbg_btn = st.columns([2, 1])
        with col_dbg_txt:
            st.caption("🛠️ SISTEMA")
        with col_dbg_btn:
            if st.button("🔄 Tick", help="Forzar avance del tiempo (Debug)"):
                with st.spinner("⏳"):
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

    # Título más compacto
    st.markdown('<div class="war-room-title">📟 Enlace Neuronal de Mando</div>', unsafe_allow_html=True)
    
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