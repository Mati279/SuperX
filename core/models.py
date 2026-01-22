# core/models.py (Completo)
"""
Modelos de Dominio Tipados.
Define las estructuras de datos centrales del juego usando Pydantic
para garantizar validación y serialización consistente.
Refactorizado para cumplir con el esquema V2 Híbrido (SQL + JSON).
Actualizado v5.1.4: Estandarización de IDs de Roles (Fix Error 22P02).
Actualizado V4.3: Enums de Conocimiento y Secretos.
Corregido v5.1.5: Fix BiologicalSex Enum y defaults.
Refactor v5.2: Seguridad movida a tabla 'planets'.
"""

from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator
from enum import Enum
import copy

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
    CANDIDATE = "Candidato"

class BiologicalSex(str, Enum):
    MALE = "Masculino"
    FEMALE = "Femenino"
    ASEXUAL = "Asexual"

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
    """Niveles de conocimiento sobre un personaje (V4.3)."""
    UNKNOWN = "unknown"     # Bio superficial
    KNOWN = "known"         # Bio conocida + rasgos
    FRIEND = "friend"       # Bio profunda + secreto revelado


class SecretType(str, Enum):
    """Tipos de secretos revelables al alcanzar nivel 'amigo' (V4.3)."""
    PROFESSIONAL = "profesional"  # +XP fijo
    PERSONAL = "personal"         # +2 Voluntad
    CRITICAL = "critico"          # Misión personal

class MarketOrderStatus(str, Enum):
    """Estados de una orden de mercado."""
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

# --- SUB-MODELOS DE PERSONAJE (COMPOSICIÓN) ---

class CharacterBio(BaseModel):
    """Identificadores de Entidad y Biografía de 3 Niveles."""
    model_config = ConfigDict(extra='allow')
    nombre: str
    apellido: str
    edad: int = Field(default=30)
    # Corregido: Default válido para evitar AttributeError
    sexo: BiologicalSex = Field(default=BiologicalSex.MALE)
    
    # Biografía de 3 Capas (Consolidada v5.1.0)
    biografia_corta: str = Field(default="Sin biografía registrada.")
    bio_conocida: str = Field(default="Sin información adicional disponible.")
    bio_profunda: str = Field(default="Sin secretos registrados.")
    
    # Control de acceso interno (Legacy/JSON)
    nivel_acceso: str = Field(default="unknown")
    
    apariencia_visual: Optional[str] = Field(
        default=None, 
        description="Descripción visual inmutable y de alta densidad (ADN Visual) para generación de imágenes consistente."
    )

class CharacterTaxonomy(BaseModel):
    """Taxonomía Biológica y Evolutiva."""
    raza: str = Field(default="Humano")
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
    feats: List[Any] = Field(default_factory=list) # Cambiado a Any para soportar objetos complejos

class CharacterBehavior(BaseModel):
    """Perfiles de Comportamiento y Capas Sociales."""
    rasgos_personalidad: List[str] = Field(default_factory=list)
    relaciones: List[Dict[str, Any]] = Field(default_factory=list) # Lista de nodos de relación
    lealtad: int = Field(default=5, ge=0, le=100) # Inyectado desde SQL
    mision_personal_disponible: bool = False

class CharacterLogistics(BaseModel):
    """Logística y Equipamiento."""
    equipo: List[Dict[str, Any]] = Field(default_factory=list)
    slots_ocupados: int = 0
    slots_maximos: int = 10

class CharacterLocation(BaseModel):
    """Geolocalización Lógica."""
    # IDs Relacionales (Prioridad - Inyectados desde SQL)
    system_id: Optional[int] = None
    planet_id: Optional[int] = None
    sector_id: Optional[int] = None
    
    # Textos descriptivos (Legacy/UI)
    sistema_actual: str = "Desconocido"
    ubicacion_local: str = "Base Principal"
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
    Representa la estructura completa procesada (hidratada).
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
    datos: int = Field(default=0, ge=0)

    def to_dict(self) -> Dict[str, int]:
        return {
            "creditos": self.creditos,
            "materiales": self.materiales,
            "componentes": self.componentes,
            "celulas_energia": self.celulas_energia,
            "influencia": self.influencia,
            "datos": self.datos
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerResources':
        return cls(
            creditos=data.get("creditos", 0),
            materiales=data.get("materiales", 0),
            componentes=data.get("componentes", 0),
            celulas_energia=data.get("celulas_energia", 0),
            influencia=data.get("influencia", 0),
            datos=data.get("datos", 0)
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
    datos: int = 0
    recursos_lujo: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None

    @property
    def resources(self) -> PlayerResources:
        return PlayerResources(
            creditos=self.creditos,
            materiales=self.materiales,
            componentes=self.componentes,
            celulas_energia=self.celulas_energia,
            influencia=self.influencia,
            datos=self.datos
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerData':
        if not data:
            raise ValueError("No se puede crear PlayerData desde datos vacíos")
        return cls(**{k: v for k, v in data.items() if v is not None})


# --- MODELOS DE MERCADO ---

class MarketOrder(BaseModel):
    """Orden de compra/venta en el mercado galáctico."""
    model_config = ConfigDict(extra='allow')
    
    id: int
    player_id: int
    resource_type: str
    amount: int # Positivo = Compra, Negativo = Venta
    price_per_unit: int
    status: MarketOrderStatus = MarketOrderStatus.PENDING
    created_at_tick: int
    processed_at_tick: Optional[int] = None

    @property
    def total_value(self) -> int:
        return abs(self.amount) * self.price_per_unit

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketOrder':
        return cls(**data)


# --- MODELOS DE COMANDANTE / PERSONAJE (API V2 Híbrido) ---

class CommanderData(BaseModel):
    """
    Datos del comandante o personaje recuperados de la DB.
    Wrapper sobre la tabla 'characters' en modelo Híbrido Relacional/JSON.
    Refleja la 'Fuente de Verdad' en columnas SQL.
    """
    model_config = ConfigDict(extra='allow')

    # Identificadores SQL
    id: int
    player_id: Optional[int]
    nombre: str
    apellido: str = ""
    rango: str = "Comandante"
    es_comandante: bool = True
    is_npc: bool = False
    
    # Datos Relacionales Numéricos (Fuente de Verdad SQL)
    level: int = 1
    xp: int = 0
    class_id: int = 0
    loyalty: int = 50  # 0-100
    estado_id: int = 1  # 1=Disponible
    
    # Estandarización V5.1.4: rol es un ID entero en la DB.
    rol: Optional[Union[str, int]] = Field(default=0) 

    @field_validator('rol', mode='before')
    @classmethod
    def hydrate_role_id(cls, v: Any) -> str:
        """
        HIDRATACIÓN DE ROL: Convierte IDs enteros de la DB a strings del Enum CharacterRole.
        Mapeo Inverso al definido en el repositorio.
        """
        role_reverse_map = {
            0: "Sin Asignar",
            1: "Comandante",
            2: "Piloto",
            3: "Artillero",
            4: "Ingeniero",
            5: "Médico",
            6: "Científico",
            7: "Diplomático",
            8: "Infante"
        }
        if isinstance(v, int):
            return role_reverse_map.get(v, "Sin Asignar")
        if v is None: 
            return "Sin Asignar"
        return str(v)
    
    # Jerarquía de Ubicación (Fuente de Verdad SQL)
    location_system_id: Optional[int] = None
    location_planet_id: Optional[int] = None
    location_sector_id: Optional[int] = None
    
    # Legacy/Fallback (Se mantienen para UI simple)
    ubicacion: str = "Base Principal"
    estado: str = "Disponible"
    
    # Metadata
    portrait_url: Optional[str] = None
    recruited_at_tick: int = 0
    last_processed_tick: int = 0
    faccion_id: Optional[int] = None

    # JSON "lite" (Datos complejos no relacionales)
    stats_json: Dict[str, Any] = Field(default_factory=dict)

    @property
    def sheet(self) -> CharacterSchema:
        """
        Devuelve el esquema completo del personaje validado.
        REHIDRATA el JSON inyectando los valores de columnas SQL (Source of Truth).
        """
        try:
            full_stats = copy.deepcopy(self.stats_json)
            
            # Asegurar estructura mínima mediante bucle de inicialización
            for section in ["bio", "progresion", "estado", "comportamiento", "taxonomia", "capacidades", "logistica"]:
                if section not in full_stats:
                    full_stats[section] = {}
            
            if not full_stats["taxonomia"].get("raza"):
                full_stats["taxonomia"]["raza"] = "Humano"
            
            full_stats["bio"]["nombre"] = self.nombre
            full_stats["bio"]["apellido"] = self.apellido
            
            if "edad" not in full_stats["bio"]:
                full_stats["bio"]["edad"] = 30
            if "sexo" not in full_stats["bio"]:
                # Fallback seguro en caso de hidratación incorrecta
                full_stats["bio"]["sexo"] = "Masculino"
            
            full_stats["progresion"]["nivel"] = self.level
            full_stats["progresion"]["xp"] = self.xp
            full_stats["progresion"]["rango"] = self.rango
            
            if "clase" not in full_stats["progresion"]:
                full_stats["progresion"]["clase"] = "Desconocida"

            full_stats["comportamiento"]["lealtad"] = self.loyalty

            status_map = {1: "Disponible", 2: "En Misión", 3: "Herido", 4: "Fallecido", 5: "Entrenando", 6: "En Tránsito", 7: "Candidato", 99: "Retirado"}
            status_text = status_map.get(self.estado_id, "Disponible")
            
            full_stats["estado"]["estados_activos"] = [status_text]
            
            # Sincronización de rol operativo (ya hidratado por el validator)
            full_stats["estado"]["rol_asignado"] = self.rol if self.rol else "Sin Asignar"
            
            full_stats["estado"]["ubicacion"] = {
                "system_id": self.location_system_id,
                "planet_id": self.location_planet_id,
                "sector_id": self.location_sector_id,
                "ubicacion_local": self.ubicacion 
            }

            return CharacterSchema(**full_stats)

        except Exception as e:
            print(f"DEBUG - Error en Hidratación: {str(e)}")
            return CharacterSchema(
                bio=CharacterBio(nombre=self.nombre, apellido=self.apellido, edad=30, biografia_corta=f"Error Schema: {str(e)}"),
                taxonomia=CharacterTaxonomy(raza="Humano"),
                progresion=CharacterProgression(nivel=self.level, xp=self.xp),
                capacidades=CharacterCapabilities(),
                comportamiento=CharacterBehavior(lealtad=self.loyalty),
                logistica=CharacterLogistics(),
                estado=CharacterDynamicState()
            )

    @property
    def attributes(self) -> CharacterAttributes:
        """Acceso directo a atributos."""
        if "capacidades" in self.stats_json and "atributos" in self.stats_json["capacidades"]:
             return CharacterAttributes(**self.stats_json["capacidades"]["atributos"])
        if "atributos" in self.stats_json:
            return CharacterAttributes(**self.stats_json["atributos"])
        return CharacterAttributes()

    @property
    def nivel(self) -> int:
        return self.level

    @property
    def clase(self) -> str:
        if "progresion" in self.stats_json:
            return self.stats_json["progresion"].get("clase", "Novato")
        return "Novato"

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
        return cls(**{k: v for k, v in data.items() if k in cls.model_fields})


# --- MODELOS DE PLANETA Y EDIFICIOS ---

class PlanetAsset(BaseModel):
    """Activo planetario (colonia del jugador)."""
    model_config = ConfigDict(extra='allow')

    id: int
    planet_id: int
    system_id: int
    player_id: int
    nombre_asentamiento: str = "Colonia"
    poblacion: float = 0.0  # Población en Billones
    pops_activos: int = 0
    pops_desempleados: int = 0
    base_tier: int = Field(default=1, ge=1)
    # Refactor V5.2: Seguridad movida a tabla planets, eliminada de aquí.
    infraestructura_defensiva: int = 0

    # Infraestructura de Módulos
    module_sensor_ground: int = 0
    module_sensor_orbital: int = 0
    module_defense_aa: int = 0
    module_defense_ground: int = 0

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
    datos: int = 0

    def add(self, other: 'ProductionSummary') -> 'ProductionSummary':
        return ProductionSummary(
            materiales=self.materiales + other.materiales,
            componentes=self.componentes + other.componentes,
            celulas_energia=self.celulas_energia + other.celulas_energia,
            influencia=self.influencia + other.influencia,
            creditos=self.creditos + other.creditos,
            datos=self.datos + other.datos
        )

    def to_dict(self) -> Dict[str, int]:
        return {
            "materiales": self.materiales,
            "componentes": self.componentes,
            "celulas_energia": self.celulas_energia,
            "influencia": self.influencia,
            "creditos": self.creditos,
            "datos": self.datos
        }

# --- RESULTADOS DE OPERACIONES ---

class EconomyTickResult(BaseModel):
    """Resultado del procesamiento económico."""
    player_id: int
    total_income: int = 0
    production: ProductionSummary = Field(default_factory=ProductionSummary)
    maintenance_cost: Dict[str, int] = Field(default_factory=dict) # Costo total pagado
    buildings_disabled: List[int] = Field(default_factory=list)
    buildings_reactivated: List[int] = Field(default_factory=list)
    luxury_extracted: Dict[str, int] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    success: bool = True