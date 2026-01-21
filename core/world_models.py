# core/world_models.py
"""
Modelos de datos para el universo de SuperX.
Define la jerarquía de cuerpos celestes, sectores y estructuras galácticas.
Actualizado v4.3.0: Soporte para Planetología Avanzada (Anillos, Masa y Sectores).
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

@dataclass
class Sector:
    """Modelo que representa un sector dentro de un planeta (V4.2.0)."""
    id: int
    planet_id: int
    type: str  # 'Urbano', 'Llanura', 'Montañoso', 'Inhospito'
    slots: int
    
    # Metadata opcional
    resource_type: Optional[str] = None
    buildings_count: int = 0
    explored_by: List[int] = field(default_factory=list) # IDs de jugadores
    owner_id: Optional[int] = None # ID del jugador dueño de la base/puesto
    has_outpost: bool = False
    is_known: bool = False # V4.3.0: Soporte para niebla de superficie
    
    def is_explored_by(self, player_id: int) -> bool:
        return player_id in self.explored_by

    def available_slots(self) -> int:
        return max(0, self.slots - self.buildings_count)

@dataclass
class CelestialBody:
    id: int
    name: str
    x: float = 0.0  # Coordenada relativa o global según contexto
    y: float = 0.0

@dataclass
class Star:
    # Representación simplificada de la estrella para el modelo
    class_type: str  # O, B, A, F, G, K, M
    color: str
    size: float
    energy_output: float

@dataclass
class Planet(CelestialBody):
    system_id: int = 0
    biome: str = "Desconocido"
    is_habitable: bool = False
    slots: int = 0
    resources: Dict[str, float] = field(default_factory=dict)
    
    # --- Actualización V4.3.0: Planetología Avanzada ---
    orbital_ring: int = 3 # Posición en el sistema (1-6)
    mass_class: str = "Estándar" # Enano, Estándar, Grande, Gigante
    max_sectors: int = 4 # Capacidad física de subdivisiones
    is_known: bool = False # Niebla de guerra a nivel planeta
    
    # --- Actualización V4.2.0: Sectores y Control ---
    sectors: List[Sector] = field(default_factory=list)
    orbital_owner_id: Optional[int] = None
    surface_owner_id: Optional[int] = None
    is_disputed: bool = False
    
    # Referencias auxiliares
    base_defense: int = 0
    population: int = 0

    def get_urban_sector(self) -> Optional[Sector]:
        """Retorna el primer sector urbano encontrado."""
        for sector in self.sectors:
            if sector.type == 'Urbano':
                return sector
        return None

    def get_sectors_owned_by(self, player_id: int) -> List[Sector]:
        """Retorna sectores donde el jugador tiene presencia (Base o Puesto)."""
        return [s for s in self.sectors if s.owner_id == player_id]

    @property
    def total_sector_slots(self) -> int:
        """Suma de slots de todos los sectores."""
        return sum(s.slots for s in self.sectors)

    @property
    def used_sector_slots(self) -> int:
        """Suma de slots usados en todos los sectores."""
        return sum(s.buildings_count for s in self.sectors)

@dataclass
class Moon(CelestialBody):
    planet_id: int = 0

@dataclass
class AsteroidBelt(CelestialBody):
    system_id: int = 0
    density: float = 1.0

@dataclass
class System:
    id: int
    name: str
    x: float
    y: float
    star: Star
    planets: List[Planet] = field(default_factory=list)
    neighbors: List[int] = field(default_factory=list)
    description: str = ""
    controlling_faction_id: Optional[int] = None

@dataclass
class Galaxy:
    systems: List[System] = field(default_factory=list)
    starlanes: List[Tuple[int, int]] = field(default_factory=list) 
    
    def get_system_by_id(self, system_id: int) -> Optional[System]:
        for sys in self.systems:
            if sys.id == system_id:
                return sys
        return None