# ui/state.py
import streamlit as st
from typing import Dict, Any
# Importamos funciones del repositorio para limpiar DB
from data.player_repository import clear_session_token

def initialize_session_state() -> None:
    # ... (Igual que antes) ...
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'player_data' not in st.session_state:
        st.session_state.player_data = None
    if 'commander_data' not in st.session_state:
        st.session_state.commander_data = None
    if 'is_registering' not in st.session_state:
        st.session_state.is_registering = False 
    if 'registration_step' not in st.session_state:
        st.session_state.registration_step = 0
    if 'temp_player' not in st.session_state:
        st.session_state.temp_player = None 
    if 'temp_char_bio' not in st.session_state:
        st.session_state.temp_char_bio = {} 

def login_user(player_data: Dict[str, Any], commander_data: Dict[str, Any]) -> None:
    """Loguea al usuario en el estado de sesión."""
    st.session_state.logged_in = True
    st.session_state.player_data = player_data
    st.session_state.commander_data = commander_data
    st.session_state.is_registering = False
    st.session_state.registration_step = 0

def logout_user(cookie_manager=None) -> None:
    """Cierra sesión, limpia cookies y DB."""
    # 1. Limpiar Token en DB
    if st.session_state.player_data:
        clear_session_token(st.session_state.player_data['id'])
    
    # 2. Limpiar Cookie (Si se pasó el manager)
    if cookie_manager:
        try:
            cookie_manager.delete('superx_session_token')
        except:
            pass # A veces falla si ya no existe, no importa

    # 3. Limpiar Estado
    st.session_state.logged_in = False
    st.session_state.player_data = None
    st.session_state.commander_data = None
    st.session_state.is_registering = False
    st.session_state.registration_step = 0
    st.session_state.temp_player = None
    st.session_state.temp_char_bio = {}
    st.rerun()

# ... (start_registration, cancel_registration, next_registration_step siguen igual) ...
def start_registration() -> None:
    st.session_state.is_registering = True
    st.session_state.registration_step = 0
    st.rerun()

def cancel_registration() -> None:
    st.session_state.is_registering = False
    st.session_state.registration_step = 0
    st.rerun()

def next_registration_step() -> None:
    st.session_state.registration_step += 1
    st.rerun()