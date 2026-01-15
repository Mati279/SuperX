import streamlit as st
import pandas as pd
# Eliminamos la creación de cliente duplicada
# from supabase import create_client (Ya no hace falta aquí)
# from dotenv import load_dotenv (Ya lo maneja game_engine)

# Importamos la instancia de supabase ya creada en game_engine
from game_engine import get_ai_instruction, resolve_action, supabase

# --- Configuración de la página ---
st.set_page_config(page_title="SuperX Engine", layout="wide")

# --- Estado de la sesión ---
if 'current_player_id' not in st.session_state:
    st.session_state.current_player_id = None
if 'current_player_name' not in st.session_state:
    st.session_state.current_player_name = "Nadie"

# --- Sidebar ---
with st.sidebar:
    st.header("Configuración del Jugador")

    try:
        # Usamos la instancia importada
        players_response = supabase.table("players").select("id", "nombre").execute()
        player_names = {player['nombre']: player['id'] for player in players_response.data}
        
        if not player_names:
            st.warning("No hay jugadores en la base de datos.")
            selected_player_name = None
        else:
            selected_player_name = st.selectbox(
                "Selecciona tu personaje",
                options=list(player_names.keys()),
                index=0,
                key="player_select"
            )

        if st.button("Cargar Personaje") and selected_player_name:
            st.session_state.current_player_id = player_names[selected_player_name]
            st.session_state.current_player_name = selected_player_name
            st.success(f"Personaje '{selected_player_name}' cargado.")

    except Exception as e:
        st.error(f"Error de conexión con Base de Datos: {e}")

    st.info(f"Jugador actual: **{st.session_state.current_player_name}**")

# --- Tabs Principales ---
tab1, tab2 = st.tabs(["Juego", "Administración"])

with tab1:
    st.header("Consola de Juego")

    # Área de visualización de logs
    st.subheader("Registro de Eventos")
    log_container = st.container(height=400)
    
    try:
        logs_response = supabase.table("logs").select("evento_texto").order("id", desc=True).limit(10).execute()
        if logs_response.data:
            for log in reversed(logs_response.data):
                log_container.chat_message("assistant", avatar="📜").write(log['evento_texto'])
        else:
            log_container.info("No hay eventos registrados aún.")
    except Exception as e:
        log_container.error("No se pudieron cargar los logs.")

    # Input de acción
    st.subheader("¿Qué quieres hacer?")
    action_text = st.chat_input("Describe tu acción...")

    if action_text:
        if st.session_state.current_player_id:
            with st.spinner("El universo está procesando tu destino..."):
                result = resolve_action(action_text, st.session_state.current_player_id)
                
                # Actualizar la narrativa y refrescar la página
                if result and result.get("narrative"):
                    st.rerun()
                else:
                    st.error("Hubo un problema al procesar la acción.")
        else:
            st.warning("Por favor, selecciona y carga un personaje en la barra lateral.")


with tab2:
    st.header("Panel de Administración del Mundo")

    st.info("Aquí puedes definir las reglas y la ambientación del juego en tiempo real.")

    # Cargar configuración actual
    try:
        game_config = get_ai_instruction()
    except Exception as e:
        st.error(f"No se pudo cargar la configuración: {e}")
        game_config = {}

    # Editor de reglas y descripción
    world_description = st.text_area(
        "Descripción del Mundo",
        value=game_config.get('world_description', ''),
        height=150
    )

    rules = st.text_area(
        "Reglas del Juego",
        value=game_config.get('rules', ''),
        height=300
    )
    
    system_prompt = st.text_area(
        "System Prompt del GM (Avanzado)",
        value=game_config.get('system_prompt', ''),
        height=100
    )

    if st.button("Guardar Cambios en el Mundo"):
        try:
            # Upsert para actualizar o crear las configuraciones
            supabase.table("game_config").upsert({"key": "world_description", "value": world_description}).execute()
            supabase.table("game_config").upsert({"key": "rules", "value": rules}).execute()
            supabase.table("game_config").upsert({"key": "system_prompt", "value": system_prompt}).execute()
            st.success("¡El mundo ha sido actualizado! Los cambios se aplicarán en la próxima acción.")
        except Exception as e:
            st.error(f"Error al guardar: {e}")

    st.warning("Nota: Los cambios guardados se aplicarán a todas las acciones futuras de los jugadores.")
