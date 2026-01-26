# core/exploration_engine.py (Completo)
"""
Motor de Exploración de Sectores V1.3.
Transforma la exploración de una acción de UI a una orden operativa basada en habilidades.
Gestiona la resolución MRG, la validación de ubicación y la narrativa determinista.
Actualizado V1.3: Eliminación de dependencia de IA para narrativas. Textos estandarizados.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass

from core.mrg_engine import resolve_action, MRGResult, ResultType
from core.models import UnitSchema, UnitStatus
from core.mrg_constants import DIFFICULTY_STANDARD
from core.movement_constants import MAX_LOCAL_MOVES_PER_TURN
from data.unit_repository import (
    get_unit_by_id, 
    update_unit_status, 
    increment_unit_local_moves
)
from data.planet_repository import grant_sector_knowledge, get_sector_by_id
from data.database import get_supabase
from data.log_repository import log_event

@dataclass
class ExplorationResult:
    """Resultado de una operación de exploración."""
    success: bool
    mrg_result: MRGResult
    narrative: str
    sector_id: int
    unit_id: int
    details: Dict[str, Any]


def resolve_sector_exploration(
    unit_id: int, 
    sector_id: int, 
    player_id: int
) -> ExplorationResult:
    """
    Ejecuta una operación de exploración sobre un sector.
    
    Reglas V1.3:
    1. Validación de ubicación y fatiga.
    2. MRG: skill_exploracion vs Dificultad 50 (STANDARD).
    3. Narrativa Determinista (Sin IA).
    4. Consecuencias mecánicas directas.
    """
    
    # 1. Obtener y Validar Unidad
    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        raise ValueError(f"Unidad {unit_id} no encontrada.")
    
    unit = UnitSchema.from_dict(unit_data)
    
    if unit.player_id != player_id:
        raise PermissionError("No tienes autoridad sobre esta unidad.")
        
    if unit.status == UnitStatus.TRANSIT:
        raise ValueError("La unidad está en tránsito y no puede realizar exploraciones.")

    # Validación de Fatiga de Movimiento
    move_limit = 1 if unit.status == UnitStatus.STEALTH_MODE else MAX_LOCAL_MOVES_PER_TURN
    
    if unit.local_moves_count >= move_limit:
        raise ValueError(f"La unidad no tiene acciones suficientes para explorar. ({unit.local_moves_count}/{move_limit})")

    if unit.movement_locked:
        raise ValueError("La unidad tiene sus sistemas de navegación bloqueados.")

    # 2. Obtener y Validar Sector
    # Se ajusta la consulta para asegurar campos de recursos y nombre
    db = get_supabase()
    resp = db.table('sectors').select('*, resource_category, luxury_resource, planets(name)').eq('id', sector_id).single().execute()
    
    if not resp.data:
        raise ValueError(f"Sector {sector_id} no encontrado.")
    
    sector_data = resp.data
    
    # Aplanar nombre del planeta y asegurar nombre del sector
    if sector_data.get('planets'):
        sector_data['planet_name'] = sector_data['planets'].get('name')
    
    # Si el sector no tiene columna 'name', usamos el ID como fallback visual
    if 'name' not in sector_data or not sector_data['name']:
        sector_data['name'] = f"S-{sector_id}"

    sector_planet_id = sector_data.get('planet_id')
    
    # Validación de Proximidad Física
    if unit.location_planet_id != sector_planet_id:
        raise ValueError(f"La unidad debe estar en la superficie del planeta para explorar este sector.")

    # 3. Preparar Tirada MRG
    merit_points = unit.skill_exploracion
    difficulty = DIFFICULTY_STANDARD # 50
    
    action_desc = f"Exploración de Sector {sector_id} por {unit.name}"

    mrg_result = resolve_action(
        merit_points=merit_points,
        difficulty=difficulty,
        action_description=action_desc,
        player_id=player_id,
        details={
            "unit_id": unit.id,
            "sector_id": sector_id,
            "sector_type": sector_data.get('sector_type')
        }
    )

    # 4. Procesar Consecuencias y Narrativa Manual
    success = mrg_result.success
    narrative = ""
    
    # Consumir Acción (Siempre incrementa fatiga al explorar)
    increment_unit_local_moves(unit_id)

    if success:
        narrative = "Sector cartografiado. Análisis de recursos completado."
        
        # Efecto mecánico: Revelar sector
        grant_sector_knowledge(player_id, sector_id)
        log_event(f"🗺️ Exploración exitosa: {unit.name} ha cartografiado el sector {sector_data['name']}.", player_id)

    else:
        # Penalización Condicional
        is_severe_failure = mrg_result.result_type in [ResultType.CRITICAL_FAILURE, ResultType.TOTAL_FAILURE]
        
        if is_severe_failure:
            narrative = "❌ La unidad se ha perdido, pierde sus acciones por el resto del turno."
            
            # Efecto mecánico: Bloqueo total
            updates = {
                'movement_locked': True,
                'local_moves_count': move_limit 
            }
            get_supabase().table('units').update(updates).eq('id', unit.id).execute()
            
            log_event(f"{narrative} ({unit.name})", player_id)
        else:
            narrative = "Interferencia en los sensores. Datos no concluyentes."
            log_event(f"⚠️ Exploración fallida: {unit.name} no pudo obtener datos. Acción consumida.", player_id)

    return ExplorationResult(
        success=success,
        mrg_result=mrg_result,
        narrative=narrative,
        sector_id=sector_id,
        unit_id=unit.id,
        details=sector_data
    )