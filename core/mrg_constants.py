# core/mrg_constants.py
"""
Constantes del Motor de Resolución Galáctico (MRG).
Basado en Reglas SuperX v2.1.
Define la matemática pura de tiradas, márgenes y dificultades.
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

# --- DIFICULTADES V2.1 (Niveles Estandarizados) ---
DIFFICULTY_ROUTINE = 25
DIFFICULTY_STANDARD = 50
DIFFICULTY_CHALLENGING = 75
DIFFICULTY_HEROIC = 100

DIFFICULTY_PRESETS = {
    "rutinario": DIFFICULTY_ROUTINE,
    "estándar": DIFFICULTY_STANDARD,
    "desafiante": DIFFICULTY_CHALLENGING,
    "heroico": DIFFICULTY_HEROIC,
}

# Mapping de legacy para evitar rupturas inmediatas si algo externo llama a las keys viejas
# (Opcional: se puede eliminar si se confirma que nada externo usa las keys viejas)
# Por ahora, mapeamos las antiguas a las nuevas más cercanas
DIFFICULTY_LEGACY_MAP = {
    "trivial": DIFFICULTY_ROUTINE,
    "fácil": DIFFICULTY_ROUTINE,
    "normal": DIFFICULTY_STANDARD,
    "difícil": DIFFICULTY_CHALLENGING,
    "muy difícil": DIFFICULTY_CHALLENGING,
    "legendario": DIFFICULTY_HEROIC
}

# --- SATURACIÓN ASINTÓTICA (Regla 3.2 - Revisión v2.1) ---
# Fórmula: Bono = Max * (Puntos / (Puntos + K))
# Se reduce el Max Bonus a 50 para evitar trivializar dificultades altas.
ASYMPTOTIC_MAX_BONUS = 50
# K=150 se mantiene para suavizar la curva de especialización.
ASYMPTOTIC_K_FACTOR = 150

# --- ESTADOS DE ENTIDAD ---
# Se alinean con los valores usados en CharacterStatus (core/models.py)
# Mantenidos por consistencia de datos, aunque el MRG ya no aplica efectos directamente.
ENTITY_STATUS_ACTIVE = "Disponible"
ENTITY_STATUS_INCAPACITATED = "Herido"
ENTITY_STATUS_EXPOSED = "Expuesto"