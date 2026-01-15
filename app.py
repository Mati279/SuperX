import streamlit as st
from game_engine import (
    supabase,
    generate_random_character,
    resolve_action,
    verify_password
)

# --- Page Configuration ---
st.set_page_config(page_title="SuperX Engine", layout="wide")

# --- Session State Initialization ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'player_info' not in st.session_state:
    st.session_state.player_info = None

# --- Main Game UI ---
def main_game_interface():
    player = st.session_state.player_info

    # Display Faction Banner and Name
    st.markdown(f"## Comandante: {player['nombre']} | Facción: {player['faccion_nombre']}")
    if player.get('banner_url'):
        st.image(player['banner_url'], width=150)

    st.sidebar.header("SuperX Galactic")
    st.sidebar.info(f"Sesión activa como: **{player['nombre']}**")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.player_info = None
        st.rerun()
        
    st.sidebar.divider()

    # Main game tabs
    tab1, tab2 = st.tabs(["Juego", "Administración"])

    with tab1:
        st.header("Centro de Mando")
        st.subheader("Últimos Eventos")
        log_container = st.container(height=300)
        try:
            logs_resp = supabase.table("logs").select("*").order("id", desc=True).limit(10).execute()
            for log in reversed(logs_resp.data):
                if "ERROR" not in log['evento_texto']:
                    log_container.chat_message("assistant", avatar="📜").write(log['evento_texto'])
        except Exception:
            log_container.info("Sin datos de eventos.")

        action = st.chat_input("¿Cuáles son sus órdenes, Comandante?")
        if action:
            with st.spinner("Procesando directiva..."):
                res = resolve_action(action, player['id'])
                if res.get("narrative"):
                    st.rerun()

    with tab2:
        st.header("Administración & Personaje")
        st.subheader("Ficha del Personaje")
        st.json(player.get('stats_json', {}))
        
        st.subheader("Monitor del Sistema (Logs)")
        if st.button("Refrescar Logs"):
            st.rerun()
        try:
            all_logs = supabase.table("logs").select("*").order("id", desc=True).limit(20).execute()
            if all_logs.data:
                for log in all_logs.data:
                    msg = log['evento_texto']
                    if "ERROR" in msg:
                        st.error(f"[{log['id']}] {msg}")
                    else:
                        st.text(f"[{log['id']}] {msg}")
        except Exception as e:
            st.error(f"No se pudo cargar el monitor: {e}")

# --- Authentication Screen ---
def authentication_screen():
    st.title("SuperX: Galactic Command")
    st.header("Acceso a la Terminal de Mando")

    login_tab, register_tab = st.tabs(["Iniciar Sesión", "Registrar Nuevo Comandante"])

    # Login Form
    with login_tab:
        with st.form("login_form"):
            commander_name = st.text_input("Nombre de Comandante")
            password = st.text_input("Palabra Clave", type="password")
            submitted = st.form_submit_button("Acceder")

            if submitted:
                try:
                    response = supabase.table("players").select("*").eq("nombre", commander_name).single().execute()
                    player_data = response.data
                    if player_data and verify_password(player_data['password'], password):
                        st.session_state.logged_in = True
                        st.session_state.player_info = player_data
                        st.rerun()
                    else:
                        st.error("Nombre de Comandante o Palabra Clave incorrectos.")
                except Exception as e:
                    st.error("Error al verificar credenciales. Es posible que el comandante no exista.")

    # Registration Form
    with register_tab:
        with st.form("register_form", clear_on_submit=True):
            new_commander_name = st.text_input("Asignar Nombre de Comandante")
            new_password = st.text_input("Definir Palabra Clave", type="password")
            faction_name = st.text_input("Nombre de la Facción")
            banner_file = st.file_uploader("Estandarte de la Facción (Opcional, PNG/JPG)", type=['png', 'jpg'])
            reg_submitted = st.form_submit_button("Registrar y Generar Perfil de Comandante")

            if reg_submitted:
                if not new_commander_name or not new_password or not faction_name:
                    st.warning("Nombre, Palabra Clave y Nombre de Facción son obligatorios.")
                else:
                    with st.spinner("Forjando un nuevo líder en las estrellas..."):
                        # Check if player already exists
                        try:
                            existing = supabase.table("players").select("id").eq("nombre", new_commander_name).execute()
                            if existing.data:
                                st.error("Ese nombre de Comandante ya está en uso.")
                                return
                        except Exception:
                            pass # Good, means user doesn't exist
                            
                        new_player = generate_random_character(
                            player_name=new_commander_name,
                            password=new_password,
                            faction_name=faction_name,
                            banner_file=banner_file
                        )
                        if new_player:
                            st.success(f"¡Comandante {new_commander_name} registrado! Ahora puedes iniciar sesión.")
                        else:
                            st.error("Error durante la creación del perfil. Inténtalo de nuevo.")

# --- Main App Logic ---
if st.session_state.logged_in:
    main_game_interface()
else:
    authentication_screen()
