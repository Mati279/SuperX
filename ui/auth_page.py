# ui/auth_page.py
import streamlit as st
import time
from .state import login_user, start_registration
from data.player_repository import authenticate_player, create_session_token
from data.character_repository import get_commander_by_player_id
from config.app_constants import (
    PIN_LENGTH,
    SESSION_COOKIE_NAME,
    LOGIN_SUCCESS_DELAY_SECONDS
)

def render_auth_page(cookie_manager): # <--- Recibe el cookie_manager
    st.title("SuperX: Galactic Command")
    
    tab_login, tab_reg = st.tabs(["Acceso Identificado", "Nuevo Registro"])
    
    with tab_login:
        st.subheader("Terminal de Acceso")
        with st.form("login_form"):
            user_name = st.text_input("Usuario")
            pin = st.text_input("PIN", type="password", max_chars=PIN_LENGTH)
            
            if st.form_submit_button("Entrar"):
                if not user_name or not pin:
                    st.error("El usuario y el PIN son obligatorios.")
                else:
                    try:
                        player = authenticate_player(user_name, pin)
                        
                        if player:
                            commander = get_commander_by_player_id(player['id'])
                            if commander:
                                # 1. Generar token seguro en DB
                                token = create_session_token(player['id'])

                                # 2. Guardar en Cookie (Expira en 30 días)
                                cookie_manager.set(SESSION_COOKIE_NAME, token, expires_at=None, key="set_auth_cookie")

                                # 3. Login en Estado
                                login_user(player, commander)
                                st.success("Acceso concedido. Iniciando sistemas...")
                                time.sleep(LOGIN_SUCCESS_DELAY_SECONDS)  # Pequeña pausa para asegurar que la cookie se escriba
                                st.rerun()
                            else:
                                st.error("Usuario sin Comandante asignado.")
                        else:
                            st.error("Credenciales inválidas.")
                            
                    except Exception as e:
                        st.error(f"Error del sistema: {e}")

    with tab_reg:
        # ... (Igual que antes) ...
        st.subheader("Protocolo de Reclutamiento")
        st.info("Crea una nueva Facción y diseña tu primer Comandante.")
        if st.button("Comenzar Reclutamiento"):
            start_registration()