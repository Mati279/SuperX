# core/prestige_constants.py
"""
Constantes del sistema de prestigio y hegemonía.

Este módulo centraliza todos los parámetros del sistema de competencia política
entre facciones, incluyendo umbrales de poder, mecánicas de fricción y condiciones
de victoria.
"""

# ============================================================
# CONFIGURACIÓN BASE DE FACCIONES
# ============================================================

# Número de facciones (fijo)
TOTAL_FACTIONS = 7
INITIAL_PRESTIGE = 100.0 / TOTAL_FACTIONS  # ~14.29%

# ============================================================
# UMBRALES DE ESTADO DE PODER
# ============================================================

# Hegemonía
HEGEMONY_THRESHOLD = 25.0      # Umbral para ascender a Hegemón
HEGEMONY_FALL_THRESHOLD = 20.0 # Umbral para perder Hegemonía (buffer -5%)

# Estados de debilidad
IRRELEVANCE_THRESHOLD = 5.0    # Estado de Irrelevancia (<5%)
COLLAPSE_THRESHOLD = 2.0       # Estado de Colapso (<2%)

# ============================================================
# CONDICIONES DE VICTORIA
# ============================================================

# Contador de victoria por hegemonía temporal
HEGEMONY_VICTORY_TICKS = 20    # Ticks para ganar manteniendo hegemonía

# ============================================================
# RECOMPENSAS PVE (HITOS)
# ============================================================

# Tiers de recompensa por acciones PvE (Suma cero: se drena del resto)
PVE_TIER_I = 0.2     # Hito Menor (ej: Completar misión básica)
PVE_TIER_II = 0.5    # Hito Medio (ej: Descubrimiento importante)
PVE_TIER_III = 0.75  # Hito Mayor (ej: Gran logro diplomático)
PVE_TIER_IV = 1.0    # Hito Legendario (ej: Maravilla galáctica)

# ============================================================
# MECÁNICAS DE COMBATE (IDP)
# ============================================================

# Índice de Disparidad de Poder (IDP)
# IDP = max(0, 1 + (P_Victima - P_Atacante) / IDP_DIVISOR)
IDP_DIVISOR = 20               # Divisor en la fórmula IDP

# Hard Cap Anti-Bullying: Si IDP = 0, no hay transferencia de prestigio
IDP_MINIMUM = 0.0              # IDP mínimo (previene bullying)

# ============================================================
# FRICCIÓN GALÁCTICA (REDISTRIBUCIÓN AUTOMÁTICA)
# ============================================================

# Impuesto Imperial
FRICTION_THRESHOLD = 20.0      # Facciones > 20% pagan fricción
FRICTION_RATE = 1.5            # 1.5% por tick

# Subsidio de Supervivencia
SUBSIDY_THRESHOLD = 5.0        # Facciones < 5% reciben subsidio

# ============================================================
# VALIDACIÓN Y TOLERANCIA
# ============================================================

# Tolerancia para validación de suma cero
PRESTIGE_SUM_TOLERANCE = 0.01  # ±0.01% de tolerancia
PRESTIGE_TOTAL = 100.0         # El prestigio total debe ser exactamente 100%

# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================

# Prefijos para logs de prestigio
LOG_PREFIX_FRICTION = "📉"      # Pérdida por fricción
LOG_PREFIX_SUBSIDY = "📈"       # Ganancia por subsidio
LOG_PREFIX_HEGEMONY = "👑"      # Eventos de hegemonía
LOG_PREFIX_VICTORY = "🏆"       # Victoria
LOG_PREFIX_FALL = "💔"          # Caída de hegemonía
LOG_PREFIX_TRANSFER = "⚔️"      # Transferencia PVP
LOG_PREFIX_PVE = "🌍"           # Eventos PvE / Hitos

# ============================================================
# NOMBRES DE ESTADOS (para UI)
# ============================================================

STATE_NAME_HEGEMONIC = "Hegemónico"
STATE_NAME_NORMAL = "Normal"
STATE_NAME_IRRELEVANT = "Irrelevante"
STATE_NAME_COLLAPSED = "Colapsado"