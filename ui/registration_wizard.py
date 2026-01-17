# ui/registration_wizard.py
import streamlit as st
from .state import cancel_registration, next_registration_step, login_user
from data.player_repository import register_player_account
from data.character_repository import update_commander_profile, get_commander_by_player_id
from core.constants import RACES, CLASSES, POINTS_AVAILABLE_FOR_ATTRIBUTES
from core.rules import calculate_attribute_cost


def render_registration_wizard():
    """
    Renderiza el wizard de creación de personaje de múltiples pasos.
    """
    if st.button("⬅ Cancelar y Volver"):
        cancel_registration()

    st.title("Estación de Reclutamiento")
    progress_text = ["Datos de Facción", "Expediente Personal", "Matriz de Atributos"]
    step = st.session_state.registration_step
    st.progress((step + 1) / 3, text=f"Fase {step + 1}: {progress_text[step]}")

    if step == 0:
        _render_step_1_account()
    elif step == 1:
        _render_step_2_bio()
    elif step == 2:
        _render_step_3_attributes()

def _render_step_1_account():
    st.header("Paso 1: Registro de Facción")
    st.caption("Establece las credenciales de acceso seguro para tu facción.")
    
    with st.form("step1_form"):
        new_user = st.text_input("Nombre de Comandante (Usuario)*")
        new_pin = st.text_input("PIN de Seguridad (4 Números)*", type="password", max_chars=4)
        faction = st.text_input("Nombre de la Facción*")
        banner = st.file_uploader("Estandarte de la Facción (PNG, JPG)", type=['png', 'jpg'])
        
        if st.form_submit_button("Continuar"):
            errors = []
            if not new_user.strip(): errors.append("- El nombre de usuario es obligatorio.")
            if not faction.strip(): errors.append("- El nombre de la facción es obligatorio.")
            if not new_pin.isdigit() or len(new_pin) != 4: errors.append("- El PIN debe contener exactamente 4 números.")
            
            if errors:
                for err in errors: st.error(err)
            else:
                try:
                    with st.spinner("Registrando facción..."):
                        player = register_player_account(new_user, new_pin, faction, banner)
                    if player:
                        st.session_state.temp_player = player
                        next_registration_step()
                except Exception as e:
                    st.error(f"⚠️ {e}")

def _render_step_2_bio():
    st.header("Paso 2: Expediente del Comandante")
    st.text_input("Identidad", value=st.session_state.temp_player['nombre'], disabled=True)
    
    c1, c2 = st.columns(2)
    with c1:
        raza = st.selectbox("Seleccionar Raza", list(RACES.keys()))
        st.info(f"🧬 **{raza}**: {RACES[raza]['desc']}\n\n✨ Bono: {RACES[raza]['bonus']}")
        edad = st.number_input("Edad", min_value=18, max_value=120, value=25)
    with c2:
        clase = st.selectbox("Seleccionar Clase", list(CLASSES.keys()))
        st.info(f"🛡️ **{clase}**: {CLASSES[clase]['desc']}\n\n⭐ Atributo Principal: {CLASSES[clase]['bonus_attr'].capitalize()}")
        sexo = st.selectbox("Sexo Biológico", ["Hombre", "Mujer"])
    
    bio_text = st.text_area("Biografía / Antecedentes", placeholder="Una breve historia de tu comandante...")

    if st.button("Confirmar Datos y Pasar a Atributos", type="primary"):
        st.session_state.temp_char_bio = {
            "nombre": st.session_state.temp_player['nombre'], "raza": raza, "clase": clase,
            "edad": edad, "sexo": sexo, "rol": "Comandante", "historia": bio_text
        }
        next_registration_step()

def _render_step_3_attributes():
    st.header("Paso 3: Matriz de Atributos")
    st.markdown(f"""
    - Todos los atributos comienzan en **5** (más bonos de raza y clase).
    - Tienes **{POINTS_AVAILABLE_FOR_ATTRIBUTES} Puntos** (Nivel 6) para distribuir.
    - Subir un atributo por encima de **15** cuesta el doble (2:1).
    """)
    
    bio = st.session_state.temp_char_bio
    raza_bonus = RACES[bio['raza']]['bonus']
    clase_bonus_attr = CLASSES[bio['clase']]['bonus_attr']
    
    # Ajustado a Base 5 según Módulo 19.2
    base_stats = { "fuerza": 5, "agilidad": 5, "intelecto": 5, "tecnica": 5, "presencia": 5, "voluntad": 5 }
    for attr, val in raza_bonus.items():
        base_stats[attr] += val
    base_stats[clase_bonus_attr] += 1
    
    cols = st.columns(3)
    final_attrs, total_spent = {}, 0
    attr_keys = list(base_stats.keys())

    for i, attr in enumerate(attr_keys):
        base = base_stats[attr]
        with cols[i % 3]:
            val = st.number_input(f"{attr.capitalize()} (Base: {base})", min_value=base, max_value=20, value=base, key=f"attr_{attr}")
            cost = calculate_attribute_cost(base, val)
            total_spent += cost
            final_attrs[attr] = val
            if cost > 0: st.caption(f"Costo: {cost} pts")

    remaining = POINTS_AVAILABLE_FOR_ATTRIBUTES - total_spent
    st.divider()
    c_res1, c_res2 = st.columns([3, 1])
    with c_res1:
        if remaining >= 0: st.success(f"💎 Puntos Restantes: **{remaining}**")
        else: st.error(f"⛔ Has gastado demasiados puntos: **{remaining}**")
    
    with c_res2:
        if st.button("Finalizar Creación y Desplegar", type="primary", disabled=(remaining < 0)):
            try:
                with st.spinner("Estableciendo base de operaciones y protocolos iniciales..."):
                    commander = update_commander_profile(
                        st.session_state.temp_player['id'],
                        st.session_state.temp_char_bio,
                        final_attrs
                    )

                if commander:
                    st.balloons()
                    login_user(st.session_state.temp_player, commander)
                else:
                    commander = get_commander_by_player_id(st.session_state.temp_player['id'])
                    if commander:
                        st.balloons()
                        login_user(st.session_state.temp_player, commander)
                    else:
                        st.error("No se encontró el comandante. Contacta soporte.")
            except Exception as e:
                st.error(f"Error al guardar: {e}")