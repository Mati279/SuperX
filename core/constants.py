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

# Reglas de Costos y Límites
MIN_ATTRIBUTE_VALUE: int = 5
MAX_ATTRIBUTE_VALUE: int = 20
ATTRIBUTE_SOFT_CAP: int = 15     # A partir de aquí cuesta el doble
ATTRIBUTE_COST_MULTIPLIER: int = 2

# --- Constantes de Progresión de Personajes ---

# Tabla de XP requerido para cada nivel (acumulativo)
XP_TABLE: Dict[int, int] = {
    1: 0,
    2: 500,
    3: 1500,
    4: 3000,
    5: 5500,
    6: 9000,
    7: 13500,
    8: 19000,
    9: 25500,
    10: 33000,
    11: 42000,
    12: 52500,
    13: 64500,
    14: 78000,
    15: 93000,
    16: 110000,
    17: 129000,
    18: 150000,
    19: 173000,
    20: 200000
}

# Puntos de habilidad ganados por nivel
SKILL_POINTS_PER_LEVEL: int = 5

# Niveles en los que se gana un punto de atributo extra
ATTRIBUTE_POINT_LEVELS: Tuple[int, ...] = (3, 6, 9, 12, 15, 18)

# Niveles en los que se gana un feat
FEAT_LEVELS: Tuple[int, ...] = (1, 4, 8, 12, 16, 20)

# Atributos base para generación de personajes
BASE_ATTRIBUTE_MIN: int = 5
BASE_ATTRIBUTE_MAX: int = 12

# Pool de Feats disponibles con visibilidad
# Los feats físicos obvios son "visible: True"
AVAILABLE_FEATS: Tuple[Dict[str, Any], ...] = (
    # Feats físicos visibles
    {"nombre": "Tuerto", "visible": True, "desc": "Perdió un ojo en combate."},
    {"nombre": "Cicatrizado", "visible": True, "desc": "Rostro marcado por heridas."},
    {"nombre": "Imponente", "visible": True, "desc": "Físico intimidante."},
    {"nombre": "Brazo Cibernético", "visible": True, "desc": "Prótesis mecánica visible."},
    {"nombre": "Albino", "visible": True, "desc": "Piel y cabello sin pigmento."},
    # Feats no visibles (requieren conocer al personaje)
    {"nombre": "Liderazgo Táctico", "visible": False, "desc": "Talento natural para comandar."},
    {"nombre": "Reflejos Mejorados", "visible": False, "desc": "Reacciona más rápido que lo normal."},
    {"nombre": "Conexiones Políticas", "visible": False, "desc": "Tiene contactos en el gobierno."},
    {"nombre": "Mente Analítica", "visible": False, "desc": "Procesa información rápidamente."},
    {"nombre": "Memoria Eidética", "visible": False, "desc": "Recuerda todo lo que ve."},
    {"nombre": "Resistencia al Dolor", "visible": False, "desc": "Soporta heridas sin debilitarse."},
    {"nombre": "Instinto de Supervivencia", "visible": False, "desc": "Sabe cuándo retirarse."},
    {"nombre": "Mecánico Nato", "visible": False, "desc": "Repara cualquier cosa."},
    {"nombre": "Piloto Prodigio", "visible": False, "desc": "Vuela como si naciera en una nave."},
    {"nombre": "Negociador", "visible": False, "desc": "Siempre consigue un buen trato."},
    {"nombre": "Infiltrador", "visible": False, "desc": "Se mueve sin ser detectado."},
    {"nombre": "Tirador Experto", "visible": False, "desc": "Precisión letal con armas."},
)

# Pool de rasgos de personalidad
PERSONALITY_TRAITS: Tuple[str, ...] = (
    "Leal", "Ambicioso", "Cauteloso", "Temerario", "Calculador",
    "Compasivo", "Despiadado", "Honorable", "Pragmático", "Idealista",
    "Solitario", "Carismático", "Reservado", "Impulsivo", "Metódico",
    "Optimista", "Pesimista", "Curioso", "Disciplinado", "Rebelde",
    "Protector", "Vengativo", "Paciente", "Ansioso", "Estoico"
)