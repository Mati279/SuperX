# ui/auth_page.py
import streamlit as st
from .state import login_user, start_registration
from data.player_repository import authenticate_player
from data.character_repository import get_commander_by_player_id

def render_auth_page():
    """
    Renderiza la página de autenticación, que incluye el formulario de login
    y el botón para iniciar el proceso de registro.
    """
    st.title("SuperX: Galactic Command")
    
    tab_login, tab_reg = st.tabs(["Acceso Identificado", "Nuevo Registro"])
    
    # --- Pestaña de Login ---
    with tab_login:
        st.subheader("Terminal de Acceso")
        with st.form("login_form"):
            user_name = st.text_input("Usuario")
            pin = st.text_input("PIN", type="password", max_chars=4)
            
            if st.form_submit_button("Entrar"):
                if not user_name or not pin:
                    st.error("El usuario y el PIN son obligatorios.")
                else:
                    try:
                        # La lógica de autenticación está ahora en el repositorio
                        player = authenticate_player(user_name, pin)
                        
                        if player:
                            # Si el jugador existe, buscamos su comandante
                            commander = get_commander_by_player_id(player['id'])
                            if commander:
                                # La lógica de login está en el state manager
                                login_user(player, commander)
                                st.rerun()
                            else:
                                # Caso borde: el jugador existe pero no tiene comandante
                                st.error("Autenticación correcta, pero no se encontró un Comandante asignado.")
                        else:
                            st.error("Credenciales inválidas. Verifique su usuario y PIN.")
                            
                    except Exception as e:
                        st.error(f"Error del sistema: {e}")

    # --- Pestaña de Registro ---
    with tab_reg:
        st.subheader("Protocolo de Reclutamiento")
        st.info("Crea una nueva Facción y diseña tu primer Comandante para unirte al conflicto galáctico.")
        if st.button("Comenzar Reclutamiento"):
            # Llama a la función del state manager para cambiar de estado
            start_registration()
