# core/exploration_engine.py (Completo)
"""
Motor de Exploración de Sectores V1.2.
Transforma la exploración de una acción de UI a una orden operativa basada en habilidades.
Gestiona la resolución MRG, la validación de ubicación y la narrativa técnica.
Actualizado V1.1: Dificultad Estándar (50) y penalización condicional (Solo Críticos).
Actualizado V1.2: Integración con sistema de fatiga de movimiento (local_moves_count).
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
from data.database import get_supabase, get_service_container
from data.log_repository import log_event

# Configuración del modelo para narrativas
EXPLORATION_MODEL_NAME = "gemini-2.5-flash"

@dataclass
class ExplorationResult:
    """Resultado de una operación de exploración."""
    success: bool
    mrg_result: MRGResult
    narrative: str
    sector_id: int
    unit_id: int
    details: Dict[str, Any]


def _generate_exploration_narrative(
    sector_data: Dict[str, Any],
    unit_name: str,
    success: bool,
    margin: int
) -> str:
    """
    Genera una narrativa técnica del hallazgo usando IA.
    """
    container = get_service_container()
    
    # Fallback si no hay IA disponible
    status_text = "ÉXITO CONFIRMADO" if success else "FALLO DE SENSORES"
    
    if not container.is_ai_available():
        if success:
            return f"REPORT: Análisis topográfico completado por {unit_name}. Sector cartografiado exitosamente."
        return f"REPORT: {unit_name} reporta fallo en sensores. Imposible establecer mapa detallado."

    try:
        # Prompt técnico para Gemini 2.5 Flash
        sector_type = sector_data.get('sector_type', 'Desconocido')
        planet_name = sector_data.get('planet_name', 'Planeta Desconocido')
        
        prompt = (
            f"Genera un reporte corto de exploración militar sci-fi (max 2 frases).\n"
            f"Unidad: {unit_name}\n"
            f"Objetivo: Sector {sector_type} en {planet_name}\n"
            f"Resultado: {status_text} (Margen: {margin})\n"
            f"Estilo: Técnico, breve, transmisión de datos."
        )

        response = container.ai.models.generate_content(
            model=EXPLORATION_MODEL_NAME,
            contents=prompt
        )
        return response.text.strip()
        
    except Exception as e:
        print(f"Error generando narrativa de exploración: {e}")
        return f"Datos de exploración procesados. Estado: {status_text}."


def resolve_sector_exploration(
    unit_id: int, 
    sector_id: int, 
    player_id: int
) -> ExplorationResult:
    """
    Ejecuta una operación de exploración sobre un sector.
    
    Reglas V1.2:
    1. La unidad debe estar en el mismo planeta/ubicación que el sector.
    2. MRG: skill_exploracion vs Dificultad 50 (STANDARD).
    3. Consume 1 Movimiento Local (Fatiga).
    4. Éxito: Revela el sector (grant_sector_knowledge).
    5. Fallo:
       - Fallo Normal: Consume acción pero no bloquea totalmente.
       - Fallo Crítico/Total: Bloquea movimiento (fatiga de sensores) y quema todos los movimientos restantes del turno.
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

    # V1.2 Validación de Fatiga de Movimiento
    move_limit = 1 if unit.status == UnitStatus.STEALTH_MODE else MAX_LOCAL_MOVES_PER_TURN
    
    if unit.local_moves_count >= move_limit:
        raise ValueError(f"La unidad no tiene acciones suficientes para explorar. ({unit.local_moves_count}/{move_limit})")

    if unit.movement_locked:
        raise ValueError("La unidad tiene sus sistemas de navegación bloqueados.")

    # 2. Obtener y Validar Sector
    # Necesitamos saber en qué planeta está el sector para comparar con la unidad
    sector_data = get_sector_by_id(sector_id) # Asumiendo existencia de esta función o fetch directo
    if not sector_data:
        # Fallback manual si no existe el helper
        db = get_supabase()
        # V1.2 Fix: Corrección de nombre de tabla 'map_sectors' a 'sectors'
        resp = db.table('sectors').select('*, planets(name)').eq('id', sector_id).single().execute()
        if not resp.data:
            raise ValueError(f"Sector {sector_id} no encontrado.")
        sector_data = resp.data
        # Aplanar nombre del planeta para el prompt
        if sector_data.get('planets'):
            sector_data['planet_name'] = sector_data['planets'].get('name')

    sector_planet_id = sector_data.get('planet_id')
    
    # Validación de Proximidad Física
    # La unidad debe estar en el mismo planeta que el sector objetivo
    if unit.location_planet_id != sector_planet_id:
        raise ValueError(f"La unidad debe estar en la superficie del planeta para explorar este sector.")

    # 3. Preparar Tirada MRG
    # Usar skill_exploracion (Habilidad Colectiva de Unidad V17)
    merit_points = unit.skill_exploracion
    difficulty = DIFFICULTY_STANDARD # 50 (Ajuste V1.1)
    
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

    # 4. Procesar Consecuencias
    success = mrg_result.success
    narrative = _generate_exploration_narrative(sector_data, unit.name, success, mrg_result.margin)
    
    # V1.2: Consumir Acción (Siempre incrementa fatiga al explorar)
    increment_unit_local_moves(unit_id)

    if success:
        # Revelar sector
        grant_sector_knowledge(player_id, sector_id)
        log_event(f"🗺️ Exploración exitosa: {unit.name} ha cartografiado un nuevo sector. {narrative}", player_id)
    else:
        # Penalización Condicional (V1.1 y V1.2)
        # Solo bloqueamos movimiento si es un fallo grave (CRITICAL o TOTAL)
        is_severe_failure = mrg_result.result_type in [ResultType.CRITICAL_FAILURE, ResultType.TOTAL_FAILURE]
        
        if is_severe_failure:
            # V1.2: Quemar turno completo (Simular que gastó todas las acciones tratando de recuperarse)
            # Forzamos local_moves_count al límite y bloqueamos
            updates = {
                'movement_locked': True,
                'local_moves_count': move_limit 
            }
            get_supabase().table('units').update(updates).eq('id', unit.id).execute()
            
            log_event(f"❌ FALLO CRÍTICO DE SENSORES: {unit.name} pierde el resto del turno. Movimiento bloqueado. {narrative}", player_id)
        else:
            log_event(f"⚠️ Exploración fallida: {unit.name} no pudo obtener datos concluyentes. Acción consumida. {narrative}", player_id)

    return ExplorationResult(
        success=success,
        mrg_result=mrg_result,
        narrative=narrative,
        sector_id=sector_id,
        unit_id=unit.id,
        details=sector_data
    )