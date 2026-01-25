# core/movement_constants.py (Completo)
"""
Constantes del Motor de Movimiento V10.0.
Define tiempos de viaje, costos y reglas de navegación.
Actualizado V14.0: Nuevos umbrales para Warp, Starlane Boost y Costos por Nave.
"""

# --- TICKS DE VIAJE (SUPERFICIE) ---
TICKS_SECTOR_TO_SECTOR = 1           # Superficie a superficie (mismo planeta)

# --- TICKS DE VIAJE (SUPERFICIE <-> ÓRBITA) ---
TICKS_SURFACE_TO_ORBIT = 0           # Instantáneo pero bloquea movimiento
MOVEMENT_LOCK_ON_ORBIT_CHANGE = True # Activa movement_locked tras subir/bajar

# --- TICKS DE VIAJE (ENTRE ANILLOS) ---
TICKS_BETWEEN_RINGS_SHORT = 1        # Costo unificado para cualquier salto entre anillos
INTER_RING_LONG_DISTANCE_THRESHOLD = 3 # Umbral de distancia (diferencia de anillos) para cobrar energía
INTER_RING_ENERGY_COST_PER_SHIP = 2    # Costo de energía por nave si supera el umbral

# Legacy constant reference (se mantiene para compatibilidad si algo externo la usa, pero se prefiere la nueva)
ENERGY_COST_LONG_INTER_RING = INTER_RING_ENERGY_COST_PER_SHIP 

# --- STARLANES ---
STARLANE_DISTANCE_THRESHOLD = 15.0   # Distancia para viaje corto (V14.0: Aumentado de 10.0 a 15.0)
TICKS_STARLANE_SHORT = 1             # Starlane con distancia <= threshold (o con Boost)
TICKS_STARLANE_LONG = 2              # Starlane con distancia > threshold
STARLANE_ENERGY_BOOST_COST = 5       # Costo de energía por nave para reducir tiempo de viaje largo

# --- WARP (Sin Starlane - Viaje FTL Directo) ---
WARP_MAX_DISTANCE = 30.0                 # Distancia máxima permitida para salto Warp
WARP_ENERGY_COST_PER_UNIT_DISTANCE = 1   # Células de energía por unidad de distancia
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