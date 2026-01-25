# core/movement_constants.py (Completo)
"""
Constantes del Motor de Movimiento V10.0.
Define tiempos de viaje, costos y reglas de navegación.
"""

# --- TICKS DE VIAJE (SUPERFICIE) ---
TICKS_SECTOR_TO_SECTOR = 1           # Superficie a superficie (mismo planeta)

# --- TICKS DE VIAJE (SUPERFICIE <-> ÓRBITA) ---
TICKS_SURFACE_TO_ORBIT = 0           # Instantáneo pero bloquea movimiento
MOVEMENT_LOCK_ON_ORBIT_CHANGE = True # Activa movement_locked tras subir/bajar

# --- TICKS DE VIAJE (ENTRE ANILLOS) ---
TICKS_BETWEEN_RINGS_SHORT = 1        # Costo unificado para cualquier salto entre anillos (Max dist 3)
ENERGY_COST_LONG_INTER_RING = 3      # Costo de energía por nave para saltos > 3 anillos

# --- STARLANES ---
STARLANE_DISTANCE_THRESHOLD = 10.0   # Distancia para viaje corto
TICKS_STARLANE_SHORT = 1             # Starlane con distancia <= threshold
TICKS_STARLANE_LONG = 2              # Starlane con distancia > threshold

# --- WARP (Sin Starlane - Viaje FTL Directo) ---
WARP_ENERGY_COST_PER_UNIT_DISTANCE = 1  # Células de energía por unidad de distancia
WARP_TICKS_BASE = 3                      # Ticks base para cualquier salto warp
WARP_TICKS_PER_10_DISTANCE = 1           # +1 tick por cada 10 unidades de distancia

# --- LOGÍSTICA ---
TRANSIT_COST_PER_TROOP = 5           # Créditos por tropa por tick en espacio
AUTO_TRANSPORT_ENABLED = True         # Tropas terrestres usan "nave de transporte automática"

# --- INTERDICCIÓN ---
INTERDICTION_MODULE_ID = "interdictor_field"  # ID del módulo que permite interdicción

# --- LÍMITES DE UNIDADES ---
MAX_UNIT_SLOTS = 8                   # Capacidad máxima de slots por unidad
MIN_CHARACTERS_PER_UNIT = 1          # Mínimo 1 personaje (líder) por unidad
MAX_LOCAL_MOVES_PER_TURN = 2         # Máximo de movimientos locales (intra-sistema) por turno antes del bloqueo

# --- ANILLOS PLANETARIOS ---
RING_STELLAR = 0                     # Sector Estelar (espacio profundo del sistema)
RING_MIN = 1                         # Anillo planetario interior
RING_MAX = 6                         # Anillo planetario exterior