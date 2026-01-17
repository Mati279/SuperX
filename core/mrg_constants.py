# core/mrg_constants.py
"""
Constantes del Motor de Resolución Galáctico (MRG).
Basado en Reglas SuperX v2.0 - Sección 3.
Combina reglas nuevas con definiciones de dificultad requeridas por el sistema.
"""

# --- DADOS Y DISTRIBUCIÓN ---
DICE_SIDES = 50  # El sistema usa 2d50 (Triangular 1-100, media 51)
DICE_COUNT = 2   # Variable legacy para compatibilidad

# --- RANGOS DE CRÍTICOS (Regla 3.1) ---
# Los extremos anulan el cálculo de margen matemático.
CRITICAL_FAILURE_MAX = 5   # Resultados 2, 3, 4, 5 son PIFIAS AUTOMÁTICAS.
CRITICAL_SUCCESS_MIN = 96  # Resultados 96, 97, 98, 99, 100 son CRÍTICOS AUTOMÁTICOS.

# --- UMBRALES DE MARGEN (Regla 3.3) ---
# Fórmula: Margen = (Tirada + Bonos) - Dificultad
MARGIN_TOTAL_SUCCESS = 25     # Margen > +25
MARGIN_PARTIAL_SUCCESS = 0    # Margen 0 a +25
MARGIN_PARTIAL_FAILURE = -25  # Margen -25 a 0
# Margen < -25 es Fracaso Total

# --- DIFICULTADES ESTÁNDAR (Requeridas por gemini_service y time_engine) ---
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

# --- VALORES DE BENEFICIOS (Regla 3.3 - Selección de Éxito Total) ---
BENEFIT_EFFICIENCY_REFUND = 0.50  # Devuelve 50% del costo de energía
BENEFIT_PRESTIGE_GAIN = 0.05      # +0.05% de Prestigio Global
BENEFIT_IMPETUS_TICK_REDUCTION = 1 # -1 Tick a la siguiente misión

# --- VALORES DE MALUS (Regla 3.3 - Selección de Fracaso Total) ---
MALUS_OPERATIVE_DOWN_TICKS = 2    # Personaje herido/inutilizable por 2 Ticks
MALUS_DISCREDIT_LOSS = 0.05       # -0.05% de Prestigio Global
MALUS_EXPOSURE_RISK = True        # Revela posición o secretos

# --- SATURACIÓN ASINTÓTICA (Regla 3.2) ---
# Fórmula: Bono = Max * (Puntos / (Puntos + K))
ASYMPTOTIC_MAX_BONUS = 100
ASYMPTOTIC_K_FACTOR = 50

# --- ESTADOS DE ENTIDAD (Restaurados para compatibilidad) ---
# Se alinean con los valores usados en CharacterStatus (core/models.py)
ENTITY_STATUS_ACTIVE = "Disponible"
ENTITY_STATUS_INCAPACITATED = "Herido"  # Mapeado a 'Herido' para consistencia en DB
ENTITY_STATUS_EXPOSED = "Expuesto"      # Estado temporal lógico