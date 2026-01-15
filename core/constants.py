# core/constants.py
from typing import Dict, Any, Tuple

# --- Constantes de Creación de Personajes ---

RACES: Dict[str, Dict[str, Any]] = {
    "Humano": {"desc": "Versátiles y ambiciosos. Dominan la política galáctica.", "bonus": {"voluntad": 1}},
    "Cyborg": {"desc": "Humanos mejorados con implantes. Resistentes y fríos.", "bonus": {"tecnica": 1}},
    "Marciano": {"desc": "Nacidos en la baja gravedad roja. Ágiles pero frágiles.", "bonus": {"agilidad": 1}},
    "Selenita": {"desc": "Habitantes del lado oscuro de la luna. Misteriosos y pálidos.", "bonus": {"intelecto": 1}},
    "Androide": {"desc": "Inteligencia artificial en cuerpo sintético. Incansables.", "bonus": {"fuerza": 1}}
}

CLASSES: Dict[str, Dict[str, str]] = {
    "Soldado": {"desc": "Entrenado en armas y tácticas militares.", "bonus_attr": "fuerza"},
    "Piloto": {"desc": "Experto en navegación y combate vehicular.", "bonus_attr": "agilidad"},
    "Ingeniero": {"desc": "Maestro de la reparación y la tecnología.", "bonus_attr": "tecnica"},
    "Diplomático": {"desc": "La palabra es más fuerte que el láser.", "bonus_attr": "presencia"},
    "Espía": {"desc": "El arte del sigilo y el subterfugio.", "bonus_attr": "agilidad"},
    "Hacker": {"desc": "Domina el ciberespacio y los sistemas de seguridad.", "bonus_attr": "intelecto"}
}

# --- Constantes de Reglas del Juego ---

SKILL_MAPPING: Dict[str, Tuple[str, str]] = {
    "Combate Cercano": ("fuerza", "agilidad"),
    "Puntería": ("agilidad", "tecnica"),
    "Hacking": ("intelecto", "tecnica"),
    "Pilotaje": ("agilidad", "intelecto"),
    "Persuasión": ("presencia", "voluntad"),
    "Medicina": ("intelecto", "tecnica"),
    "Sigilo": ("agilidad", "presencia"),
    "Ingeniería": ("tecnica", "intelecto")
}

POINTS_AVAILABLE_FOR_ATTRIBUTES: int = 15
ATTRIBUTE_SOFT_CAP: int = 15
ATTRIBUTE_COST_MULTIPLIER: int = 2
