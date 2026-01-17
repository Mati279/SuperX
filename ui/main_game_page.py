# ui/main_game_page.py
import streamlit as st
from .state import logout_user, get_player, get_commander
from data.log_repository import get_recent_logs, log_event
from services.gemini_service import resolve_player_action

# --- Nuevos imports para STRT (Sistema de Tiempo) ---
from core.time_engine import get_world_status_display, check_and_trigger_tick, debug_force_tick
from data.world_repository import get_pending_actions_count
from data.player_repository import get_player_finances

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

def _render_war_room_styles():
    """Estilos visuales para el Puente de Mando con corrección para mensajes de usuario."""
    st.markdown(
        """
        <style>
        @import url("https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700&family=Share+Tech+Mono&display=swap");

        /* Header del Puente */
        .war-room-header {
            margin-bottom: 12px;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(90, 190, 255, 0.25);
            position: relative;
        }
        .war-room-header::after {
            content: "";
            position: absolute;
            left: 0;
            bottom: 0;
            width: 150px;
            height: 2px;
            background: linear-gradient(90deg, rgba(95, 216, 255, 0.95), rgba(95, 216, 255, 0));
            box-shadow: 0 0 10px rgba(95, 216, 255, 0.5);
        }
        .war-room-title {
            font-family: "Orbitron", sans-serif;
            font-size: 32px;
            font-weight: 700;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: #dff6ff;
            text-shadow: 0 0 14px rgba(88, 210, 255, 0.4);
        }
        .war-room-section {
            font-family: "Orbitron", sans-serif;
            font-size: 15px;
            letter-spacing: 1.6px;
            text-transform: uppercase;
            color: #b8e7ff;
            margin: 6px 0 10px 0;
        }

        /* --- ESTILOS DE CHAT --- */

        /* 1. Mensajes por defecto (IA/Assistant) - Azul Tecnológico */
        div[data-testid="stChatMessage"] {
            border-radius: 12px;
            border: 1px solid rgba(80, 170, 220, 0.3);
            background: linear-gradient(145deg, rgba(10, 20, 32, 0.95), rgba(6, 12, 20, 0.95));
            box-shadow: inset 0 0 14px rgba(60, 180, 235, 0.08);
            margin-bottom: 10px;
        }

        /* 2. Mensajes del Usuario (Player) - GRIS OSCURO 
           Detectamos el mensaje usando el marcador invisible .user-marker */
        div[data-testid="stChatMessage"]:has(.user-marker) {
            background: linear-gradient(145deg, #161b22, #0d1117) !important;
            border: 1px solid rgba(160, 160, 160, 0.3) !important;
            box-shadow: inset 0 0 10px rgba(0, 0, 0, 0.2) !important;
        }

        /* Texto de los mensajes */
        div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] {
            font-family: "Share Tech Mono", monospace;
            color: #d5f3ff;
            font-size: 14px;
        }
        
        div[data-testid="stChatMessage"] span[title] {
            font-family: "Orbitron", sans-serif;
            letter-spacing: 1px;
        }

        /* Input de Chat */
        div[data-testid="stChatInput"] {
            border-radius: 16px;
            border: 1px solid rgba(90, 200, 255, 0.5);
            background: linear-gradient(135deg, rgba(9, 18, 30, 0.95), rgba(6, 12, 20, 0.95));
            box-shadow: 0 12px 26px rgba(8, 14, 24, 0.5), inset 0 0 18px rgba(75, 200, 255, 0.12);
        }
        div[data-testid="stChatInput"] textarea {
            font-family: "Share Tech Mono", monospace;
            font-size: 14px;
            color: #dcf6ff;
        }
        div[data-testid="stChatInput"] button {
            border-radius: 10px;
            border: 1px solid rgba(120, 215, 255, 0.5);
            background: linear-gradient(135deg, rgba(36, 86, 122, 0.9), rgba(20, 40, 64, 0.9));
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_chat_interface(chat_container, commander_name: str, player_id: int, is_frozen: bool):
    """
    Renderiza la interfaz de chat Neural Link.
    CRÍTICO: Itera sobre st.session_state.messages ANTES de st.chat_input()
    para garantizar persistencia entre reruns de Streamlit.
    """
    # --- PASO 1: Renderizar historial de mensajes desde session_state ---
    # Esto DEBE ocurrir ANTES del chat_input para que los mensajes persistan
    with chat_container:
        for message in st.session_state.messages:
            role = message.get("role", "assistant")
            content = message.get("content")

            # Manejar mensajes que tienen tool_calls en lugar de content
            if content is None:
                tool_calls = message.get("tool_calls")
                if tool_calls:
                    # Mostrar indicador de tool call
                    content = "[Ejecutando acción del sistema...]"
                else:
                    # Saltar mensajes vacíos
                    continue

            # Determinar avatar e icono según el rol y contenido
            if role == "user":
                with st.chat_message("user", avatar="👤"):
                    st.write(content)
                    st.markdown('<div class="user-marker" style="display:none;"></div>', unsafe_allow_html=True)
            else:
                # Mensaje de assistant/sistema
                icon = "🤖"
                if "VENTANA DE BLOQUEO" in str(content) or "⏱️" in str(content):
                    icon = "⏳"
                elif "CONGELADO" in str(content) or "❄️" in str(content):
                    icon = "❄️"
                elif "Misión EXITOSA" in str(content) or "✅" in str(content):
                    icon = "✅"
                elif "Misión FALLIDA" in str(content) or "❌" in str(content):
                    icon = "❌"

                st.chat_message("assistant", avatar=icon).write(content)

    # --- PASO 2: Input del chat (DESPUÉS de renderizar mensajes) ---
    input_placeholder = f"¿Órdenes, Comandante {commander_name}?"
    if is_frozen:
        input_placeholder = "Sistemas congelados. Entrada deshabilitada."

    action = st.chat_input(input_placeholder, disabled=is_frozen)

    # --- PASO 3: Procesar nuevo mensaje ---
    if action:
        # Agregar mensaje del usuario al estado de sesión
        st.session_state.messages.append({
            "role": "user",
            "content": action
        })

        # Registrar en la bitácora persistente (DB)
        log_event(f"[PLAYER] {action}", player_id)

        # Procesar con IA
        with st.spinner("Transmitiendo órdenes..."):
            try:
                result = resolve_player_action(action, player_id)

                # Agregar respuesta de la IA al estado de sesión
                if result:
                    # Manejar diferentes formatos de respuesta
                    if isinstance(result, dict):
                        response_content = result.get("content") or result.get("message") or str(result)
                    else:
                        response_content = str(result)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_content
                    })

                st.rerun()
            except Exception as e:
                error_msg = f"Error de comunicación: {e}"
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg
                })
                st.error(f"⚠️ {error_msg}")


def _render_war_room_page():
    """Página del Puente de Mando con integración STRT y layout de columnas."""
    _render_war_room_styles()

    # --- Header del Puente de Mando ---
    st.markdown(
        """
        <div class="war-room-header">
            <div class="war-room-title">Puente de Mando</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    status = get_world_status_display()

    if status['is_lock_in']:
        st.warning("⚠️ VENTANA DE BLOQUEO ACTIVA: Las órdenes se ejecutarán al iniciar el próximo ciclo.")
    if status['is_frozen']:
        st.error("❄️ ALERTA: El flujo temporal está detenido (FREEZE). Sistemas tácticos en espera.")

    player = get_player()
    commander = get_commander()

    if not player or not commander:
        st.error("No se pudieron cargar los datos. Por favor, reinicia la sesión.")
        return

    player_id = player['id']
    commander_name = commander['nombre']

    # --- LAYOUT: Mapa (Izquierda) | Chat Neural Link (Derecha) ---
    col_map, col_chat = st.columns([7, 3])

    # === COLUMNA IZQUIERDA: Bitácora de Misión ===
    with col_map:
        st.markdown(
            "<div class=\"war-room-section\">Bitacora de Mision</div>",
            unsafe_allow_html=True,
        )

        log_container = st.container(height=520)
        logs = get_recent_logs(player_id, limit=20)

        for log in reversed(logs):
            mensaje = log.get('message', '')
            if "ERROR" not in mensaje:
                if mensaje.startswith("[PLAYER]"):
                    mensaje_limpio = mensaje.replace("[PLAYER] ", "")
                    with log_container.chat_message("user", avatar="👤"):
                        st.write(mensaje_limpio)
                        st.markdown('<div class="user-marker" style="display:none;"></div>', unsafe_allow_html=True)
                else:
                    icon = "🤖"
                    if "VENTANA DE BLOQUEO" in mensaje or "⏱️" in mensaje:
                        icon = "⏳"
                    elif "CONGELADO" in mensaje or "❄️" in mensaje:
                        icon = "❄️"
                    elif "DEBUG" in mensaje:
                        icon = "🛠️"
                    elif "Misión EXITOSA" in mensaje or "✅" in mensaje:
                        icon = "✅"
                    elif "Misión FALLIDA" in mensaje or "❌" in mensaje:
                        icon = "❌"
                    elif "[ASISTENTE]" in mensaje or "🤖" in mensaje:
                        icon = "🤖"

                    mensaje_limpio = mensaje
                    prefijos_a_limpiar = ["[GM] ", "🤖 [ASISTENTE] ", "[ASISTENTE] ", "🤖 "]
                    for prefijo in prefijos_a_limpiar:
                        if mensaje_limpio.startswith(prefijo):
                            mensaje_limpio = mensaje_limpio.replace(prefijo, "", 1)
                            break

                    log_container.chat_message("assistant", avatar=icon).write(mensaje_limpio)

    # === COLUMNA DERECHA: Chat Neural Link ===
    with col_chat:
        st.markdown(
            "<div class=\"war-room-section\">Neural Link</div>",
            unsafe_allow_html=True,
        )

        # Crear contenedor con altura fija para scroll
        chat_container = st.container(height=600)

        # Renderizar interfaz de chat (mensajes + input)
        _render_chat_interface(chat_container, commander_name, player_id, status['is_frozen'])


def _render_commander_sheet_page():
    """Página de la Ficha del Comandante."""
    st.title("Ficha de Servicio del Comandante")

    commander = get_commander()
    stats = commander.get('stats_json', {})
    bio = stats.get('bio', {})
    atributos = stats.get('atributos', {})
    habilidades = stats.get('habilidades', {})

    st.header(f"Informe de {commander['nombre']}")

    # Biografía
    st.subheader("Biografía")
    col_bio1, col_bio2 = st.columns(2)
    with col_bio1:
        st.markdown(f"**Raza:** {bio.get('raza', 'N/A')}")
        st.markdown(f"**Clase:** {bio.get('clase', 'N/A')}")
    with col_bio2:
        if bio.get('descripcion_raza'):
            st.caption(f"*{bio.get('descripcion_raza')}*")
        if bio.get('descripcion_clase'):
            st.caption(f"*{bio.get('descripcion_clase')}*")

    st.markdown("---")

    # Atributos con barras visuales
    st.subheader("Atributos")
    attr_colors = {
        "fuerza": "#ff6b6b", "agilidad": "#4ecdc4", "intelecto": "#45b7d1",
        "tecnica": "#f9ca24", "presencia": "#a55eea", "voluntad": "#26de81"
    }
    cols = st.columns(2)
    for i, (attr, value) in enumerate(atributos.items()):
        with cols[i % 2]:
            color = attr_colors.get(attr.lower(), "#888")
            percentage = min(100, (value / 20) * 100)
            st.markdown(f"""
                <div style="margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                        <span style="font-size: 0.85em; color: #ccc;">{attr.upper()}</span>
                        <span style="font-size: 0.85em; font-weight: bold; color: {color};">{value}</span>
                    </div>
                    <div style="background: #1a1a2e; border-radius: 4px; height: 8px; overflow: hidden;">
                        <div style="background: {color}; width: {percentage}%; height: 100%; border-radius: 4px;"></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # Habilidades con chips visuales
    st.subheader("Habilidades")
    if habilidades:
        skills_html = ""
        for skill, val in sorted(habilidades.items(), key=lambda x: -x[1]):
            if val >= 30:
                color, border = "#ffd700", "#ffd700"  # Dorado - Maestro
            elif val >= 20:
                color, border = "#45b7d1", "#45b7d1"  # Azul - Experto
            else:
                color, border = "#888", "#444"  # Gris - Normal
            skills_html += f"""
                <span style="
                    display: inline-block; padding: 4px 10px; margin: 2px 4px 2px 0;
                    background: rgba(0,0,0,0.3); border: 1px solid {border};
                    border-radius: 12px; font-size: 0.75em; color: {color};
                ">{skill}: <b>{val}</b></span>
            """
        st.markdown(f'<div style="margin-top: 8px;">{skills_html}</div>', unsafe_allow_html=True)
    else:
        st.info("No hay habilidades calculadas.")