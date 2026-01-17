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
    
    # Contenedor principal
    with st.container():
        # Añadimos un pequeño espacio arriba para que el HUD no tape el título
        st.write("") 
        render_func = PAGES.get(st.session_state.current_page, _render_war_room_page)
        render_func()


def _render_sticky_top_hud(player, commander):
    """
    Renderiza la barra superior STICKY (siempre visible).
    Usa CSS para fijarla arriba y tooltips para los nombres.
    """
    
    finances = get_player_finances(player['id'])
    status = get_world_status_display()

    # Definir colores de estado
    time_color = "#56d59f"  # Verde
    if status["is_lock_in"]: time_color = "#f9ca24" # Amarillo
    if status["is_frozen"]: time_color = "#ff6b6b" # Rojo

    # CSS para hacer la barra Sticky y estilizada
    st.markdown(f"""
        <style>
        /* Contenedor principal de la barra superior */
        .top-hud-sticky {{
            position: sticky;
            top: 0;
            z-index: 9999;
            background-color: #0e1117; /* Mismo color de fondo que la app */
            border-bottom: 2px solid #333;
            padding: 10px 0;
            margin-top: -60px; /* Hack para subirlo lo más posible en Streamlit */
            margin-left: -20px;
            margin-right: -20px;
            padding-left: 20px;
            padding-right: 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }}

        /* Cajas de recursos */
        .hud-resource-group {{
            display: flex;
            gap: 15px;
        }}
        
        .hud-metric {{
            background: #1a1c24;
            border: 1px solid #444;
            border-radius: 6px;
            padding: 4px 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: help; /* Indica que hay info extra */
            transition: all 0.2s;
        }}
        
        .hud-metric:hover {{
            border-color: #666;
            background: #252836;
            transform: translateY(-1px);
        }}

        .hud-icon {{ font-size: 1.2em; }}
        .hud-value {{ 
            font-family: 'Source Code Pro', monospace; 
            font-weight: bold; 
            color: #eee;
        }}

        /* Sección del Reloj */
        .hud-clock-group {{
            display: flex;
            align-items: center;
            gap: 15px;
            background: rgba(0,0,0,0.2);
            padding: 4px 12px;
            border-radius: 6px;
            border: 1px solid #333;
        }}

        .hud-time {{ 
            font-family: 'Orbitron', monospace; 
            color: {time_color}; 
            font-weight: bold; 
            font-size: 1.1em;
            letter-spacing: 1px;
        }}
        
        .hud-tick {{ font-size: 0.8em; color: #888; }}
        </style>
    """, unsafe_allow_html=True)

    # Construir el HTML de los recursos (Izquierda)
    # title="..." es lo que muestra el nombre on hover
    resources_html = f"""
        <div class="hud-resource-group">
            <div class="hud-metric" title="Créditos (Moneda estándar)">
                <span class="hud-icon">💳</span>
                <span class="hud-value">{finances.get('creditos', 0):,}</span>
            </div>
            <div class="hud-metric" title="Materiales (Construcción y Reparación)">
                <span class="hud-icon">📦</span>
                <span class="hud-value">{finances.get('materiales', 0):,}</span>
            </div>
            <div class="hud-metric" title="Componentes (Tecnología y Armas)">
                <span class="hud-icon">🧩</span>
                <span class="hud-value">{finances.get('componentes', 0):,}</span>
            </div>
            <div class="hud-metric" title="Células de Energía (Combustible)">
                <span class="hud-icon">⚡</span>
                <span class="hud-value">{finances.get('celulas_energia', 0):,}</span>
            </div>
            <div class="hud-metric" title="Influencia (Poder Político)">
                <span class="hud-icon">👑</span>
                <span class="hud-value">{finances.get('influencia', 0):,}</span>
            </div>
        </div>
    """

    # Construir HTML del Reloj (Derecha)
    clock_html = f"""
        <div class="hud-clock-group">
            <div style="text-align: right; line-height: 1.1;">
                <div class="hud-time">{status['time']}</div>
                <div class="hud-tick">CICLO {status['tick']}</div>
            </div>
        </div>
    """

    # Renderizar todo en una sola estructura HTML/Markdown para asegurar el layout sticky
    # Nota: El botón de debug de Streamlit no se puede meter dentro del HTML puro fácilmente,
    # así que usamos columnas de Streamlit dentro del contenedor sticky si fuera posible, 
    # pero para 'sticky' puro es mejor HTML. 
    # Haremos un híbrido: HTML para recursos/reloj, y el botón debug lo ponemos abajo o flotante.
    
    st.markdown(f"""
        <div class="top-hud-sticky">
            {resources_html}
            {clock_html}
        </div>
    """, unsafe_allow_html=True)
    
    # Botón de Debug: Lo ponemos justo después, flotando sutilmente o integrado.
    # Para simplicidad y robustez, lo dejamos en un expander colapsado o esquina.
    # O, lo inyectamos visualmente.


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
        
        # Botón Debug (Ahora en el sidebar, abajo de todo, para no romper el CSS del topbar)
        with st.expander("🛠️ Debug Tools"):
            if st.button("🚨 FORZAR TICK"):
                with st.spinner("⏳ Saltando tiempo..."):
                    debug_force_tick()
                st.rerun()

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

    logs = get_recent_logs(player_id, limit=30) 

    with chat_box:
        if not logs:
            st.info(f"Conexión establecida. Esperando órdenes, Comandante {commander_name}...")
        
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