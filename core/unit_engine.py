# core/unit_engine.py (Completo)
"""
Motor de Lógica de Unidades y Tropas (V9.0).
Gestiona:
1. Registro de combates y nivelación (Level Up).
2. Promoción de Tropas a Héroes (Hero Spawn).
3. Gestión de miembros de unidad.
"""

from typing import Optional, Dict, Any, List
from data.unit_repository import (
    get_troop_by_id, 
    update_troop_stats, 
    delete_troop,
    get_unit_by_id,
    add_unit_member,
    remove_unit_member
)
from data.log_repository import log_event
from services.character_generation_service import recruit_character_with_ai
from core.models import TroopSchema, UnitSchema, CharacterRole

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