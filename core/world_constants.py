# core/world_constants.py
"""
Constantes universales y definiciones de juego.
Incluye recursos, tipos de estrellas y definiciones de edificios/módulos.
"""

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

# Biomas planetarios para generacion procedural
PLANET_BIOMES = {
    "Desertico": {"bonuses": {"materiales": 1}, "construction_slots": 4, "maintenance_mod": 1.2},
    "Oceanico": {"bonuses": {"energia": 1}, "construction_slots": 3, "maintenance_mod": 1.0},
    "Templado": {"bonuses": {"poblacion": 1}, "construction_slots": 6, "maintenance_mod": 0.8},
    "Glacial": {"bonuses": {"componentes": 1}, "construction_slots": 3, "maintenance_mod": 1.3},
    "Volcanico": {"bonuses": {"materiales": 2}, "construction_slots": 2, "maintenance_mod": 1.5},
    "Toxico": {"bonuses": {"quimicos": 1}, "construction_slots": 2, "maintenance_mod": 1.8},
    "Gaseoso": {"bonuses": {"combustible": 2}, "construction_slots": 0, "maintenance_mod": 2.0},
    "Arido": {"bonuses": {}, "construction_slots": 4, "maintenance_mod": 1.1},
}

# Configuracion de zonas orbitales
ORBITAL_ZONES = {
    "inner": {
        "rings": [1, 2],
        "planet_weights": {
            "Volcanico": 3, "Desertico": 2, "Toxico": 1, "Arido": 1,
            "Oceanico": 0, "Templado": 0, "Glacial": 0, "Gaseoso": 0
        }
    },
    "habitable": {
        "rings": [3, 4],
        "planet_weights": {
            "Templado": 4, "Oceanico": 3, "Desertico": 2, "Arido": 2,
            "Volcanico": 0, "Toxico": 0, "Glacial": 1, "Gaseoso": 0
        }
    },
    "outer": {
        "rings": [5, 6],
        "planet_weights": {
            "Glacial": 3, "Gaseoso": 4, "Arido": 2, "Toxico": 1,
            "Volcanico": 0, "Desertico": 0, "Oceanico": 0, "Templado": 0
        }
    },
}

# Probabilidad de cinturon de asteroides
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

# Recursos metálicos (para generación de planetas y filtros de mapa)
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

# Costos para ascender el Tier de la Base Principal
BASE_TIER_COSTS = {
    2: {"creditos": 2000, "materiales": 1000},
    3: {"creditos": 5000, "materiales": 2500, "tecnologia": "Expansión Modular"},
    4: {"creditos": 10000, "materiales": 5000, "tecnologia": "Citadela Planetaria"}
}

# Módulos de Infraestructura (Sensores y Defensas)
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

# Edificios Construibles (Ocupan Slots)
# 'maintenance' define el costo POR TURNO para operar.
# Si no se paga, el edificio se desactiva (is_active=False).
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
        "maintenance": {"creditos": 50, "materiales": 10}, # Requiere 'combustible' (materiales)
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

# Prioridad de apagado (Mayor número = Se apaga primero)
BUILDING_SHUTDOWN_PRIORITY = {
    "extraccion": 4,
    "industria": 3,
    "tecnologia": 2,
    "defensa": 1,
    "energia": 0, # Energía es vital, se intenta mantener hasta el final
    "administracion": 0
}

ECONOMY_RATES = {
    # Actualizado para escala de Población 1.0 - 10.0 (1.0 = 1B Habitantes)
    "income_per_pop": 150.0, # Créditos por 1.0 de pop (antes 0.1 por unidad)
    
    # Valores base para cálculo de Seguridad (0-100)
    "security_base": 25.0,
    "security_per_1b_pop": 5.0, # +5 seguridad por cada 1.0 de pop (1B)
    
    # Bonus de infraestructura a la seguridad (puntos planos)
    "security_bonus_sensor": 2.0,
    "security_bonus_defense_aa": 5.0,
    "security_bonus_defense_ground": 5.0,
    "security_bonus_defense_orbital": 10.0
}

BROKER_PRICES = {
    "materiales": 10,
    "componentes": 25,
    "celulas_energia": 5
}