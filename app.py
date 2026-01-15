import streamlit as st
import pandas as pd
from game_engine import resolve_action, generate_random_character, supabase

# --- Configuración de la página ---
st.set_page_config(page_title="SuperX Engine", layout="wide")

# --- Estado de la sesión ---
if 'current_player_id' not in st.session_state:
    st.session_state.current_player_id = None
if 'current_player_name' not in st.session_state:
    st.session_state.current_player_name = "Nadie"

# --- Sidebar ---
with st.sidebar:
    st.header("SuperX Galactic")
    
    # Selector de Jugador
    try:
        players_response = supabase.table("players").select("id", "nombre").execute()
        player_names = {player['nombre']: player['id'] for player in players_response.data}
        
        if not player_names:
            st.warning("Sin jugadores.")
            selected_player_name = None
        else:
            selected_player_name = st.selectbox(
                "Comandante",
                options=list(player_names.keys()),
                index=0
            )

        if st.button("Cargar") and selected_player_name:
            st.session_state.current_player_id = player_names[selected_player_name]
            st.session_state.current_player_name = selected_player_name
            st.success(f"Mando: {selected_player_name}")

    except Exception as e:
        st.error(f"Error DB: {e}")

    st.info(f"Activo: **{st.session_state.current_player_name}**")
    st.divider()
    
    # Reclutamiento
    st.subheader("Reclutamiento")
    if st.button("Reclutar Operativo"):
        with st.spinner("Procesando..."):
            new_char = generate_random_character()
            if new_char:
                st.success(f"¡{new_char['nombre']} unido!")
                with st.expander("Ver Ficha"):
                    st.json(new_char['stats_json'])
            else:
                st.error("Fallo al reclutar. Revisa los logs en Admin.")

# --- Tabs ---
tab1, tab2 = st.tabs(["Juego", "Administración"])

with tab1:
    st.header("Centro de Mando")

    # LOGS VISUALES (Últimos 5 eventos para el jugador)
    st.subheader("Últimos Eventos")
    log_container = st.container(height=300)
    try:
        # Filtramos solo lo que NO es error para la pantalla de juego
        logs_response = supabase.table("logs").select("evento_texto").ilike("evento_texto", "%ERROR%").is_("eq", False).order("id", desc=True).limit(5).execute() 
        # Nota: La query de arriba intenta filtrar, si falla, traemos todo y filtramos en python
        # Simplificación: Traemos los últimos 10 y mostramos
        logs_resp = supabase.table("logs").select("*").order("id", desc=True).limit(10).execute()
        
        for log in reversed(logs_resp.data):
            if "ERROR" not in log['evento_texto']:
                log_container.chat_message("assistant", avatar="📜").write(log['evento_texto'])
                
    except Exception:
        log_container.info("Sin datos.")

    # Acción
    action = st.chat_input("Órdenes...")
    if action:
        if st.session_state.current_player_id:
            with st.spinner("Ejecutando..."):
                res = resolve_action(action, st.session_state.current_player_id)
                if res.get("narrative"): st.rerun()
        else:
            st.warning("Selecciona Comandante.")

with tab2:
    st.header("Administración & Debug")
    
    # --- MONITOR DE LOGS (NUEVO) ---
    st.subheader("🔍 Monitor del Sistema (Logs Completos)")
    if st.button("Refrescar Logs"):
        st.rerun()
        
    try:
        # Traemos más logs para admin
        all_logs = supabase.table("logs").select("*").order("id", desc=True).limit(20).execute()
        if all_logs.data:
            for log in all_logs.data:
                msg = log['evento_texto']
                if "ERROR" in msg:
                    st.error(f"[{log['id']}] {msg}")
                else:
                    st.text(f"[{log['id']}] {msg}")
        else:
            st.info("Log vacío.")
    except Exception as e:
        st.error(f"No se pudo cargar el monitor: {e}")

    st.divider()
    
    # Configuración del Mundo
    st.subheader("Configuración Global")
    # (Aquí iría la lógica de edición de config si la necesitas, simplificada por espacio)
    if st.button("Ver Configuración Actual (JSON)"):
         try:
             conf = supabase.table("game_config").select("*").execute()
             st.json(conf.data)
         except: pass