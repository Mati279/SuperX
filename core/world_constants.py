# core/world_constants.py
from typing import Dict, Any

# --- Clasificación Estelar y sus Efectos ---
STAR_TYPES: Dict[str, Dict[str, Any]] = {
    "Enana Amarilla (G)": {
        "rarity": "Común",
        "energy_modifier": 0.0,
        "special_rule": "Estabilidad máxima; sin penalizaciones.",
        "class": "G"
    },
    "Gigante Azul (O)": {
        "rarity": "Rara",
        "energy_modifier": 0.50,
        "special_rule": "Radiación Alta: Daño gradual a escudos de naves en órbita.",
        "class": "O"
    },
    "Enana Roja (M)": {
        "rarity": "Muy Común",
        "energy_modifier": -0.25,
        "special_rule": "Zona de Habitabilidad Estrecha: Menos planetas terrestres.",
        "class": "M"
    },
    "Enana Blanca (D)": {
        "rarity": "Rara",
        "energy_modifier": 0.10,
        "special_rule": "Gravedad Densa: +20% coste de combustible para salir del sistema.",
        "class": "D"
    },
    "Agujero Negro / Pulsar": {
        "rarity": "Única",
        "energy_modifier": -0.75,
        "special_rule": "Distorsión: Escaneo de largo alcance reducido; recursos exóticos.",
        "class": "X" # Clase exótica
    }
}

# Probabilidades de aparición de estrellas (deben sumar 100)
STAR_RARITY_WEIGHTS = {
    "Enana Amarilla (G)": 45,
    "Gigante Azul (O)": 5,
    "Enana Roja (M)": 35,
    "Enana Blanca (D)": 10,
    "Agujero Negro / Pulsar": 5,
}

# --- Taxonomía Planetaria y sus Efectos ---
PLANET_BIOMES: Dict[str, Dict[str, Any]] = {
    "Terrestre (Gaya)": {
        "bonuses": "Equilibrio perfecto. Bono a producción de alimentos/biomasa.",
        "construction_slots": 5, # Estándar
        "maintenance_mod": 0.0
    },
    "Desértico": {
        "bonuses": "Escasez de agua. Bono a extracción de minerales pesados.",
        "construction_slots": 5,
        "maintenance_mod": 0.0
    },
    "Oceánico": {
        "bonuses": "Dificultad de construcción. Bono a investigación científica.",
        "construction_slots": 3, # Penalización por dificultad
        "maintenance_mod": 0.0
    },
    "Volcánico": {
        "bonuses": "Peligro ambiental. Bono masivo a energía térmica.",
        "construction_slots": 5,
        "maintenance_mod": 0.20 # Coste extra de mantenimiento
    },
    "Gélido": {
        "bonuses": "Consumo extra de energía. Bono a almacenamiento de datos y computación fría.",
        "construction_slots": 5,
        "maintenance_mod": 0.10 # Mantenimiento por calefacción
    },
    "Gigante Gaseoso": {
        "bonuses": "No colonizable en superficie. Requiere Estaciones Orbitales para extraer Helio-3.",
        "construction_slots": 0, # No hay superficie
        "maintenance_mod": 0.0
    }
}

# --- Anatomía de un Sistema Orbital ---
ORBITAL_ZONES = {
    "Caliente": {
        "rings": (1, 2, 3),
        "planet_weights": {
            "Terrestre (Gaya)": 5, "Desértico": 40, "Oceánico": 0,
            "Volcánico": 45, "Gélido": 0, "Gigante Gaseoso": 10
        }
    },
    "Habitable": {
        "rings": (4, 5, 6),
        "planet_weights": {
            "Terrestre (Gaya)": 50, "Desértico": 20, "Oceánico": 20,
            "Volcánico": 5, "Gélido": 5, "Gigante Gaseoso": 0
        }
    },
    "Fría": {
        "rings": (7, 8, 9),
        "planet_weights": {
            "Terrestre (Gaya)": 0, "Desértico": 5, "Oceánico": 5,
            "Volcánico": 0, "Gélido": 40, "Gigante Gaseoso": 50
        }
    }
}

# Probabilidad de que un anillo orbital contenga un campo de asteroides en lugar de un planeta.
ASTEROID_BELT_CHANCE = 0.15 # 15%

# --- Constantes de Navegación ---
PROPULSION_FACTOR = 0.5 # Factor estándar para UTV (Unidades de Tiempo de Viaje)

# --- Constantes de Infraestructura ---
BASE_CLASSES: Dict[str, Dict[str, Any]] = {
    "Puesto de Avanzada": {"size": "Pequeña", "module_capacity": 2, "function": "Vigilancia y reabastecimiento."},
    "Hub Comercial": {"size": "Mediana", "module_capacity": 5, "function": "Generación de Créditos y mercado."},
    "Ciudadela Militar": {"size": "Grande", "module_capacity": 10, "function": "Astilleros pesados y defensa orbital."},
    "Matriz Científica": {"size": "Mediana", "module_capacity": 4, "function": "Investigación y escaneo profundo."}
}

# --- Recursos metálicos ---
# Cinco metales reales y tres ficticios (muy raros e inestables)
METAL_RESOURCES: Dict[str, Dict[str, Any]] = {
    "Hierro": {"rarity": "Comun", "stability": "Estable"},
    "Cobre": {"rarity": "Comun", "stability": "Estable"},
    "Niquel": {"rarity": "Poco comun", "stability": "Estable"},
    "Titanio": {"rarity": "Poco comun", "stability": "Estable"},
    "Platino": {"rarity": "Raro", "stability": "Estable"},
    "Oricalco Oscuro": {"rarity": "Muy raro", "stability": "Inestable"},
    "Neutrilium": {"rarity": "Muy raro", "stability": "Inestable"},
    "Aetherion": {"rarity": "Extremo", "stability": "Volatil"},
}

# Probabilidades relativas de cada recurso segun clase estelar
# (se normalizan al asignar recursos a planetas)
RESOURCE_STAR_WEIGHTS: Dict[str, Dict[str, int]] = {
    "G": {
        "Hierro": 30,
        "Cobre": 25,
        "Niquel": 18,
        "Titanio": 15,
        "Platino": 8,
        "Oricalco Oscuro": 3,
        "Neutrilium": 1,
        "Aetherion": 0,
    },
    "O": {
        "Hierro": 20,
        "Cobre": 10,
        "Niquel": 20,
        "Titanio": 20,
        "Platino": 15,
        "Oricalco Oscuro": 7,
        "Neutrilium": 5,
        "Aetherion": 3,
    },
    "M": {
        "Hierro": 35,
        "Cobre": 30,
        "Niquel": 15,
        "Titanio": 10,
        "Platino": 5,
        "Oricalco Oscuro": 2,
        "Neutrilium": 1,
        "Aetherion": 0,
    },
    "D": {
        "Hierro": 25,
        "Cobre": 15,
        "Niquel": 20,
        "Titanio": 15,
        "Platino": 10,
        "Oricalco Oscuro": 7,
        "Neutrilium": 5,
        "Aetherion": 3,
    },
    "X": {
        "Hierro": 10,
        "Cobre": 8,
        "Niquel": 10,
        "Titanio": 10,
        "Platino": 10,
        "Oricalco Oscuro": 12,
        "Neutrilium": 12,
        "Aetherion": 18,
    },
}

# --- MMFR: Recursos Tier 2 (Lujo) ---
# No se compran en el mercado. Se extraen de planetas especiales.
LUXURY_RESOURCES: Dict[str, Dict[str, Any]] = {
    # Categoría: Materiales Avanzados
    "superconductores": {
        "category": "materiales_avanzados",
        "name": "Superconductores",
        "description": "Materiales de resistencia cero. Esenciales para motores de salto.",
        "extraction_difficulty": "Media"
    },
    "aleaciones_exoticas": {
        "category": "materiales_avanzados",
        "name": "Aleaciones Exóticas",
        "description": "Metales imposibles de sintetizar. Base de cascos de naves pesadas.",
        "extraction_difficulty": "Alta"
    },
    "nanotubos_carbono": {
        "category": "materiales_avanzados",
        "name": "Nanotubos de Carbono",
        "description": "Estructuras microscópicas ultra-resistentes.",
        "extraction_difficulty": "Media"
    },

    # Categoría: Componentes Avanzados
    "reactores_fusion": {
        "category": "componentes_avanzados",
        "name": "Reactores de Fusión",
        "description": "Núcleos energéticos compactos. Permiten naves capitales.",
        "extraction_difficulty": "Muy Alta"
    },
    "chips_cuanticos": {
        "category": "componentes_avanzados",
        "name": "Chips Cuánticos",
        "description": "Procesadores de última generación. Necesarios para IA avanzada.",
        "extraction_difficulty": "Alta"
    },
    "sistemas_armamento": {
        "category": "componentes_avanzados",
        "name": "Sistemas de Armamento",
        "description": "Plataformas de armas listas para integrar.",
        "extraction_difficulty": "Alta"
    },

    # Categoría: Energía Avanzada
    "antimateria": {
        "category": "energia_avanzada",
        "name": "Antimateria",
        "description": "Combustible definitivo. Extremadamente peligrosa.",
        "extraction_difficulty": "Extrema"
    },
    "cristales_energeticos": {
        "category": "energia_avanzada",
        "name": "Cristales Energéticos",
        "description": "Almacenan energía masiva en forma sólida.",
        "extraction_difficulty": "Alta"
    },
    "helio3": {
        "category": "energia_avanzada",
        "name": "Helio-3",
        "description": "Isótopo limpio extraído de gigantes gaseosos.",
        "extraction_difficulty": "Media"
    },

    # Categoría: Influencia Avanzada
    "data_encriptada": {
        "category": "influencia_avanzada",
        "name": "Data Encriptada",
        "description": "Información clasificada de valor incalculable.",
        "extraction_difficulty": "Alta"
    },
    "artefactos_antiguos": {
        "category": "influencia_avanzada",
        "name": "Artefactos de Precursores",
        "description": "Tecnología alienígena perdida.",
        "extraction_difficulty": "Extrema"
    },
    "cultura_galactica": {
        "category": "influencia_avanzada",
        "name": "Puntos de Cultura Galáctica",
        "description": "Representación abstracta del soft power.",
        "extraction_difficulty": "Media"
    }
}

# --- MMFR: Economía de Recursos Base ---
# Precios del Broker Galáctico (Mercado NPC)
BROKER_PRICES: Dict[str, int] = {
    "materiales": 2,      # 2 CI por unidad
    "componentes": 5,     # 5 CI por unidad
    "celulas_energia": 3, # 3 CI por unidad
    "influencia": 10      # 10 CI por unidad (más cara)
}

# Tasas económicas
ECONOMY_RATES = {
    "income_per_pop": 0.5,        # CI generados por POP por turno (base)
    "security_min": 0.3,          # Multiplicador mínimo si seguridad es 0
    "security_max": 1.2,          # Multiplicador máximo si seguridad es 100+
    "happiness_bonus_max": 0.5,   # +50% de ingresos con felicidad al máximo
    "infrastructure_security_rate": 0.01  # Cada punto de infraestructura = +1% seguridad
}

# --- MMFR: Edificios Planetarios ---
BUILDING_TYPES: Dict[str, Dict[str, Any]] = {
    # === EXTRACCIÓN BASE ===
    "extractor_materiales": {
        "name": "Extractor de Materiales",
        "tier": 1,
        "category": "extraccion",
        "pops_required": 100,
        "energy_cost": 5,
        "construction_cost": {"creditos": 500, "componentes": 10},
        "production": {"materiales": 20},
        "description": "Mina básica de recursos minerales."
    },
    "extractor_componentes": {
        "name": "Fábrica de Componentes",
        "tier": 1,
        "category": "extraccion",
        "pops_required": 150,
        "energy_cost": 10,
        "construction_cost": {"creditos": 800, "materiales": 50},
        "production": {"componentes": 10},
        "description": "Ensambla componentes mecánicos básicos."
    },
    "generador_energia": {
        "name": "Planta de Energía",
        "tier": 1,
        "category": "extraccion",
        "pops_required": 80,
        "energy_cost": 0,  # Produce energía, no consume
        "construction_cost": {"creditos": 1000, "materiales": 30, "componentes": 20},
        "production": {"celulas_energia": 50},
        "description": "Reactor de fusión básico."
    },
    "centro_influencia": {
        "name": "Centro de Relaciones",
        "tier": 1,
        "category": "extraccion",
        "pops_required": 50,
        "energy_cost": 3,
        "construction_cost": {"creditos": 600, "componentes": 5},
        "production": {"influencia": 2},
        "description": "Genera influencia política mediante diplomacia."
    },

    # === INDUSTRIA PESADA ===
    "fundicion_avanzada": {
        "name": "Fundición Avanzada",
        "tier": 2,
        "category": "industria_pesada",
        "pops_required": 250,
        "energy_cost": 20,
        "construction_cost": {"creditos": 2000, "materiales": 100, "componentes": 50},
        "production": {"materiales": 50},
        "description": "Procesamiento industrial a gran escala."
    },
    "astillero_ligero": {
        "name": "Astillero Ligero",
        "tier": 2,
        "category": "industria_pesada",
        "pops_required": 300,
        "energy_cost": 30,
        "construction_cost": {"creditos": 5000, "materiales": 200, "componentes": 100},
        "production": {},  # No produce recursos base, se usa para construir naves
        "description": "Construye naves pequeñas y medianas."
    },

    # === ALTA TECNOLOGÍA ===
    "laboratorio_investigacion": {
        "name": "Laboratorio de Investigación",
        "tier": 3,
        "category": "alta_tecnologia",
        "pops_required": 200,
        "energy_cost": 25,
        "construction_cost": {"creditos": 8000, "materiales": 150, "componentes": 200},
        "production": {},  # Genera puntos de investigación (sistema futuro)
        "description": "Acelera el desarrollo tecnológico."
    },

    # === INFRAESTRUCTURA DEFENSIVA ===
    "bunker_defensa": {
        "name": "Búnker de Defensa",
        "tier": 1,
        "category": "defensa",
        "pops_required": 50,
        "energy_cost": 5,
        "construction_cost": {"creditos": 1500, "materiales": 80, "componentes": 30},
        "production": {},
        "defense_value": 10,  # Añade 10 puntos de infraestructura defensiva
        "description": "Fortificación básica. Mejora la seguridad del planeta."
    },
    "escudo_planetario": {
        "name": "Escudo Planetario",
        "tier": 3,
        "category": "defensa",
        "pops_required": 100,
        "energy_cost": 50,
        "construction_cost": {"creditos": 10000, "materiales": 300, "componentes": 500},
        "production": {},
        "defense_value": 30,
        "description": "Campo de fuerza avanzado. Protección contra bombardeos."
    }
}

# Prioridades de desactivación (orden inverso: se desactivan primero los de mayor prioridad)
BUILDING_SHUTDOWN_PRIORITY = {
    "alta_tecnologia": 1,    # Se desactivan primero
    "industria_pesada": 2,
    "defensa": 3,
    "extraccion": 4          # Se desactivan al final (críticos)
}
