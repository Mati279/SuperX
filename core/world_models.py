from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional

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
    # Nuevo: Lista de IDs de sistemas conectados
    neighbors: List[int] = field(default_factory=list) 

@dataclass
class Galaxy:
    systems: List[System] = field(default_factory=list)
    # Nuevo: Lista de tuplas (id_origen, id_destino) representando las conexiones
    starlanes: List[Tuple[int, int]] = field(default_factory=list) 
    
    def get_system_by_id(self, system_id: int) -> Optional[System]:
        for sys in self.systems:
            if sys.id == system_id:
                return sys
        return None