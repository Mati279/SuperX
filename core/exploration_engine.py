# core/exploration_engine.py (Completo)
"""
Motor de Exploración de Sectores V1.5.
Transforma la exploración de una acción de UI a una orden operativa basada en habilidades.
Gestiona la resolución MRG, la validación de ubicación y la narrativa determinista.
Actualizado V1.5: 
- Eliminado recálculo forzado de habilidades al vuelo; ahora confía estrictamente en el valor persistido en DB (unit.skill_exploracion).
- Optimización de lecturas a base de datos (eliminada lectura redundante).
- Formateo estandarizado de recursos en narrativa y logs.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass

from core.mrg_engine import resolve_action, MRGResult, ResultType
from core.models import UnitSchema, UnitStatus
from core.mrg_constants import DIFFICULTY_STANDARD
from core.movement_constants import MAX_LOCAL_MOVES_PER_TURN
# Importación eliminada para evitar recálculo forzado
# from core.unit_engine import calculate_and_update_unit_skills
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
    
    Reglas V1.5:
    1. Validación de unidad básica.
    2. Validación de fatiga con datos frescos.
    3. Extracción directa de skill_exploracion desde la unidad (DB).
    4. MRG: skill_exploracion vs Dificultad 50 (STANDARD).
    5. Narrativa estandarizada: 'Sector {nombre}. Recursos: {lista}.'
    """
    
    # 1. Obtener y Validar Unidad (Fuente de verdad: Base de Datos)
    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        raise ValueError(f"Unidad {unit_id} no encontrada.")
    
    # Hidratación del esquema (incluye skill_exploracion)
    unit = UnitSchema.from_dict(unit_data)
    
    if unit.player_id != player_id:
        raise PermissionError("No tienes autoridad sobre esta unidad.")
        
    if unit.status == UnitStatus.TRANSIT:
        raise ValueError("La unidad está en tránsito y no puede realizar exploraciones.")

    # 2. Extracción EXPLÍCITA de skill_exploracion (Sin recálculo al vuelo)
    # Se usa estrictamente el valor almacenado en la columna 'skill_exploracion'
    unit_skill_exploracion = unit.skill_exploracion if unit.skill_exploracion is not None else 0

    # Log de diagnóstico si el skill es 0 (posible unidad antigua o sin actualizar)
    if unit_skill_exploracion == 0:
        log_event(
            f"⚠️ DEBUG: La unidad {unit.name} está explorando con skill_exploracion=0. Verifique que sus stats estén actualizados.",
            player_id,
            event_type="SKILL_WARNING"
        )

    # Validación de Fatiga de Movimiento
    move_limit = 1 if unit.status == UnitStatus.STEALTH_MODE else MAX_LOCAL_MOVES_PER_TURN
    
    if unit.local_moves_count >= move_limit:
        raise ValueError(f"La unidad no tiene acciones suficientes para explorar. ({unit.local_moves_count}/{move_limit})")

    if unit.movement_locked:
        raise ValueError("La unidad tiene sus sistemas de navegación bloqueados.")

    # 3. Obtener y Validar Sector
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

    # 4. Preparar Tirada MRG
    # IMPORTANTE: Usamos el skill_exploracion DIRECTO de la UNIDAD.
    merit_points = unit_skill_exploracion
    difficulty = DIFFICULTY_STANDARD  # 50

    action_desc = f"Exploración de Sector {sector_id} por {unit.name}"

    mrg_result = resolve_action(
        merit_points=merit_points,
        difficulty=difficulty,
        action_description=action_desc,
        player_id=player_id,
        skill_source="unit.skill_exploracion (DB)",  # Trazabilidad clara
        details={
            "unit_id": unit.id,
            "unit_name": unit.name,
            "sector_id": sector_id,
            "sector_type": sector_data.get('sector_type'),
            "skill_exploracion_usado": unit_skill_exploracion
        }
    )

    # 5. Procesar Consecuencias y Narrativa
    success = mrg_result.success
    narrative = ""
    
    # Consumir Acción (Siempre incrementa fatiga al explorar)
    increment_unit_local_moves(unit_id)

    if success:
        # --- Construcción de Notificación de Recursos ---
        sec_name = sector_data.get('name', f"S-{sector_id}")
        
        resources_list = []
        if sector_data.get('resource_category'):
            resources_list.append(sector_data['resource_category'])
        if sector_data.get('luxury_resource'):
            resources_list.append(sector_data['luxury_resource'])
            
        if resources_list:
            resource_info = ", ".join(resources_list)
        else:
            resource_info = "Ninguno"

        # Formateo de nombre de sector para evitar "Sector Sector..."
        display_name = sec_name
        if not display_name.strip().lower().startswith("sector"):
            display_name = f"Sector {sec_name}"
        
        narrative = f"{display_name}. Recursos: {resource_info}."
        
        # Efecto mecánico: Revelar sector
        grant_sector_knowledge(player_id, sector_id)

        # Log estandarizado
        log_event(
            f"{narrative} (Skill: {unit_skill_exploracion})",
            player_id,
            event_type="EXPLORATION_SUCCESS"
        )

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

            log_event(
                f"{narrative} ({unit.name}, Skill: {unit_skill_exploracion})",
                player_id,
                event_type="EXPLORATION_CRITICAL_FAIL"
            )
        else:
            narrative = "Interferencia en los sensores. Datos no concluyentes."
            log_event(
                f"⚠️ Exploración fallida: {unit.name} no pudo obtener datos. (Skill: {unit_skill_exploracion})",
                player_id,
                event_type="EXPLORATION_FAIL"
            )

    return ExplorationResult(
        success=success,
        mrg_result=mrg_result,
        narrative=narrative,
        sector_id=sector_id,
        unit_id=unit.id,
        details=sector_data
    )