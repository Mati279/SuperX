# ui/state.py
import streamlit as st
from typing import Dict, Any, Optional

def initialize_session_state() -> None:
    """
    Inicializa todas las claves requeridas en el st.session_state si no existen.
    Esto previene errores de 'KeyError' y centraliza la gestión del estado.
    """
    # Estado de autenticación
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'player_data' not in st.session_state:
        st.session_state.player_data = None
    if 'commander_data' not in st.session_state:
        st.session_state.commander_data = None

    # Estado del flujo de registro
    if 'is_registering' not in st.session_state:
        st.session_state.is_registering = False 
    if 'registration_step' not in st.session_state:
        st.session_state.registration_step = 0
        
    # Datos temporales para el wizard de registro
    if 'temp_player' not in st.session_state:
        st.session_state.temp_player = None 
    if 'temp_char_bio' not in st.session_state:
        st.session_state.temp_char_bio = {} 

def login_user(player_data: Dict[str, Any], commander_data: Dict[str, Any]) -> None:
    """Actualiza el estado de la sesión para loguear a un usuario."""
    st.session_state.logged_in = True
    st.session_state.player_data = player_data
    st.session_state.commander_data = commander_data
    # Limpiar cualquier estado de registro residual
    st.session_state.is_registering = False
    st.session_state.registration_step = 0

def logout_user() -> None:
    """Limpia completamente el estado de la sesión para desloguear al usuario."""
    st.session_state.logged_in = False
    st.session_state.player_data = None
    st.session_state.commander_data = None
    st.session_state.is_registering = False
    st.session_state.registration_step = 0
    st.session_state.temp_player = None
    st.session_state.temp_char_bio = {}
    st.rerun()

def start_registration() -> None:
    """Inicia el flujo de registro."""
    st.session_state.is_registering = True
    st.session_state.registration_step = 0
    st.rerun()

def cancel_registration() -> None:
    """Cancela el flujo de registro y vuelve a la pantalla de autenticación."""
    st.session_state.is_registering = False
    st.session_state.registration_step = 0
    st.rerun()

def next_registration_step() -> None:
    """Avanza al siguiente paso del wizard de registro."""
    st.session_state.registration_step += 1
    st.rerun()
