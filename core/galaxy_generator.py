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
    INHOSPITABLE_BIOME_NAMES # Nuevo import
)
# V4.4: Importar lógica de seguridad para cálculo inicial
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
        
        # Selección aleatoria de sistemas vacíos/salvajes (V4.5)
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
            
            # Determinar si el sistema está civilizado (no está en la lista de vacíos)
            is_civilized = i not in empty_system_indices
            
            new_system.planets = self._generate_planets_for_system(new_system, is_civilized)
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

    def _generate_planets_for_system(self, system: System, is_civilized: bool) -> List[Planet]:
        """
        Genera planetas aplicando reglas de masa y zonas orbitales.
        V4.5: Aplica distribución de población y garantía de nodo vital si is_civilized es True.
        """
        num_planets = random.randint(1, 6)
        planets = []
        
        # Rings disponibles: 1 a 6
        available_rings = list(range(1, 7))
        random.shuffle(available_rings)

        # --- FASE 1: Creación Física de Planetas ---
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
            
            # V4.4: Determinar Base Stat (Defensa) para el planeta
            base_defense = random.randint(10, 30)
            initial_population = 0 # Se calculará en Fase 2
            
            planet_id = (system.id * 100) + j
            new_planet = Planet(
                id=planet_id,
                system_id=system.id,
                name=f"{system.name}-{j+1}",
                biome=biome,
                is_habitable=PLANET_BIOMES[biome].get('habitability', 0) > 0.4, 
                orbital_ring=ring,
                mass_class=chosen_mass,
                max_sectors=max_sectors,
                # V4.4 Fields
                base_defense=base_defense,
                population=initial_population,
                security=0 # Se calculará en Fase 2
            )
            
            # 3. Generación de Sectores (Tarea 3.3)
            # Nota: Esto se regenerará luego si el bioma cambia forzosamente, 
            # pero es necesario instanciarlo ahora.
            new_planet.sectors = self._generate_sectors_for_planet(new_planet)
            planets.append(new_planet)

        # --- FASE 2: Lógica de Población y Civilización (V4.5) ---
        if is_civilized and planets:
            # Identificar candidatos habitables existentes
            habitable_candidates = [p for p in planets if p.is_habitable]
            primary_planet = None

            # Garantía de Nodo Vital
            if not habitable_candidates:
                # Si no hay habitables, forzar mutación en el mejor candidato (anillos centrales)
                # Buscamos el más cercano a 3.5 (entre anillo 3 y 4)
                best_candidate = min(planets, key=lambda p: abs(p.orbital_ring - 3.5))
                
                # Mutar a Templado (Habitabilidad 0.9)
                best_candidate.biome = "Templado"
                best_candidate.is_habitable = True
                
                # Regenerar sectores para reflejar el nuevo bioma habitable
                best_candidate.sectors = self._generate_sectors_for_planet(best_candidate)
                
                primary_planet = best_candidate
            else:
                primary_planet = random.choice(habitable_candidates)

            # Asignación de Población
            for p in planets:
                pop = 0
                if p == primary_planet:
                    # Planeta principal obtiene población garantizada
                    pop = random.randint(*POP_RANGE)
                else:
                    # Distribución Estocástica para el resto
                    # Aplicamos WILD_POPULATION_CHANCE
                    if random.random() < WILD_POPULATION_CHANCE:
                         pop = random.randint(*POP_RANGE)
                
                p.population = pop

        # --- FASE 3: Sincronización de Seguridad ---
        for p in planets:
            # Calcular seguridad final basada en la población asignada (o cero si es wild/vacío)
            p.security = calculate_planet_security(
                base_stat=p.base_defense,
                pop_count=p.population,
                infrastructure_defense=0,
                orbital_ring=p.orbital_ring
            )
            
        return sorted(planets, key=lambda p: p.orbital_ring)

    def _select_biome_by_ring(self, ring: int) -> str:
        """Aplica Weighted Random Choice basado en la Zona Orbital."""
        # Se asume que PLANET_BIOMES ya no tiene 'allowed_zones' con mapeo directo
        # sino que usamos preferred_rings o lógica custom.
        
        biomes = list(PLANET_BIOMES.keys())
        weights = []
        
        for b in biomes:
            preferred = PLANET_BIOMES[b].get('preferred_rings', [])
            if ring in preferred:
                weights.append(10)
            elif (ring - 1) in preferred or (ring + 1) in preferred:
                weights.append(3)
            else:
                weights.append(1)

        return random.choices(biomes, weights=weights, k=1)[0]

    def _generate_sectors_for_planet(self, planet: Planet) -> List[Sector]:
        """
        Refactorización completa (V4.3.0) - Flujo de 4 Pasos.
        Actualización V4.6: Asignación dinámica de slots por tipo de sector.
        Actualización V4.7: Garantía de habitabilidad y nombres dinámicos inhóspitos.
        """
        sectors = []
        biome_data = PLANET_BIOMES[planet.biome]
        biome_habitability = biome_data.get('habitability', 0.0)
        
        prob_map = {
            "ALTA": RESOURCE_PROB_HIGH,
            "MEDIA": RESOURCE_PROB_MEDIUM,
            "BAJA": RESOURCE_PROB_LOW,
            "NULA": RESOURCE_PROB_NONE
        }

        # Contador para verificar si se generó al menos un sector habitable
        generated_habitable_count = 0

        for k in range(planet.max_sectors):
            sector_index = k + 1 # 1-based index
            sector_id = (planet.id * 1000) + sector_index
            
            # --- PASO 1: Determinación de Habitabilidad Física ---
            is_physically_habitable = random.random() < biome_habitability
            
            # Garantía de habitabilidad (V4.7): 
            # Si es el último sector, no se han generado habitables y el planeta NO es gaseoso, forzarlo.
            if planet.biome != "Gaseoso" and k == (planet.max_sectors - 1) and generated_habitable_count == 0:
                is_physically_habitable = True

            sec_type = SECTOR_TYPE_INHOSPITABLE
            slots = 0 # Valor por defecto para inhóspito
            resource_category = None
            luxury_res = None
            
            if is_physically_habitable:
                generated_habitable_count += 1
                
                # --- PASO 2: Asignación de Recursos (Solo Habitable) ---
                resource_found = False
                
                # A) Check de Anillo
                preferred_rings = biome_data.get('preferred_rings', [])
                if planet.orbital_ring in preferred_rings:
                    if random.random() < 0.5: # 50% chance
                        common_list = biome_data.get('common_resources', [])
                        if common_list:
                            resource_category = random.choice(common_list)
                            resource_found = True
                
                # B) Check de Matriz (Si no se asignó en A)
                if not resource_found:
                    matrix = biome_data.get('resource_matrix', {})
                    candidates = []
                    # Recolectamos candidatos que pasen su chequeo de probabilidad individual
                    for cat, prob_key in matrix.items():
                        prob = prob_map.get(prob_key, 0.0)
                        if random.random() < prob:
                            candidates.append(cat)
                    
                    if candidates:
                        resource_category = random.choice(candidates)
                        resource_found = True
                
                # Asignación de datos si se encontró recurso
                if resource_found and resource_category:
                    sec_type = SECTOR_NAMES_BY_CATEGORY.get(resource_category, SECTOR_TYPE_PLAIN)
                    
                    # Check de Lujo (V4.1.3)
                    if random.random() < 0.2: # 20%
                        lux_list = LUXURY_RESOURCES_BY_CATEGORY.get(resource_category, [])
                        if lux_list:
                            luxury_res = random.choice(lux_list)

                # --- PASO 3: Definición de Sectores Habitables sin Recurso ---
                else:
                    sec_type = random.choice([SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN])

                # Asignación de slots basada en la configuración (Llanura 3, Montaña/Recursos 2)
                # Fallback de seguridad es 2 para habitables desconocidos
                slots = SECTOR_SLOTS_CONFIG.get(sec_type, 2)
            
            else:
                # --- Nomenclatura Dinámica para Inhóspitos (V4.7) ---
                # Asignar nombre temático según el bioma del planeta
                sec_type = INHOSPITABLE_BIOME_NAMES.get(planet.biome, SECTOR_TYPE_INHOSPITABLE)
                # Slots para inhóspitos (debería ser 0 según configuración)
                slots = SECTOR_SLOTS_CONFIG.get(sec_type, 0)

            # --- PASO 4: Regla Forzada de Urbanismo ---
            # Si hay población inicial asignada al planeta (ojo: esto se evalúa al generar,
            # si population se asigna después, este check podría fallar en la primera pasada,
            # pero es correcto para regeneraciones o si population > 0 ya está set).
            # En la V4.5, si regeneramos sectores tras forzar bioma, esto aplicará correctamente.
            if planet.population > 0 and sector_index == 1:
                sec_type = SECTOR_TYPE_URBAN
                # Asignación de slots para sector urbano (2 según reglas)
                slots = SECTOR_SLOTS_CONFIG.get(SECTOR_TYPE_URBAN, 2)
                resource_category = None # Limpiamos recurso si se fuerza urbano
                luxury_res = None
            
            is_known = (sec_type == SECTOR_TYPE_URBAN)

            new_sector = Sector(
                id=sector_id,
                planet_id=planet.id,
                type=sec_type,
                slots=slots,
                resource_type=resource_category,
                luxury_resource=luxury_res,
                is_known=is_known
            )
            sectors.append(new_sector)

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