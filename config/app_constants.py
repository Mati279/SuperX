# config/app_constants.py
"""
Constantes globales de la aplicación para escalabilidad y mantenibilidad.
Centraliza valores mágicos dispersos en el código.
"""

# --- Configuración de Tiempo (STRT) ---
LOCK_IN_WINDOW_START_HOUR = 23
LOCK_IN_WINDOW_START_MINUTE = 50
TIMEZONE_NAME = 'America/Argentina/Buenos_Aires'

# --- Configuración de Autenticación ---
PIN_LENGTH = 4
PIN_MIN_VALUE = 1000
PIN_MAX_VALUE = 9999
SESSION_COOKIE_NAME = 'superx_session_token'
LOGIN_SUCCESS_DELAY_SECONDS = 0.5  # Delay para asegurar escritura de cookie

# --- Configuración de Generación Procedural ---
CANDIDATE_NAME_SUFFIX_MIN = 100
CANDIDATE_NAME_SUFFIX_MAX = 999
ATTRIBUTE_BASE_MIN = 1
ATTRIBUTE_BASE_MAX = 5
RECRUITMENT_BASE_COST_MULTIPLIER = 25
RECRUITMENT_COST_VARIANCE_MIN = 0.8
RECRUITMENT_COST_VARIANCE_MAX = 1.2
DEFAULT_CANDIDATE_POOL_SIZE = 3

# --- Configuración de UI ---
UI_COLOR_NOMINAL = "#56d59f"      # Verde - Sistema operativo
UI_COLOR_LOCK_IN = "#f6c45b"      # Naranja - Ventana de bloqueo
UI_COLOR_FROZEN = "#f06464"       # Rojo - Mundo congelado
LOG_CONTAINER_HEIGHT = 300        # Altura del contenedor de logs en píxeles

# --- Configuración de IA (Gemini) ---
TEXT_MODEL_NAME = "gemini-2.5-flash"
IMAGE_MODEL_NAME = "imagen-3.0-generate-001"

# --- Configuración de Base de Datos ---
DEFAULT_PLAYER_CREDITS = 1000     # Créditos iniciales para nuevos jugadores
LOG_LIMIT_DEFAULT = 10            # Cantidad de logs a mostrar por defecto
WORLD_STATE_SINGLETON_ID = 1      # ID único de la fila world_state

# --- Configuración de Personajes ---
DEFAULT_RECRUIT_RANK = "Operativo"
DEFAULT_RECRUIT_STATUS = "Disponible"
DEFAULT_RECRUIT_LOCATION = "Barracones"
COMMANDER_RANK = "Comandante"
COMMANDER_STATUS = "Activo"
COMMANDER_LOCATION = "Puente de Mando"
