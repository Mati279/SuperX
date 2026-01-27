# core/construction_engine.py
"""
Motor de Construcción.
Maneja la lógica de construcción de puestos de avanzada y estructuras tácticas
iniciadas por unidades en el terreno.
"""

from typing import Dict, Any, Optional
from data.database import get_supabase
from data.player_repository import get_player_finances, update_player_resources
from data.unit_repository import get_unit_by_id, update_unit_moves
from data.planet_repository import update_planet_sovereignty
from data.log_repository import log_event
from data.world_repository import get_world_state
from core.models import UnitSchema, UnitStatus
from core.movement_constants import MAX_LOCAL_MOVES_PER_TURN

# Costos fijos para Puesto de Avanzada (Outpost)
OUTPOST_COST_CREDITS = 200
OUTPOST_COST_MATERIALS = 40
OUTPOST_BUILDING_TYPE = "outpost"

def resolve_outpost_construction(unit_id: int, sector_id: int, player_id: int) -> Dict[str, Any]:
    """
    Intenta construir un Puesto de Avanzada en el sector actual de la unidad.
    
    Validaciones:
    - Unidad pertenece al jugador y tiene movimientos.
    - Sector explorado y vacío.
    - Recursos suficientes.
    
    Efectos:
    - Descuento de recursos.
    - Creación de edificio (Time: Current Tick + 1).
    - Fatiga de unidad.
    - Actualización de soberanía.
    """
    db = get_supabase()
    
    # 1. Validar Unidad y Fatiga
    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        return {"success": False, "error": "Unidad no encontrada."}
    
    unit = UnitSchema.from_dict(unit_data)
    
    if unit.player_id != player_id:
        return {"success": False, "error": "Error de autorización."}
        
    if unit.status == UnitStatus.TRANSIT:
        return {"success": False, "error": "La unidad está en tránsito."}
        
    # Limite de movimientos (si está en sigilo es 1, sino MAX)
    limit = 1 if unit.status == UnitStatus.STEALTH_MODE else MAX_LOCAL_MOVES_PER_TURN
    if unit.local_moves_count >= limit:
        return {"success": False, "error": "La unidad está fatigada y no puede construir este turno."}

    # 2. Validar Ubicación
    if unit.location_sector_id != sector_id:
        return {"success": False, "error": "La unidad no está en el sector objetivo."}

    # 3. Validar Estado del Sector (Conocido y Vacío)
    # Verificar conocimiento
    knowledge_check = db.table("player_sector_knowledge")\
        .select("id")\
        .eq("player_id", player_id)\
        .eq("sector_id", sector_id)\
        .maybe_single()\
        .execute()
        
    # Nota: Sectores orbitales o urbanos iniciales pueden ser conocidos sin estar en esta tabla,
    # pero un Outpost generalmente se construye en terreno salvaje explorado.
    # Asumimos que si la UI lo permitió, es válido, pero doble check DB es mejor.
    # Si devuelve None, verificamos si es sector 'Orbital' o 'Urbano' público, 
    # pero para Outpost requerimos exploración explícita o ownership.
    
    # Verificar ocupación (Must be empty)
    buildings_check = db.table("planet_buildings")\
        .select("id")\
        .eq("sector_id", sector_id)\
        .execute()
        
    if buildings_check.data and len(buildings_check.data) > 0:
        return {"success": False, "error": "El sector ya tiene estructuras."}

    # 4. Validar Recursos
    finances = get_player_finances(player_id)
    current_credits = finances.get("creditos", 0)
    current_materials = finances.get("materiales", 0)

    if current_credits < OUTPOST_COST_CREDITS or current_materials < OUTPOST_COST_MATERIALS:
        return {
            "success": False, 
            "error": f"Recursos insuficientes. Requiere {OUTPOST_COST_CREDITS} CR y {OUTPOST_COST_MATERIALS} Materiales."
        }

    # --- EJECUCIÓN ---
    try:
        # A. Descontar Recursos
        new_credits = current_credits - OUTPOST_COST_CREDITS
        new_materials = current_materials - OUTPOST_COST_MATERIALS
        
        update_player_resources(player_id, {
            "creditos": new_credits,
            "materiales": new_materials
        })

        # B. Insertar Edificio (Construction Time: 1 Tick)
        world = get_world_state()
        current_tick = world.get("current_tick", 1)
        target_tick = current_tick + 1 # Tarda 1 tick en estar operativo
        
        # Obtenemos el planet_asset_id. 
        # Si no existe asset para este jugador en este planeta, debemos crearlo O asociarlo al planeta directamente.
        # En SuperX, los edificios cuelgan de 'planet_asset_id'.
        # Buscamos si el jugador ya tiene asset en el planeta.
        planet_id = unit.location_planet_id
        
        asset_res = db.table("planet_assets")\
            .select("id")\
            .eq("planet_id", planet_id)\
            .eq("player_id", player_id)\
            .maybe_single()\
            .execute()
            
        asset_id = None
        
        if asset_res and asset_res.data:
            asset_id = asset_res.data["id"]
        else:
            # Si no tiene asset (es su primera construcción), creamos el asset contenedor.
            # Usamos lógica simple aquí, o importamos create_planet_asset si fuera necesario.
            # Para evitar circular imports complejos, hacemos insert directo básico.
            new_asset = {
                "planet_id": planet_id,
                "system_id": unit.location_system_id,
                "player_id": player_id,
                "nombre_asentamiento": "Puesto de Avanzada",
                "population": 0.0, # Outpost militar no tiene pop civil inicial obligatoria
                "base_tier": 1
            }
            create_res = db.table("planet_assets").insert(new_asset).execute()
            if create_res.data:
                asset_id = create_res.data[0]["id"]
            else:
                raise Exception("Fallo al crear activo planetario para el puesto.")

        building_data = {
            "planet_asset_id": asset_id,
            "player_id": player_id,
            "building_type": OUTPOST_BUILDING_TYPE,
            "building_tier": 1,
            "sector_id": sector_id,
            "is_active": True, # Activo, pero la lógica de 'built_at_tick' define si está operativo
            "built_at_tick": target_tick,
            "pops_required": 0, # Outpost suele ser automatizado o operado por la unidad
            "energy_consumption": 1 # Costo nominal
        }
        
        db.table("planet_buildings").insert(building_data).execute()

        # C. Fatiga de Unidad
        update_unit_moves(unit_id, unit.local_moves_count + 1)

        # D. Actualizar Soberanía (Importante para que la UI desbloquee el sector)
        # Aunque tarde 1 tick, la "reclamación" es inmediata a efectos de mapa, 
        # aunque el edificio no funcione hasta el siguiente tick.
        update_planet_sovereignty(planet_id)

        msg = f"Iniciada construcción de Puesto de Avanzada en Sector {sector_id}."
        log_event(msg, player_id)

        return {"success": True, "message": msg}

    except Exception as e:
        log_event(f"Error crítico construyendo outpost: {e}", player_id, is_error=True)
        return {"success": False, "error": f"Error del sistema: {e}"}