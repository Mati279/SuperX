# core/galaxy_generator.py
import math
import random
from typing import List, Tuple
from .world_models import Galaxy, System, Star, Planet, Sector
from .world_constants import (
    STAR_TYPES, STAR_RARITY_WEIGHTS, PLANET_BIOMES,
    PLANET_MASS_CLASSES, ORBITAL_ZONE_WEIGHTS,
    SECTOR_TYPE_URBAN, SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN, SECTOR_TYPE_INHOSPITABLE,
    MAX_SLOTS_PER_SECTOR
)

class GalaxyGenerator:
    def __init__(self, seed: int = 42, num_systems: int = 40):
        self.seed = seed
        self.num_systems = num_systems
        self.galaxy = Galaxy()
        random.seed(self.seed)

    def generate_galaxy(self) -> Galaxy:
        """Genera una nueva galaxia con lógica de planetología avanzada."""
        systems = []
        
        for i in range(self.num_systems):
            angle = 0.5 * i
            dist = 10 * math.sqrt(i + 1)
            
            x = (dist * math.cos(angle)) + random.uniform(-2, 2)
            y = (dist * math.sin(angle)) + random.uniform(-2, 2)
            
            star = self._generate_random_star()
            
            new_system = System(
                id=i + 1,
                name=f"System-{i+1:03d}",
                x=x,
                y=y,
                star=star,
                planets=[]
            )
            
            new_system.planets = self._generate_planets_for_system(new_system)
            systems.append(new_system)

        self.galaxy.systems = systems
        self._generate_starlanes()
        return self.galaxy

    def _generate_random_star(self) -> Star:
        """Selecciona una estrella basada en pesos de rareza."""
        classes = list(STAR_RARITY_WEIGHTS.keys())
        weights = list(STAR_RARITY_WEIGHTS.values())
        chosen_class = random.choices(classes, weights=weights, k=1)[0]
        star_data = STAR_TYPES.get(chosen_class, STAR_TYPES["G"])
        
        return Star(
            class_type=chosen_class,
            color=star_data.get("color", "#FFFFFF"),
            size=star_data.get("size", 1.0),
            energy_output=star_data.get("energy_modifier", 1.0)
        )

    def _generate_planets_for_system(self, system: System) -> List[Planet]:
        """Genera planetas aplicando reglas de masa y zonas orbitales."""
        num_planets = random.randint(1, 6)
        planets = []
        
        # Rings disponibles: 1 a 6
        available_rings = list(range(1, 7))
        random.shuffle(available_rings)

        for j in range(min(num_planets, len(available_rings))):
            ring = available_rings.pop()
            
            # 1. Determinar Masa (Tarea 3.1)
            # Pesos: Enano 20%, Estándar 50%, Grande 20%, Gigante 10%
            mass_types = list(PLANET_MASS_CLASSES.keys())
            mass_weights = [0.20, 0.50, 0.20, 0.10]
            chosen_mass = random.choices(mass_types, weights=mass_weights, k=1)[0]
            max_sectors = PLANET_MASS_CLASSES[chosen_mass]

            # 2. Selección de Bioma (Tarea 3.2)
            biome = self._select_biome_by_ring(ring)
            
            planet_id = (system.id * 100) + j
            new_planet = Planet(
                id=planet_id,
                system_id=system.id,
                name=f"{system.name}-{j+1}",
                biome=biome,
                is_habitable=PLANET_BIOMES[biome]['modifiers']['habitability'] > -50,
                orbital_ring=ring,
                mass_class=chosen_mass,
                max_sectors=max_sectors
            )
            
            # 3. Generación de Sectores (Tarea 3.3)
            new_planet.sectors = self._generate_sectors_for_planet(new_planet)
            planets.append(new_planet)
            
        return sorted(planets, key=lambda p: p.orbital_ring)

    def _select_biome_by_ring(self, ring: int) -> str:
        """Aplica Weighted Random Choice basado en la Zona Orbital."""
        if ring <= 2: zone = "INNER"
        elif ring <= 4: zone = "HABITABLE"
        else: zone = "OUTER"

        biomes = list(PLANET_BIOMES.keys())
        weights = []

        for b in biomes:
            w_str = PLANET_BIOMES[b]['allowed_zones'].get(zone)
            w_val = ORBITAL_ZONE_WEIGHTS.get(w_str, 0) if w_str else 0
            weights.append(w_val)

        # Fallback si todos los pesos son 0 por error de config
        if sum(weights) == 0: return "Arido" 
        
        return random.choices(biomes, weights=weights, k=1)[0]

    def _generate_sectors_for_planet(self, planet: Planet) -> List[Sector]:
        """Genera N sectores físicos e instancia la niebla de superficie."""
        sectors = []
        num_sectors = planet.max_sectors
        biome_data = PLANET_BIOMES[planet.biome]
        
        # Habitabilidad influye en la probabilidad de Llanura vs Inhóspito
        habitability = biome_data['modifiers'].get('habitability', 0)

        for k in range(num_sectors):
            sector_index = k + 1
            sector_id = (planet.id * 1000) + sector_index
            
            # Sector 1: Siempre Urbano y Conocido (Landing Zone)
            if sector_index == 1:
                sec_type = SECTOR_TYPE_URBAN
                is_known = True
            else:
                is_known = False
                # Lógica de habitabilidad de sector
                # Si habitabilidad < -20, chance alta de ser inhóspito
                inhospitable_threshold = (habitability + 100) / 200 # 0.0 a 1.0
                if random.random() > inhospitable_threshold:
                    sec_type = SECTOR_TYPE_INHOSPITABLE
                else:
                    sec_type = random.choice([SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN])

            sectors.append(Sector(
                id=sector_id,
                planet_id=planet.id,
                type=sec_type,
                slots=MAX_SLOTS_PER_SECTOR if sec_type != SECTOR_TYPE_INHOSPITABLE else 0,
                is_known=is_known
            ))

        return sectors

    def _generate_starlanes(self):
        """Genera conexiones entre sistemas usando Gabriel Graph."""
        systems = self.galaxy.systems
        n = len(systems)
        starlanes = []

        for sys in systems: sys.neighbors = []

        for i in range(n):
            for j in range(i + 1, n):
                sys_a, sys_b = systems[i], systems[j]
                mid_x, mid_y = (sys_a.x + sys_b.x) / 2, (sys_a.y + sys_b.y) / 2
                dist_ab_sq = (sys_a.x - sys_b.x)**2 + (sys_a.y - sys_b.y)**2
                radius_sq = dist_ab_sq / 4.0

                blocked = False
                for k in range(n):
                    if k == i or k == j: continue
                    sys_c = systems[k]
                    if (sys_c.x - mid_x)**2 + (sys_c.y - mid_y)**2 < radius_sq:
                        blocked = True
                        break
                
                if not blocked:
                    sys_a.neighbors.append(sys_b.id)
                    sys_b.neighbors.append(sys_a.id)
                    starlanes.append((sys_a.id, sys_b.id))

        self.galaxy.starlanes = starlanes

def get_galaxy() -> Galaxy:
    return GalaxyGenerator().generate_galaxy()