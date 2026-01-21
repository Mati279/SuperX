# core/galaxy_generator.py
import math
import random
from typing import List, Tuple
from .world_models import Galaxy, System, Star, Planet, Sector
from .world_constants import (
    STAR_TYPES, STAR_RARITY_WEIGHTS, PLANET_BIOMES,
    SECTOR_TYPE_URBAN, SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN, SECTOR_TYPE_INHOSPITABLE,
    BIOME_INHOSPITABLE_CHANCE, BIOME_RESOURCE_MATRIX, MAX_SLOTS_PER_SECTOR,
    RESOURCE_CHANCE_HIGH, RESOURCE_CHANCE_MEDIUM, RESOURCE_CHANCE_LOW, RESOURCE_CHANCE_NONE
)

class GalaxyGenerator:
    def __init__(self, seed: int = 42, num_systems: int = 40):
        # Aumentado de 30 a 40 para mayor densidad base
        self.seed = seed
        self.num_systems = num_systems
        self.galaxy = Galaxy()
        random.seed(self.seed)

    def generate_galaxy(self) -> Galaxy:
        """
        Genera una nueva galaxia con sistemas, planetas y rutas (starlanes).
        """
        systems = []
        
        # 1. Generar posiciones (Espirales simples)
        for i in range(self.num_systems):
            # Lógica simple de espiral para distribución
            angle = 0.5 * i  # Ajustar para la forma de la espiral
            dist = 10 * math.sqrt(i + 1) # Raíz cuadrada para distribución uniforme de área
            
            # Añadir algo de "jitter" aleatorio
            jitter_x = random.uniform(-2, 2)
            jitter_y = random.uniform(-2, 2)
            
            x = (dist * math.cos(angle)) + jitter_x
            y = (dist * math.sin(angle)) + jitter_y
            
            star = self._generate_random_star()
            
            new_system = System(
                id=i + 1,
                name=f"System-{i+1:03d}", # Nombre placeholder
                x=x,
                y=y,
                star=star,
                planets=[]
            )
            
            # Generar planetas para este sistema
            new_system.planets = self._generate_planets_for_system(new_system)
            systems.append(new_system)

        self.galaxy.systems = systems
        
        # 2. Generar Starlanes usando Gabriel Graph
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
        """Genera una cantidad aleatoria de planetas para el sistema."""
        num_planets = random.randint(1, 6) # Configurable
        planets = []
        
        for j in range(num_planets):
            planet_id = (system.id * 100) + j
            # Lógica simplificada de biomas
            biome_keys = list(PLANET_BIOMES.keys())
            biome = random.choice(biome_keys)
            
            # Crear instancia básica de planeta
            new_planet = Planet(
                id=planet_id,
                system_id=system.id,
                name=f"{system.name}-{j+1}",
                biome=biome,
                is_habitable=PLANET_BIOMES[biome].get("construction_slots", 0) > 0,
                slots=PLANET_BIOMES[biome].get("construction_slots", 2)
            )
            
            # V4.2.0: Generar Sectores para el planeta
            new_planet.sectors = self._generate_sectors_for_planet(new_planet)
            
            planets.append(new_planet)
            
        return planets

    def _generate_sectors_for_planet(self, planet: Planet) -> List[Sector]:
        """
        Genera los sectores iniciales de un planeta basado en su bioma.
        Garantiza al menos un sector Urbano si el planeta es habitable/poblado potencial.
        """
        sectors = []
        num_sectors = 6  # Estándar hexagonal para profundidad de juego
        
        # Obtener probabilidades base según bioma
        inhospitable_chance = BIOME_INHOSPITABLE_CHANCE.get(planet.biome, 0.5)
        resource_chance = BIOME_RESOURCE_MATRIX.get(planet.biome, RESOURCE_CHANCE_LOW)
        
        has_urban = False
        
        for k in range(num_sectors):
            sector_id = (planet.id * 100) + k
            
            # Determinar tipo de sector
            roll_type = random.random()
            
            if roll_type < inhospitable_chance:
                sec_type = SECTOR_TYPE_INHOSPITABLE
                slots = 0
            else:
                # Si es habitable y jugable, distribuimos entre Llanura y Montaña
                sec_type = random.choice([SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN])
                slots = MAX_SLOTS_PER_SECTOR
            
            # Determinar recursos
            res_roll = random.random()
            resource_type = None
            if sec_type != SECTOR_TYPE_INHOSPITABLE and res_roll < resource_chance:
                # Placeholder: Aquí se asignaría un recurso específico
                # Por ahora solo marcamos que tiene "Minerales" genéricos
                resource_type = "Minerales Comunes"

            sectors.append(Sector(
                id=sector_id,
                planet_id=planet.id,
                type=sec_type,
                slots=slots,
                resource_type=resource_type
            ))

        # GARANTÍA: Si el planeta es "bueno", asegurar 1 sector Urbano inicial
        # Esto es vital para que la colonia inicial tenga donde construirse.
        if planet.is_habitable:
            # Reemplazar el primer sector no-inhóspito con Urbano, o forzar el primero
            target_idx = 0
            found_candidate = False
            
            # Buscar un sector válido para urbanizar
            for idx, s in enumerate(sectors):
                if s.type != SECTOR_TYPE_INHOSPITABLE:
                    target_idx = idx
                    found_candidate = True
                    break
            
            # Si todo es inhóspito pero el planeta dice ser habitable, forzamos el 0
            sectors[target_idx].type = SECTOR_TYPE_URBAN
            sectors[target_idx].slots = MAX_SLOTS_PER_SECTOR # Máxima capacidad
            sectors[target_idx].resource_type = None # Urbano suele limpiar recursos naturales

        return sectors

    def _generate_starlanes(self):
        """
        Genera conexiones entre sistemas usando el algoritmo Gabriel Graph.
        Dos nodos A y B se conectan si el círculo con diámetro AB no contiene
        ningún otro nodo C.
        """
        systems = self.galaxy.systems
        n = len(systems)
        starlanes = []

        # Limpiar vecinos previos por seguridad
        for sys in systems:
            sys.neighbors = []

        for i in range(n):
            for j in range(i + 1, n):
                sys_a = systems[i]
                sys_b = systems[j]

                # 1. Calcular punto medio y distancia cuadrada AB
                mid_x = (sys_a.x + sys_b.x) / 2
                mid_y = (sys_a.y + sys_b.y) / 2
                
                dx = sys_a.x - sys_b.x
                dy = sys_a.y - sys_b.y
                dist_ab_sq = dx*dx + dy*dy
                
                # El radio al cuadrado del círculo de Gabriel es (d_ab / 2)^2
                # O simplemente d_ab_sq / 4
                radius_sq = dist_ab_sq / 4.0

                # 2. Verificar condición de Gabriel
                blocked = False
                for k in range(n):
                    if k == i or k == j:
                        continue
                    
                    sys_c = systems[k]
                    
                    # Distancia cuadrada de C al punto medio
                    dc_x = sys_c.x - mid_x
                    dc_y = sys_c.y - mid_y
                    dist_c_mid_sq = dc_x*dc_x + dc_y*dc_y

                    # Si C está estrictamente dentro del círculo, bloquea la conexión
                    if dist_c_mid_sq < radius_sq:
                        blocked = True
                        break
                
                # 3. Si nadie bloquea, creamos conexión
                if not blocked:
                    # Agregar a vecinos (grafo de adyacencia)
                    if sys_b.id not in sys_a.neighbors:
                        sys_a.neighbors.append(sys_b.id)
                    if sys_a.id not in sys_b.neighbors:
                        sys_b.neighbors.append(sys_a.id)
                    
                    # Agregar a lista global de aristas
                    starlanes.append((sys_a.id, sys_b.id))

        self.galaxy.starlanes = starlanes

# Instancia Singleton (opcional, según uso en el proyecto)
GALAXY = GalaxyGenerator().generate_galaxy()

def get_galaxy() -> Galaxy:
    return GALAXY