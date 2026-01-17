# core/models.py
"""
Modelos de Dominio Tipados.
Define las estructuras de datos centrales del juego usando Pydantic
para garantizar validación y serialización consistente.
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
    """Estados posibles de un personaje."""
    AVAILABLE = "Disponible"
    ON_MISSION = "En Misión"
    INJURED = "Herido"
    DECEASED = "Fallecido"


class CharacterClass(str, Enum):
    """Clases de personajes disponibles."""
    OPERACIONES = "Operaciones"
    CIENCIA = "Ciencia"
    INGENIERIA = "Ingeniería"
    TACTICO = "Táctico"
    DIPLOMATICO = "Diplomático"
    EXPLORADOR = "Explorador"


# --- MODELOS DE ATRIBUTOS ---

class CharacterAttributes(BaseModel):
    """Atributos base de un personaje."""
    model_config = ConfigDict(extra='allow')

    fuerza: int = Field(default=5, ge=1, le=20, description="Fuerza física")
    destreza: int = Field(default=5, ge=1, le=20, description="Agilidad y reflejos")
    constitucion: int = Field(default=5, ge=1, le=20, description="Resistencia física")
    inteligencia: int = Field(default=5, ge=1, le=20, description="Capacidad analítica")
    sabiduria: int = Field(default=5, ge=1, le=20, description="Percepción y juicio")
    carisma: int = Field(default=5, ge=1, le=20, description="Liderazgo y persuasión")


class CharacterStats(BaseModel):
    """Estadísticas completas de un personaje."""
    model_config = ConfigDict(extra='allow')

    nivel: int = Field(default=1, ge=1)
    xp: int = Field(default=0, ge=0)
    xp_next: int = Field(default=100, ge=0)
    atributos: CharacterAttributes = Field(default_factory=CharacterAttributes)
    habilidades: Dict[str, int] = Field(default_factory=dict)
    talentos: List[str] = Field(default_factory=list)


# --- MODELOS DE RECURSOS ---

class PlayerResources(BaseModel):
    """Recursos económicos del jugador."""
    creditos: int = Field(default=0, ge=0, description="Créditos Imperiales")
    materiales: int = Field(default=0, ge=0, description="Materiales base")
    componentes: int = Field(default=0, ge=0, description="Componentes manufacturados")
    celulas_energia: int = Field(default=0, ge=0, description="Células de energía")
    influencia: int = Field(default=0, ge=0, description="Influencia política")

    def to_dict(self) -> Dict[str, int]:
        """Convierte a diccionario para actualizaciones de DB."""
        return {
            "creditos": self.creditos,
            "materiales": self.materiales,
            "componentes": self.componentes,
            "celulas_energia": self.celulas_energia,
            "influencia": self.influencia
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerResources':
        """Crea instancia desde diccionario de DB."""
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
        """Obtiene los recursos como objeto tipado."""
        return PlayerResources(
            creditos=self.creditos,
            materiales=self.materiales,
            componentes=self.componentes,
            celulas_energia=self.celulas_energia,
            influencia=self.influencia
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerData':
        """Crea instancia desde diccionario de DB (maneja claves faltantes)."""
        if not data:
            raise ValueError("No se puede crear PlayerData desde datos vacíos")
        return cls(**{k: v for k, v in data.items() if v is not None})


# --- MODELOS DE COMANDANTE ---

class CommanderData(BaseModel):
    """Datos del comandante (personaje principal del jugador)."""
    model_config = ConfigDict(extra='allow')

    id: int
    player_id: int
    nombre: str
    rango: str = "Comandante"
    es_comandante: bool = True
    clase: str = "Operaciones"
    nivel: int = 1
    xp: int = 0
    ubicacion: str = "Puesto de Mando"
    estado: str = "Disponible"
    stats_json: Dict[str, Any] = Field(default_factory=dict)
    faccion_id: Optional[int] = None

    @property
    def stats(self) -> CharacterStats:
        """Obtiene las estadísticas como objeto tipado."""
        return CharacterStats(**self.stats_json) if self.stats_json else CharacterStats()

    @property
    def attributes(self) -> CharacterAttributes:
        """Acceso directo a atributos."""
        return self.stats.atributos

    def get_merit_points(self) -> int:
        """Calcula los puntos de mérito totales (suma de atributos)."""
        attrs = self.attributes
        return (
            attrs.fuerza + attrs.destreza + attrs.constitucion +
            attrs.inteligencia + attrs.sabiduria + attrs.carisma
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommanderData':
        """Crea instancia desde diccionario de DB."""
        if not data:
            raise ValueError("No se puede crear CommanderData desde datos vacíos")
        return cls(**{k: v for k, v in data.items() if v is not None})


# --- MODELOS DE PLANETA ---

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
        """Crea instancia desde diccionario de DB."""
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
        """Crea instancia desde diccionario de DB."""
        if not data:
            raise ValueError("No se puede crear Building desde datos vacíos")
        return cls(**{k: v for k, v in data.items() if v is not None})


# --- MODELO DE PRODUCCIÓN ---

class ProductionSummary(BaseModel):
    """Resumen de producción de un planeta o jugador."""
    materiales: int = 0
    componentes: int = 0
    celulas_energia: int = 0
    influencia: int = 0
    creditos: int = 0

    def add(self, other: 'ProductionSummary') -> 'ProductionSummary':
        """Suma dos resúmenes de producción."""
        return ProductionSummary(
            materiales=self.materiales + other.materiales,
            componentes=self.componentes + other.componentes,
            celulas_energia=self.celulas_energia + other.celulas_energia,
            influencia=self.influencia + other.influencia,
            creditos=self.creditos + other.creditos
        )

    def to_dict(self) -> Dict[str, int]:
        """Convierte a diccionario."""
        return {
            "materiales": self.materiales,
            "componentes": self.componentes,
            "celulas_energia": self.celulas_energia,
            "influencia": self.influencia,
            "creditos": self.creditos
        }


# --- RESULTADOS DE OPERACIONES ---

class EconomyTickResult(BaseModel):
    """Resultado del procesamiento económico de un jugador."""
    player_id: int
    total_income: int = 0
    production: ProductionSummary = Field(default_factory=ProductionSummary)
    buildings_disabled: List[int] = Field(default_factory=list)
    buildings_reactivated: List[int] = Field(default_factory=list)
    luxury_extracted: Dict[str, int] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    success: bool = True
