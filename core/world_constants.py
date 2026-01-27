# core/world_constants.py (Completo)
"""
Constantes universales y definiciones de juego.
Incluye recursos, tipos de estrellas y definiciones de edificios/módulos.
Actualizado v4.1.3: Recurso Datos y Categorías de Lujo.
Actualizado v4.2.0: Arquitectura de Sectores y Matriz de Probabilidad.
Actualizado v4.3.0: Planetología Avanzada y Subdivisión de Sectores (Refactorización Completa).
Actualizado v4.6.0: Refactorización de Capacidad de Sectores (Slots por Tipo).
Actualizado v4.7.0: Alineación con Reglas Definitivas (Biomas y Nomenclatura).
Actualizado v4.8.0: Correcciones de Reglas (Habitabilidad, Economía Logarítmica, Pesos).
Actualizado v4.8.2: Limpieza de constantes de seguridad obsoletas.
Actualizado v5.2.0: Definición de Biomas de Nacimiento Habitables.
Actualizado v5.3.0: Integración de Precios Base para Recursos de Lujo.
Actualizado v6.3.0: Definición de Puestos de Avanzada, Estaciones Orbitales y Soberanía.
Actualizado v6.4.0: Implementación de Sector Orbital y Soberanía Espacial.
Actualizado v7.6.0: Ajuste de Capacidad Urbana (3 Slots).
Actualizado v8.0.0: Control del Sistema (Nivel Estelar) - Megaestructuras y Bonos de Sistema.
Actualizado v8.1.0: Estandarización de UI de Recursos (RESOURCE_UI_CONFIG).
Actualizado V20.1: Ajuste de costos de Estación Orbital para construcción táctica.
Actualizado V23.0: Refactorización Sistema de Edificios Terrestres (Tier System).
"""
from typing import Dict, List

# --- COSTOS ESTÁNDAR (V23.0) ---
CIVILIAN_BUILD_COST = {"creditos": 350, "materiales": 20}
CIVILIAN_UPGRADE_COST = {"creditos": 500, "materiales": 35}

# --- ESTRELLAS ---

# Tipos de estrellas y sus colores para el mapa
STAR_TYPES = {
    "O": {"color": "#9bb0ff", "size": 1.2, "rarity": "legendary", "energy_modifier": 2.0, "special_rule": "Radiation Zone", "class": "O"},
    "B": {"color": "#aabfff", "size": 1.1, "rarity": "epic", "energy_modifier": 1.5, "special_rule": None, "class": "B"},
    "A": {"color": "#cad7ff", "size": 1.05, "rarity": "rare", "energy_modifier": 1.2, "special_rule": None, "class": "A"},
    "F": {"color": "#f8f7ff", "size": 1.02, "rarity": "uncommon", "energy_modifier": 1.1, "special_rule": None, "class": "F"},
    "G": {"color": "#fff4ea", "size": 1.0, "rarity": "common", "energy_modifier": 1.0, "special_rule": None, "class": "G"},
    "K": {"color": "#ffd2a1", "size": 0.95, "rarity": "common", "energy_modifier": 0.9, "special_rule": None, "class": "K"},
    "M": {"color": "#ffcc6f", "size": 0.9, "rarity": "common", "energy_modifier": 0.7, "special_rule": "Low Light", "class": "M"},
}

# Pesos de rareza de estrellas para generacion procedural
STAR_RARITY_WEIGHTS = {
    "O": 0.01,  # Gigantes azules muy raras
    "B": 0.05,
    "A": 0.10,
    "F": 0.15,
    "G": 0.25,  # Estrellas tipo Sol comunes
    "K": 0.24,
    "M": 0.20,  # Enanas rojas comunes
}

# --- PLANETOLOGÍA AVANZADA (TAREA 2) ---

# Clases de Masa y Capacidad de Sectores
PLANET_MASS_CLASSES = {
    'Enano': 2,
    'Estándar': 4,
    'Grande': 6,
    'Gigante': 8
}

# Pesos de Probabilidad por Zona Orbital
# Alta=6, Media=3, Baja=1
ORBITAL_ZONE_WEIGHTS = {
    "ALTA": 6,
    "MEDIA": 3,
    "BAJA": 1
}

# --- DEFINICIONES DE RECURSOS Y SECTORES (NUEVO V4.3.0) ---

# Nombres temáticos de sectores por categoría de recurso
SECTOR_NAMES_BY_CATEGORY = {
    "materiales": "Macizo de Estratos Densos",
    "componentes": "Geoda de Elementos Cristalinos",
    "celulas_energia": "Falla de Emanación Radiante",
    "influencia": "Cuna de Identidad Primigenia",
    "datos": "Cuenca de Ecos Magnéticos"
}

# Nombres dinámicos para sectores inhóspitos por bioma (V4.7.0)
INHOSPITABLE_BIOME_NAMES = {
    "Volcánico": "Flujos Piroclásticos",
    "Tóxico": "Páramo Tóxico",
    "Desértico": "Dunas Muertas",
    "Templado": "Yermos Estériles",
    "Oceánico": "Abismo Oceánico",
    "Glacial": "Glaciar Perpetuo",
    "Gaseoso": "Capa de Nubes Densa"
}

# Listas de Recursos de Lujo (V4.1.3)
LUXURY_RESOURCES_BY_CATEGORY = {
    "materiales": ["Wolframio", "Neodimio", "Paladio", "Platino", "Iridio"],
    "componentes": ["Sensores de Precisión", "Nanobots", "Circuitos Cuánticos"],
    "celulas_energia": ["Cristales de Foco", "Plasma Estable", "Materia Oscura"],
    "influencia": ["Archivos Diplomáticos", "Reliquias Culturales"],
    "datos": ["Códigos de Encriptación", "Matrices de IA", "Núcleos de Datos Crípticos"]
}

# Probabilidades base para la matriz de recursos
RESOURCE_PROB_HIGH = 0.6
RESOURCE_PROB_MEDIUM = 0.3
RESOURCE_PROB_LOW = 0.1
RESOURCE_PROB_NONE = 0.0

# Tabla Maestra de Biomas Actualizada (V4.7.0)
PLANET_BIOMES = {
    "Volcánico": {
        "habitability": 0.3,
        "common_resources": ["materiales", "celulas_energia"],
        "preferred_rings": [1, 2],
        "resource_matrix": {
            "materiales": "ALTA", "celulas_energia": "ALTA", "componentes": "MEDIA", "influencia": "BAJA", "datos": "MEDIA"
        },
        "description": "Actividad tectónica extrema y ríos de lava."
    },
    "Tóxico": {
        "habitability": 0.2,
        "common_resources": ["datos", "celulas_energia"],
        "preferred_rings": [1, 2], # Ajustado V4.7
        "resource_matrix": {
            "datos": "ALTA", "celulas_energia": "MEDIA", "materiales": "BAJA", "componentes": "MEDIA", "influencia": "ALTA"
        },
        "description": "Atmósfera corrosiva rica en compuestos químicos raros."
    },
    "Desértico": {
        "habitability": 0.6,
        "common_resources": ["materiales", "componentes"],
        "preferred_rings": [2, 3, 4],
        "resource_matrix": {
            "materiales": "ALTA", "celulas_energia": "MEDIA", "componentes": "ALTA", "influencia": "MEDIA", "datos": "MEDIA"
        },
        "description": "Vastas extensiones de arena y formaciones rocosas. Escasez de agua."
    },
    "Templado": {
        "habitability": 1.0, # Ajustado V4.7
        "common_resources": ["influencia", "materiales"],
        "preferred_rings": [3, 4],
        "resource_matrix": {
            "materiales": "MEDIA", "celulas_energia": "BAJA", "componentes": "BAJA", "influencia": "ALTA", "datos": "ALTA"
        },
        "description": "Clima estable y ecosistemas diversos. Ideal para la vida."
    },
    "Oceánico": {
        "habitability": 0.8,
        "common_resources": ["influencia", "componentes"],
        "preferred_rings": [3, 4], # Ajustado V4.7
        "resource_matrix": {
            "materiales": "BAJA", "celulas_energia": "ALTA", "componentes": "MEDIA", "influencia": "ALTA", "datos": "MEDIA"
        },
        "description": "Superficie cubierta casi totalmente por agua líquida."
    },
    "Glacial": {
        "habitability": 0.5, # Ajustado V4.7
        "common_resources": ["datos", "celulas_energia"],
        "preferred_rings": [5, 6],
        "resource_matrix": {
            "materiales": "MEDIA", "celulas_energia": "BAJA", "componentes": "ALTA", "influencia": "MEDIA", "datos": "ALTA"
        },
        "description": "Temperaturas bajo cero con depósitos minerales congelados."
    },
    "Gaseoso": {
        "habitability": 0.0,
        "common_resources": ["celulas_energia", "datos"],
        "preferred_rings": [5, 6],
        "resource_matrix": {
            "materiales": "NULA", "celulas_energia": "ALTA", "componentes": "MEDIA", "influencia": "BAJA", "datos": "MEDIA"
        },
        "description": "Gigante sin superficie sólida."
    }
}

# --- REGLA DE NACIMIENTO: BIOMAS HABITABLES ---
# Define los únicos biomas donde los personajes pueden nacer "naturalmente"
# Se excluyen Volcánico, Tóxico y Gaseoso por lógica biológica estándar.
HABITABLE_BIRTH_BIOMES = ["Templado", "Desértico", "Oceánico", "Glacial"]

# --- RECURSOS Y PESOS ---

ASTEROID_BELT_CHANCE = 0.15

# --- REGLAS DE BASE (MÓDULO 20) ---
# Las bases se construyen en sectores urbanos "doblegados" (bajo soberanía del jugador)
# Niveles 1-4. Tiempo de mejora = nivel_destino + 1 ticks.

# Coste de CONSTRUCCIÓN de Base Nv.1 (inicial)
BASE_CONSTRUCTION_COST = {
    "creditos": 1000,
    "materiales": 110
}

# Coste de MEJORA de Base (por nivel destino)
BASE_UPGRADE_COSTS = {
    2: {"creditos": 1500, "materiales": 150},
    3: {"creditos": 3000, "materiales": 500},
    4: {"creditos": 6500, "materiales": 750}
}

# Tiempo de mejora en ticks (nivel_destino + 1)
def get_base_upgrade_time(target_level: int) -> int:
    """Retorna el tiempo de mejora en ticks para subir a un nivel dado."""
    return target_level + 1

# Módulos desbloqueados por nivel de base
# Cada módulo se puede mejorar hasta (nivel_base * 2)
# Módulos nuevos arrancan en (nivel_base + 1)
BASE_MODULES_BY_TIER = {
    1: ["sensor_planetary", "sensor_orbital", "defense_ground", "bunker"],
    2: ["defense_aa"],  # + 1 Slot de construcción extra
    3: ["defense_missile", "energy_shield"],
    4: ["planetary_shield"]  # + 1 Slot de construcción extra
}

# Slots extra otorgados por nivel de base
BASE_EXTRA_SLOTS = {
    1: 0,
    2: 1,
    3: 0,
    4: 1
}

# Definición completa de módulos de infraestructura
BASE_MODULES = {
    "sensor_planetary": {
        "name": "Sensor Planetario",
        "cost_base": {"creditos": 300, "materiales": 50},
        "cost_per_level": {"creditos": 150, "materiales": 25},
        "unlock_tier": 1,
        "desc": "Detecta incursiones terrestres y espías.",
        "effect": {"detection_ground": 2}  # +2 por nivel
    },
    "sensor_orbital": {
        "name": "Sensor Orbital",
        "cost_base": {"creditos": 300, "materiales": 50},
        "cost_per_level": {"creditos": 150, "materiales": 25},
        "unlock_tier": 1,
        "desc": "Detecta flotas en órbita y bloqueos.",
        "effect": {"detection_orbital": 2}  # +2 por nivel
    },
    "defense_ground": {
        "name": "Defensas Terrestres",
        "cost_base": {"creditos": 400, "materiales": 80},
        "cost_per_level": {"creditos": 200, "materiales": 40},
        "unlock_tier": 1,
        "desc": "Combate ejércitos invasores.",
        "effect": {"defense_ground": 5}  # +5 por nivel
    },
    "bunker": {
        "name": "Búnker",
        "cost_base": {"creditos": 500, "materiales": 100},
        "cost_per_level": {"creditos": 250, "materiales": 50},
        "unlock_tier": 1,
        "desc": "Protección para población civil y recursos críticos.",
        "effect": {"population_protection": 10}  # +10% por nivel
    },
    "defense_aa": {
        "name": "Defensas Anti-Aéreas",
        "cost_base": {"creditos": 600, "materiales": 120},
        "cost_per_level": {"creditos": 300, "materiales": 60},
        "unlock_tier": 2,
        "desc": "Mitiga bombardeos aéreos y atmosféricos.",
        "effect": {"defense_air": 5}  # +5 por nivel
    },
    "defense_missile": {
        "name": "Defensas Anti-Misiles",
        "cost_base": {"creditos": 800, "materiales": 200},
        "cost_per_level": {"creditos": 400, "materiales": 100},
        "unlock_tier": 3,
        "desc": "Intercepta misiles y torpedos orbitales.",
        "effect": {"defense_missile": 8}  # +8 por nivel
    },
    "energy_shield": {
        "name": "Escudo de Energía",
        "cost_base": {"creditos": 1000, "materiales": 300},
        "cost_per_level": {"creditos": 500, "materiales": 150},
        "unlock_tier": 3,
        "desc": "Escudo energético que protege el sector de la base.",
        "effect": {"shield_sector": 15}  # +15 absorción por nivel
    },
    "planetary_shield": {
        "name": "Escudo de Energía (Planetario)",
        "cost_base": {"creditos": 2000, "materiales": 500},
        "cost_per_level": {"creditos": 1000, "materiales": 250},
        "unlock_tier": 4,
        "desc": "Escudo energético que cubre todo el planeta.",
        "effect": {"shield_planet": 25}  # +25 absorción por nivel
    }
}

# Nivel máximo de módulo = nivel_base * 2
def get_max_module_level(base_tier: int) -> int:
    """Retorna el nivel máximo permitido para módulos según el tier de la base."""
    return base_tier * 2

# Nivel inicial de módulos nuevos al desbloquear = nivel_base + 1
def get_initial_module_level(base_tier: int) -> int:
    """Retorna el nivel inicial de un módulo recién desbloqueado."""
    return base_tier + 1

# Legacy: Mantener compatibilidad con código antiguo
BASE_TIER_COSTS = BASE_UPGRADE_COSTS

INFRASTRUCTURE_MODULES = {
    "sensor_ground": BASE_MODULES["sensor_planetary"],
    "sensor_orbital": BASE_MODULES["sensor_orbital"],
    "defense_aa": BASE_MODULES["defense_aa"],
    "defense_ground": BASE_MODULES["defense_ground"],
    "defense_orbital": {
        "name": "Batería Orbital",
        "cost_base": 1000,
        "min_base_tier": 3,
        "desc": "Artillería superficie-espacio. +10 Seguridad."
    }
}

# --- SECTORES Y GENERACIÓN V4.2.0 (ADELANTADO PARA REFERENCIA EN BUILDINGS) ---

SECTOR_TYPE_URBAN = "Urbano"
SECTOR_TYPE_PLAIN = "Llanura"
SECTOR_TYPE_MOUNTAIN = "Montañoso"
SECTOR_TYPE_INHOSPITABLE = "Inhospito"
SECTOR_TYPE_ORBITAL = "Orbital"  # Nuevo V6.4
SECTOR_TYPE_STELLAR = "Estelar"  # V8.0: Sector a nivel de sistema para megaestructuras

VALID_SECTOR_TYPES = [
    SECTOR_TYPE_URBAN,
    SECTOR_TYPE_PLAIN,
    SECTOR_TYPE_MOUNTAIN,
    SECTOR_TYPE_INHOSPITABLE,
    SECTOR_TYPE_ORBITAL,
    SECTOR_TYPE_STELLAR
]

# Definición de sectores válidos para Outposts (Todo menos Urbano, Inhóspito y Orbital)
OUTPOST_ALLOWED_TERRAIN = [SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN] + list(SECTOR_NAMES_BY_CATEGORY.values())

# Terrenos válidos para nuevas estructuras civiles (V23.0)
CIVILIAN_ALLOWED_TERRAIN = [SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN] + list(SECTOR_NAMES_BY_CATEGORY.values())

BUILDING_TYPES = {
    "outpost": {
        "name": "Puesto de Avanzada",
        "credit_cost": CIVILIAN_BUILD_COST["creditos"],
        "material_cost": CIVILIAN_BUILD_COST["materiales"],
        "maintenance": {"creditos": 10, "materiales": 5},
        "description": "Establece presencia sin urbanizar. Costo reducido.",
        "max_tier": 1,
        "pops_required": 10,
        "category": "expansion",
        "allowed_terrain": OUTPOST_ALLOWED_TERRAIN,
        "consumes_slots": False,
        "production": {}
    },
    "mat_foundry": {
        "name": "Fundición de Materiales",
        "credit_cost": CIVILIAN_BUILD_COST["creditos"],
        "material_cost": CIVILIAN_BUILD_COST["materiales"],
        "maintenance": {"creditos": 20, "celulas_energia": 5},
        "description": "Procesa mineral crudo en materiales de construcción.",
        "max_tier": 2,
        "pops_required": 100,
        "category": "industria",
        "allowed_terrain": CIVILIAN_ALLOWED_TERRAIN,
        "consumes_slots": True,
        "production": {"materiales": 20}
    },
    "assembly_plant": {
        "name": "Planta de Ensamblaje",
        "credit_cost": CIVILIAN_BUILD_COST["creditos"],
        "material_cost": CIVILIAN_BUILD_COST["materiales"],
        "maintenance": {"creditos": 20, "celulas_energia": 5},
        "description": "Manufactura componentes avanzados de tecnología.",
        "max_tier": 2,
        "pops_required": 100,
        "category": "tecnologia",
        "allowed_terrain": CIVILIAN_ALLOWED_TERRAIN,
        "consumes_slots": True,
        "production": {"componentes": 5}
    },
    "fusion_core": {
        "name": "Núcleo de Fusión",
        "credit_cost": CIVILIAN_BUILD_COST["creditos"],
        "material_cost": CIVILIAN_BUILD_COST["materiales"],
        "maintenance": {"creditos": 20, "materiales": 5},
        "description": "Generador de energía mediante fusión controlada.",
        "max_tier": 2,
        "pops_required": 50,
        "category": "celulas_energia",
        "allowed_terrain": CIVILIAN_ALLOWED_TERRAIN,
        "consumes_slots": True,
        "production": {"celulas_energia": 5}
    },
    "foreign_ministry": {
        "name": "Ministerio de Asuntos Exteriores",
        "credit_cost": CIVILIAN_BUILD_COST["creditos"],
        "material_cost": CIVILIAN_BUILD_COST["materiales"],
        "maintenance": {"creditos": 50},
        "description": "Centro diplomático y cultural.",
        "max_tier": 2,
        "pops_required": 100,
        "category": "administracion",
        "allowed_terrain": CIVILIAN_ALLOWED_TERRAIN,
        "consumes_slots": True,
        "production": {"influencia": 5}
    },
    "encryption_center": {
        "name": "Centro de Encriptación",
        "credit_cost": CIVILIAN_BUILD_COST["creditos"],
        "material_cost": CIVILIAN_BUILD_COST["materiales"],
        "maintenance": {"creditos": 30, "celulas_energia": 10},
        "description": "Procesamiento de datos y criptografía.",
        "max_tier": 2,
        "pops_required": 80,
        "category": "tecnologia",
        "allowed_terrain": CIVILIAN_ALLOWED_TERRAIN,
        "consumes_slots": True,
        "production": {"datos": 5}
    },
    "orbital_station": {
        "name": "Estación Orbital",
        "material_cost": 30, # Ajustado V20.1
        "credit_cost": 800,  # Agregado V20.1
        "maintenance": {"creditos": 50, "celulas_energia": 20},
        "description": "Base en órbita geoestacionaria. Controla el espacio.",
        "max_tier": 3,
        "pops_required": 20,
        "category": "orbital",
        "is_orbital": True,
        "allowed_terrain": [SECTOR_TYPE_ORBITAL], # Restricción V6.4
        "consumes_slots": True, # V6.4: Consume el slot único orbital
        "production": {"datos": 5}
    },

    # --- MEGAESTRUCTURAS ESTELARES (V8.0) ---
    # Estructuras Básicas (disponibles para cualquier tipo de estrella)

    "stellar_fortress": {
        "name": "Fortaleza Estelar",
        "material_cost": 2000,
        "maintenance": {"creditos": 200, "celulas_energia": 50, "materiales": 30},
        "description": "Estación de defensa masiva. Protege todo el sistema contra incursiones.",
        "pops_required": 0,
        "category": "defensa_estelar",
        "is_stellar": True,
        "allowed_terrain": [SECTOR_TYPE_STELLAR],
        "consumes_slots": True,
        "production": {},
        "system_bonus": {"defense": 50}
    },
    "approach_sensor": {
        "name": "Sensor de Aproximación",
        "material_cost": 800,
        "maintenance": {"creditos": 80, "celulas_energia": 30},
        "description": "Red de detección temprana. Alerta de flotas enemigas entrando al sistema.",
        "pops_required": 0,
        "category": "deteccion_estelar",
        "is_stellar": True,
        "allowed_terrain": [SECTOR_TYPE_STELLAR],
        "consumes_slots": True,
        "production": {},
        "system_bonus": {"detection_range": 2}
    },
    "trade_beacon": {
        "name": "Baliza Comercial",
        "material_cost": 1200,
        "maintenance": {"creditos": 100, "celulas_energia": 20},
        "description": "Atrae rutas comerciales. +15% ingresos fiscales y mitiga penalización orbital.",
        "pops_required": 0,
        "category": "comercio_estelar",
        "is_stellar": True,
        "allowed_terrain": [SECTOR_TYPE_STELLAR],
        "consumes_slots": True,
        "production": {},
        "system_bonus": {"fiscal_multiplier": 1.15, "mitigate_ring_penalty": True}
    },
    "surveillance_network": {
        "name": "Red de Vigilancia",
        "material_cost": 1000,
        "maintenance": {"creditos": 75, "celulas_energia": 25, "datos": 10},
        "description": "Monitoreo constante. +10 Seguridad base a todos los planetas del sistema.",
        "pops_required": 0,
        "category": "seguridad_estelar",
        "is_stellar": True,
        "allowed_terrain": [SECTOR_TYPE_STELLAR],
        "consumes_slots": True,
        "production": {},
        "system_bonus": {"security_flat": 10.0}
    },
    "logistics_hub": {
        "name": "Centro Logístico",
        "material_cost": 1500,
        "maintenance": {"creditos": 120, "celulas_energia": 40},
        "description": "Optimiza suministros. -10% coste de mantenimiento de todos los edificios del sistema.",
        "pops_required": 0,
        "category": "logistica_estelar",
        "is_stellar": True,
        "allowed_terrain": [SECTOR_TYPE_STELLAR],
        "consumes_slots": True,
        "production": {},
        "system_bonus": {"maintenance_multiplier": 0.9}
    },

    # Estructuras Específicas por Tipo de Estrella

    "radiation_collector": {
        "name": "Colector de Radiación",
        "material_cost": 3000,
        "maintenance": {"creditos": 150, "materiales": 50},
        "description": "Aprovecha la intensa radiación de estrellas clase O. +200 energía.",
        "pops_required": 0,
        "category": "energia_estelar",
        "is_stellar": True,
        "allowed_terrain": [SECTOR_TYPE_STELLAR],
        "required_star_class": "O",
        "consumes_slots": True,
        "production": {"celulas_energia": 200}
    },
    "stellar_synchrotron": {
        "name": "Sincrotrón Estelar",
        "material_cost": 2500,
        "maintenance": {"creditos": 180, "celulas_energia": 60},
        "description": "Acelera partículas usando el campo magnético de estrellas clase B. +20% datos.",
        "pops_required": 0,
        "category": "investigacion_estelar",
        "is_stellar": True,
        "allowed_terrain": [SECTOR_TYPE_STELLAR],
        "required_star_class": "B",
        "consumes_slots": True,
        "production": {},
        "system_bonus": {"data_multiplier": 1.20}
    },
    "jump_relay": {
        "name": "Relé de Salto",
        "material_cost": 4000,
        "maintenance": {"creditos": 250, "celulas_energia": 100},
        "description": "Amplifica la gravedad de estrellas clase A para viajes FTL rápidos.",
        "pops_required": 0,
        "category": "transporte_estelar",
        "is_stellar": True,
        "allowed_terrain": [SECTOR_TYPE_STELLAR],
        "required_star_class": "A",
        "consumes_slots": True,
        "production": {},
        "system_bonus": {"ftl_speed_bonus": 0.5}
    },
    "integrated_refinery": {
        "name": "Refinería Integrada",
        "material_cost": 2800,
        "maintenance": {"creditos": 140, "celulas_energia": 45},
        "description": "Aprovecha la estabilidad de estrellas clase K para refinado eficiente. +15% materiales.",
        "pops_required": 0,
        "category": "extraccion_estelar",
        "is_stellar": True,
        "allowed_terrain": [SECTOR_TYPE_STELLAR],
        "required_star_class": "K",
        "consumes_slots": True,
        "production": {},
        "system_bonus": {"material_multiplier": 1.15}
    }
}

BUILDING_SHUTDOWN_PRIORITY = {
    "extraccion": 4,
    "industria": 3,
    "tecnologia": 2,
    "defensa": 1,
    "celulas_energia": 0,
    "administracion": 0,
    "orbital": 0,
    "expansion": 5,
    # V8.0: Prioridades de estructuras estelares (alta prioridad = se apagan primero)
    "defensa_estelar": 1,       # Crítico, se apaga último
    "deteccion_estelar": 2,
    "seguridad_estelar": 2,
    "comercio_estelar": 3,
    "logistica_estelar": 3,
    "energia_estelar": 0,       # Energía crítica
    "investigacion_estelar": 4,
    "transporte_estelar": 4,
    "extraccion_estelar": 4
}

ECONOMY_RATES = {
    "income_per_pop": 150.0, # OBSOLETO: Reemplazado por modelo logarítmico en rules.py
    "security_base": 30.0,      # Aumentado de 25.0 a 30.0 (Estandarización)
    "security_per_1b_pop": 3.0, # Reducido de 5.0 a 3.0
    "security_bonus_sensor": 2.0,
    "security_bonus_defense_aa": 5.0,
    "security_bonus_defense_ground": 5.0,
    "security_bonus_defense_orbital": 10.0
}

# Penalización a la eficiencia económica si el planeta está en disputa o bloqueado (v4.2.0)
DISPUTED_PENALTY_MULTIPLIER = 0.3

BROKER_PRICES = {
    "materiales": 20,
    "componentes": 30,
    "celulas_energia": 30,
    "influencia": 50,
    "datos": 20
}

# Precios Base de Recursos de Lujo (V5.3.0)
LUXURY_PRICES = {
    # Metales
    "Wolframio": 65,
    "Neodimio": 78,
    "Paladio": 92,
    "Platino": 115,
    "Iridio": 138,
    # Componentes
    "Sensores de Precisión": 85,
    "Nanobots": 110,
    "Circuitos Cuánticos": 145,
    # Energía
    "Cristales de Foco": 82,
    "Plasma Estable": 118,
    "Materia Oscura": 165,
    # Influencia
    "Archivos Diplomáticos": 140,
    "Reliquias Culturales": 185,
    # Datos
    "Códigos de Encriptación": 72,
    "Matrices de IA": 98,
    "Núcleos de Datos Crípticos": 132
}

# --- CONFIGURACIÓN UI DE RECURSOS (V8.1) ---
# Estandarización de visualización en la interfaz
RESOURCE_UI_CONFIG = {
    "materiales": {"icon": "📦", "color": "gray"},
    "componentes": {"icon": "⚙️", "color": "red"},
    "celulas_energia": {"icon": "⚡", "color": "orange"},
    "influencia": {"icon": "🎭", "color": "violet"},
    "datos": {"icon": "💾", "color": "blue"}
}

# Configuración de Slots por Tipo de Sector (V4.6.0)
# Define la capacidad de construcción según geografía
SECTOR_SLOTS_CONFIG = {
    SECTOR_TYPE_PLAIN: 3,        # Llanuras: 3 slots (Máximo)
    SECTOR_TYPE_MOUNTAIN: 2,     # Montañoso: 2 slots
    SECTOR_TYPE_URBAN: 3,        # Urbano: 3 slots (Ajustado V7.6)
    SECTOR_TYPE_INHOSPITABLE: 0, # Inhóspito: 0 slots
    SECTOR_TYPE_ORBITAL: 1,      # Orbital: 1 slot (V6.4)
    SECTOR_TYPE_STELLAR: 1,      # Estelar: 1 slot (Ajuste V8.0 - Megaestructuras Únicas)
    # Mapeo dinámico de yacimientos de recursos (Todos 2 slots)
    **{name: 2 for name in SECTOR_NAMES_BY_CATEGORY.values()},
    # Mapeo dinámico de sectores inhóspitos por bioma (Todos 0 slots)
    **{name: 0 for name in INHOSPITABLE_BIOME_NAMES.values()}
}

# Probabilidad de aparición de recursos (Alta, Media, Baja, Nula)
RESOURCE_CHANCE_HIGH = 0.60
RESOURCE_CHANCE_MEDIUM = 0.30
RESOURCE_CHANCE_LOW = 0.10
RESOURCE_CHANCE_NONE = 0.0

# --- GENERACIÓN DE POBLACIÓN (V4.5) ---

EMPTY_SYSTEMS_COUNT = 5 # Cantidad de nodos que deben permanecer con población cero
WILD_POPULATION_CHANCE = 0.25 # Probabilidad de asignación de datos en nodos secundarios
POP_RANGE = (1.0, 10.0) # Rango de magnitud para el atributo población en miles de millones (Float)