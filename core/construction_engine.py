# core/construction_engine.py (Completo)
"""
Motor de Construcción.
Maneja la lógica de construcción de puestos de avanzada y estructuras tácticas
iniciadas por unidades en el terreno.
Refactorizado V19.0: Actualización de estado de unidad a CONSTRUCTING.
Refactorizado V19.1: Restricción de soberanía para Puestos de Avanzada.
Refactorizado V20.0: Restricciones de Sectores Urbanos y Soberanía Centralizada.
Refactorizado V20.1: Implementación de Construcción Orbital Táctica.
Refactorizado V21.0: Implementación de Estaciones Orbitales (Stellar Buildings).
Refactorizado V21.2: Soporte para Modo Debug (Bypass Subyugación) en Bases Militares.
Refactorizado V22.0: Homogeneización de firmas (player_id explícito) en Orbital Station.
Refactorizado V22.1: Implementación de Construcción Diferida y Estandarización de Errores (message).
Refactorizado V23.0: Estandarización de Costes Civiles (Outposts usan CIVILIAN_BUILD_COST).
Refactorizado V23.2: Construcción Diferida Real (is_active=False inicial para Outposts).
Refactorizado V23.3: Validación de terreno por exclusión lógica para Outposts.
"""

from typing import Dict, Any, Optional
from data.database import get_supabase, get_service_container
from data.player_repository import get_player_finances, update_player_resources
from data.unit_repository import get_unit_by_id, update_unit_moves
from data.planet_repository import update_planet_sovereignty, create_planet_asset
from data.log_repository import log_event
from data.world_repository import get_world_state
from core.models import UnitSchema, UnitStatus
from core.movement_constants import MAX_LOCAL_MOVES_PER_TURN
from core.world_constants import SECTOR_TYPE_ORBITAL, CIVILIAN_BUILD_COST, FORBIDDEN_CIVILIAN_TYPES
from config.app_constants import TEXT_MODEL_NAME
from google.genai import types

# Costos estandarizados para Puesto de Avanzada (Civilian Tier 1)
OUTPOST_COST_CREDITS = CIVILIAN_BUILD_COST["creditos"]
OUTPOST_COST_MATERIALS = CIVILIAN_BUILD_COST["materiales"]
OUTPOST_BUILDING_TYPE = "outpost"

# Costos fijos para Base Militar
BASE_COST_CREDITS = 500
BASE_COST_MATERIALS = 100

# Costos fijos para Estación Orbital (V20.1 / V21.0)
ORBITAL_STATION_COST_CREDITS = 800
ORBITAL_STATION_COST_MATERIALS = 30
ORBITAL_BUILDING_TYPE = "orbital_station"

# Alias para la tarea solicitada
ORBITAL_STATION_CREDITS = ORBITAL_STATION_COST_CREDITS
ORBITAL_STATION_MATERIALS = ORBITAL_STATION_COST_MATERIALS

def resolve_outpost_construction(unit_id: int, sector_id: int, player_id: int) -> Dict[str, Any]:
    """
    Intenta construir un Puesto de Avanzada en el sector actual de la unidad.
    
    Reglas Actualizadas V20.0:
    - PROHIBIDO en sectores 'URBAN'.
    - PROHIBIDO en CUALQUIER sector del planeta si el planeta tiene al menos un sector 'URBAN' (Soberanía Centralizada).
    - Soberanía: El jugador NO debe ser ya el dueño del planeta.
    
    Actualización V22.1 (Diferido):
    - Tiempo de construcción: 1 Tick.
    - Persiste construction_end_tick = current_tick + 1.
    
    Actualización V23.2 (Inactivo):
    - Se crea con is_active=False. Se activará en el Time Engine cuando current_tick >= built_at_tick.
    
    Actualización V23.3 (Terreno):
    - Se valida el terreno por EXCLUSIÓN. Si el sector NO es de un tipo prohibido (Urbano, Inhospito, Orbital), es válido.
    """
    db = get_supabase()
    
    # 1. Validar Unidad y Fatiga
    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        return {"success": False, "message": "Unidad no encontrada."}
    
    unit = UnitSchema.from_dict(unit_data)
    
    if unit.player_id != player_id:
        return {"success": False, "message": "Error de autorización."}
        
    if unit.status == UnitStatus.TRANSIT:
        return {"success": False, "message": "La unidad está en tránsito."}
    
    if unit.status == UnitStatus.CONSTRUCTING:
         return {"success": False, "message": "La unidad ya está ocupada construyendo."}
        
    limit = 1 if unit.status == UnitStatus.STEALTH_MODE else MAX_LOCAL_MOVES_PER_TURN
    if unit.local_moves_count >= limit:
        return {"success": False, "message": "La unidad está fatigada y no puede construir este turno."}

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
                    "message": "Tu facción ya controla la soberanía de este planeta. Construye infraestructura civil directamente."
                }
    except Exception as e:
        return {"success": False, "message": f"Error verificando soberanía planetaria: {e}"}

    # 2. Validar Ubicación
    if unit.location_sector_id != sector_id:
        return {"success": False, "message": "La unidad no está en el sector objetivo."}

    # 3. Validar Tipo de Sector (V23.3: Lógica de Exclusión)
    target_sector_res = db.table("sectors").select("sector_type, name").eq("id", sector_id).maybe_single().execute()
    
    if not target_sector_res.data:
        return {"success": False, "message": "Error: Sector no encontrado."}
    
    target_sector_data = target_sector_res.data
    sector_type = target_sector_data.get("sector_type", "")
    
    # --- REGLA V23.3: Exclusión explícita ---
    # Si el tipo de sector está en la lista de prohibidos, rechazamos.
    # Esto permite automáticamente cualquier sector de recursos, llanura, montaña o tipos personalizados no restringidos.
    if sector_type in FORBIDDEN_CIVILIAN_TYPES:
        return {
            "success": False,
            "message": f"🚫 Terreno no apto. No se pueden construir Puestos de Avanzada en sectores de tipo {sector_type}."
        }

    # --- REGLA V20.0: SOBERANÍA CENTRALIZADA (Bloqueo Planetario) ---
    # Verificar si el planeta tiene ALGÚN sector URBANO
    urban_check = db.table("sectors")\
        .select("id")\
        .eq("planet_id", unit.location_planet_id)\
        .eq("sector_type", "URBAN")\
        .execute()
        
    if urban_check.data and len(urban_check.data) > 0:
        return {
            "success": False,
            "message": "🚫 Planeta Habitado: La soberanía se decide en los Centros Urbanos. No puedes reclamar territorio salvaje mediante Puestos de Avanzada."
        }

    # 4. Validar Ocupación (Ya hay edificios)
    buildings_check = db.table("planet_buildings")\
        .select("id")\
        .eq("sector_id", sector_id)\
        .execute()
        
    if buildings_check.data and len(buildings_check.data) > 0:
        return {"success": False, "message": "El sector ya tiene estructuras."}

    # 5. Validar Recursos
    finances = get_player_finances(player_id)
    current_credits = finances.get("creditos", 0)
    current_materials = finances.get("materiales", 0)

    if current_credits < OUTPOST_COST_CREDITS or current_materials < OUTPOST_COST_MATERIALS:
        return {
            "success": False, 
            "message": f"Recursos insuficientes. Requiere {OUTPOST_COST_CREDITS} CR y {OUTPOST_COST_MATERIALS} Materiales."
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
        target_tick = current_tick + 1 # Construcción rápida (1 turno)
        
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
            "is_active": False, # V23.2: Se inicia inactivo hasta que se complete (Tick Actual >= target_tick)
            "built_at_tick": target_tick,
            "pops_required": 0,
            "energy_consumption": 1
        }
        
        db.table("planet_buildings").insert(building_data).execute()

        # C. Fatiga y Estado Diferido
        db.table("units").update({
            "status": UnitStatus.CONSTRUCTING,
            "local_moves_count": MAX_LOCAL_MOVES_PER_TURN,
            "construction_end_tick": target_tick
        }).eq("id", unit_id).execute()

        # D. Actualizar Soberanía
        # Nota: La soberanía definitiva se actualizará en Time Engine cuando is_active pase a True.
        # Sin embargo, marcamos el intento inicial.
        update_planet_sovereignty(planet_id)

        msg = f"Unidad '{unit.name}' iniciando construcción de Puesto de Avanzada en Sector {sector_id} (ETA: 1 ciclo)."
        log_event(msg, player_id)

        return {"success": True, "message": msg}

    except Exception as e:
        log_event(f"Error crítico construyendo outpost: {e}", player_id, is_error=True)
        return {"success": False, "message": f"Error del sistema: {e}"}

def resolve_base_construction(unit_id: Optional[int], sector_id: int, player_id: int, bypass_subjugation: bool = False) -> Dict[str, Any]:
    """
    Intenta construir una Base Militar en un sector URBANO.
    
    Reglas Actualizadas V20.0:
    - Permitido en 'URBAN' SOLO si `is_subjugated=True`.
    - No debe existir otra Base en el sector.
    
    Reglas V21.2 (Debug):
    - Si bypass_subjugation=True, ignora subyugación y permite unit_id=None (Modo Admin/Debug).
    """
    db = get_supabase()
    
    # 1. Recuperar info del Sector para ubicación y validación
    sector_res = db.table("sectors").select("sector_type, is_subjugated, planet_id").eq("id", sector_id).maybe_single().execute()
    
    if not sector_res.data:
        return {"success": False, "message": "Sector no encontrado."}
    
    sector_data = sector_res.data
    location_planet_id = sector_data.get("planet_id")

    unit_name = "Comando Central (Debug)"
    unit = None

    # 1. Validar Unidad y Fatiga (Si NO estamos en modo bypass unit_id)
    if unit_id is not None:
        unit_data = get_unit_by_id(unit_id)
        if not unit_data:
            return {"success": False, "message": "Unidad no encontrada."}
        
        unit = UnitSchema.from_dict(unit_data)
        unit_name = unit.name
        
        if unit.player_id != player_id:
            return {"success": False, "message": "Error de autorización."}
            
        if unit.status == UnitStatus.TRANSIT:
            return {"success": False, "message": "La unidad está en tránsito."}
        
        if unit.status == UnitStatus.CONSTRUCTING:
             return {"success": False, "message": "La unidad ya está ocupada construyendo."}
            
        limit = 1 if unit.status == UnitStatus.STEALTH_MODE else MAX_LOCAL_MOVES_PER_TURN
        if unit.local_moves_count >= limit:
            return {"success": False, "message": "La unidad está fatigada y no puede construir este turno."}

        # 2. Validar Ubicación Física de la Unidad
        if unit.location_sector_id != sector_id:
            return {"success": False, "message": "La unidad no está en el sector objetivo."}
    else:
        # Modo Debug / Bypass Unit
        if not bypass_subjugation:
            return {"success": False, "message": "ID de unidad requerido para construcción estándar."}
        
    # 3. Validar Tipo de Sector y Subyugación (V20.0)
    if sector_data.get("sector_type") != "URBAN":
        return {"success": False, "message": "Las Bases Militares solo pueden construirse en sectores URBANOS."}

    # REGLA V20.0: Check de Subyugación (Con Bypass)
    if not bypass_subjugation and not sector_data.get("is_subjugated", False):
        return {
            "success": False, 
            "message": "🚫 Sector Urbano hostil. Debes SUBYUGAR la población local antes de establecer una Base Militar."
        }

    # 4. Validar Unicidad (No debe existir otra base en el sector)
    base_check = db.table("bases").select("id").eq("sector_id", sector_id).maybe_single().execute()
    if base_check.data:
        return {"success": False, "message": "Ya existe una Base Militar en este sector."}

    # 5. Validar Recursos (Incluso en debug, cobramos para mantener economía consistente, o se podría skippear)
    # De momento se cobra siempre
    finances = get_player_finances(player_id)
    current_credits = finances.get("creditos", 0)
    current_materials = finances.get("materiales", 0)

    if current_credits < BASE_COST_CREDITS or current_materials < BASE_COST_MATERIALS:
        return {
            "success": False, 
            "message": f"Recursos insuficientes. Requiere {BASE_COST_CREDITS} CR y {BASE_COST_MATERIALS} Materiales."
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
            "planet_id": location_planet_id,
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

        # C. Fatiga (Solo si hay unidad real)
        if unit_id is not None:
            db.table("units").update({
                "status": UnitStatus.CONSTRUCTING,
                "local_moves_count": MAX_LOCAL_MOVES_PER_TURN,
                # Las bases son complejas, podríamos diferir más, pero V19.0 no especificaba tiempo extra para bases
                # Asumimos 1 ciclo estándar
                "construction_end_tick": target_tick
            }).eq("id", unit_id).execute()

        # D. Actualizar Soberanía
        update_planet_sovereignty(location_planet_id)

        msg_prefix = "[DEBUG] " if bypass_subjugation else ""
        msg = f"{msg_prefix}Unidad '{unit_name}' estableciendo Base Militar en Sector {sector_id} (ETA: 1 ciclo)."
        log_event(msg, player_id)

        return {"success": True, "message": msg}

    except Exception as e:
        log_event(f"Error crítico construyendo base militar: {e}", player_id, is_error=True)
        return {"success": False, "message": f"Error del sistema: {e}"}

def resolve_orbital_construction(unit_id: int, sector_id: int, player_id: int) -> Dict[str, Any]:
    """
    OBSOLETO: Usar build_orbital_station para nuevas implementaciones (V21.0).
    Mantiene compatibilidad con estructuras planet_buildings antiguas.
    """
    # Propagamos el player_id para la nueva firma
    return build_orbital_station(unit_id, sector_id, player_id)

def build_orbital_station(unit_id: int, sector_id: int, player_id: int) -> Dict[str, Any]:
    """
    V21.0: Construye una Estación Orbital en un sector espacial (Orbital o Deep Space).
    Registra la construcción en 'stellar_buildings'.
    
    Actualización V22.1 (Diferido):
    - Tiempo de construcción: 2 Ticks (Proyecto de envergadura).
    - Inicia con is_active=False.
    - Bloquea unidad con status=CONSTRUCTING por 2 ciclos.
    """
    db = get_supabase()
    
    # 1. Recuperar Unidad y Datos
    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        return {"success": False, "message": "Unidad no encontrada."}
    
    unit = UnitSchema.from_dict(unit_data)
    
    # Validación de Seguridad V22.0
    if unit.player_id != player_id:
        return {"success": False, "message": "Error de autorización."}
    
    # 2. Validaciones de Unidad (Estado y Movimiento)
    if unit.status == UnitStatus.TRANSIT:
        return {"success": False, "message": "La unidad está en tránsito."}
    
    if unit.status == UnitStatus.CONSTRUCTING:
         return {"success": False, "message": "La unidad ya está ocupada construyendo."}
        
    limit = 1 if unit.status == UnitStatus.STEALTH_MODE else MAX_LOCAL_MOVES_PER_TURN
    if unit.local_moves_count >= limit:
        return {"success": False, "message": "La unidad está fatigada y no puede construir este turno."}
    
    if unit.location_sector_id != sector_id:
        return {"success": False, "message": "La unidad no está en el sector objetivo."}

    # 3. Validar Tipo de Sector
    sector_res = db.table("sectors").select("sector_type, name").eq("id", sector_id).maybe_single().execute()
    if not sector_res.data:
        return {"success": False, "message": "Sector no encontrado."}
    
    sector_info = sector_res.data
    sector_type = sector_info.get("sector_type", "")
    
    # Permitir 'Orbital' o 'Deep Space'
    allowed_types = [SECTOR_TYPE_ORBITAL, "Deep Space", "Espacio Profundo"]
    if sector_type not in allowed_types:
        return {"success": False, "message": f"Las Estaciones Orbitales requieren espacio abierto (Orbital/Deep Space). Actual: {sector_type}"}

    # 4. Validar Existencia Previa (Stellar Buildings)
    existing = db.table("stellar_buildings")\
        .select("id")\
        .eq("sector_id", sector_id)\
        .execute() # Validamos incluso inactivas para no superponer obras
        
    if existing.data and len(existing.data) > 0:
        return {"success": False, "message": "Ya existe una estructura estelar (o una obra en curso) en este sector."}

    # 5. Validar Recursos
    finances = get_player_finances(player_id)
    curr_cred = finances.get("creditos", 0)
    curr_mat = finances.get("materiales", 0)
    
    if curr_cred < ORBITAL_STATION_CREDITS or curr_mat < ORBITAL_STATION_MATERIALS:
        return {
            "success": False, 
            "message": f"Recursos insuficientes. Requiere {ORBITAL_STATION_CREDITS} CR y {ORBITAL_STATION_MATERIALS} Materiales."
        }

    # --- EJECUCIÓN DIFERIDA V22.1 ---
    try:
        world = get_world_state()
        current_tick = world.get("current_tick", 1)
        target_tick = current_tick + 2  # Construcción orbital toma 2 ciclos
        
        # A. Descontar Recursos
        update_player_resources(player_id, {
            "creditos": curr_cred - ORBITAL_STATION_CREDITS,
            "materiales": curr_mat - ORBITAL_STATION_MATERIALS
        })
        
        # B. Insertar en Stellar Buildings (INACTIVO)
        stellar_data = {
            "sector_id": sector_id,
            "player_id": player_id,
            "building_type": "Orbital Station",
            "is_active": False, # Se activa en Phase 3.7 cuando built_at_tick <= current_tick
            "built_at_tick": target_tick
        }
        
        db.table("stellar_buildings").insert(stellar_data).execute()
        
        # C. Actualizar Estado Unidad
        db.table("units").update({
            "status": UnitStatus.CONSTRUCTING,
            "local_moves_count": MAX_LOCAL_MOVES_PER_TURN,
            "construction_end_tick": target_tick
        }).eq("id", unit_id).execute()
        
        # D. Generar Log Narrativo con IA (Gemini)
        narrative_log = f"Construcción de Estación Orbital iniciada en {sector_info.get('name')} (ETA: 2 ciclos)."
        try:
            container = get_service_container()
            if container.is_ai_available():
                prompt = (
                    f"Genera un mensaje de registro militar breve (1 frase) confirmando el inicio de la construcción "
                    f"de una Estación Orbital en el sector {sector_info.get('name')} por la unidad {unit.name}. "
                    f"Menciona que la obra tardará 2 ciclos solares. Estilo: Sci-fi, ingenieril."
                )
                
                # Configuración explícita para Gemini
                ai_resp = container.ai.models.generate_content(
                    model=TEXT_MODEL_NAME,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        max_output_tokens=100
                    )
                )
                if ai_resp.text:
                    narrative_log = ai_resp.text.strip()
        except Exception as ai_e:
            print(f"Error generando narrativa AI: {ai_e}")
            # Fallback silencioso al log por defecto

        log_event(narrative_log, player_id)
        
        return {"success": True, "message": narrative_log}

    except Exception as e:
        log_event(f"Error crítico en build_orbital_station: {e}", player_id, is_error=True)
        return {"success": False, "message": f"Error del sistema: {e}"}
