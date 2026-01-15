# core/world_models.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class Star:
    """Representa una estrella en el centro de un sistema."""
    name: str
    type: str
    rarity: str
    energy_modifier: float
    special_rule: str
    class_type: str # G, O, M, D, X

@dataclass
class Moon:
    """Representa una luna orbitando un planeta."""
    id: int
    name: str
    # Futuro: podría tener su propio bioma o características especiales
    # base_slots: int = 1 

@dataclass
class CelestialBody:
    """Clase base para objetos en anillos orbitales."""
    name: str
    ring: int

@dataclass
class Planet(CelestialBody):
    """Representa un planeta en un anillo orbital."""
    id: int
    biome: str
    bonuses: str
    construction_slots: int
    maintenance_mod: float
    moons: List[Moon] = field(default_factory=list)

@dataclass
class AsteroidBelt(CelestialBody):
    """Representa un campo de asteroides en un anillo orbital."""
    id: int
    hazard_level: float # Nivel de peligro de 0.1 a 1.0
    # Futuro: podría tener una lista de recursos extraíbles
    # available_resources: List[str] = field(default_factory=list)

@dataclass
class System:
    """Representa un sistema estelar completo."""
    id: int
    name: str
    star: Star
    orbital_rings: Dict[int, Optional[CelestialBody]] = field(default_factory=dict) # Anillo -> Planeta/Asteroide/None
    position: tuple[int, int] = (0, 0) # Posición (x, y) en el mapa galáctico para el grafo

@dataclass
class Galaxy:
    """Representa la galaxia entera, un conjunto de sistemas."""
    systems: List[System] = field(default_factory=list)
    # Futuro: podría contener las conexiones del grafo para viajes inter-estelares
    # system_connections: Dict[int, List[int]] = field(default_factory=dict)
