# core/models.py
"""
Modelos de Dominio Tipados.
Define las estructuras de datos centrales del juego usando Pydantic
para garantizar validación y serialización consistente.
Refactorizado para cumplir con el esquema V2 de Personajes.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


# --- ENUMS ---

class PlayerStatus(str, Enum):
    """Estados posibles de un jugador."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"

class CharacterStatus(str, Enum):
    """Estados dinámicos del personaje."""
    AVAILABLE = "Disponible"
    ON_MISSION = "En Misión"
    INJURED = "Herido"
    DECEASED = "Fallecido"
    TRAINING = "Entrenando"
    TRANSIT = "En Tránsito"
    CANDIDATE = "Candidato"  # <--- NUEVO ESTADO PARA RECLUTAMIENTO

class BiologicalSex(str, Enum):
    MALE = "Masculino"
    FEMALE = "Femenino"
    ANDROGYNOUS = "Andrógino"
    ASEXUAL = "Asexual"
    UNKNOWN = "Desconocido"

class CharacterRole(str, Enum):
    """Roles operativos asignables."""
    COMMANDER = "Comandante"
    PILOT = "Piloto"
    GUNNER = "Artillero"
    ENGINEER = "Ingeniero"
    MEDIC = "Médico"
    SCIENTIST = "Científico"
    DIPLOMAT = "Diplomático"
    MARINE = "Infante"
    NONE = "Sin Asignar"


class KnowledgeLevel(str, Enum):
    """Niveles de conocimiento sobre un personaje."""
    UNKNOWN = "desconocido"     # Bio superficial, sin rasgos de personalidad
    KNOWN = "conocido"          # Bio conocida + rasgos de personalidad
    FRIEND = "amigo"            # Bio profunda + secreto revelado


class SecretType(str, Enum):
    """Tipos de secretos revelables al alcanzar nivel 'amigo'."""
    PROFESSIONAL = "profesional"  # +XP fijo (mejor entrenamiento)
    PERSONAL = "personal"         # +2 Voluntad (se siente parte del equipo)
    CRITICAL = "critico"          # Misión personal (desarrollo futuro)

# --- SUB-MODELOS DE PERSONAJE (COMPOSICIÓN) ---

class CharacterBio(BaseModel):
    """Identificadores de Entidad."""
    model_config = ConfigDict(extra='allow')
    nombre: str
    apellido: str
    edad: int
    sexo: BiologicalSex = BiologicalSex.UNKNOWN
    biografia_corta: str = Field(default="Sin biografía registrada.")

class CharacterTaxonomy(BaseModel):
    """Taxonomía Biológica y Evolutiva."""
    raza: str
    transformaciones: List[str] = Field(default_factory=list)

class CharacterProgression(BaseModel):
    """Progresión y Jerarquía."""
    nivel: int = Field(default=1, ge=1)
    clase: str = Field(default="Novato")  # "Novato" para niveles 1-2
    xp: int = Field(default=0, ge=0)
    xp_next: int = Field(default=500)
    rango: str = Field(default="Recluta")

class CharacterAttributes(BaseModel):
    """
    Atributos Primarios.
    Alineados con SKILL_MAPPING en constants.py para cálculo de habilidades.
    """
    model_config = ConfigDict(extra='allow')
    fuerza: int = Field(default=5, ge=1, le=20)
    agilidad: int = Field(default=5, ge=1, le=20)
    tecnica: int = Field(default=5, ge=1, le=20)
    intelecto: int = Field(default=5, ge=1, le=20)
    voluntad: int = Field(default=5, ge=1, le=20)
    presencia: int = Field(default=5, ge=1, le=20)

class CharacterCapabilities(BaseModel):
    """Núcleo de Capacidades."""
    atributos: CharacterAttributes = Field(default_factory=CharacterAttributes)
    habilidades: Dict[str, int] = Field(default_factory=dict)
    feats: List[str] = Field(default_factory=list)

class CharacterBehavior(BaseModel):
    """Perfiles de Comportamiento y Capas Sociales."""
    rasgos_personalidad: List[str] = Field(default_factory=list)
    relaciones: List[Dict[str, Any]] = Field(default_factory=list) # Lista de nodos de relación

class CharacterLogistics(BaseModel):
    """Logística y Equipamiento."""
    equipo: List[Dict[str, Any]] = Field(default_factory=list)
    slots_ocupados: int = 0
    slots_maximos: int = 10

class CharacterLocation(BaseModel):
    """Geolocalización."""
    sistema_actual: str = "Desconocido"
    ubicacion_local: str = "Base Principal" # Planeta o Estación
    coordenadas: Optional[Dict[str, float]] = None

class CharacterDynamicState(BaseModel):
    """Estado Dinámico y Simulación."""
    estados_activos: List[str] = Field(default_factory=list) # Ej: "Herido", "Motivado"
    ubicacion: CharacterLocation = Field(default_factory=CharacterLocation)
    rol_asignado: CharacterRole = CharacterRole.NONE
    accion_actual: str = "Esperando órdenes"

class CharacterSchema(BaseModel):
    """
    ESQUEMA MAESTRO DEL PERSONAJE.
    Representa la estructura completa almacenada en 'stats_json'.
    """
    model_config = ConfigDict(extra='allow')
    
    bio: CharacterBio
    taxonomia: CharacterTaxonomy
    progresion: CharacterProgression
    capacidades: CharacterCapabilities
    comportamiento: CharacterBehavior
    logistica: CharacterLogistics
    estado: CharacterDynamicState


# --- MODELOS DE RECURSOS JUGADOR ---

class PlayerResources(BaseModel):
    """Recursos económicos del jugador."""
    creditos: int = Field(default=0, ge=0)
    materiales: int = Field(default=0, ge=0)
    componentes: int = Field(default=0, ge=0)
    celulas_energia: int = Field(default=0, ge=0)
    influencia: int = Field(default=0, ge=0)

    def to_dict(self) -> Dict[str, int]:
        return {
            "creditos": self.creditos,
            "materiales": self.materiales,
            "componentes": self.componentes,
            "celulas_energia": self.celulas_energia,
            "influencia": self.influencia
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerResources':
        return cls(
            creditos=data.get("creditos", 0),
            materiales=data.get("materiales", 0),
            componentes=data.get("componentes", 0),
            celulas_energia=data.get("celulas_energia", 0),
            influencia=data.get("influencia", 0)
        )


# --- MODELOS DE JUGADOR ---

class PlayerData(BaseModel):
    """Datos completos del jugador."""
    model_config = ConfigDict(extra='allow')

    id: int
    nombre: str
    faccion_nombre: Optional[str] = None
    banner_url: Optional[str] = None
    session_token: Optional[str] = None
    creditos: int = 0
    materiales: int = 0
    componentes: int = 0
    celulas_energia: int = 0
    influencia: int = 0
    recursos_lujo: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None

    @property
    def resources(self) -> PlayerResources:
        return PlayerResources(
            creditos=self.creditos,
            materiales=self.materiales,
            componentes=self.componentes,
            celulas_energia=self.celulas_energia,
            influencia=self.influencia
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerData':
        if not data:
            raise ValueError("No se puede crear PlayerData desde datos vacíos")
        return cls(**{k: v for k, v in data.items() if v is not None})


# --- MODELOS DE COMANDANTE / PERSONAJE (API) ---

class CommanderData(BaseModel):
    """
    Datos del comandante o personaje recuperados de la DB.
    Actúa como wrapper sobre la tabla 'characters'.
    """
    model_config = ConfigDict(extra='allow')

    id: int
    player_id: int
    nombre: str
    rango: str = "Comandante"
    es_comandante: bool = True
    ubicacion: str = "Base Principal" # Columna DB legacy/sync
    estado: str = "Disponible" # Columna DB legacy/sync
    stats_json: Dict[str, Any] = Field(default_factory=dict)
    faccion_id: Optional[int] = None
    recruited_at_tick: int = 0 # <--- NUEVO CAMPO

    @property
    def sheet(self) -> CharacterSchema:
        """
        Devuelve el esquema completo del personaje validado.
        Si falla la validación (datos viejos), intenta migrar al vuelo o devuelve defecto.
        """
        try:
            return CharacterSchema(**self.stats_json)
        except Exception:
            # Fallback para datos antiguos o corruptos, intenta reconstruir un mínimo viable
            # Esto evita crashes si la DB tiene esquemas viejos
            return CharacterSchema(
                bio=CharacterBio(nombre=self.nombre, apellido="", edad=30, biografia_corta="Datos migrados"),
                taxonomia=CharacterTaxonomy(raza="Humano"),
                progresion=CharacterProgression(),
                capacidades=CharacterCapabilities(),
                comportamiento=CharacterBehavior(),
                logistica=CharacterLogistics(),
                estado=CharacterDynamicState()
            )

    @property
    def attributes(self) -> CharacterAttributes:
        """Acceso directo a atributos."""
        # Intenta obtener de la estructura nueva, fallback a la vieja si es necesario
        if "capacidades" in self.stats_json and "atributos" in self.stats_json["capacidades"]:
             return CharacterAttributes(**self.stats_json["capacidades"]["atributos"])
        # Fallback estructura vieja (directamente en raiz o bajo stats)
        if "atributos" in self.stats_json:
            return CharacterAttributes(**self.stats_json["atributos"])
        return CharacterAttributes()

    @property
    def nivel(self) -> int:
        if "progresion" in self.stats_json:
            return self.stats_json["progresion"].get("nivel", 1)
        return self.stats_json.get("nivel", 1)

    @property
    def clase(self) -> str:
        if "progresion" in self.stats_json:
            return self.stats_json["progresion"].get("clase", "Novato")
        return self.stats_json.get("clase", "Novato")

    def get_merit_points(self) -> int:
        """Calculate total merit points from all six attributes."""
        attrs = self.attributes
        return (
            attrs.fuerza + attrs.agilidad + attrs.tecnica +
            attrs.intelecto + attrs.voluntad + attrs.presencia
        )
    
    def get_ticks_in_service(self, current_tick: int) -> int:
        """Calcula cuántos ticks lleva en servicio."""
        return max(0, current_tick - self.recruited_at_tick)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommanderData':
        if not data:
            raise ValueError("No se puede crear CommanderData desde datos vacíos")
        return cls(**{k: v for k, v in data.items() if v is not None})


# --- MODELOS DE PLANETA Y EDIFICIOS ---

class PlanetAsset(BaseModel):
    """Activo planetario (colonia del jugador)."""
    model_config = ConfigDict(extra='allow')

    id: int
    planet_id: int
    system_id: int
    player_id: int
    nombre_asentamiento: str = "Colonia"
    poblacion: int = 0
    pops_activos: int = 0
    pops_desempleados: int = 0
    seguridad: float = 1.0
    infraestructura_defensiva: int = 0
    felicidad: float = 1.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlanetAsset':
        if not data:
            raise ValueError("No se puede crear PlanetAsset desde datos vacíos")
        return cls(**{k: v for k, v in data.items() if v is not None})


class Building(BaseModel):
    """Edificio construido en un planeta."""
    model_config = ConfigDict(extra='allow')

    id: int
    planet_asset_id: int
    player_id: int
    building_type: str
    building_tier: int = 1
    is_active: bool = True
    pops_required: int = 0
    energy_consumption: int = 0
    built_at_tick: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Building':
        if not data:
            raise ValueError("No se puede crear Building desde datos vacíos")
        return cls(**{k: v for k, v in data.items() if v is not None})


# --- MODELO DE PRODUCCIÓN ---

class ProductionSummary(BaseModel):
    """Resumen de producción."""
    materiales: int = 0
    componentes: int = 0
    celulas_energia: int = 0
    influencia: int = 0
    creditos: int = 0

    def add(self, other: 'ProductionSummary') -> 'ProductionSummary':
        return ProductionSummary(
            materiales=self.materiales + other.materiales,
            componentes=self.componentes + other.componentes,
            celulas_energia=self.celulas_energia + other.celulas_energia,
            influencia=self.influencia + other.influencia,
            creditos=self.creditos + other.creditos
        )

    def to_dict(self) -> Dict[str, int]:
        return {
            "materiales": self.materiales,
            "componentes": self.componentes,
            "celulas_energia": self.celulas_energia,
            "influencia": self.influencia,
            "creditos": self.creditos
        }

# --- RESULTADOS DE OPERACIONES ---

class EconomyTickResult(BaseModel):
    """Resultado del procesamiento económico."""
    player_id: int
    total_income: int = 0
    production: ProductionSummary = Field(default_factory=ProductionSummary)
    buildings_disabled: List[int] = Field(default_factory=list)
    buildings_reactivated: List[int] = Field(default_factory=list)
    luxury_extracted: Dict[str, int] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    success: bool = True