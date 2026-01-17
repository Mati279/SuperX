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
    Página principal del juego con HUD superior y navegación lateral.
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

    # --- 1. RENDERIZAR HUD SUPERIOR (Recursos + Reloj) ---
    _render_top_hud(player, commander)

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
    
    # Contenedor principal para el contenido de la página
    with st.container():
        render_func = PAGES.get(st.session_state.current_page, _render_war_room_page)
        render_func()


def _render_top_hud(player, commander):
    """Renderiza la barra superior de recursos y tiempo (Estilo RTS)."""
    
    # Estilos CSS para el HUD
    st.markdown("""
        <style>
        .hud-container {
            background-color: #0e1117;
            border-bottom: 2px solid #333;
            padding: 10px 5px;
            margin-bottom: 20px;
        }
        .metric-box {
            background-color: #1a1c24;
            border: 1px solid #444;
            border-radius: 5px;
            padding: 5px 10px;
            text-align: center;
            color: #fff;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        .metric-icon { font-size: 1.2em; margin-right: 5px; }
        .metric-value { font-family: monospace; font-weight: bold; font-size: 1.1em; color: #56d59f; }
        .hud-time { font-family: monospace; color: #f9ca24; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

    finances = get_player_finances(player['id'])
    status = get_world_status_display()
    
    # Layout de 7 columnas: 5 Recursos + 1 Espacio + 2 Tiempo/Debug
    # Usamos st.columns para distribuir horizontalmente
    c1, c2, c3, c4, c5, c_spacer, c_time, c_debug = st.columns([1, 1, 1, 1, 1, 0.5, 1.5, 0.8])

    # Función helper para renderizar métrica compacta
    def hud_metric(col, icon, value, help_text):
        col.markdown(f"""
            <div class="metric-box" title="{help_text}">
                <span class="metric-icon">{icon}</span>
                <span class="metric-value">{value}</span>
            </div>
        """, unsafe_allow_html=True)

    hud_metric(c1, "💳", finances.get('creditos', 0), "Créditos")
    hud_metric(c2, "📦", finances.get('materiales', 0), "Materiales")
    hud_metric(c3, "🧩", finances.get('componentes', 0), "Componentes")
    hud_metric(c4, "⚡", finances.get('celulas_energia', 0), "Células de Energía")
    hud_metric(c5, "👑", finances.get('influencia', 0), "Influencia")

    # Reloj
    with c_time:
        st.markdown(f"""
            <div style="text-align:right; line-height:1.2;">
                <div class="hud-time">{status['time']}</div>
                <div style="font-size:0.7em; color:#888;">CICLO {status['tick']}</div>
            </div>
        """, unsafe_allow_html=True)

    # Botón Debug (Pequeño)
    with c_debug:
        if st.button("🔄", help="DEBUG: Forzar avance de tiempo"):
            with st.spinner("⏳"):
                debug_force_tick()
            st.rerun()

    st.divider()


def _render_navigation_sidebar(player, commander, cookie_manager):
    """Sidebar limpia: Solo identidad y menú."""
    with st.sidebar:
        # --- SECCIÓN: IDENTIDAD ---
        st.header(f"{player['faccion_nombre']}")
        if player.get('banner_url'):
            st.image(player['banner_url'], width='stretch')

        st.caption(f"Comandante {commander['nombre']}")
        
        pending = get_pending_actions_count(player['id'])
        if pending > 0:
            st.info(f"📩 {pending} orden(es) en cola.")

        # --- SECCIÓN: NAVEGACIÓN ---
        st.divider()
        st.subheader("Sistemas")

        # Botones de navegación (Estilo menú vertical)
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
        render_character_card(commander, player['id'], is_commander=True)
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
    
    player_id = get_player()['id']
    commander_name = get_commander()['nombre']
    status = get_world_status_display()

    # Título más compacto
    st.markdown('<div class="war-room-title">📟 Enlace Neuronal de Mando</div>', unsafe_allow_html=True)
    
    if status['is_lock_in']:
        st.warning("⚠️ VENTANA DE BLOQUEO ACTIVA")
    
    # --- CONTENEDOR DE CHAT (SCROLLABLE) ---
    # Usamos st.container con altura fija para crear la "caja roja" que pediste
    chat_box = st.container(height=500, border=True)

    logs = get_recent_logs(player_id, limit=30) # Aumentamos el límite ya que ahora hay scroll

    with chat_box:
        if not logs:
            st.info(f"Conexión establecida. Esperando órdenes, Comandante {commander_name}...")
        
        # Renderizar logs (invertidos para que el más nuevo esté abajo si usamos scroll, 
        # pero Streamlit suele renderizar arriba->abajo. 
        # Para un chat tipo "WhatsApp", lo viejo va arriba, lo nuevo abajo.)
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