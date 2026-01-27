# core/construction_engine.py (Completo)
"""
Motor de Construcción.
Maneja la lógica de construcción de puestos de avanzada y estructuras tácticas
iniciadas por unidades en el terreno.
Refactorizado V19.0: Actualización de estado de unidad a CONSTRUCTING.
Refactorizado V19.1: Restricción de soberanía para Puestos de Avanzada.
Refactorizado V20.0: Restricciones de Sectores Urbanos y Soberanía Centralizada.
Refactorizado V20.1: Implementación de Construcción Orbital Táctica.
"""

from typing import Dict, Any, Optional
from data.database import get_supabase
from data.player_repository import get_player_finances, update_player_resources
from data.unit_repository import get_unit_by_id, update_unit_moves
from data.planet_repository import update_planet_sovereignty, create_planet_asset
from data.log_repository import log_event
from data.world_repository import get_world_state
from core.models import UnitSchema, UnitStatus
from core.movement_constants import MAX_LOCAL_MOVES_PER_TURN
from core.world_constants import SECTOR_TYPE_ORBITAL

# Costos fijos para Puesto de Avanzada (Outpost)
OUTPOST_COST_CREDITS = 200
OUTPOST_COST_MATERIALS = 40
OUTPOST_BUILDING_TYPE = "outpost"

# Costos fijos para Base Militar
BASE_COST_CREDITS = 500
BASE_COST_MATERIALS = 100

# Costos fijos para Estación Orbital (V20.1)
ORBITAL_STATION_COST_CREDITS = 800
ORBITAL_STATION_COST_MATERIALS = 30
ORBITAL_BUILDING_TYPE = "orbital_station"

def resolve_outpost_construction(unit_id: int, sector_id: int, player_id: int) -> Dict[str, Any]:
    """
    Intenta construir un Puesto de Avanzada en el sector actual de la unidad.
    
    Reglas Actualizadas V20.0:
    - PROHIBIDO en sectores 'URBAN'.
    - PROHIBIDO en CUALQUIER sector del planeta si el planeta tiene al menos un sector 'URBAN' (Soberanía Centralizada).
    - Soberanía: El jugador NO debe ser ya el dueño del planeta.
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
    
    if unit.status == UnitStatus.CONSTRUCTING:
         return {"success": False, "error": "La unidad ya está ocupada construyendo."}
        
    limit = 1 if unit.status == UnitStatus.STEALTH_MODE else MAX_LOCAL_MOVES_PER_TURN
    if unit.local_moves_count >= limit:
        return {"success": False, "error": "La unidad está fatigada y no puede construir este turno."}

    # 1.5 Validar Soberanía Planetaria Existente
    try:
        planet_check = db.table("planets")\
            .select("surface_owner_id")\
            .eq("id", unit.location_planet_id)\
            .maybe_single()\
            .execute()
            
        if planet_check.data:
            surface_owner = planet_check.data.get("surface_owner_id")
            if surface_owner == player_id:
                return {
                    "success": False, 
                    "error": "Tu facción ya controla la soberanía de este planeta. Construye infraestructura civil directamente."
                }
    except Exception as e:
        return {"success": False, "error": f"Error verificando soberanía planetaria: {e}"}

    # 2. Validar Ubicación
    if unit.location_sector_id != sector_id:
        return {"success": False, "error": "La unidad no está en el sector objetivo."}

    # --- REGLAS V20.0: RESTRICCIONES URBANAS ---
    
    # A. Verificar si el sector actual es URBANO
    target_sector_res = db.table("sectors").select("sector_type").eq("id", sector_id).maybe_single().execute()
    if target_sector_res.data and target_sector_res.data.get("sector_type") == "URBAN":
        return {
            "success": False, 
            "error": "🚫 No se pueden construir Puestos de Avanzada en sectores URBANOS. Debes subyugar la población y construir una Base Militar."
        }

    # B. Verificar si el planeta tiene ALGÚN sector URBANO (Bloqueo Planetario)
    urban_check = db.table("sectors")\
        .select("id")\
        .eq("planet_id", unit.location_planet_id)\
        .eq("sector_type", "URBAN")\
        .execute()
        
    if urban_check.data and len(urban_check.data) > 0:
        return {
            "success": False,
            "error": "🚫 Planeta Habitado: La soberanía se decide en los Centros Urbanos. No puedes reclamar territorio salvaje mediante Puestos de Avanzada."
        }

    # 3. Validar Estado del Sector (Ocupación)
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

        # B. Insertar Edificio
        world = get_world_state()
        current_tick = world.get("current_tick", 1)
        target_tick = current_tick + 1 
        
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
            new_asset = create_planet_asset(
                planet_id=planet_id,
                system_id=unit.location_system_id,
                player_id=player_id,
                settlement_name="Puesto de Avanzada",
                initial_population=0.0 
            )
            asset_id = new_asset["id"]

        building_data = {
            "planet_asset_id": asset_id,
            "player_id": player_id,
            "building_type": OUTPOST_BUILDING_TYPE,
            "building_tier": 1,
            "sector_id": sector_id,
            "is_active": True,
            "built_at_tick": target_tick,
            "pops_required": 0,
            "energy_consumption": 1
        }
        
        db.table("planet_buildings").insert(building_data).execute()

        # C. Fatiga
        db.table("units").update({
            "status": UnitStatus.CONSTRUCTING,
            "local_moves_count": MAX_LOCAL_MOVES_PER_TURN
        }).eq("id", unit_id).execute()

        # D. Actualizar Soberanía
        update_planet_sovereignty(planet_id)

        msg = f"Unidad '{unit.name}' iniciando construcción de Puesto de Avanzada en Sector {sector_id} (ETA: 1 ciclo)."
        log_event(msg, player_id)

        return {"success": True, "message": msg}

    except Exception as e:
        log_event(f"Error crítico construyendo outpost: {e}", player_id, is_error=True)
        return {"success": False, "error": f"Error del sistema: {e}"}

def resolve_base_construction(unit_id: int, sector_id: int, player_id: int) -> Dict[str, Any]:
    """
    Intenta construir una Base Militar en un sector URBANO.
    
    Reglas Actualizadas V20.0:
    - Permitido en 'URBAN' SOLO si `is_subjugated=True`.
    - No debe existir otra Base en el sector.
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
    
    if unit.status == UnitStatus.CONSTRUCTING:
         return {"success": False, "error": "La unidad ya está ocupada construyendo."}
        
    limit = 1 if unit.status == UnitStatus.STEALTH_MODE else MAX_LOCAL_MOVES_PER_TURN
    if unit.local_moves_count >= limit:
        return {"success": False, "error": "La unidad está fatigada y no puede construir este turno."}

    # 2. Validar Ubicación
    if unit.location_sector_id != sector_id:
        return {"success": False, "error": "La unidad no está en el sector objetivo."}

    # 3. Validar Tipo de Sector y Subyugación (V20.0)
    sector_res = db.table("sectors").select("sector_type, is_subjugated").eq("id", sector_id).maybe_single().execute()
    
    if not sector_res.data:
        return {"success": False, "error": "Sector no encontrado."}
    
    sector_data = sector_res.data
    
    if sector_data.get("sector_type") != "URBAN":
        return {"success": False, "error": "Las Bases Militares solo pueden construirse en sectores URBANOS."}

    # REGLA V20.0: Check de Subyugación
    if not sector_data.get("is_subjugated", False):
        return {
            "success": False, 
            "error": "🚫 Sector Urbano hostil. Debes SUBYUGAR la población local antes de establecer una Base Militar."
        }

    # 4. Validar Unicidad (No debe existir otra base en el sector)
    base_check = db.table("bases").select("id").eq("sector_id", sector_id).maybe_single().execute()
    if base_check.data:
        return {"success": False, "error": "Ya existe una Base Militar en este sector."}

    # 5. Validar Recursos
    finances = get_player_finances(player_id)
    current_credits = finances.get("creditos", 0)
    current_materials = finances.get("materiales", 0)

    if current_credits < BASE_COST_CREDITS or current_materials < BASE_COST_MATERIALS:
        return {
            "success": False, 
            "error": f"Recursos insuficientes. Requiere {BASE_COST_CREDITS} CR y {BASE_COST_MATERIALS} Materiales."
        }

    # --- EJECUCIÓN ---
    try:
        # A. Descontar Recursos
        new_credits = current_credits - BASE_COST_CREDITS
        new_materials = current_materials - BASE_COST_MATERIALS
        
        update_player_resources(player_id, {
            "creditos": new_credits,
            "materiales": new_materials
        })

        # B. Insertar Base
        world = get_world_state()
        current_tick = world.get("current_tick", 1)
        target_tick = current_tick + 1
        
        base_data = {
            "player_id": player_id,
            "planet_id": unit.location_planet_id,
            "sector_id": sector_id,
            "tier": 1,
            "created_at_tick": target_tick,
            "module_sensor_planetary": 0,
            "module_sensor_orbital": 0,
            "module_defense_ground": 0,
            "module_bunker": 0
        }
        
        insert_res = db.table("bases").insert(base_data).execute()
        
        if not insert_res.data:
            update_player_resources(player_id, {
                "creditos": current_credits,
                "materiales": current_materials
            })
            raise Exception("Error DB al insertar base.")

        # C. Fatiga
        db.table("units").update({
            "status": UnitStatus.CONSTRUCTING,
            "local_moves_count": MAX_LOCAL_MOVES_PER_TURN
        }).eq("id", unit_id).execute()

        # D. Actualizar Soberanía
        update_planet_sovereignty(unit.location_planet_id)

        msg = f"Unidad '{unit.name}' estableciendo Base Militar en Sector {sector_id} (ETA: 1 ciclo)."
        log_event(msg, player_id)

        return {"success": True, "message": msg}

    except Exception as e:
        log_event(f"Error crítico construyendo base militar: {e}", player_id, is_error=True)
        return {"success": False, "error": f"Error del sistema: {e}"}

def resolve_orbital_construction(unit_id: int, sector_id: int, player_id: int) -> Dict[str, Any]:
    """
    V20.1: Intenta construir una Estación Orbital en el sector actual de la unidad.
    
    Reglas:
    - Sector debe ser tipo 'ORBITAL'.
    - Solo una estructura por sector (máx 1 slot).
    - Costo: 800 CR / 30 MAT.
    - Tiempo: 2 ciclos.
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
    
    if unit.status == UnitStatus.CONSTRUCTING:
         return {"success": False, "error": "La unidad ya está ocupada construyendo."}
        
    limit = 1 if unit.status == UnitStatus.STEALTH_MODE else MAX_LOCAL_MOVES_PER_TURN
    if unit.local_moves_count >= limit:
        return {"success": False, "error": "La unidad está fatigada y no puede construir este turno."}

    # 2. Validar Ubicación y Tipo de Sector
    if unit.location_sector_id != sector_id:
        return {"success": False, "error": "La unidad no está en el sector objetivo."}
    
    sector_res = db.table("sectors").select("sector_type").eq("id", sector_id).maybe_single().execute()
    if not sector_res.data or sector_res.data.get("sector_type") != SECTOR_TYPE_ORBITAL:
         return {"success": False, "error": "Las Estaciones Orbitales solo pueden construirse en sectores ORBITAL."}

    # 3. Validar Ocupación (Máx 1 Estación)
    buildings_check = db.table("planet_buildings")\
        .select("id")\
        .eq("sector_id", sector_id)\
        .execute()
        
    if buildings_check.data and len(buildings_check.data) > 0:
        return {"success": False, "error": "El sector orbital ya está ocupado."}

    # 4. Validar Recursos
    finances = get_player_finances(player_id)
    current_credits = finances.get("creditos", 0)
    current_materials = finances.get("materiales", 0)

    if current_credits < ORBITAL_STATION_COST_CREDITS or current_materials < ORBITAL_STATION_COST_MATERIALS:
        return {
            "success": False, 
            "error": f"Recursos insuficientes. Requiere {ORBITAL_STATION_COST_CREDITS} CR y {ORBITAL_STATION_COST_MATERIALS} Materiales."
        }

    # --- EJECUCIÓN ---
    try:
        # A. Descontar Recursos
        new_credits = current_credits - ORBITAL_STATION_COST_CREDITS
        new_materials = current_materials - ORBITAL_STATION_COST_MATERIALS
        
        update_player_resources(player_id, {
            "creditos": new_credits,
            "materiales": new_materials
        })

        # B. Insertar Edificio (Asset creation if needed)
        world = get_world_state()
        current_tick = world.get("current_tick", 1)
        target_tick = current_tick + 2 # V20.1: Tarda 2 ciclos
        
        planet_id = unit.location_planet_id
        
        # Verificar o crear Asset
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
            new_asset = create_planet_asset(
                planet_id=planet_id,
                system_id=unit.location_system_id,
                player_id=player_id,
                settlement_name="Puesto Orbital",
                initial_population=0.0 
            )
            asset_id = new_asset["id"]

        building_data = {
            "planet_asset_id": asset_id,
            "player_id": player_id,
            "building_type": ORBITAL_BUILDING_TYPE,
            "building_tier": 1,
            "sector_id": sector_id,
            "is_active": True,
            "built_at_tick": target_tick,
            "pops_required": 20, # Requiere pops eventualmente, pero se construye vacía
            "energy_consumption": 0 # Inicial
        }
        
        db.table("planet_buildings").insert(building_data).execute()

        # C. Fatiga y Estado de Unidad
        db.table("units").update({
            "status": UnitStatus.CONSTRUCTING,
            "local_moves_count": MAX_LOCAL_MOVES_PER_TURN
        }).eq("id", unit_id).execute()

        # D. Actualizar Soberanía
        update_planet_sovereignty(planet_id)

        msg = f"Unidad '{unit.name}' iniciando despliegue de Estación Orbital en Sector {sector_id} (ETA: 2 ciclos)."
        log_event(msg, player_id)

        return {"success": True, "message": msg}

    except Exception as e:
        log_event(f"Error crítico construyendo estación orbital: {e}", player_id, is_error=True)
        return {"success": False, "error": f"Error del sistema: {e}"}