import streamlit as st
from game_engine import (
    supabase,
    register_faction_and_commander,
    resolve_action,
    verify_password
)

st.set_page_config(page_title="SuperX Engine", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'player_data' not in st.session_state:
    st.session_state.player_data = None
if 'commander_data' not in st.session_state:
    st.session_state.commander_data = None

# --- Main Game UI ---
def main_game_interface():
    player = st.session_state.player_data
    commander = st.session_state.commander_data
    
    stats = commander.get('stats_json', {}) if commander else {}
    bio = stats.get('bio', {})

    # Header
    st.markdown(f"## Facción: {player['faccion_nombre']} | Líder: {bio.get('nombre', 'Desconocido')}")
    if player.get('banner_url'):
        st.image(player['banner_url'], width=150)

    st.sidebar.header("Terminal de Mando")
    st.sidebar.success(f"Usuario: {player['nombre']}")
    st.sidebar.info(f"Personaje: {bio.get('nombre', 'N/A')} ({bio.get('rol', 'N/A')})")
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.player_data = None
        st.session_state.commander_data = None
        st.rerun()
        
    st.sidebar.divider()

    tab1, tab2 = st.tabs(["Sala de Guerra", "Datos del Comandante"])

    with tab1:
        st.subheader("Bitácora de Misión")
        log_container = st.container(height=300)
        try:
            # Logs filtrados por el usuario actual o globales
            logs_resp = supabase.table("logs").select("*").order("id", desc=True).limit(10).execute()
            for log in reversed(logs_resp.data):
                if "ERROR" not in log['evento_texto']:
                    log_container.chat_message("assistant", avatar="📜").write(log['evento_texto'])
        except Exception:
            log_container.info("Sin datos.")

        action = st.chat_input(f"¿Órdenes, Comandante {bio.get('nombre', '')}?")
        if action:
            with st.spinner("Transmitiendo órdenes..."):
                res = resolve_action(action, player['id'])
                if res.get("narrative"):
                    st.rerun()

    with tab2:
        st.subheader("Hoja de Servicio")
        if commander:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### Atributos")
                st.json(stats.get('atributos', {}))
            with c2:
                st.markdown("### Habilidades")
                st.json(stats.get('habilidades', {}))
            
            st.markdown("### Biografía")
            st.write(stats.get('bio', {}))
        else:
            st.warning("No se encontraron datos del Comandante.")
        
        st.divider()
        st.subheader("Diagnóstico del Sistema")
        if st.button("Ver Logs de Sistema"):
            logs = supabase.table("logs").select("*").order("id", desc=True).limit(5).execute()
            st.table(logs.data)

# --- Auth Screen ---
def authentication_screen():
    st.title("SuperX: Galactic Command")
    
    with st.expander("🆘 Diagnóstico de Conexión"):
        if st.button("Probar Conexión DB"):
            try:
                logs = supabase.table("logs").select("id").limit(1).execute()
                st.success("Conexión a Supabase: OK")
            except Exception as e:
                st.error(f"Error: {e}")

    login_tab, register_tab = st.tabs(["Acceso Identificado", "Nueva Facción"])

    with login_tab:
        with st.form("login_form"):
            user_name = st.text_input("Usuario")
            pin = st.text_input("PIN (4 dígitos)", type="password", max_chars=4)
            if st.form_submit_button("Iniciar Enlace"):
                try:
                    # 1. Buscar Jugador
                    res = supabase.table("players").select("*").eq("nombre", user_name).single().execute()
                    p_data = res.data
                    
                    if p_data and verify_password(p_data['pin'], pin):
                        # 2. Buscar Comandante asociado
                        c_res = supabase.table("characters").select("*").eq("player_id", p_data['id']).eq("es_comandante", True).single().execute()
                        
                        st.session_state.logged_in = True
                        st.session_state.player_data = p_data
                        st.session_state.commander_data = c_res.data # Puede ser None si hubo un error en creación
                        st.rerun()
                    else:
                        st.error("Credenciales inválidas.")
                except Exception as e:
                    st.error(f"Error de acceso: {e}")

    with register_tab:
        st.markdown("### Establecer Nueva Facción")
        with st.form("reg_form"):
            new_user = st.text_input("Nombre de Usuario (Tú)")
            new_pin = st.text_input("PIN de Seguridad", type="password", max_chars=4)
            faction = st.text_input("Nombre de la Facción")
            banner = st.file_uploader("Estandarte", type=['png', 'jpg'])
            
            if st.form_submit_button("Crear Facción y Comandante"):
                if not new_user or len(new_pin) != 4 or not faction:
                    st.warning("Completa todos los campos. El PIN debe ser de 4 dígitos.")
                else:
                    with st.spinner("Inicializando protocolos de facción..."):
                        # Verificar duplicados
                        try:
                            check = supabase.table("players").select("id").eq("nombre", new_user).execute()
                            if check.data:
                                st.error("Este usuario ya existe.")
                                st.stop()
                        except: pass
                        
                        # Crear todo
                        result = register_faction_and_commander(new_user, new_pin, faction, banner)
                        
                        if result:
                            st.success("¡Facción establecida! Accede desde la pestaña de 'Acceso Identificado'.")
                        else:
                            st.error("Error al crear la facción. Revisa los logs de diagnóstico.")

if st.session_state.logged_in:
    main_game_interface()
else:
    authentication_screen()