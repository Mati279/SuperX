# core/world_constants.py
"""
Constantes universales y definiciones de juego.
Incluye recursos, tipos de estrellas y definiciones de edificios/módulos.
Actualizado v4.1.3: Recurso Datos y Categorías de Lujo.
Actualizado v4.2.0: Arquitectura de Sectores y Matriz de Probabilidad.
Actualizado v4.3.0: Planetología Avanzada y Subdivisión de Sectores (Refactorización Completa).
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

# Modificadores de Seguridad por distancia (Distancia al Sol)
SECURITY_MOD_INNER = {1: -5, 2: -3}
SECURITY_MOD_OUTER = {5: -3, 6: -5}

# Tabla Maestra de Biomas (Extraída de image_c5ef58.png)
PLANET_BIOMES = {
    "Volcánico": {
        "resources": ["Magnetita", "Cristales de Foco", "Azufre"],
        "modifiers": {"habitability": -30, "industry": +20},
        "description": "Actividad tectónica extrema y ríos de lava. Común en zona interna.",
        "allowed_zones": {"INNER": "ALTA", "HABITABLE": "BAJA", "OUTER": None}
    },
    "Tóxico": {
        "resources": ["Gases Nobles", "Núcleos de Datos Crípticos"],
        "modifiers": {"habitability": -50, "science": +15},
        "description": "Atmósfera corrosiva rica en compuestos químicos raros.",
        "allowed_zones": {"INNER": "ALTA", "HABITABLE": "MEDIA", "OUTER": "BAJA"}
    },
    "Templado": {
        "resources": ["Agua", "Oxígeno", "Biomasa"],
        "modifiers": {"habitability": +40, "growth": +10},
        "description": "Clima estable y ecosistemas diversos. Ideal para la vida.",
        "allowed_zones": {"INNER": None, "HABITABLE": "ALTA", "OUTER": None}
    },
    "Oceánico": {
        "resources": ["Agua", "Hielo Metano", "Perlas de Sílice"],
        "modifiers": {"habitability": +20, "food": +25},
        "description": "Superficie cubierta casi totalmente por agua líquida.",
        "allowed_zones": {"INNER": None, "HABITABLE": "ALTA", "OUTER": "MEDIA"}
    },
    "Glacial": {
        "resources": ["Hielo Creativo", "Isótopos Fríos"],
        "modifiers": {"habitability": -20, "energy": +10},
        "description": "Temperaturas bajo cero con depósitos minerales congelados.",
        "allowed_zones": {"INNER": None, "HABITABLE": "BAJA", "OUTER": "ALTA"}
    },
    "Gaseoso": {
        "resources": ["Helio-3", "Hidrógeno", "Núcleos de Datos Crípticos"],
        "modifiers": {"habitability": -100, "extraction": +40},
        "description": "Gigante sin superficie sólida, extracción mediante plataformas.",
        "allowed_zones": {"INNER": None, "HABITABLE": None, "OUTER": "ALTA"}
    }
}

# --- RECURSOS Y PESOS ---

ASTEROID_BELT_CHANCE = 0.15

# Pesos de recursos por clase de estrella
RESOURCE_STAR_WEIGHTS = {
    "O": {"Platino": 3, "Uranio": 4, "Oro": 2, "Titanio": 1},
    "B": {"Platino": 2, "Uranio": 3, "Oro": 2, "Titanio": 2},
    "A": {"Oro": 3, "Platino": 1, "Titanio": 2, "Hierro": 2},
    "F": {"Titanio": 3, "Oro": 2, "Hierro": 2, "Cobre": 2},
    "G": {"Hierro": 4, "Titanio": 2, "Cobre": 3, "Aluminio": 3},
    "K": {"Hierro": 3, "Cobre": 3, "Aluminio": 4, "Titanio": 1},
    "M": {"Hierro": 2, "Aluminio": 3, "Cobre": 2},
}

METAL_RESOURCES = {
    "Hierro": {"value": 1, "tier": 1},
    "Titanio": {"value": 2, "tier": 1},
    "Cobre": {"value": 1, "tier": 1},
    "Aluminio": {"value": 1, "tier": 1},
    "Oro": {"value": 5, "tier": 2},
    "Platino": {"value": 10, "tier": 3},
    "Uranio": {"value": 15, "tier": 3},
}

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

BUILDING_TYPES = {
    "hq": {
        "name": "Comando Central",
        "material_cost": 0,
        "maintenance": {"creditos": 50},
        "description": "Sede administrativa. Nivel 3 permite Multitasking.",
        "max_tier": 5,
        "pops_required": 0,
        "category": "administracion",
        "production": {}
    },
    "barracks": {
        "name": "Barracas",
        "material_cost": 300,
        "maintenance": {"creditos": 20, "materiales": 5},
        "description": "Alojamiento militar. Aumenta límite de reclutas.",
        "pops_required": 50,
        "category": "defensa",
        "production": {}
    },
    "mine_basic": {
        "name": "Mina de Superficie",
        "material_cost": 150,
        "maintenance": {"creditos": 10, "celulas_energia": 5},
        "description": "Extracción básica de minerales locales.",
        "pops_required": 100,
        "category": "extraccion",
        "production": {"materiales": 10}
    },
    "solar_plant": {
        "name": "Planta Solar",
        "material_cost": 100,
        "maintenance": {"creditos": 5},
        "description": "Generación de energía pasiva.",
        "pops_required": 20,
        "category": "energia",
        "production": {"celulas_energia": 15}
    },
    "fusion_reactor": {
        "name": "Reactor de Fusión",
        "material_cost": 500,
        "maintenance": {"creditos": 50, "materiales": 10},
        "description": "Generación masiva de energía (Tier 2).",
        "pops_required": 50,
        "min_tier": 2,
        "category": "energia",
        "production": {"celulas_energia": 50}
    },
    "factory": {
        "name": "Fundición Industrial",
        "material_cost": 400,
        "maintenance": {"creditos": 30, "celulas_energia": 10, "materiales": 10},
        "description": "Procesa minerales en aleaciones.",
        "pops_required": 200,
        "category": "industria",
        "production": {"componentes": 5}
    }
}

BUILDING_SHUTDOWN_PRIORITY = {
    "extraccion": 4,
    "industria": 3,
    "tecnologia": 2,
    "defensa": 1,
    "energia": 0,
    "administracion": 0
}

ECONOMY_RATES = {
    "income_per_pop": 150.0,
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

# --- ECONOMÍA V4.1.3: CATEGORÍAS DE LUJO ---

LUXURY_DATA = {
    "metales": {
        "wolframio": {"base_price": 65, "name": "Wolframio"},
        "neodimio": {"base_price": 78, "name": "Neodimio"},
        "paladio": {"base_price": 92, "name": "Paladio"},
        "platino": {"base_price": 115, "name": "Platino"},
        "iridio": {"base_price": 138, "name": "Iridio"},
    },
    "componentes_avanzados": {
        "sensores_precision": {"base_price": 85, "name": "Sensores de Precisión"},
        "nanobots": {"base_price": 110, "name": "Nanobots"},
        "circuitos_cuanticos": {"base_price": 145, "name": "Circuitos Cuánticos"},
    },
    "energia_avanzada": {
        "cristales_foco": {"base_price": 82, "name": "Cristales de Foco"},
        "plasma_estable": {"base_price": 118, "name": "Plasma Estable"},
        "materia_oscura": {"base_price": 165, "name": "Materia Oscura"},
    },
    "influencia_superior": {
        "archivos_diplomaticos": {"base_price": 140, "name": "Archivos Diplomáticos"},
        "reliquias_culturales": {"base_price": 185, "name": "Reliquias Culturales"},
    },
    "datos_criticos": {
        "codigos_encriptacion": {"base_price": 72, "name": "Códigos de Encriptación"},
        "matrices_ai": {"base_price": 98, "name": "Matrices de IA"},
        "nucleos_datos": {"base_price": 132, "name": "Núcleos de Datos Crípticos"},
    },
}

# --- SECTORES Y GENERACIÓN V4.2.0 ---

SECTOR_TYPE_URBAN = "Urbano"
SECTOR_TYPE_PLAIN = "Llanura"
SECTOR_TYPE_MOUNTAIN = "Montañoso"
SECTOR_TYPE_INHOSPITABLE = "Inhospito"

VALID_SECTOR_TYPES = [
    SECTOR_TYPE_URBAN,
    SECTOR_TYPE_PLAIN,
    SECTOR_TYPE_MOUNTAIN,
    SECTOR_TYPE_INHOSPITABLE
]

# Probabilidad de aparición de recursos (Alta, Media, Baja, Nula)
RESOURCE_CHANCE_HIGH = 0.60
RESOURCE_CHANCE_MEDIUM = 0.30
RESOURCE_CHANCE_LOW = 0.10
RESOURCE_CHANCE_NONE = 0.0

MAX_SLOTS_PER_SECTOR = 3