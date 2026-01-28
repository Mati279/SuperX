# core/world_models.py (Completo)
"""
Modelos de datos para el universo de SuperX.
Define la jerarquía de cuerpos celestes, sectores y estructuras galácticas.
Actualizado v4.8.1: Eliminación de recursos planetarios (migrados a Sectores).
Actualizado v4.8.2: Refactorización de Sector (max_slots, resource_category) y validación de tipos.
Refactorizado v5.3: Limpieza de redundancia 'slots' en Planeta. Fuente de verdad: total_sector_slots.
Actualizado v7.2: Soporte para Niebla de Superficie (is_explored_by_player).
Actualizado v7.8: Inclusión de nombres de soberanía (surface_owner_name, orbital_owner_name) para UI.
Actualizado v8.0: Soporte para Sectores Estelares (Control de Sistema y Megaestructuras).
Actualizado v9.1: Inclusión de Seguridad de Sistema (Promedio de planetas).
Refactorizado v23.2: Helper methods en Sector para edificios en construcción.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

@dataclass
class Sector:
    """
    Modelo que representa un sector dentro de un planeta o sistema (V4.2.0).
    Actualizado V8.0: Soporte para Sectores Estelares (system_id opcional).
    """
    id: int
    planet_id: Optional[int] = None  # V8.0: Ahora opcional (None para sectores estelares)
    system_id: Optional[int] = None  # V8.0: ID del sistema (para sectores estelares)
    type: str = "Desconocido"  # 'Urbano', 'Llanura', 'Montañoso', 'Inhospito', 'Orbital', 'Estelar'
    max_slots: int = 0  # Renombrado de slots a max_slots (V4.8.2)

    # Campos descriptivos
    name: str = "Sector Desconocido"  # Añadido para consistencia con generador

    # Metadata opcional
    resource_category: Optional[str] = None  # Renombrado de resource_type a resource_category (V4.8.2)
    luxury_resource: Optional[str] = None  # V4.3.0: Recurso de lujo específico

    # V8.0: Restricción de tipo de estrella para estructuras específicas
    required_star_class: Optional[str] = None  # 'O', 'B', 'A', 'K', etc.

    # Estado de construcción
    buildings: List[Dict[str, Any]] = field(default_factory=list)  # Lista de edificios instalados
    buildings_count: int = 0

    # Propiedad y Exploración
    explored_by: List[int] = field(default_factory=list)  # IDs de jugadores (Histórico/Lore)
    is_explored_by_player: bool = False  # V7.2: Flag dinámico para UI actual
    owner_id: Optional[int] = None  # ID del jugador dueño de la base/puesto
    has_outpost: bool = False
    is_known: bool = False  # V4.3.0: Soporte para niebla de superficie (Legacy/Global)

    def is_explored_by(self, player_id: int) -> bool:
        return player_id in self.explored_by or self.is_explored_by_player

    def available_slots(self) -> int:
        # Actualizado para usar max_slots
        return max(0, self.max_slots - self.buildings_count)

    def is_stellar(self) -> bool:
        """V8.0: Retorna True si es un sector estelar (nivel de sistema)."""
        return self.system_id is not None and self.planet_id is None
        
    def get_operational_buildings(self) -> List[Dict[str, Any]]:
        """
        V23.2: Retorna solo los edificios que están marcados como activos (ya construidos).
        Útil para UI que muestra producción.
        """
        return [b for b in self.buildings if b.get("is_active", True)]

    def get_constructing_buildings(self) -> List[Dict[str, Any]]:
        """
        V23.2: Retorna edificios en proceso de construcción (is_active=False).
        """
        return [b for b in self.buildings if not b.get("is_active", True)]

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
    # Refactor V5.3: Eliminado 'slots' redundante.
    # resources: Dict[str, float] eliminado en v4.8.1 - Ahora gestionado por Sector
    
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
    
    # --- Actualización V7.8: Nombres de Soberanía (UI) ---
    surface_owner_name: str = "Neutral"
    orbital_owner_name: str = "Neutral"
    
    # Referencias auxiliares y Stats (V4.8 - Actualizado para precisión decimal)
    base_defense: int = 0
    security: float = 0.0 # Valor calculado (0.0-100.0) - Actualizado a float
    population: float = 0.0 # Actualizado a float (Millones, ej: 1.50)

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
        """Suma de slots de todos los sectores. Actualizado V4.8.2."""
        return sum(s.max_slots for s in self.sectors)

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
    """
    Modelo que representa un sistema estelar.
    Actualizado V8.0: Soporte para Sectores Estelares (megaestructuras a nivel de sistema).
    Actualizado V9.1: Soporte para Seguridad de Sistema (Promedio).
    """
    id: int
    name: str
    x: float
    y: float
    star: Star
    planets: List[Planet] = field(default_factory=list)
    neighbors: List[int] = field(default_factory=list)
    description: str = ""
    controlling_player_id: Optional[int] = None
    
    # V9.1: Seguridad Promedio del Sistema (0.0 - 100.0)
    security: float = 0.0

    # V8.0: Sectores Estelares para megaestructuras
    sectors: List[Sector] = field(default_factory=list)

    def get_stellar_sector(self) -> Optional[Sector]:
        """V8.0: Retorna el sector estelar principal del sistema."""
        for sector in self.sectors:
            if sector.is_stellar():
                return sector
        return None

    def get_active_stellar_buildings(self) -> List[Dict[str, Any]]:
        """V8.0: Retorna todos los edificios activos en sectores estelares."""
        buildings = []
        for sector in self.sectors:
            if sector.is_stellar():
                for b in sector.buildings:
                    if b.get("is_active", True):
                        buildings.append(b)
        return buildings

@dataclass
class Galaxy:
    systems: List[System] = field(default_factory=list)
    starlanes: List[Tuple[int, int]] = field(default_factory=list) 
    
    def get_system_by_id(self, system_id: int) -> Optional[System]:
        for sys in self.systems:
            if sys.id == system_id:
                return sys
        return None