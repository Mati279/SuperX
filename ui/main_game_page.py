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
        st.error("❌ ERROR CRÍTICO: No se pudieron cargar los datos del jugador. Reinicia sesión.")
        if st.button("Volver al Login"):
            logout_user(cookie_manager)
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


def _render_war_room_styles():
    """Estilos visuales para el Puente de Mando."""
    st.markdown(
        """
        <style>
        @import url("https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700&family=Share+Tech+Mono&display=swap");

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
        div[data-testid="stChatMessage"] {
            border-radius: 12px;
            border: 1px solid rgba(80, 170, 220, 0.3);
            background: linear-gradient(145deg, rgba(10, 20, 32, 0.95), rgba(6, 12, 20, 0.95));
            box-shadow: inset 0 0 14px rgba(60, 180, 235, 0.08);
            margin-bottom: 10px;
        }

        /* Color explícito para asegurar contraste */
        div[data-testid="stChatMessage"] div[data-testid="stChatMessageContent"] {
            font-family: "Share Tech Mono", monospace;
            color: #ffffff !important; 
            font-size: 14px;
        }
        
        div[data-testid="stChatMessage"] span[title] {
            font-family: "Orbitron", sans-serif;
            letter-spacing: 1px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_war_room_page():
    """Página del Puente de Mando con historial persistente robusto."""
    _render_war_room_styles()
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

    st.markdown(
        "<div class=\"war-room-section\">Bitacora de Mision</div>",
        unsafe_allow_html=True,
    )
    
    player_id = get_player()['id']
    commander_name = get_commander()['nombre']
    
    # --- RENDERIZADO DEL CHAT ---
    # 1. Obtenemos logs. Si falla, logs será [].
    logs = get_recent_logs(player_id, limit=30)
    
    # 2. Contenedor PRINCIPAL (Sin altura fija para evitar bugs de rendering)
    log_container = st.container()

    if not logs:
        st.info(f"ℹ️ Inicializando sistemas de comunicación para el Comandante {commander_name}. Historial vacío.")
    
    with log_container:
        # Nota: logs viene ordenado DESC (nuevo -> viejo), usamos reversed para renderizar viejo -> nuevo (arriba -> abajo)
        for log in reversed(logs):
            mensaje = log.get('message', '')
            
            # Filtro básico de basura técnica
            if "[DEBUG]" in mensaje or "Traceback" in mensaje:
                continue

            if mensaje.startswith("[PLAYER]"):
                mensaje_limpio = mensaje.replace("[PLAYER] ", "")
                with st.chat_message("user", avatar="👤"):
                    st.write(mensaje_limpio)
            else:
                icon = "🤖"
                if "VENTANA DE BLOQUEO" in mensaje or "⏱️" in mensaje: icon = "⏳"
                elif "CONGELADO" in mensaje or "❄️" in mensaje: icon = "❄️"
                elif "Misión EXITOSA" in mensaje or "✅" in mensaje: icon = "✅"
                elif "Misión FALLIDA" in mensaje or "❌" in mensaje: icon = "❌"

                # Limpieza de prefijos
                mensaje_limpio = mensaje
                for p in ["[GM] ", "🤖 [ASISTENTE] ", "[ASISTENTE] ", "🤖 "]:
                    if mensaje_limpio.startswith(p):
                        mensaje_limpio = mensaje_limpio.replace(p, "", 1)
                        break

                with st.chat_message("assistant", avatar=icon):
                    st.write(mensaje_limpio)
            
    # Espaciador para separar el chat del input en pantallas grandes
    st.write("") 
    st.write("") 

    # --- INPUT DE CHAT (Siempre abajo) ---
    input_placeholder = f"¿Órdenes, Comandante {commander_name}?"
    if status['is_frozen']:
        input_placeholder = "Sistemas congelados. Entrada deshabilitada."
        
    action = st.chat_input(input_placeholder, disabled=status['is_frozen'])

    if action:
        # Registrar el mensaje del usuario inmediatamente
        log_event(f"[PLAYER] {action}", player_id)

        # Spinner mientras procesa
        with st.spinner("Procesando orden..."):
            try:
                resolve_player_action(action, player_id)
                # Forzar recarga inmediata para ver el resultado
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ Error crítico en enlace neuronal: {e}")