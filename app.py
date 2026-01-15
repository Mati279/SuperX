import streamlit as st
from game_engine import (
    supabase,
    register_player_account,
    create_commander_manual,
    resolve_action,
    verify_password,
    RACES,
    CLASSES
)

st.set_page_config(page_title="SuperX Engine", layout="wide")

# --- Session State Management ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'player_data' not in st.session_state:
    st.session_state.player_data = None
if 'commander_data' not in st.session_state:
    st.session_state.commander_data = None

# Variables para el flujo de registro
if 'is_registering' not in st.session_state:
    st.session_state.is_registering = False  # NUEVO: Control maestro del modo registro
if 'registration_step' not in st.session_state:
    st.session_state.registration_step = 0 # 0: Auth, 1: Bio, 2: Atributos
if 'temp_player' not in st.session_state:
    st.session_state.temp_player = None 
if 'temp_char_bio' not in st.session_state:
    st.session_state.temp_char_bio = {} 

# --- MAIN GAME UI (Solo si ya está logueado y con personaje) ---
def main_game_interface():
    player = st.session_state.player_data
    commander = st.session_state.commander_data
    
    stats = commander.get('stats_json', {}) if commander else {}
    bio = stats.get('bio', {})

    st.markdown(f"## Facción: {player['faccion_nombre']} | Líder: {bio.get('nombre', 'Desconocido')}")
    if player.get('banner_url'):
        st.image(player['banner_url'], width=150)

    st.sidebar.header("Terminal de Mando")
    st.sidebar.success(f"Comandante: {bio.get('nombre', 'N/A')}")
    st.sidebar.info(f"Clase: {bio.get('clase', 'N/A')} | Raza: {bio.get('raza', 'N/A')}")
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.player_data = None
        st.session_state.commander_data = None
        st.session_state.is_registering = False # Resetear registro
        st.rerun()
        
    st.sidebar.divider()

    tab1, tab2 = st.tabs(["Sala de Guerra", "Datos del Comandante"])

    with tab1:
        st.subheader("Bitácora de Misión")
        log_container = st.container(height=300)
        try:
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
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Atributos")
            st.json(stats.get('atributos', {}))
        with c2:
            st.markdown("### Habilidades")
            st.json(stats.get('habilidades', {}))
        
        st.markdown("### Biografía")
        st.write(bio)

# --- WIZARD DE REGISTRO ---

def registration_wizard():
    # Botón para cancelar y volver atrás
    if st.button("⬅ Volver al Inicio"):
        st.session_state.is_registering = False
        st.session_state.registration_step = 0
        st.rerun()

    st.title("Estación de Reclutamiento")
    progress_text = ["Datos de Facción", "Expediente Personal", "Evaluación de Combate"]
    st.progress((st.session_state.registration_step + 1) / 3, text=f"Fase {st.session_state.registration_step + 1}: {progress_text[st.session_state.registration_step]}")
    
    # PASO 1: CUENTA DE JUGADOR (Auth)
    if st.session_state.registration_step == 0:
        st.header("Paso 1: Registro de Facción")
        st.caption("Establece las credenciales de acceso seguro.")
        
        with st.form("step1_form"):
            new_user = st.text_input("Nombre de Comandante (Usuario)*")
            new_pin = st.text_input("PIN de Seguridad (4 Números)*", type="password", max_chars=4)
            faction = st.text_input("Nombre de la Facción*")
            banner = st.file_uploader("Estandarte de la Facción (Opcional)", type=['png', 'jpg'])
            
            submit = st.form_submit_button("Establecer Facción y Continuar")
            
            if submit:
                # Validaciones estrictas
                errors = []
                if not new_user.strip(): errors.append("- El nombre de usuario es obligatorio.")
                if not faction.strip(): errors.append("- El nombre de la facción es obligatorio.")
                if not new_pin.isdigit() or len(new_pin) != 4: errors.append("- El PIN debe contener exactamente 4 números.")
                
                if errors:
                    for err in errors: st.error(err)
                else:
                    try:
                        check = supabase.table("players").select("id").eq("nombre", new_user).execute()
                        if check.data:
                            st.error("⚠️ Ese nombre de Comandante ya está en uso.")
                        else:
                            player = register_player_account(new_user, new_pin, faction, banner)
                            if player:
                                st.session_state.temp_player = player
                                st.session_state.registration_step = 1 # Avanzar al siguiente paso
                                st.rerun()
                            else:
                                st.error("Error del sistema al crear la cuenta. Intente nuevamente.")
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")

    # PASO 2: DATOS BIOGRÁFICOS
    elif st.session_state.registration_step == 1:
        st.header("Paso 2: Expediente del Comandante")
        st.info(f"Identidad confirmada: **{st.session_state.temp_player['nombre']}**")
        
        with st.form("step2_form"):
            st.text_input("Identidad (Nombre)", value=st.session_state.temp_player['nombre'], disabled=True)
            
            c1, c2 = st.columns(2)
            with c1:
                raza_opts = list(RACES.keys())
                raza = st.selectbox("Raza", raza_opts)
                st.info(f"🧬 **{raza}**: {RACES[raza]['desc']}\n\n✨ Bono: {RACES[raza]['bonus']}")
                
                edad = st.number_input("Edad", min_value=18, max_value=120, value=25)

            with c2:
                clase_opts = list(CLASSES.keys())
                clase = st.selectbox("Clase / Especialidad", clase_opts)
                st.info(f"🛡️ **{clase}**: {CLASSES[clase]['desc']}\n\n⭐ Atributo Principal: {CLASSES[clase]['bonus_attr'].capitalize()}")

                sexo = st.selectbox("Sexo", ["Hombre", "Mujer"])
            
            bio_text = st.text_area("Biografía / Antecedentes (Opcional)", placeholder="Escribe brevemente tu historia...")

            if st.form_submit_button("Confirmar Datos y Asignar Atributos"):
                st.session_state.temp_char_bio = {
                    "nombre": st.session_state.temp_player['nombre'],
                    "raza": raza,
                    "clase": clase,
                    "edad": edad,
                    "sexo": sexo,
                    "rol": "Comandante",
                    "historia": bio_text
                }
                st.session_state.registration_step = 2
                st.rerun()

    # PASO 3: ATRIBUTOS
    elif st.session_state.registration_step == 2:
        st.header("Paso 3: Evaluación de Capacidades")
        st.markdown("Asigna los niveles de atributos (Escala 1-20).")
        
        bio = st.session_state.temp_char_bio
        raza_bonus = RACES[bio['raza']]['bonus']
        clase_bonus_attr = CLASSES[bio['clase']]['bonus_attr']
        
        st.success(f"Bonificaciones Activas: {raza_bonus} | +1 a {clase_bonus_attr.capitalize()} (Clase)")

        with st.form("step3_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                fuerza = st.number_input("Fuerza", 1, 20, 10, help="Capacidad física y combate cuerpo a cuerpo.")
                tecnica = st.number_input("Técnica", 1, 20, 10, help="Habilidad manual, uso de herramientas y armas.")
            with c2:
                agilidad = st.number_input("Agilidad", 1, 20, 10, help="Reflejos, velocidad y sigilo.")
                presencia = st.number_input("Presencia", 1, 20, 10, help="Carisma, liderazgo y persuasión.")
            with c3:
                intelecto = st.number_input("Intelecto", 1, 20, 10, help="Capacidad lógica, memoria y hacking.")
                voluntad = st.number_input("Voluntad", 1, 20, 10, help="Resistencia mental y determinación.")
            
            submitted = st.form_submit_button("Finalizar Reclutamiento")
            
            if submitted:
                raw_attrs = {
                    "fuerza": fuerza, "agilidad": agilidad, "intelecto": intelecto,
                    "tecnica": tecnica, "presencia": presencia, "voluntad": voluntad
                }
                
                # Sumar bonos automáticamente
                for attr, val in raza_bonus.items():
                    if attr in raw_attrs: raw_attrs[attr] += val
                
                if clase_bonus_attr in raw_attrs:
                    raw_attrs[clase_bonus_attr] += 1
                
                success = create_commander_manual(
                    st.session_state.temp_player['id'],
                    st.session_state.temp_player['nombre'],
                    st.session_state.temp_char_bio,
                    raw_attrs
                )
                
                if success:
                    st.balloons()
                    st.success("¡Comandante Registrado Exitosamente!")
                    # Auto-login
                    st.session_state.player_data = st.session_state.temp_player
                    c_res = supabase.table("characters").select("*").eq("player_id", st.session_state.temp_player['id']).single().execute()
                    st.session_state.commander_data = c_res.data
                    st.session_state.logged_in = True
                    # Resetear variables de registro
                    st.session_state.is_registering = False
                    st.session_state.registration_step = 0
                    st.session_state.temp_player = None
                    st.rerun()
                else:
                    st.error("Error crítico al guardar el personaje. Por favor contacta al soporte.")


# --- AUTH SCREEN (LOGIN O REGISTRO) ---
def authentication_screen():
    # AHORA: Si la bandera 'is_registering' es True, mostramos el wizard, SIN IMPORTAR el paso.
    if st.session_state.is_registering:
        registration_wizard()
        return

    st.title("SuperX: Galactic Command")
    
    tab_login, tab_reg = st.tabs(["Acceso Identificado", "Nuevo Registro"])
    
    with tab_login:
        with st.form("login_form"):
            user_name = st.text_input("Usuario")
            pin = st.text_input("PIN", type="password", max_chars=4)
            if st.form_submit_button("Entrar"):
                try:
                    res = supabase.table("players").select("*").eq("nombre", user_name).single().execute()
                    if res.data and verify_password(res.data['pin'], pin):
                        c_res = supabase.table("characters").select("*").eq("player_id", res.data['id']).eq("es_comandante", True).single().execute()
                        st.session_state.player_data = res.data
                        st.session_state.commander_data = c_res.data
                        st.session_state.logged_in = True
                        st.rerun()
                    else:
                        st.error("Credenciales inválidas.")
                except Exception as e:
                    st.error("Error de acceso o usuario no encontrado.")

    with tab_reg:
        st.info("Crea una nueva Facción y diseña tu primer Comandante.")
        # Este botón ahora activa la bandera MAESTRA 'is_registering'
        if st.button("Comenzar Protocolo de Reclutamiento"):
            st.session_state.is_registering = True
            st.session_state.registration_step = 0 # Asegura inicio en paso 0
            st.rerun()

# --- Main App Logic ---
if st.session_state.logged_in:
    main_game_interface()
else:
    authentication_screen()