# core/detection_constants.py
"""
Constantes del Sistema de Detección y Emboscada V14.1.
Define los modificadores y umbrales para el motor de detección.
"""

# --- PENALIZADORES DE GRUPO ---
# Penalización a defensa por cada entidad adicional en el bando defensor
GROUP_SIZE_PENALTY_PER_ENTITY = -2

# --- BONIFICADORES DE SIGILO ---
# Bono a la defensa si la unidad tiene STEALTH_MODE activo
STEALTH_MODE_DEFENSE_BONUS = 15

# --- UMBRALES DE DETECCIÓN ---
# Margen requerido para éxito total en detección (revela todos)
DETECTION_TOTAL_SUCCESS_MARGIN = 25

# --- DIFICULTADES BASE ---
# Dificultad base para tiradas de detección
DETECTION_BASE_DIFFICULTY = 50

# --- CONTEXTO DE COMBATE ---
# Tipos de situación resultante de la detección
class DetectionOutcome:
    """Resultados posibles del proceso de detección mutua."""
    CONFLICT = "CONFLICT"       # Ambos bandos se detectan
    AMBUSH_A = "AMBUSH_A"       # Bando A detecta a B, B no detecta a A
    AMBUSH_B = "AMBUSH_B"       # Bando B detecta a A, A no detecta a B
    MUTUAL_STEALTH = "MUTUAL_STEALTH"  # Ninguno detecta al otro

# --- CONSECUENCIAS ---
# Restricción de movimiento local por tick cuando está disoriented
DISORIENTED_MAX_LOCAL_MOVES = 1

# --- HABILIDADES UTILIZADAS ---
# Nombres de habilidades según SKILL_MAPPING
SKILL_DETECTION = "Detección"
SKILL_STEALTH_GROUND = "Sigilo físico"
SKILL_SENSOR_EVASION = "Evasión de sensores"
SKILL_TACTICAL_ESCAPE = "Escape táctico"
SKILL_HUNT = "Caza"

# --- TIPOS DE AMBIENTE ---
class DetectionEnvironment:
    """Contexto físico de la detección."""
    GROUND = "GROUND"   # En superficie (usa Sigilo físico)
    SPACE = "SPACE"     # En espacio/órbita (usa Evasión de sensores)
