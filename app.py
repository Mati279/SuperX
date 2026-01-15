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
    
    # --- LOG VIEWER BUTTON (SIEMPRE VISIBLE) ---
    with st.expander("🆘 Ver Logs de Error (Diagnóstico)"):
        st.info("Usa esto si tienes problemas al registrarte o iniciar sesión.")
        if st.button("Consultar Errores Recientes"):
            try:
                # Trae los ultimos 5 errores
                errors = supabase.table("logs").select("*").ilike("evento_texto", "%ERROR%").order("id", desc=True).limit(5).execute()
                if errors.data:
                    for err in errors.data:
                        st.error(f"ID {err['id']}: {err['evento_texto']}")
                else:
                    st.success("No se encontraron errores recientes en la base de datos.")
            except Exception as e:
                st.warning(f"No se pudo conectar a los logs: {e}")

    st.header("Acceso a la Terminal de Mando")

    login_tab, register_tab = st.tabs(["Iniciar Sesión", "Registrar Nuevo Comandante"])

    # Login Form
    with login_tab:
        with st.form("login_form"):
            commander_name = st.text_input("Nombre de Comandante")
            # CAMBIO: PIN de 4 dígitos
            password = st.text_input("PIN de Acceso a Terminal", type="password", help="Tu código numérico de 4 dígitos", max_chars=4)
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
                        st.error("Credenciales incorrectas.")
                except Exception as e:
                    st.error("Error al verificar credenciales. Es posible que el comandante no exista.")

    # Registration Form
    with register_tab:
        with st.form("register_form", clear_on_submit=True):
            st.markdown("### Nuevo Registro")
            new_commander_name = st.text_input("Asignar Nombre de Comandante")
            
            # CAMBIO: PIN de 4 dígitos
            new_password = st.text_input("Definir PIN de Acceso (4 Dígitos)", type="password", max_chars=4, help="Usa 4 números, ej: 1234")
            
            faction_name = st.text_input("Nombre de la Facción")
            banner_file = st.file_uploader("Estandarte de la Facción (Opcional, PNG/JPG)", type=['png', 'jpg'])
            reg_submitted = st.form_submit_button("Registrar y Generar Perfil")

            if reg_submitted:
                # Validaciones
                if not new_commander_name or not new_password or not faction_name:
                    st.warning("Todos los campos de texto son obligatorios.")
                elif not new_password.isdigit() or len(new_password) != 4:
                    st.error("El PIN debe ser exactamente 4 números.")
                else:
                    with st.spinner("Forjando un nuevo líder en las estrellas..."):
                        # Check if player already exists
                        try:
                            existing = supabase.table("players").select("id").eq("nombre", new_commander_name).execute()
                            if existing.data:
                                st.error("Ese nombre de Comandante ya está en uso.")
                                st.stop()
                        except Exception:
                            pass 
                            
                        new_player = generate_random_character(
                            player_name=new_commander_name,
                            password=new_password,
                            faction_name=faction_name,
                            banner_file=banner_file
                        )
                        if new_player:
                            st.success(f"¡Comandante {new_commander_name} registrado! Ahora puedes iniciar sesión con tu PIN.")
                        else:
                            st.error("Error crítico durante la creación. Abre 'Ver Logs de Error' arriba para ver el detalle.")

# --- Main App Logic ---
if st.session_state.logged_in:
    main_game_interface()
else:
    authentication_screen()