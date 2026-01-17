# ui/auth_page.py
import streamlit as st
import time
from .state import login_user, start_registration
from data.player_repository import authenticate_player
from config.app_constants import LOGIN_SUCCESS_DELAY_SECONDS

def render_auth_page(cookie_manager):
    st.markdown("<h1 style='text-align: center; color: #56d59f;'>SuperX: Enlace Galáctico</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            st.subheader("Identificación")
            username = st.text_input("Comandante", placeholder="Nombre de usuario")
            pin = st.text_input("PIN de Seguridad", type="password", placeholder="****")
            
            col_login, col_reg = st.columns(2)
            
            with col_login:
                if st.button("Conectar", type="primary", use_container_width=True):
                    if username and pin:
                        player = authenticate_player(username, pin)
                        if player:
                            st.success(f"Bienvenido, Comandante {player['nombre']}.")
                            time.sleep(LOGIN_SUCCESS_DELAY_SECONDS)
                            login_user(player, cookie_manager)
                            st.rerun()
                        else:
                            st.error("Credenciales inválidas.")
                    else:
                        st.warning("Ingrese usuario y PIN.")
            
            with col_reg:
                if st.button("Reclutar", type="secondary", use_container_width=True):
                    start_registration() # Ahora sí existe en state.py