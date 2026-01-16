# core/galaxy_generator.py
import math
import random
from typing import List, Dict, Optional

from .world_models import Galaxy, System, Star, Planet, Moon, AsteroidBelt, CelestialBody
from .world_constants import (
    STAR_TYPES,
    STAR_RARITY_WEIGHTS,
    PLANET_BIOMES,
    ORBITAL_ZONES,
    ASTEROID_BELT_CHANCE,
    RESOURCE_STAR_WEIGHTS,
)

# --- Listas de Nombres Predefinidos para dar Sabor ---
STAR_NAME_PREFIXES = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Omega"]
STAR_NAME_SUFFIXES = ["Centauri", "Orionis", "Cygnus", "Draconis", "Pegasi", "Aquarii"]
PLANET_NAMES = ["Aethel", "Barovia", "Cygnus X1", "Dantooine", "Endor", "Felucia", "Giedi", "Hoth", "Ithor", "Jakku", "Kamino"]

class GalaxyGenerator:
    """
    Clase responsable de la generación procedural de la galaxia.
    Utiliza un 'seed' para que la galaxia sea la misma en cada ejecución.
    """
    def __init__(self, seed: int = 42, num_systems: int = 30):
        self.seed = seed
        self.num_systems = num_systems
        self.random = random.Random(seed)
        self.galaxy = Galaxy()
        self._used_system_names = set()
        self._celestial_body_id_counter = 0

    def _get_unique_id(self) -> int:
        self._celestial_body_id_counter += 1
        return self._celestial_body_id_counter

    def _generate_unique_system_name(self) -> str:
        while True:
            prefix = self.random.choice(STAR_NAME_PREFIXES)
            suffix = self.random.choice(STAR_NAME_SUFFIXES)
            num = self.random.randint(1, 100)
            name = f"{prefix}-{suffix}-{num}"
            if name not in self._used_system_names:
                self._used_system_names.add(name)
                return name

    def _create_star(self) -> Star:
        star_type_name = self.random.choices(
            list(STAR_RARITY_WEIGHTS.keys()),
            weights=list(STAR_RARITY_WEIGHTS.values()),
            k=1
        )[0]
        
        star_data = STAR_TYPES[star_type_name]
        
        return Star(
            name=f"{star_type_name}",
            type=star_type_name,
            rarity=star_data['rarity'],
            energy_modifier=star_data['energy_modifier'],
            special_rule=star_data['special_rule'],
            class_type=star_data['class']
        )

    def _pick_planet_size(self) -> str:
        """Devuelve un tamaño basico para el planeta."""
        roll = self.random.random()
        if roll < 0.25:
            return "Pequeno"
        if roll < 0.75:
            return "Mediano"
        return "Grande"

    def _sample_resources(self, star_class: str, max_items: int = 3) -> List[str]:
        """Selecciona entre 1 y max_items recursos metalicos segun la clase estelar."""
        weights = RESOURCE_STAR_WEIGHTS.get(star_class, {})
        items = [(name, w) for name, w in weights.items() if w > 0]
        if not items:
            return []

        chosen = set()
        count = self.random.randint(1, max_items)
        for _ in range(count):
            names, w = zip(*items)
            pick = self.random.choices(names, weights=w, k=1)[0]
            chosen.add(pick)
        return list(chosen)

    def _create_planet(self, ring: int, system_name: str, zone_weights: Dict[str, int], star_class: str) -> Planet:
        biome_name = self.random.choices(
            list(zone_weights.keys()),
            weights=list(zone_weights.values()),
            k=1
        )[0]
        biome_data = PLANET_BIOMES[biome_name]
        size = self._pick_planet_size()
        explored_pct = round(self.random.uniform(5, 35), 2)
        resources = self._sample_resources(star_class, max_items=3)

        # Generar lunas
        num_moons = self.random.randint(0, 5)
        moons = []
        for i in range(num_moons):
            moon_id = self._get_unique_id()
            moons.append(Moon(id=moon_id, name=f"Luna {i+1}"))
            
        return Planet(
            id=self._get_unique_id(),
            name=f"{system_name}-{ring}",
            ring=ring,
            biome=biome_name,
            size=size,
            bonuses=biome_data['bonuses'],
            construction_slots=biome_data['construction_slots'],
            maintenance_mod=biome_data['maintenance_mod'],
            explored_pct=explored_pct,
            resources=resources,
            moons=moons
        )

    def _create_asteroid_belt(self, ring: int, system_name: str) -> AsteroidBelt:
        return AsteroidBelt(
            id=self._get_unique_id(),
            name=f"Cinturón de {system_name}-{ring}",
            ring=ring,
            hazard_level=self.random.uniform(0.1, 0.9)
        )

    def _create_system(self, system_id: int, system_index: int) -> System:
        system_name = self._generate_unique_system_name()
        star = self._create_star()
        
        # --- Lógica de Posicionamiento en Espiral ---
        # Estos valores se pueden ajustar para cambiar la forma de la galaxia
        angle = system_index * 137.5  # Angulo dorado para distribución uniforme
        radius_scale = 15  # Escala del radio
        radius = radius_scale * math.sqrt(system_index)
        
        # Añadir algo de aleatoriedad para que no sea una espiral perfecta
        angle_randomness = self.random.uniform(-10, 10)
        radius_randomness = self.random.uniform(-5, 5)

        # Coordenadas polares a cartesianas
        # El centro de la galaxia estará en (500, 400)
        center_x, center_y = 500, 400
        x = center_x + (radius + radius_randomness) * math.cos(math.radians(angle + angle_randomness))
        y = center_y + (radius + radius_randomness) * math.sin(math.radians(angle + angle_randomness))
        
        system = System(
            id=system_id,
            name=system_name,
            star=star,
            position=(x, y)
        )

        for ring in range(1, 7):
            # Determinar la zona orbital
            current_zone = None
            for zone_info in ORBITAL_ZONES.values():
                if ring in zone_info['rings']:
                    current_zone = zone_info
                    break
            
            # Decidir si el anillo tiene un planeta o un cinturón de asteroides
            if self.random.random() < ASTEROID_BELT_CHANCE:
                system.orbital_rings[ring] = self._create_asteroid_belt(ring, system_name)
            else:
                # No crear planeta si la zona no tiene opciones (ej. Oceánico en Zona Caliente)
                if sum(current_zone['planet_weights'].values()) > 0:
                    system.orbital_rings[ring] = self._create_planet(
                        ring, system_name, current_zone['planet_weights'], star.class_type
                    )
                else:
                    system.orbital_rings[ring] = None # Anillo vacío

        return system

    def generate_galaxy(self) -> Galaxy:
        """Genera y devuelve el objeto Galaxia completo."""
        if self.galaxy.systems:
            return self.galaxy # No regenerar si ya existe

        for i in range(self.num_systems):
            system = self._create_system(system_id=i, system_index=i)
            self.galaxy.systems.append(system)
        
        return self.galaxy

# --- Instancia Singleton del Generador ---
# De esta forma, toda la aplicación puede importar y usar la misma galaxia generada.
_galaxy_generator_instance = GalaxyGenerator(seed=42, num_systems=30)
GALAXY = _galaxy_generator_instance.generate_galaxy()

def get_galaxy() -> Galaxy:
    """Función de acceso para obtener la galaxia generada."""
    return GALAXY
