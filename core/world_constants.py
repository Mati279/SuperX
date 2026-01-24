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
"""
from typing import Dict, List

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

BASE_TIER_COSTS = {
    2: {"creditos": 2000, "materiales": 1000},
    3: {"creditos": 5000, "materiales": 2500, "tecnologia": "Expansión Modular"},
    4: {"creditos": 10000, "materiales": 5000, "tecnologia": "Citadela Planetaria"}
}

INFRASTRUCTURE_MODULES = {
    "sensor_ground": {
        "name": "Sensor Planetario", 
        "cost_base": 500,
        "desc": "Detecta incursiones terrestres y espías. +2 Seguridad."
    },
    "sensor_orbital": {
        "name": "Sensor Orbital", 
        "cost_base": 500,
        "desc": "Detecta flotas en órbita y bloqueos. +2 Seguridad."
    },
    "defense_aa": {
        "name": "Defensa Anti-Aérea", 
        "cost_base": 400,
        "desc": "Mitiga bombardeos. +5 Seguridad."
    },
    "defense_ground": {
        "name": "Defensa Terrestre", 
        "cost_base": 400,
        "desc": "Combate ejércitos invasores. +5 Seguridad."
    },
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
SECTOR_TYPE_ORBITAL = "Orbital" # Nuevo V6.4

VALID_SECTOR_TYPES = [
    SECTOR_TYPE_URBAN,
    SECTOR_TYPE_PLAIN,
    SECTOR_TYPE_MOUNTAIN,
    SECTOR_TYPE_INHOSPITABLE,
    SECTOR_TYPE_ORBITAL
]

# Definición de sectores válidos para Outposts (Todo menos Urbano, Inhóspito y Orbital)
OUTPOST_ALLOWED_TERRAIN = [SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN] + list(SECTOR_NAMES_BY_CATEGORY.values())

BUILDING_TYPES = {
    "hq": {
        "name": "Comando Central",
        "material_cost": 0,
        "maintenance": {"creditos": 50},
        "description": "Sede administrativa. Establece control territorial.",
        "max_tier": 5,
        "pops_required": 0,
        "category": "administracion",
        "allowed_terrain": [SECTOR_TYPE_URBAN],
        "consumes_slots": True,
        "production": {}
    },
    "outpost": {
        "name": "Puesto de Avanzada",
        "material_cost": 100,
        "maintenance": {"creditos": 10, "materiales": 5},
        "description": "Establece presencia sin urbanizar. Costo reducido.",
        "max_tier": 1,
        "pops_required": 10,
        "category": "expansion",
        "allowed_terrain": OUTPOST_ALLOWED_TERRAIN,
        "consumes_slots": False,
        "production": {}
    },
    "orbital_station": {
        "name": "Estación Orbital",
        "material_cost": 500,
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
    "barracks": {
        "name": "Barracas",
        "material_cost": 300,
        "maintenance": {"creditos": 20, "materiales": 5},
        "description": "Alojamiento militar. Aumenta límite de reclutas.",
        "pops_required": 50,
        "category": "defensa",
        "consumes_slots": True,
        "production": {}
    },
    "mine_basic": {
        "name": "Mina de Superficie",
        "material_cost": 150,
        "maintenance": {"creditos": 10, "celulas_energia": 5},
        "description": "Extracción básica de minerales locales.",
        "pops_required": 100,
        "category": "extraccion",
        "consumes_slots": True,
        "production": {"materiales": 10}
    },
    "solar_plant": {
        "name": "Planta Solar",
        "material_cost": 100,
        "maintenance": {"creditos": 5},
        "description": "Generación de energía pasiva.",
        "pops_required": 20,
        "category": "celulas_energia",
        "consumes_slots": True,
        "production": {"celulas_energia": 15}
    },
    "fusion_reactor": {
        "name": "Reactor de Fusión",
        "material_cost": 500,
        "maintenance": {"creditos": 50, "materiales": 10},
        "description": "Generación masiva de energía (Tier 2).",
        "pops_required": 50,
        "min_tier": 2,
        "category": "celulas_energia",
        "consumes_slots": True,
        "production": {"celulas_energia": 50}
    },
    "factory": {
        "name": "Fundición Industrial",
        "material_cost": 400,
        "maintenance": {"creditos": 30, "celulas_energia": 10, "materiales": 10},
        "description": "Procesa minerales en aleaciones.",
        "pops_required": 200,
        "category": "industria",
        "consumes_slots": True,
        "production": {"componentes": 5}
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
    "expansion": 5
}

ECONOMY_RATES = {
    "income_per_pop": 150.0, # OBSOLETO: Reemplazado por modelo logarítmico en rules.py
    "security_base": 25.0,
    "security_per_1b_pop": 5.0,
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

# Configuración de Slots por Tipo de Sector (V4.6.0)
# Define la capacidad de construcción según geografía
SECTOR_SLOTS_CONFIG = {
    SECTOR_TYPE_PLAIN: 3,        # Llanuras: 3 slots (Máximo)
    SECTOR_TYPE_MOUNTAIN: 2,     # Montañoso: 2 slots
    SECTOR_TYPE_URBAN: 2,        # Urbano: 2 slots
    SECTOR_TYPE_INHOSPITABLE: 0, # Inhóspito: 0 slots
    SECTOR_TYPE_ORBITAL: 1,      # Orbital: 1 slot (V6.4)
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