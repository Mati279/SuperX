# ui/main_game_page.py
import streamlit as st
from .state import logout_user, get_player, get_commander
from core.time_engine import get_world_status_display, check_and_trigger_tick
# ... (otros imports de vistas)

def render_main_game_page(cookie_manager):
    # Ejecutamos el trigger del tiempo al cargar la página
    check_and_trigger_tick()
    
    player = get_player()
    commander = get_commander()
    # ... (lógica de navegación existente)
    _render_navigation_sidebar(player, commander, cookie_manager)
    # ... (renderizado de página seleccionada)

def _render_navigation_sidebar(player, commander, cookie_manager):
    with st.sidebar:
        # --- BLOQUE DEL RELOJ GALÁCTICO ---
        status = get_world_status_display()
        color = "#56d59f"  # Verde nominal
        if status["is_lock_in"]: color = "#f6c45b" # Naranja bloqueo
        if status["is_frozen"]: color = "#f06464"  # Rojo freeze

        st.markdown(f"""
            <div style="background-color: #0e1117; padding: 15px; border: 1px solid #333; border-radius: 10px; text-align: center;">
                <p style="margin: 0; color: #888; font-size: 0.8em;">CICLO SOLAR GALÁCTICO</p>
                <h2 style="margin: 5px 0; color: {color}; font-family: monospace;">{status['time']}</h2>
                <p style="margin: 0; font-size: 0.9em;">Estado: <b>{status['status']}</b></p>
                <p style="margin: 0; font-size: 0.8em; color: #555;">Tick actual: {status['tick']}</p>
            </div>
        """, unsafe_allow_html=True)
        st.divider()
        # --- FIN DEL RELOJ ---

        st.header(f"Facción: {player['faccion_nombre']}")
        # ... (resto de botones de navegación)