import streamlit as st
import pandas as pd
from game_engine import get_ai_instruction, resolve_action, supabase, generate_random_character

# --- Configuración de la página ---
st.set_page_config(page_title="SuperX Engine", layout="wide")

# --- Estado de la sesión ---
if 'current_character_id' not in st.session_state:
    st.session_state.current_character_id = None
if 'current_character_name' not in st.session_state:
    st.session_state.current_character_name = "Nadie"
if 'current_character_data' not in st.session_state:
    st.session_state.current_character_data = None

# --- Sidebar ---
with st.sidebar:
    st.header("Selección de Operativo")

    try:
        # Ahora los 'jugadores' son las entidades de tipo 'Operativo'
        response = supabase.table("entities").select("id", "nombre").eq("tipo", "Operativo").execute()
        character_map = {char['nombre']: char['id'] for char in response.data}
        
        if not character_map:
            st.warning("No hay operativos en la base de datos. Recluta uno en 'Administración'.")
            selected_char_name = None
        else:
            selected_char_name = st.selectbox(
                "Selecciona un operativo",
                options=list(character_map.keys()),
                index=0,
                key="char_select"
            )

        if st.button("Cargar Operativo") and selected_char_name:
            char_id = character_map[selected_char_name]
            st.session_state.current_character_id = char_id
            st.session_state.current_character_name = selected_char_name
            
            # Cargar la ficha completa del personaje
            char_data_response = supabase.table("entities").select("*").eq("id", char_id).single().execute()
            st.session_state.current_character_data = char_data_response.data
            
            st.success(f"Operativo '{selected_char_name}' cargado.")
            st.rerun()

    except Exception as e:
        st.error(f"Error de conexión con la Base de Datos: {e}")

    st.info(f"Operativo actual: **{st.session_state.current_character_name}**")

# --- Tabs Principales ---
tab1, tab2, tab3 = st.tabs(["Consola de Juego", "Ficha de Personaje", "Administración"])

with tab1:
    st.header("Consola de Juego")

    st.subheader("Registro de Eventos")
    log_container = st.container(height=400)
    
    try:
        logs = supabase.table("logs").select("evento_texto").order("id", desc=True).limit(15).execute()
        if logs.data:
            for log in reversed(logs.data):
                log_container.chat_message("assistant", avatar="📜").write(log['evento_texto'])
        else:
            log_container.info("No hay eventos registrados.")
    except Exception:
        log_container.error("No se pudieron cargar los logs.")

    st.subheader("¿Qué quieres hacer?")
    action_text = st.chat_input("Describe tu acción...")

    if action_text:
        if st.session_state.current_character_id:
            with st.spinner("El universo está procesando tu destino..."):
                resolve_action(action_text, st.session_state.current_character_id)
                st.rerun()
        else:
            st.warning("Por favor, selecciona y carga un operativo en la barra lateral.")

with tab2:
    st.header(f"Ficha de Personaje: {st.session_state.current_character_name}")

    if not st.session_state.current_character_data:
        st.info("Carga un operativo desde la barra lateral para ver sus detalles.")
    else:
        char_data = st.session_state.current_character_data
        stats = char_data.get("stats_json", {})
        bio = stats.get("biografia", {})
        attrs = stats.get("atributos", {})

        # Fila superior de Biografía
        st.subheader("Biografía")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Nombre", bio.get("nombre", "N/A"))
        col2.metric("Raza", bio.get("raza", "N/A"))
        col3.metric("Edad", bio.get("edad", "N/A"))
        col4.metric("Sexo", bio.get("sexo", "N/A"))
        
        st.divider()

        # Cuadrícula de Atributos
        st.subheader("Atributos")
        attr_cols = st.columns(6)
        attr_map = {
            "Fuerza": "fuerza", "Agilidad": "agilidad", "Intelecto": "intelecto",
            "Técnica": "tecnica", "Presencia": "presencia", "Voluntad": "voluntad"
        }
        for i, (label, key) in enumerate(attr_map.items()):
            attr_cols[i].metric(label, attrs.get(key, "N/A"))

with tab3:
    st.header("Panel de Administración")
    
    st.subheader("Gestión de Operativos")
    if st.button("Reclutar Nuevo Operativo"):
        with st.spinner("Contactando con reclutadores galácticos..."):
            new_char = generate_random_character()
            if new_char:
                st.success("¡Nuevo operativo reclutado con éxito!")
                # Opcional: Recargar para que aparezca en la lista
                st.rerun()
            else:
                st.error("El reclutamiento falló. Revisa los logs del sistema.")

    st.divider()

    st.subheader("Configuración del Mundo")
    st.info("Define aquí las reglas y la ambientación del juego.")

    try:
        game_config = get_ai_instruction()
    except Exception as e:
        st.error(f"No se pudo cargar la configuración: {e}")
        game_config = {}

    world_description = st.text_area("Descripción del Mundo", value=game_config.get('world_description', ''), height=150)
    rules = st.text_area("Reglas del Juego", value=game_config.get('rules', ''), height=200)
    
    if st.button("Guardar Cambios del Mundo"):
        try:
            supabase.table("game_config").upsert({"key": "world_description", "value": world_description}).execute()
            supabase.table("game_config").upsert({"key": "rules", "value": rules}).execute()
            st.success("¡El mundo ha sido actualizado!")
        except Exception as e:
            st.error(f"Error al guardar: {e}")
