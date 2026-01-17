# core/world_constants.py
"""
Constantes universales y definiciones de juego.
Incluye recursos, tipos de estrellas y definiciones de edificios/módulos.
"""

# Tipos de estrellas y sus colores para el mapa
STAR_TYPES = {
    "O": {"color": "#9bb0ff", "size": 1.2},
    "B": {"color": "#aabfff", "size": 1.1},
    "A": {"color": "#cad7ff", "size": 1.05},
    "F": {"color": "#f8f7ff", "size": 1.02},
    "G": {"color": "#fff4ea", "size": 1.0},
    "K": {"color": "#ffd2a1", "size": 0.95},
    "M": {"color": "#ffcc6f", "size": 0.9},
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
# Estos NO ocupan slots de construcción, tienen sus propios espacios fijos.
INFRASTRUCTURE_MODULES = {
    "sensor_ground": {
        "name": "Sensor Planetario", 
        "cost_base": 500,
        "desc": "Detecta incursiones terrestres y espías."
    },
    "sensor_orbital": {
        "name": "Sensor Orbital", 
        "cost_base": 500,
        "desc": "Detecta flotas en órbita y bloqueos."
    },
    "defense_aa": {
        "name": "Defensa Anti-Aérea", 
        "cost_base": 400,
        "desc": "Mitiga bombardeos y derriba cápsulas."
    },
    "defense_ground": {
        "name": "Defensa Terrestre", 
        "cost_base": 400,
        "desc": "Combate ejércitos invasores en superficie."
    },
    "defense_orbital": {
        "name": "Batería Orbital", 
        "cost_base": 1000, 
        "min_base_tier": 3,
        "desc": "Artillería superficie-espacio (Tier 3+)."
    }
}

# Edificios Construibles (Ocupan Slots)
BUILDING_TYPES = {
    "hq": {
        "name": "Comando Central",
        "material_cost": 0,
        "energy_cost": 0,
        "description": "Sede administrativa. Nivel 3 permite Multitasking.",
        "max_tier": 5,
        "pops_required": 0
    },
    "barracks": {
        "name": "Barracas",
        "material_cost": 300,
        "energy_cost": 2,
        "description": "Alojamiento militar. Aumenta límite de reclutas.",
        "pops_required": 50
    },
    "mine_basic": {
        "name": "Mina de Superficie",
        "material_cost": 150,
        "energy_cost": 5,
        "description": "Extracción básica de minerales locales.",
        "pops_required": 100
    },
    "solar_plant": {
        "name": "Planta Solar",
        "material_cost": 100,
        "energy_cost": 0,
        "description": "Generación de energía pasiva.",
        "pops_required": 20
    },
    "fusion_reactor": {
        "name": "Reactor de Fusión",
        "material_cost": 500,
        "energy_cost": 0,
        "description": "Generación masiva de energía (Tier 2).",
        "pops_required": 50,
        "min_tier": 2
    },
    "factory": {
        "name": "Fundición Industrial",
        "material_cost": 400,
        "energy_cost": 10,
        "description": "Procesa minerales en aleaciones.",
        "pops_required": 200
    }
}

BUILDING_SHUTDOWN_PRIORITY = {
    "extraccion": 4,
    "defensa": 3,
    "industria": 2,
    "tecnologia": 1
}

ECONOMY_RATES = {
    "income_per_pop": 0.1,
    "infrastructure_security_rate": 0.01,
    "security_min": 0.5,
    "security_max": 1.2,
    "happiness_bonus_max": 0.5
}

BROKER_PRICES = {
    "materiales": 10,
    "componentes": 25,
    "celulas_energia": 5
}