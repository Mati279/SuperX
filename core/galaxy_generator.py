# core/galaxy_generator.py (Completo)
import math
import random
from typing import List, Tuple
from .world_models import Galaxy, System, Star, Planet, Sector
from .world_constants import (
    STAR_TYPES, STAR_RARITY_WEIGHTS, PLANET_BIOMES,
    PLANET_MASS_CLASSES, ORBITAL_ZONE_WEIGHTS,
    SECTOR_TYPE_URBAN, SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN, SECTOR_TYPE_INHOSPITABLE,
    SECTOR_SLOTS_CONFIG, SECTOR_NAMES_BY_CATEGORY, LUXURY_RESOURCES_BY_CATEGORY,
    RESOURCE_PROB_HIGH, RESOURCE_PROB_MEDIUM, RESOURCE_PROB_LOW, RESOURCE_PROB_NONE,
    EMPTY_SYSTEMS_COUNT, WILD_POPULATION_CHANCE, POP_RANGE,
    INHOSPITABLE_BIOME_NAMES 
)
from .rules import calculate_planet_security

class GalaxyGenerator:
    def __init__(self, seed: int = 42, num_systems: int = 40):
        self.seed = seed
        self.num_systems = num_systems
        self.galaxy = Galaxy()
        random.seed(self.seed)

    def generate_galaxy(self) -> Galaxy:
        """Genera una nueva galaxia con lógica de planetología avanzada y distribución de población."""
        systems = []
        
        # Selección aleatoria de sistemas vacíos/salvajes
        empty_system_indices = set(random.sample(range(self.num_systems), min(self.num_systems, EMPTY_SYSTEMS_COUNT)))

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
            
            # Determinar si el sistema está civilizado
            is_civilized = i not in empty_system_indices
            
            new_system.planets = self._generate_planets_for_system(new_system, is_civilized)
            systems.append(new_system)

        self.galaxy.systems = systems
        self._generate_starlanes() # Ahora este método existe
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

    def _generate_planets_for_system(self, system: System, is_civilized: bool) -> List[Planet]:
        """Genera planetas, sectores y asigna población según reglas."""
        num_planets = random.randint(1, 6)
        planets = []
        available_rings = list(range(1, 7))
        random.shuffle(available_rings)

        # --- FASE 1: Creación Física ---
        for j in range(min(num_planets, len(available_rings))):
            ring = available_rings.pop()
            
            # Masa
            mass_types = list(PLANET_MASS_CLASSES.keys())
            mass_weights = [0.20, 0.50, 0.20, 0.10]
            chosen_mass = random.choices(mass_types, weights=mass_weights, k=1)[0]
            max_sectors_potential = PLANET_MASS_CLASSES[chosen_mass]
            
            # Bioma
            biome = self._select_biome_by_ring(ring)
            
            # Stats base
            base_defense = random.randint(10, 30)
            
            planet_id = (system.id * 100) + j
            new_planet = Planet(
                id=planet_id,
                system_id=system.id,
                name=f"{system.name}-{j+1}",
                biome=biome,
                is_habitable=PLANET_BIOMES[biome].get('habitability', 0) > 0.4, 
                orbital_ring=ring,
                mass_class=chosen_mass,
                max_sectors=max_sectors_potential, # Inicialmente potencial
                base_defense=base_defense,
                population=0.0,
                security=0.0 
            )
            
            # Generar Sectores Iniciales
            new_planet.sectors = self._generate_sectors_for_planet(new_planet)
            
            # Refactor V5.3: Actualizar max_sectors real basado en los sectores viables generados
            new_planet.max_sectors = len(new_planet.sectors)
            
            planets.append(new_planet)

        # --- FASE 2: Población y Civilización ---
        if is_civilized and planets:
            habitable_candidates = [p for p in planets if p.is_habitable]
            primary_planet = None
            
            if not habitable_candidates:
                best_candidate = min(planets, key=lambda p: abs(p.orbital_ring - 3.5))
                best_candidate.biome = "Templado"
                best_candidate.is_habitable = True
                
                # Regenerar sectores para asegurar habitabilidad forzada
                # (Temporalmente restauramos el potencial de masa para generar)
                max_sec = PLANET_MASS_CLASSES[best_candidate.mass_class]
                best_candidate.max_sectors = max_sec 
                
                best_candidate.sectors = self._generate_sectors_for_planet(best_candidate)
                best_candidate.max_sectors = len(best_candidate.sectors)
                
                primary_planet = best_candidate
            else:
                primary_planet = random.choice(habitable_candidates)

            # Asignación de Población
            for p in planets:
                should_populate = False
                if p == primary_planet:
                    should_populate = True
                elif random.random() < WILD_POPULATION_CHANCE:
                    should_populate = True
                
                if should_populate:
                    # Rango Natural Unificado: 1.0 - 10.0 Billones
                    p.population = round(random.uniform(1.0, 10.0), 2)
                    
                    # Garantizar sector urbano si hay población
                    # Verificar si ya existe sector urbano, si no, transformar el primero
                    has_urban = any(s.type == SECTOR_TYPE_URBAN for s in p.sectors)
                    if not has_urban and p.sectors:
                         p.sectors[0].type = SECTOR_TYPE_URBAN
                         p.sectors[0].max_slots = SECTOR_SLOTS_CONFIG.get(SECTOR_TYPE_URBAN, 2)
                         p.sectors[0].resource_category = None
                         p.sectors[0].luxury_resource = None
                         p.sectors[0].is_known = True


        # --- FASE 3: Seguridad ---
        for p in planets:
            p.security = calculate_planet_security(
                base_stat=p.base_defense,
                pop_count=p.population,
                infrastructure_defense=0,
                orbital_ring=p.orbital_ring
            )
            
        return sorted(planets, key=lambda p: p.orbital_ring)

    def _select_biome_by_ring(self, ring: int) -> str:
        """Selecciona bioma según la zona orbital."""
        biomes = list(PLANET_BIOMES.keys())
        weights = []
        for b in biomes:
            preferred = PLANET_BIOMES[b].get('preferred_rings', [])
            if ring in preferred:
                weights.append(ORBITAL_ZONE_WEIGHTS["ALTA"])
            elif (ring - 1) in preferred or (ring + 1) in preferred:
                weights.append(ORBITAL_ZONE_WEIGHTS["MEDIA"])
            else:
                weights.append(ORBITAL_ZONE_WEIGHTS["BAJA"])
        return random.choices(biomes, weights=weights, k=1)[0]

    def _generate_sectors_for_planet(self, planet: Planet) -> List[Sector]:
        """
        Genera los sectores validando habitabilidad y recursos.
        Refactor V5.3: Solo instancia sectores útiles (habitables o con recursos).
        Descarta sectores inhóspitos vacíos para ahorrar espacio en DB.
        """
        sectors = []
        biome_data = PLANET_BIOMES[planet.biome]
        biome_habitability = biome_data.get('habitability', 0.0)
        prob_map = {"ALTA": RESOURCE_PROB_HIGH, "MEDIA": RESOURCE_PROB_MEDIUM, "BAJA": RESOURCE_PROB_LOW, "NULA": RESOURCE_PROB_NONE}
        
        # Iteramos sobre el potencial físico del planeta (max_sectors)
        for k in range(planet.max_sectors):
            sector_index = k + 1
            sector_id = (planet.id * 1000) + sector_index
            
            # Probabilidad de ser sector útil (habitable o con recursos explotables)
            is_viable_sector = False
            
            # 1. Check de Habitabilidad Física (para construir)
            is_physically_habitable = random.random() < biome_habitability
            
            # Garantía para el último sector si no hay ninguno habitable en planetas no gaseosos
            if planet.biome != "Gaseoso" and k == (planet.max_sectors - 1) and not sectors:
                 is_physically_habitable = True
            
            sec_type = None
            slots = 0
            resource_category = None
            luxury_res = None
            
            if is_physically_habitable:
                is_viable_sector = True
                resource_found = False
                
                # Check de Anillo
                preferred_rings = biome_data.get('preferred_rings', [])
                if planet.orbital_ring in preferred_rings and random.random() < 0.5:
                    common_list = biome_data.get('common_resources', [])
                    if common_list:
                        resource_category = random.choice(common_list)
                        resource_found = True
                
                # Check de Matriz
                if not resource_found:
                    matrix = biome_data.get('resource_matrix', {})
                    candidates = []
                    for cat, prob_key in matrix.items():
                        if random.random() < prob_map.get(prob_key, 0.0):
                            candidates.append(cat)
                    if candidates:
                        resource_category = random.choice(candidates)
                        resource_found = True
                
                if resource_found and resource_category:
                    sec_type = SECTOR_NAMES_BY_CATEGORY.get(resource_category, SECTOR_TYPE_PLAIN)
                    if random.random() < 0.2:
                        lux_list = LUXURY_RESOURCES_BY_CATEGORY.get(resource_category, [])
                        if lux_list: luxury_res = random.choice(lux_list)
                else:
                    sec_type = random.choice([SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN])

                slots = SECTOR_SLOTS_CONFIG.get(sec_type, 2)
            
            # Si NO es físicamente habitable, ¿tiene recursos extremos? (Futuro: Minería en zonas hostiles)
            # Por ahora, si no es habitable, lo consideramos "Inhóspito vacío" y lo descartamos 
            # salvo que la lógica cambie.
            
            # Regla de Urbanismo Forzado (Solo si ya se determinó población antes, o es el primer sector viable)
            if planet.population > 0 and not sectors and is_viable_sector:
                sec_type = SECTOR_TYPE_URBAN
                slots = SECTOR_SLOTS_CONFIG.get(SECTOR_TYPE_URBAN, 2)
                resource_category = None
                luxury_res = None
            
            # Solo añadimos el sector si es viable (tiene slots > 0 y tipo válido)
            if is_viable_sector and slots > 0:
                sectors.append(Sector(
                    id=sector_id,
                    planet_id=planet.id,
                    name=f"Sector {len(sectors) + 1}", # Renombrar secuencialmente
                    type=sec_type,
                    resource_category=resource_category,
                    luxury_resource=luxury_res,
                    max_slots=slots,
                    buildings=[],
                    is_known=(len(sectors) == 0) # El primer sector es conocido
                ))
                
        return sectors

    def _generate_starlanes(self):
        """Genera conexiones usando el Grafo de Gabriel."""
        self.galaxy.starlanes = []
        systems = self.galaxy.systems
        
        for i, s1 in enumerate(systems):
            for j, s2 in enumerate(systems):
                if i >= j: continue 
                
                dist_sq = (s1.x - s2.x)**2 + (s1.y - s2.y)**2
                
                is_gabriel = True
                for k, sk in enumerate(systems):
                    if k == i or k == j: continue
                    
                    d1k_sq = (s1.x - sk.x)**2 + (s1.y - sk.y)**2
                    d2k_sq = (s2.x - sk.x)**2 + (s2.y - sk.y)**2
                    
                    if d1k_sq + d2k_sq < dist_sq:
                        is_gabriel = False
                        break
                
                if is_gabriel:
                    # Distancia máxima de conexión
                    if dist_sq < 400: 
                        self.galaxy.starlanes.append((s1.id, s2.id))