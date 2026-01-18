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
    # 1. Pilotaje y Vehículos
    "Piloteo de naves pequeñas": ("agilidad", "tecnica"),
    "Piloteo de naves medianas": ("tecnica", "intelecto"),
    "Piloteo de fragatas y capitales": ("intelecto", "voluntad"),
    "Maniobras evasivas espaciales": ("agilidad", "voluntad"),
    "Navegación en zonas peligrosas": ("intelecto", "voluntad"),
    # 2. Combate y Armamento
    "Armas de precisión": ("tecnica", "agilidad"),
    "Armas pesadas": ("fuerza", "tecnica"),
    "Combate cuerpo a cuerpo": ("fuerza", "agilidad"),
    "Tácticas de escuadra": ("intelecto", "voluntad"),
    "Combate defensivo": ("voluntad", "agilidad"),
    "Uso de drones de combate": ("tecnica", "intelecto"),
    # 3. Ingeniería y Tecnología
    "Reparación mecánica": ("tecnica", "fuerza"),
    "Reparación electrónica": ("tecnica", "intelecto"),
    "Hackeo de sistemas": ("intelecto", "tecnica"),
    "Sabotaje tecnológico": ("intelecto", "agilidad"),
    "Optimización de sistemas": ("intelecto", "voluntad"),
    "Interfaz con sistemas": ("tecnica", "intelecto"),
    # 4. Ciencia e Investigación
    "Investigación científica": ("intelecto", "tecnica"),
    "Recopilación de Información": ("intelecto", "voluntad"), # RENOMBRADO de 'Análisis de datos'
    "Ingeniería inversa": ("intelecto", "tecnica"),
    "Evaluación de amenazas": ("intelecto", "presencia"),
    # 5. Sigilo e Infiltración
    "Sigilo físico": ("agilidad", "voluntad"),
    "Infiltración urbana": ("agilidad", "intelecto"),
    "Evasión de sensores": ("tecnica", "intelecto"),
    "Movimiento silencioso": ("agilidad", "voluntad"),
    "Escape táctico": ("agilidad", "intelecto"),
    # 6. Diplomacia y Social
    "Persuasión": ("presencia", "intelecto"),
    "Engaño": ("presencia", "agilidad"),
    "Intimidación": ("presencia", "fuerza"),
    "Negociación": ("presencia", "voluntad"),
    "Liderazgo": ("presencia", "voluntad"),
    "Lectura emocional": ("presencia", "intelecto"),
    # 7. Comando y Estrategia
    "Planificación de misiones": ("intelecto", "voluntad"),
    "Coordinación de unidades": ("intelecto", "presencia"),
    "Gestión de recursos": ("intelecto", "tecnica"),
    "Toma de decisiones bajo presión": ("voluntad", "intelecto"),
    # 8. Supervivencia y Físico
    "Resistencia física": ("fuerza", "voluntad"),
    "Supervivencia en entornos hostiles": ("voluntad", "fuerza"),
    "Atletismo": ("fuerza", "agilidad"),
    "Orientación y exploración": ("intelecto", "agilidad")
}

# Unificado con Módulo 19.2: Pool de 60 puntos para un personaje Nivel 6 de inicio
POINTS_AVAILABLE_FOR_ATTRIBUTES: int = 60
ATTRIBUTE_SOFT_CAP: int = 15
ATTRIBUTE_COST_MULTIPLIER: int = 2