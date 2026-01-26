# core/unit_engine.py (Completo)
"""
Motor de Lógica de Unidades y Tropas (V9.0, V16.0).
Gestiona:
1. Registro de combates y nivelación (Level Up).
2. Promoción de Tropas a Héroes (Hero Spawn).
3. Gestión de miembros de unidad.
4. V16.0: Liderazgo dinámico y supervivencia de tropas.
"""

from typing import Optional, Dict, Any, List
from data.unit_repository import (
    get_troop_by_id,
    update_troop_stats,
    delete_troop,
    get_unit_by_id,
    get_units_by_player,
    add_unit_member,
    remove_unit_member,
    get_unit_leader_skill
)
from data.log_repository import log_event
from services.character_generation_service import recruit_character_with_ai
from core.models import TroopSchema, UnitSchema, UnitMemberSchema, CharacterRole, UnitStatus
from data.character_repository import get_character_by_id

# Constantes de configuración
MAX_TROOP_LEVEL = 4
COST_PER_TRANSIT_TROOP = 5  # Créditos por tick por tropa en espacio

def get_combats_required_for_next_level(current_level: int) -> int:
    """
    Calcula combates necesarios para subir de nivel.
    Regla: combats_required = 2 * target_level
    """
    target_level = current_level + 1
    return 2 * target_level

def process_troop_combat_experience(troop_id: int, unit_id: int) -> Dict[str, Any]:
    """
    Procesa la experiencia de combate de una tropa.
    Maneja Level Up y Hero Spawn.
    """
    troop_data = get_troop_by_id(troop_id)
    if not troop_data:
        return {"status": "error", "message": "Troop not found"}

    troop = TroopSchema(**troop_data)
    player_id = troop.player_id
    
    # Incrementar combates
    new_combats = troop.combats_at_current_level + 1
    required = get_combats_required_for_next_level(troop.level)
    
    result = {
        "status": "updated", 
        "level_up": False, 
        "promoted_to_hero": False,
        "old_level": troop.level,
        "new_level": troop.level
    }

    if new_combats >= required:
        # Lógica de Nivelación
        if troop.level < MAX_TROOP_LEVEL:
            # LEVEL UP NORMAL
            new_level = troop.level + 1
            update_troop_stats(troop_id, combats=0, level=new_level)
            log_event(f"🎖️ Tropa '{troop.name}' ascendió a Nivel {new_level}!", player_id)
            result["level_up"] = True
            result["new_level"] = new_level
            
        elif troop.level == MAX_TROOP_LEVEL:
            # HERO SPAWN (Nivel Máximo alcanzado + Combates completados)
            if _trigger_hero_promotion(troop, unit_id):
                result["promoted_to_hero"] = True
                result["status"] = "promoted"
            else:
                # Fallback si falla la promoción (mantiene stats maxeadas)
                update_troop_stats(troop_id, combats=new_combats)
    else:
        # Solo actualizar contador
        update_troop_stats(troop_id, combats=new_combats)

    return result

def _trigger_hero_promotion(troop: TroopSchema, unit_id: int) -> bool:
    """
    Ejecuta la promoción de Tropa a Héroe (Character).
    1. Obtiene ubicación de la unidad.
    2. Genera Character en esa ubicación exacta.
    3. Elimina la tropa.
    4. (Opcional) Asigna el héroe a la unidad si hay espacio (TODO).
    """
    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        log_event(f"Error Promoción: Unidad {unit_id} no encontrada.", troop.player_id, is_error=True)
        return False

    unit = UnitSchema(**unit_data)
    
    # 1. Spawn Hero
    try:
        new_hero = recruit_character_with_ai(
            player_id=troop.player_id,
            location_planet_id=unit.location_planet_id,
            location_system_id=unit.location_system_id,
            location_sector_id=unit.location_sector_id,
            min_level=2,  # Héroes nacen veteranos
            max_level=4,
            initial_knowledge_level="known" # Ya es conocido por ser de tus tropas
        )
        
        if new_hero:
            hero_name = f"{new_hero.get('nombre')} {new_hero.get('rango')}"
            
            # 2. Eliminar Tropa Antigua
            # Primero remover de la unidad para liberar slot (si la DB no tiene cascade en members)
            # Asumimos que delete_troop limpia, pero por seguridad removemos referencia logica si hiciera falta.
            delete_troop(troop.id)
            
            # 3. Log
            log_event(
                f"🌟 EVENTO HEROICO: El escuadrón '{troop.name}' ha producido un líder. "
                f"¡Bienvenido {hero_name}!", 
                troop.player_id
            )
            return True
            
    except Exception as e:
        log_event(f"Error crítico en Hero Spawn: {e}", troop.player_id, is_error=True)
        return False

    return False


# --- V16.0: LIDERAZGO DINÁMICO Y SUPERVIVENCIA ---

# Constantes de capacidad
BASE_CAPACITY = 4
MAX_CAPACITY = 12


def calculate_unit_max_capacity(unit_id: int) -> int:
    """
    V16.0: Calcula la capacidad máxima de una unidad basada en su líder.
    Fórmula: 4 + (skill_liderazgo // 10)
    Rango: 4 (sin líder) a 12 (liderazgo 80+)
    """
    leader_skill = get_unit_leader_skill(unit_id)
    bonus = leader_skill // 10
    return min(MAX_CAPACITY, BASE_CAPACITY + bonus)


def is_location_controlled(player_id: int, location_data: Dict[str, Any]) -> bool:
    """
    V16.0: Verifica si un jugador controla un territorio dado.

    Reglas de control:
    - Planeta: surface_owner_id o orbital_owner_id == player_id
    - Sistema (sin planeta): controlling_player_id == player_id
    - Neutral (todos NULL): Considerado seguro/controlado

    Retorna True si el territorio es controlado o neutral.
    """
    from data.planet_repository import get_planet_by_id
    from data.world_repository import get_system_by_id

    planet_id = location_data.get("location_planet_id")
    system_id = location_data.get("location_system_id")

    # 1. Si hay planeta, verificar soberanía planetaria
    if planet_id:
        planet = get_planet_by_id(planet_id)
        if planet:
            surface_owner = planet.get("surface_owner_id")
            orbital_owner = planet.get("orbital_owner_id")

            # Neutral = controlado para este propósito
            if surface_owner is None and orbital_owner is None:
                return True

            # Controlado si soy dueño de superficie u órbita
            if surface_owner == player_id or orbital_owner == player_id:
                return True

            # Territorio hostil
            return False

    # 2. Si solo hay sistema (espacio profundo), verificar controlador
    if system_id:
        system = get_system_by_id(system_id)
        if system:
            controller = system.get("controlling_player_id")

            # Neutral = controlado para este propósito
            if controller is None:
                return True

            # Controlado si soy el controlador del sistema
            if controller == player_id:
                return True

            # Territorio hostil en espacio
            return False

    # 3. Sin ubicación definida, considerar seguro
    return True


def check_unit_at_risk(unit_id: int, player_id: int) -> Dict[str, Any]:
    """
    V16.0: Determina si una unidad está en riesgo.

    Condiciones de riesgo:
    1. Ubicación en territorio hostil (controlado por otro jugador)
    2. Número de miembros excede capacidad del líder

    Retorna dict con:
    - is_at_risk: bool
    - is_hostile_territory: bool
    - is_overcapacity: bool
    - current_count: int
    - max_capacity: int
    """
    result = {
        "is_at_risk": False,
        "is_hostile_territory": False,
        "is_overcapacity": False,
        "current_count": 0,
        "max_capacity": BASE_CAPACITY
    }

    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        return result

    # Convertir a modelo para acceder a members
    members = unit_data.get("members", [])
    result["current_count"] = len(members)

    # 1. Verificar control territorial
    location_data = {
        "location_system_id": unit_data.get("location_system_id"),
        "location_planet_id": unit_data.get("location_planet_id"),
        "location_sector_id": unit_data.get("location_sector_id")
    }

    is_hostile = not is_location_controlled(player_id, location_data)
    result["is_hostile_territory"] = is_hostile

    # 2. Verificar capacidad excedida
    max_cap = calculate_unit_max_capacity(unit_id)
    result["max_capacity"] = max_cap
    is_overcapacity = len(members) > max_cap
    result["is_overcapacity"] = is_overcapacity

    # Está en riesgo si hostil O excede capacidad
    result["is_at_risk"] = is_hostile or is_overcapacity

    return result


def handle_unit_leadership_change(unit_id: int) -> Dict[str, Any]:
    """
    V16.0: Maneja el cambio de líder de una unidad.
    Si el nuevo líder tiene menos capacidad, marca excedentes para eliminación.

    Retorna dict con:
    - new_capacity: Nueva capacidad máxima
    - excess_count: Número de miembros excedentes
    - marked_for_removal: Lista de entity_ids de tropas marcadas
    """
    result = {
        "new_capacity": BASE_CAPACITY,
        "excess_count": 0,
        "marked_for_removal": []
    }

    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        return result

    members = unit_data.get("members", [])
    new_capacity = calculate_unit_max_capacity(unit_id)
    result["new_capacity"] = new_capacity

    current_count = len(members)

    if current_count > new_capacity:
        excess = current_count - new_capacity
        result["excess_count"] = excess

        # Marcar tropas excedentes (NUNCA personajes)
        # Priorizar tropas de menor nivel para eliminación
        troops = [m for m in members if m.get("entity_type") == 'troop']

        # Ordenar por nivel (menor primero)
        troops_sorted = sorted(
            troops,
            key=lambda t: t.get("details", {}).get("level", 1) if t.get("details") else 1
        )

        for i in range(min(excess, len(troops_sorted))):
            result["marked_for_removal"].append(troops_sorted[i].get("entity_id"))

    return result


def process_troop_survival(player_id: int, current_tick: int) -> Dict[str, Any]:
    """
    V16.0: Procesa la supervivencia de tropas huérfanas en territorio hostil.

    CRÍTICO: Solo elimina entidades tipo 'troop', NUNCA personajes.

    Condiciones de eliminación:
    - Unidad en territorio hostil (no controlado)
    - Unidad excede su capacidad máxima
    - Unidad NO está en TRANSIT (protegidas durante viaje)

    Retorna:
    - troops_removed: Lista de IDs de tropas eliminadas
    - units_affected: Lista de IDs de unidades afectadas
    - total_removed: Conteo total
    """
    result = {
        "troops_removed": [],
        "units_affected": [],
        "total_removed": 0
    }

    units = get_units_by_player(player_id)

    for unit_data in units:
        unit_id = unit_data.get("id")
        unit_status = unit_data.get("status")
        unit_name = unit_data.get("name", f"Unidad {unit_id}")

        # Saltar unidades en tránsito (protegidas)
        if unit_status == UnitStatus.TRANSIT.value or unit_status == "TRANSIT":
            continue

        # Verificar riesgo
        risk_check = check_unit_at_risk(unit_id, player_id)

        # Solo procesar si está en territorio hostil Y excede capacidad
        if not risk_check["is_hostile_territory"]:
            continue

        if not risk_check["is_overcapacity"]:
            # En territorio hostil pero dentro de capacidad: advertir pero no eliminar
            continue

        # Calcular cuántas tropas eliminar
        members = unit_data.get("members", [])
        max_cap = risk_check["max_capacity"]
        current_count = len(members)
        excess = current_count - max_cap

        if excess <= 0:
            continue

        # Obtener solo tropas (NUNCA personajes)
        troops = [m for m in members if m.get("entity_type") == 'troop']

        if not troops:
            continue  # Sin tropas que eliminar

        # Ordenar por nivel (eliminar las de menor nivel primero)
        troops_sorted = sorted(
            troops,
            key=lambda t: t.get("details", {}).get("level", 1) if t.get("details") else 1
        )

        # Eliminar hasta cubrir el exceso
        removed_count = 0
        for troop_member in troops_sorted:
            if removed_count >= excess:
                break

            troop_id = troop_member.get("entity_id")
            slot_index = troop_member.get("slot_index")

            # 1. Remover de la unidad
            if remove_unit_member(unit_id, slot_index):
                # 2. Eliminar la tropa de la DB
                if delete_troop(troop_id):
                    result["troops_removed"].append(troop_id)
                    removed_count += 1

        if removed_count > 0:
            result["units_affected"].append(unit_id)
            log_event(
                f"⚠️ Deserción: {removed_count} tropa(s) de '{unit_name}' "
                f"se perdieron en territorio hostil por falta de liderazgo.",
                player_id
            )

    result["total_removed"] = len(result["troops_removed"])
    return result


def calculate_unit_exploration_merit(unit_id: int) -> int:
    """
    V16.0: Calcula el mérito de exploración de una unidad.
    Formula: (Promedio de 'Orientación y exploración' de personajes) + (3 * Cantidad de personajes).
    Valor base de habilidad: 5.
    """
    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        return 5

    members = unit_data.get("members", [])
    if not members:
        return 5

    character_skills = []
    
    for member in members:
        if member.get("entity_type") == "character":
            char_id = member.get("entity_id")
            char_data = get_character_by_id(char_id)
            if char_data:
                stats = char_data.get("stats_json", {})
                skills = stats.get("capacidades", {}).get("habilidades", {})
                # Skill base 5 si no existe
                skill_val = skills.get("Orientación y exploración", 5)
                # Validación adicional por si viene nulo
                if skill_val is None: skill_val = 5
                character_skills.append(skill_val)

    count = len(character_skills)
    if count == 0:
        return 5 # Valor base para unidad sin oficiales/personajes

    avg_skill = sum(character_skills) / count
    merit = avg_skill + (3 * count)
    
    return int(round(merit))