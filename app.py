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
    st.session_state.is_registering = False 
if 'registration_step' not in st.session_state:
    st.session_state.registration_step = 0 
if 'temp_player' not in st.session_state:
    st.session_state.temp_player = None 
if 'temp_char_bio' not in st.session_state:
    st.session_state.temp_char_bio = {} 

# --- Helpers de Lógica de Atributos ---
def calculate_single_attr_cost(start_val, target_val):
    """Calcula el costo en puntos para subir de start_val a target_val."""
    cost = 0
    # Iteramos punto por punto para aplicar la regla de "sobre 15 cuesta doble"
    for v in range(start_val + 1, target_val + 1):
        if v > 15:
            cost += 2 # Cuesta doble pasar de 15
        else:
            cost += 1
    return cost

# --- MAIN GAME UI ---
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
        st.session_state.is_registering = False
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
    if st.button("⬅ Cancelar y Volver"):
        st.session_state.is_registering = False
        st.session_state.registration_step = 0
        st.rerun()

    st.title("Estación de Reclutamiento")
    progress_text = ["Datos de Facción", "Expediente Personal", "Matriz de Atributos"]
    st.progress((st.session_state.registration_step + 1) / 3, text=f"Fase {st.session_state.registration_step + 1}: {progress_text[st.session_state.registration_step]}")
    
    # PASO 1: CUENTA DE JUGADOR (Auth) - Este sí usa Form porque no necesita interactividad inmediata
    if st.session_state.registration_step == 0:
        st.header("Paso 1: Registro de Facción")
        st.caption("Establece las credenciales de acceso seguro.")
        
        with st.form("step1_form"):
            new_user = st.text_input("Nombre de Comandante (Usuario)*")
            new_pin = st.text_input("PIN de Seguridad (4 Números)*", type="password", max_chars=4)
            faction = st.text_input("Nombre de la Facción*")
            banner = st.file_uploader("Estandarte de la Facción (Opcional)", type=['png', 'jpg'])
            
            submit = st.form_submit_button("Continuar")
            
            if submit:
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
                                st.session_state.registration_step = 1
                                st.rerun()
                            else:
                                st.error("Error del sistema al crear la cuenta.")
                    except Exception as e:
                        st.error(f"Error de conexión: {e}")

    # PASO 2: DATOS BIOGRÁFICOS - SIN FORM para que sea interactivo
    elif st.session_state.registration_step == 1:
        st.header("Paso 2: Expediente del Comandante")
        
        # Nombre fijo
        st.text_input("Identidad", value=st.session_state.temp_player['nombre'], disabled=True)
        
        c1, c2 = st.columns(2)
        with c1:
            # Dropdowns fuera de formulario para reactividad
            raza_opts = list(RACES.keys())
            raza = st.selectbox("Seleccionar Raza", raza_opts)
            # Info box que se actualiza al instante
            st.info(f"🧬 **{raza}**: {RACES[raza]['desc']}\n\n✨ Bono: {RACES[raza]['bonus']}")
            
            edad = st.number_input("Edad", min_value=18, max_value=120, value=25)

        with c2:
            clase_opts = list(CLASSES.keys())
            clase = st.selectbox("Seleccionar Clase", clase_opts)
            # Info box reactiva
            st.info(f"🛡️ **{clase}**: {CLASSES[clase]['desc']}\n\n⭐ Atributo Principal: {CLASSES[clase]['bonus_attr'].capitalize()}")

            sexo = st.selectbox("Sexo Biológico", ["Hombre", "Mujer"])
        
        bio_text = st.text_area("Biografía / Antecedentes", placeholder="Historia breve...")

        st.markdown("---")
        if st.button("Confirmar Datos y Pasar a Atributos", type="primary"):
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

    # PASO 3: ATRIBUTOS (Sistema de Puntos)
    elif st.session_state.registration_step == 2:
        st.header("Paso 3: Matriz de Atributos")
        st.markdown("""
        **Sistema de Asignación:**
        - Todos los atributos comienzan en **10** (más bonos de Raza/Clase).
        - Tienes **15 Puntos** disponibles para distribuir.
        - Subir un atributo por encima de **15** cuesta el **doble de puntos**.
        """)
        
        # Recuperar bonos
        bio = st.session_state.temp_char_bio
        raza_bonus = RACES[bio['raza']]['bonus']
        clase_bonus_attr = CLASSES[bio['clase']]['bonus_attr']
        
        # Definir atributos base (10 + Bonos)
        base_stats = {
            "fuerza": 10, "agilidad": 10, "intelecto": 10,
            "tecnica": 10, "presencia": 10, "voluntad": 10
        }
        
        # Aplicar bonos a la base
        for attr, val in raza_bonus.items():
            base_stats[attr] += val
        base_stats[clase_bonus_attr] += 1
        
        # UI de Inputs (Sin Form para calcular puntos en vivo)
        col1, col2, col3 = st.columns(3)
        input_cols = [col1, col2, col3, col1, col2, col3]
        attr_keys = ["fuerza", "agilidad", "intelecto", "tecnica", "presencia", "voluntad"]
        
        final_attrs = {}
        total_spent = 0
        
        for i, attr in enumerate(attr_keys):
            base = base_stats[attr]
            with input_cols[i]:
                # El valor mínimo es el base (no se puede bajar de lo que te da tu raza)
                val = st.number_input(
                    f"{attr.capitalize()} (Base: {base})", 
                    min_value=base, 
                    max_value=20, 
                    value=base,
                    key=f"attr_{attr}"
                )
                cost = calculate_single_attr_cost(base, val)
                total_spent += cost
                final_attrs[attr] = val
                
                # Feedback visual del costo
                if cost > 0:
                    st.caption(f"Gastado: {cost} pts")

        # Resumen de Puntos
        POINTS_AVAILABLE = 15
        remaining = POINTS_AVAILABLE - total_spent
        
        st.markdown("---")
        c_res1, c_res2 = st.columns([3, 1])
        
        with c_res1:
            if remaining >= 0:
                st.success(f"💎 Puntos Restantes: **{remaining}** / {POINTS_AVAILABLE}")
            else:
                st.error(f"⛔ Has gastado demasiados puntos: **{remaining}**")
        
        with c_res2:
            # Botón deshabilitado si te pasas de puntos
            disabled_btn = remaining < 0
            if st.button("Finalizar Creación", type="primary", disabled=disabled_btn):
                success = create_commander_manual(
                    st.session_state.temp_player['id'],
                    st.session_state.temp_player['nombre'],
                    st.session_state.temp_char_bio,
                    final_attrs
                )
                
                if success:
                    st.balloons()
                    # Auto-login
                    st.session_state.player_data = st.session_state.temp_player
                    c_res = supabase.table("characters").select("*").eq("player_id", st.session_state.temp_player['id']).single().execute()
                    st.session_state.commander_data = c_res.data
                    st.session_state.logged_in = True
                    st.session_state.is_registering = False
                    st.session_state.registration_step = 0
                    st.rerun()
                else:
                    st.error("Error al guardar.")

# --- AUTH SCREEN ---
def authentication_screen():
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
                    st.error("Error de acceso.")

    with tab_reg:
        st.info("Crea una nueva Facción y diseña tu primer Comandante.")
        if st.button("Comenzar Protocolo de Reclutamiento"):
            st.session_state.is_registering = True
            st.session_state.registration_step = 0
            st.rerun()

# --- Main App Logic ---
if st.session_state.logged_in:
    main_game_interface()
else:
    authentication_screen()