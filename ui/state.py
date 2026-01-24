# ui/state.py
"""
Gestión de Estado de Sesión.
Maneja el estado de autenticación y datos del jugador usando modelos tipados.
"""

import streamlit as st
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

from data.player_repository import clear_session_token
from config.app_constants import SESSION_COOKIE_NAME
from core.models import PlayerData, CommanderData


# --- MODELO DE ESTADO DE SESIÓN ---

@dataclass
class SessionState:
    """Estado tipado de la sesión del usuario."""
    logged_in: bool = False
    player_data: Optional[PlayerData] = None
    commander_data: Optional[CommanderData] = None
    is_registering: bool = False
    registration_step: int = 0
    temp_player: Optional[Dict[str, Any]] = None
    temp_char_bio: Dict[str, Any] = field(default_factory=dict)


# --- FUNCIONES DE INICIALIZACIÓN ---

def initialize_session_state() -> None:
    """
    Inicializa el estado de sesión de Streamlit con valores por defecto.
    Garantiza que todas las claves necesarias existan.
    """
    defaults = {
        'logged_in': False,
        'player_data': None,
        'commander_data': None,
        'is_registering': False,
        'registration_step': 0,
        'temp_player': None,
        'temp_char_bio': {},
        # --- Navegación Espacial ---
        'navigation_depth': 'galaxy',  # 'galaxy', 'system', 'planet'
        'selected_system_id': None,
        'selected_planet_id': None,
        'map_view': 'galaxy'
    }

    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def get_session_state() -> SessionState:
    """
    Obtiene el estado de sesión actual como objeto tipado.
    Útil para acceso seguro con autocompletado.
    """
    return SessionState(
        logged_in=st.session_state.get('logged_in', False),
        player_data=st.session_state.get('player_data'),
        commander_data=st.session_state.get('commander_data'),
        is_registering=st.session_state.get('is_registering', False),
        registration_step=st.session_state.get('registration_step', 0),
        temp_player=st.session_state.get('temp_player'),
        temp_char_bio=st.session_state.get('temp_char_bio', {})
    )


# --- FUNCIONES DE AUTENTICACIÓN ---

def login_user(
    player_data: Dict[str, Any],
    commander_data: Dict[str, Any]
) -> None:
    """
    Autentica al usuario y actualiza el estado de sesión.

    Args:
        player_data: Diccionario con datos del jugador desde DB
        commander_data: Diccionario con datos del comandante desde DB
    """
    try:
        # Convertir a modelos tipados para validación
        player = PlayerData.from_dict(player_data)
        commander = CommanderData.from_dict(commander_data)

        # Actualizar estado
        st.session_state.logged_in = True
        st.session_state.player_data = player
        st.session_state.commander_data = commander
        st.session_state.is_registering = False
        st.session_state.registration_step = 0

    except Exception as e:
        # Si falla la validación, guardar como diccionarios (compatibilidad)
        st.session_state.logged_in = True
        st.session_state.player_data = player_data
        st.session_state.commander_data = commander_data
        st.session_state.is_registering = False
        st.session_state.registration_step = 0


def logout_user(cookie_manager=None) -> None:
    """
    Cierra sesión del usuario.
    Limpia la cookie, el token en DB y el estado local.

    Args:
        cookie_manager: Instancia del gestor de cookies (opcional)
    """
    # 1. Limpiar Token en DB
    player_data = st.session_state.get('player_data')
    if player_data:
        player_id = _get_player_id(player_data)
        if player_id:
            try:
                clear_session_token(player_id)
            except Exception:
                pass  # Si falla, continuamos con el logout local

    # 2. Limpiar Cookie
    if cookie_manager:
        try:
            cookie_manager.delete(SESSION_COOKIE_NAME)
        except Exception:
            pass  # Puede fallar si ya no existe

    # 3. Limpiar Estado Local
    st.session_state.logged_in = False
    st.session_state.player_data = None
    st.session_state.commander_data = None
    st.session_state.is_registering = False
    st.session_state.registration_step = 0
    st.session_state.temp_player = None
    st.session_state.temp_char_bio = {}

    st.rerun()


# --- FUNCIONES DE REGISTRO ---

def start_registration() -> None:
    """Inicia el proceso de registro de nuevo jugador."""
    st.session_state.is_registering = True
    st.session_state.registration_step = 0
    st.rerun()


def cancel_registration() -> None:
    """Cancela el proceso de registro y vuelve al login."""
    st.session_state.is_registering = False
    st.session_state.registration_step = 0
    st.session_state.temp_player = None
    st.session_state.temp_char_bio = {}
    st.rerun()


def next_registration_step() -> None:
    """Avanza al siguiente paso del registro."""
    st.session_state.registration_step += 1
    st.rerun()


def prev_registration_step() -> None:
    """Retrocede al paso anterior del registro."""
    if st.session_state.registration_step > 0:
        st.session_state.registration_step -= 1
        st.rerun()


# --- FUNCIONES DE ACCESO A DATOS ---

def get_player() -> Optional[PlayerData]:
    """
    Retorna los datos del jugador desde el estado de la sesión.

    Returns:
        PlayerData tipado o None si no hay sesión
    """
    data = st.session_state.get('player_data')
    if data is None:
        return None

    # Si ya es PlayerData, retornar directamente
    if isinstance(data, PlayerData):
        return data

    # Si es diccionario, convertir
    if isinstance(data, dict):
        try:
            return PlayerData.from_dict(data)
        except Exception:
            return None

    return None


def get_player_dict() -> Optional[Dict[str, Any]]:
    """
    Retorna los datos del jugador como diccionario.
    Útil para compatibilidad con código existente.

    Returns:
        Diccionario con datos del jugador o None
    """
    data = st.session_state.get('player_data')
    if data is None:
        return None

    if isinstance(data, PlayerData):
        return data.model_dump()

    if isinstance(data, dict):
        return data

    return None


def get_commander() -> Optional[CommanderData]:
    """
    Retorna los datos del comandante desde el estado de la sesión.

    Returns:
        CommanderData tipado o None si no hay sesión
    """
    data = st.session_state.get('commander_data')
    if data is None:
        return None

    # Si ya es CommanderData, retornar directamente
    if isinstance(data, CommanderData):
        return data

    # Si es diccionario, convertir
    if isinstance(data, dict):
        try:
            return CommanderData.from_dict(data)
        except Exception:
            return None

    return None


def get_commander_dict() -> Optional[Dict[str, Any]]:
    """
    Retorna los datos del comandante como diccionario.
    Útil para compatibilidad con código existente.

    Returns:
        Diccionario con datos del comandante o None
    """
    data = st.session_state.get('commander_data')
    if data is None:
        return None

    if isinstance(data, CommanderData):
        return data.model_dump()

    if isinstance(data, dict):
        return data

    return None


def get_player_id() -> Optional[int]:
    """
    Obtiene el ID del jugador actual de forma segura.

    Returns:
        ID del jugador o None
    """
    return _get_player_id(st.session_state.get('player_data'))


def is_logged_in() -> bool:
    """Verifica si hay una sesión activa."""
    return st.session_state.get('logged_in', False)


# --- FUNCIONES AUXILIARES ---

def _get_player_id(player_data: Any) -> Optional[int]:
    """
    Extrae el ID del jugador de diferentes formatos de datos.

    Args:
        player_data: PlayerData, diccionario, o None

    Returns:
        ID del jugador o None
    """
    if player_data is None:
        return None

    if isinstance(player_data, PlayerData):
        return player_data.id

    if isinstance(player_data, dict):
        return player_data.get('id')

    return None


def update_player_resources(resources: Dict[str, int]) -> None:
    """
    Actualiza los recursos del jugador en el estado local.
    Nota: Esto NO actualiza la DB, solo el estado de sesión.

    Args:
        resources: Diccionario con recursos a actualizar
    """
    player = st.session_state.get('player_data')
    if player is None:
        return

    if isinstance(player, PlayerData):
        # Actualizar modelo Pydantic
        for key, value in resources.items():
            if hasattr(player, key):
                setattr(player, key, value)
    elif isinstance(player, dict):
        # Actualizar diccionario
        player.update(resources)


def refresh_player_data(new_data: Dict[str, Any]) -> None:
    """
    Refresca los datos del jugador desde la DB.

    Args:
        new_data: Datos actualizados del jugador
    """
    if new_data:
        try:
            st.session_state.player_data = PlayerData.from_dict(new_data)
        except Exception:
            st.session_state.player_data = new_data


def refresh_commander_data(new_data: Dict[str, Any]) -> None:
    """
    Refresca los datos del comandante desde la DB.

    Args:
        new_data: Datos actualizados del comandante
    """
    if new_data:
        try:
            st.session_state.commander_data = CommanderData.from_dict(new_data)
        except Exception:
            st.session_state.commander_data = new_data
