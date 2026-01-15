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
