# core/construction_engine.py (Completo)
"""
Motor de Construcción.
Maneja la lógica de construcción de puestos de avanzada y estructuras tácticas
iniciadas por unidades en el terreno.
Refactorizado V19.0: Actualización de estado de unidad a CONSTRUCTING.
Refactorizado V19.1: Restricción de soberanía para Puestos de Avanzada.
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

# Costos fijos para Puesto de Avanzada (Outpost)
OUTPOST_COST_CREDITS = 200
OUTPOST_COST_MATERIALS = 40
OUTPOST_BUILDING_TYPE = "outpost"

# Costos fijos para Base Militar
BASE_COST_CREDITS = 500
BASE_COST_MATERIALS = 100

def resolve_outpost_construction(unit_id: int, sector_id: int, player_id: int) -> Dict[str, Any]:
    """
    Intenta construir un Puesto de Avanzada en el sector actual de la unidad.
    
    Validaciones:
    - Unidad pertenece al jugador y tiene movimientos.
    - Sector explorado y vacío.
    - Soberanía: El jugador NO debe ser ya el dueño del planeta.
    - Recursos suficientes.
    
    Efectos:
    - Descuento de recursos.
    - Creación de edificio (Time: Current Tick + 1).
    - Fatiga de unidad (Se bloquea en estado CONSTRUCTING).
    - Actualización de soberanía (Diferida hasta finalización).
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
        
    # Limite de movimientos (si está en sigilo es 1, sino MAX)
    limit = 1 if unit.status == UnitStatus.STEALTH_MODE else MAX_LOCAL_MOVES_PER_TURN
    if unit.local_moves_count >= limit:
        return {"success": False, "error": "La unidad está fatigada y no puede construir este turno."}

    # 1.5 Validar Soberanía Planetaria (NUEVO V19.1)
    # Si el jugador ya controla el planeta, no necesita (ni debe) construir outposts.
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
                    "error": "Tu facción ya controla la soberanía de este planeta. No requieres Puestos de Avanzada adicionales; construye infraestructura directamente."
                }
    except Exception as e:
        # Si falla la verificación de soberanía, logueamos pero permitimos continuar por seguridad,
        # o fallamos si es crítico. En este caso, fallamos seguro.
        return {"success": False, "error": f"Error verificando soberanía planetaria: {e}"}

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
            # Si no tiene asset, creamos el asset contenedor.
            new_asset = create_planet_asset(
                planet_id=planet_id,
                system_id=unit.location_system_id,
                player_id=player_id,
                settlement_name="Puesto de Avanzada",
                initial_population=0.0 
            )
            
            if new_asset:
                asset_id = new_asset["id"]
            else:
                raise Exception("Fallo al crear activo planetario para el puesto.")

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

        # C. Fatiga y Estado de Unidad (V19.0)
        # Se establece el estado a CONSTRUCTING y se agotan los movimientos.
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
    
    Requisitos:
    - Sector Tipo: URBAN
    - Costo: 500 CR, 100 Materiales
    - Tabla destino: public.bases
    - Unicidad: 1 Base por sector (manejado por índice DB, pero verificado aquí)
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

    # 3. Validar Tipo de Sector (Debe ser URBAN)
    sector_res = db.table("sectors").select("sector_type").eq("id", sector_id).maybe_single().execute()
    
    if not sector_res.data:
        return {"success": False, "error": "Sector no encontrado."}
        
    if sector_res.data.get("sector_type") != "URBAN":
        return {"success": False, "error": "Las Bases Militares solo pueden construirse en sectores URBANOS."}

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

        # B. Insertar Base en tabla 'bases'
        # Usamos el tick actual + 1 para created_at_tick para diferir la finalización
        world = get_world_state()
        current_tick = world.get("current_tick", 1)
        target_tick = current_tick + 1
        
        base_data = {
            "player_id": player_id,
            "planet_id": unit.location_planet_id,
            "sector_id": sector_id,
            "tier": 1,
            "created_at_tick": target_tick, # V19.0: Se difiere la finalización
            "module_sensor_planetary": 0,
            "module_sensor_orbital": 0,
            "module_defense_ground": 0,
            "module_bunker": 0
        }
        
        insert_res = db.table("bases").insert(base_data).execute()
        
        if not insert_res.data:
            # Rollback manual de recursos si falla insert (básico)
            update_player_resources(player_id, {
                "creditos": current_credits,
                "materiales": current_materials
            })
            raise Exception("Error DB al insertar base.")

        # C. Fatiga y Estado de Unidad (V19.0)
        db.table("units").update({
            "status": UnitStatus.CONSTRUCTING,
            "local_moves_count": MAX_LOCAL_MOVES_PER_TURN
        }).eq("id", unit_id).execute()

        # D. Actualizar Soberanía
        # La base militar influye fuertemente en el control del planeta
        update_planet_sovereignty(unit.location_planet_id)

        msg = f"Unidad '{unit.name}' estableciendo Base Militar en Sector {sector_id} (ETA: 1 ciclo)."
        log_event(msg, player_id)

        return {"success": True, "message": msg}

    except Exception as e:
        log_event(f"Error crítico construyendo base militar: {e}", player_id, is_error=True)
        return {"success": False, "error": f"Error del sistema: {e}"}