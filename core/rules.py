# core/rules.py (Completo)
import math
from typing import Dict, Any, Tuple, Optional
from core.constants import SKILL_MAPPING, ATTRIBUTE_COST_MULTIPLIER
from core.world_constants import PLANET_BIOMES, SECTOR_TYPE_INHOSPITABLE
from core.models import KnowledgeLevel

# --- CONSTANTES DE BALANCEO (V4.4 SEGURIDAD) ---
SECURITY_POP_MULT = 5
RING_PENALTY = 2

def calculate_skills(attributes: Dict[str, int]) -> Dict[str, int]:
    skills = {}
    for skill_name, (attr1, attr2) in SKILL_MAPPING.items():
        val1 = attributes.get(attr1, 0)
        val2 = attributes.get(attr2, 0)
        skills[skill_name] = (val1 + val2) * 2
    return skills

def calculate_attribute_cost(start_val: int, target_val: int) -> int:
    total_cost = 0
    for v in range(start_val, target_val):
        cost = v * ATTRIBUTE_COST_MULTIPLIER
        total_cost += cost
    return total_cost

def get_color_for_level(value: int) -> str:
    if value < 20: return "#888888"
    if value < 40: return "#ffffff"
    if value < 60: return "#56d59f"
    if value < 80: return "#5eb5f5"
    if value < 100: return "#a06be0"
    return "#f6c45b"


# --- REGLAS DE CONOCIMIENTO ---

KNOWLEDGE_THRESHOLD_FRIEND_BASE = 50 

def calculate_ticks_required_for_known(presence_value: int) -> int:
    base_ticks = 20
    modifier = 10 - presence_value
    return max(1, base_ticks + modifier)


def calculate_ticks_required_for_friend(presence_value: int) -> int:
    ticks_for_known = calculate_ticks_required_for_known(presence_value)
    friend_base = KNOWLEDGE_THRESHOLD_FRIEND_BASE
    modifier = 10 - presence_value
    ticks_for_friend_phase = max(1, friend_base + modifier)
    return ticks_for_known + ticks_for_friend_phase


def calculate_passive_knowledge_progress(
    ticks_in_service: int,
    current_level: KnowledgeLevel,
    character_attributes: Dict[str, int]
) -> Tuple[KnowledgeLevel, float]:
    if current_level == KnowledgeLevel.FRIEND:
        return KnowledgeLevel.FRIEND, 100.0

    presence = character_attributes.get("presencia", 10)

    if current_level == KnowledgeLevel.UNKNOWN:
        required_ticks = calculate_ticks_required_for_known(presence)
        if ticks_in_service >= required_ticks:
            return KnowledgeLevel.KNOWN, 100.0
        progress = (ticks_in_service / required_ticks) * 100 if required_ticks > 0 else 0
        return KnowledgeLevel.UNKNOWN, max(0.0, min(100.0, progress))
    else:
        ticks_for_known = calculate_ticks_required_for_known(presence)
        total_required = calculate_ticks_required_for_friend(presence)
        if ticks_in_service >= total_required:
            return KnowledgeLevel.FRIEND, 100.0
        ticks_in_friend_phase = ticks_in_service - ticks_for_known
        friend_phase_duration = total_required - ticks_for_known
        if friend_phase_duration <= 0: friend_phase_duration = 1
        progress = (ticks_in_friend_phase / friend_phase_duration) * 100 if ticks_in_friend_phase > 0 else 0
        return KnowledgeLevel.KNOWN, max(0.0, min(100.0, progress))


# --- REGLAS DE CONTROL Y PLANETOLOGÍA (V4.3.0) ---

def calculate_system_control(system_id: int):
    from data.world_repository import get_planets_by_system_id, update_system_controller
    from data.player_repository import get_player_by_id

    planets = get_planets_by_system_id(system_id)
    if not planets: return

    total_planets = len(planets)
    faction_counts = {}

    for planet in planets:
        owner_id = planet.get("surface_owner_id")
        if owner_id:
            player = get_player_by_id(owner_id)
            if player and player.get("faction_id"):
                f_id = player["faction_id"]
                faction_counts[f_id] = faction_counts.get(f_id, 0) + 1

    new_controller_id = None
    for f_id, count in faction_counts.items():
        if count > (total_planets / 2):
            new_controller_id = f_id
            break
    
    update_system_controller(system_id, new_controller_id)


def calculate_planet_habitability(planet_id: int) -> int:
    """
    Determina la habitabilidad final basándose en Bioma y Sectores (V4.3).
    Aplica penalización por Sectores Inhóspitos sin infraestructura de soporte.
    Corrección V4.8: Acceso directo a habitability y escalado a 100.
    """
    from data.planet_repository import get_planet_by_id, get_planet_sectors_status
    
    planet = get_planet_by_id(planet_id)
    if not planet: return 0
    
    biome_info = PLANET_BIOMES.get(planet["biome"], {})
    
    # Obtener float base (ej. 0.3) y escalar a entero (30)
    base_hab_float = biome_info.get("habitability", 0.0)
    base_hab = int(base_hab_float * 100)
    
    sectors = get_planet_sectors_status(planet_id)
    penalty = 0
    
    for sec in sectors:
        # Regla 4.3: Un sector inhóspito vacío penaliza la habitabilidad global
        if sec["type"] == SECTOR_TYPE_INHOSPITABLE and sec["buildings_count"] == 0:
            penalty += 15
            
    final_habitability = base_hab - penalty
    return max(-100, min(100, final_habitability))

# --- REGLAS DE ECONOMÍA (V4.8) ---

def calculate_fiscal_income(rate_base: float, population_billions: float, security_score: int) -> float:
    """
    Calcula ingresos fiscales usando modelo logarítmico (Regla 3).
    Ingresos = (RateBase * log10(Población_Total)) * (Seguridad / 100)
    
    Args:
        rate_base: Multiplicador base de impuestos.
        population_billions: Población en miles de millones (ej. 1.5).
        security_score: Puntuación de seguridad del planeta (0-100).
    """
    if population_billions <= 0:
        return 0.0
        
    pop_total = population_billions * 1_000_000_000
    if pop_total < 1: return 0.0
    
    # log10 de la población total
    log_pop = math.log10(pop_total)
    
    # Factor de seguridad (0.0 a 1.0)
    sec_factor = max(0, min(100, security_score)) / 100.0
    
    return (rate_base * log_pop) * sec_factor

# --- REGLAS DE SEGURIDAD SISTÉMICA (V4.4) ---

def calculate_planet_security(base_stat: int, pop_count: float, infrastructure_defense: int, orbital_ring: int) -> int:
    """
    Calcula el valor de seguridad (Sp) de un planeta.
    Fórmula: Sp = Base + (Pop * 5) + Infra - (2 * Ring)
    Regla: Si Pop == 0 -> Sp = 0.
    """
    if pop_count <= 0:
        return 0
        
    raw_security = base_stat + (pop_count * SECURITY_POP_MULT) + infrastructure_defense - (orbital_ring * RING_PENALTY)
    
    # Clamping entre 0 y 100
    return max(0, min(100, int(raw_security)))

def calculate_and_update_system_security(system_id: int):
    """
    Calcula la seguridad promedio de un sistema basado en sus planetas.
    Genera un desglose detallado para transparencia.
    """
    from data.world_repository import get_planets_by_system_id, update_system_security_data
    from data.database import get_supabase
    
    # Obtener planetas directamente con su seguridad actualizada
    # Nota: get_planets_by_system_id usa "select *" así que traerá 'security' si existe
    planets = get_planets_by_system_id(system_id)
    if not planets:
        return
        
    total_security = 0.0
    breakdown_lines = []
    
    count = 0
    for p in planets:
        # Priorizar la columna 'security' de la tabla 'planets' (Source of Truth V4.4)
        sec_val = p.get('security', 0.0)
        
        # Fallback defensivo si la migración no llenó defaults
        if sec_val is None: sec_val = 0.0
            
        total_security += sec_val
        breakdown_lines.append(f"{p['name']}: {sec_val:.1f}")
        count += 1
        
    avg_security = total_security / count if count > 0 else 0.0
    avg_security = round(avg_security, 2)
    
    breakdown_text = ", ".join(breakdown_lines)
    full_breakdown = {
        "text": f"Promedio: {avg_security} (De {count} cuerpos)",
        "details": breakdown_text,
        "planet_count": count
    }
    
    update_system_security_data(system_id, avg_security, full_breakdown)