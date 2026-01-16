"""Constantes del Motor de Resolución Galáctico."""

# --- Configuración de Dados ---
DICE_SIDES = 50
DICE_COUNT = 2
MIN_ROLL = DICE_COUNT  # 2
MAX_ROLL = DICE_COUNT * DICE_SIDES  # 100

# --- Umbrales de Críticos ---
CRITICAL_SUCCESS_MIN = 96  # 96-100 = Crítico
CRITICAL_FAILURE_MAX = 5   # 2-5 = Pifia

# --- Umbrales de Margen ---
TOTAL_SUCCESS_MARGIN = 25      # Margen > 25 = Éxito Total
PARTIAL_SUCCESS_MARGIN = 0     # Margen 0-25 = Éxito Parcial
PARTIAL_FAILURE_MARGIN = -25   # Margen -25 a 0 = Fracaso Parcial
# Margen < -25 = Fracaso Total

# --- Bonos Asintóticos ---
ASYMPTOTIC_MAX_BONUS = 40  # Máximo bono teórico
ASYMPTOTIC_K_FACTOR = 50   # Factor de saturación (mayor K = curva más suave)

# --- Dificultades Estándar ---
DIFFICULTY_TRIVIAL = 20
DIFFICULTY_EASY = 35
DIFFICULTY_NORMAL = 50
DIFFICULTY_HARD = 65
DIFFICULTY_VERY_HARD = 80
DIFFICULTY_HEROIC = 95
DIFFICULTY_LEGENDARY = 110

DIFFICULTY_PRESETS = {
    "trivial": DIFFICULTY_TRIVIAL,
    "fácil": DIFFICULTY_EASY,
    "normal": DIFFICULTY_NORMAL,
    "difícil": DIFFICULTY_HARD,
    "muy difícil": DIFFICULTY_VERY_HARD,
    "heroico": DIFFICULTY_HEROIC,
    "legendario": DIFFICULTY_LEGENDARY,
}

# --- Efectos de Beneficios ---
BENEFIT_EFFICIENCY_REFUND = 0.50      # 50% de recursos devueltos
BENEFIT_PRESTIGE_GAIN = 0.05          # +0.05% de prestigio
BENEFIT_IMPETUS_TICK_REDUCTION = 1    # -1 tick en siguiente misión

# --- Efectos de Malus ---
MALUS_OPERATIVE_DOWN_TICKS = 2        # 2 ticks fuera de servicio
MALUS_DISCREDIT_LOSS = 0.05           # -0.05% de prestigio
# Exposición no tiene valor numérico, es narrativa

# --- Estados de Entidad ---
ENTITY_STATUS_ACTIVE = "Activo"
ENTITY_STATUS_INCAPACITATED = "Incapacitado"
ENTITY_STATUS_EXPOSED = "Expuesto"
