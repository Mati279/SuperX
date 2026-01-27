# data/planets/buildings.py (Completo)
"""
Gestión de Construcción y Edificios Planetarios.
Actualizado v8.2.0: Fix build_structure (Ghost Buildings Check & ID types).
Actualizado v8.2.1: Fix Not-Null Constraint (Inyección de pops_required y energy_consumption).
Actualizado v8.3.0: Business Logic para HQ Único (Reemplazo de Constraint DB).
Refactor v11.0: INTEGRACIÓN DE SISTEMA DE BASES MILITARES (Tabla 'bases').
Refactor v11.2: INTEGRACIÓN UI VISUAL DE BASES (Inyección Virtual).
Refactor v12.0: Soporte para Naming de bases y función de actualización.
Refactor v19.0: Inyección de bases con player_id real de tabla 'bases' (no del asset).
Refactor v21.0: Validación de Construcción por Soberanía (Surface Owner ID).
Refactor v23.0: Implementación de Mejoras Tier 2 y Limpieza de Lógica HQ.
"""

from typing import Dict, List, Any, Optional, Tuple

from ..log_repository import log_event
from ..world_repository import get_world_state
from data.player_repository import get_player_finances, update_player_resources
from core.world_constants import (
    BUILDING_TYPES,
    SECTOR_TYPE_URBAN,
    SECTOR_TYPE_ORBITAL,
    CIVILIAN_UPGRADE_COST
)

from .core import _get_db, get_planet_by_id
from .assets import get_planet_asset_by_id


def get_planet_buildings(planet_asset_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene los edificios de un asset planetario.
    Actualizado V11.2: Inyecta 'bases' como edificios virtuales de tipo 'military_base'.
    """
    try:
        db = _get_db()

        # 1. Edificios Estándar
        response = db.table("planet_buildings")\
            .select("*")\
            .eq("planet_asset_id", planet_asset_id)\
            .execute()

        buildings = response.data if response and response.data else []

        # 2. Inyectar Bases Militares
        # V19.0: Inyecta TODAS las bases del planeta visibles para el jugador del asset,
        #        asignando el player_id real de cada base (no del asset).
        asset = get_planet_asset_by_id(planet_asset_id)
        if asset:
            planet_id = asset["planet_id"]
            asset_player_id = asset["player_id"]

            # Obtener TODAS las bases del planeta (propias y de ocupación)
            # para que la UI pueda mostrarlas correctamente
            bases_res = db.table("bases")\
                .select("*")\
                .eq("planet_id", planet_id)\
                .execute()

            if bases_res and bases_res.data:
                for base in bases_res.data:
                    # player_id real de la base (puede diferir del dueño del asset)
                    base_player_id = base.get("player_id")

                    # Determinamos nombre visual
                    base_custom_name = base.get("name")
                    if not base_custom_name:
                        # Solo usar nombre del asset si es nuestra base
                        if base_player_id == asset_player_id:
                            base_custom_name = f"Base Militar {asset.get('nombre_asentamiento', '')}"
                        else:
                            base_custom_name = "Base Militar Enemiga"

                    virtual_base = {
                        "id": base["id"],
                        "building_type": "military_base",  # Tipo especial reservado
                        "building_tier": base.get("tier", 1),
                        "sector_id": base["sector_id"],
                        "planet_asset_id": planet_asset_id,
                        "player_id": base_player_id,  # V19.0: player_id real de la base
                        "is_active": True,
                        "built_at_tick": base.get("created_at_tick", 0),
                        "is_virtual": True,
                        "custom_name": base_custom_name  # Campo auxiliar para UI
                    }
                    buildings.append(virtual_base)

        return buildings
    except Exception as e:
        log_event(f"Error obteniendo edificios: {e}", is_error=True)
        return []


def update_base_name(base_id: int, new_name: str, player_id: int) -> bool:
    """
    Actualiza el nombre personalizado de una base militar.
    """
    try:
        db = _get_db()
        # Verificar propiedad implícita en el update con el filtro player_id (si la tabla lo permite)
        # O verificar primero. Asumimos tabla bases tiene player_id.
        response = db.table("bases")\
            .update({"name": new_name})\
            .eq("id", base_id)\
            .eq("player_id", player_id)\
            .execute()
        
        if response and response.data:
            log_event(f"Base militar renombrada a '{new_name}'", player_id)
            return True
        return False
    except Exception as e:
        log_event(f"Error renombrando base: {e}", player_id, is_error=True)
        return False


def build_structure(
    planet_asset_id: int,
    player_id: int,
    building_type: str,
    tier: int = 1,
    sector_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Construye una estructura validando espacio, ocupación hostil y permisos de soberanía.
    Refactor V21.0: 
        - Permite construir si el jugador es el Dueño de Superficie (surface_owner_id).
    Refactor V23.0:
        - Eliminada validación de "Base Única" o HQ.
        - Validación de costes explícita desde definiciones.
    """
    # Importación local para evitar dependencia circular
    from .sovereignty import update_planet_sovereignty

    if building_type not in BUILDING_TYPES: return None
    definition = BUILDING_TYPES[building_type]
    db = _get_db()

    try:
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return None
        planet_id = asset["planet_id"]

        # --- Obtener Datos del Planeta (V21.0: Soberanía) ---
        planet_info = get_planet_by_id(planet_id)
        if not planet_info:
             log_event("Planeta no encontrado.", player_id, is_error=True)
             return None
        
        surface_owner_id = planet_info.get("surface_owner_id")
        orbital_owner_id = planet_info.get("orbital_owner_id")

        is_sovereign_owner = (str(surface_owner_id) == str(player_id)) if surface_owner_id else False

        # --- Validaciones Generales de Ocupación ---

        all_assets = db.table("planet_assets").select("id, player_id").eq("planet_id", planet_id).execute().data
        all_asset_ids = [a["id"] for a in all_assets]

        all_buildings = db.table("planet_buildings")\
            .select("sector_id, building_type, planet_asset_id")\
            .in_("planet_asset_id", all_asset_ids)\
            .execute().data or []

        # Mapa de ocupación
        sector_occupants = {}

        for b in all_buildings:
            owner = next((a["player_id"] for a in all_assets if a["id"] == b["planet_asset_id"]), None)
            sid = b.get("sector_id")
            if sid:
                if sid not in sector_occupants: sector_occupants[sid] = set()
                if owner is not None:
                    sector_occupants[sid].add(owner)

        # Inyectar Bases Militares como ocupantes
        bases_res = db.table("bases").select("sector_id, player_id").eq("planet_id", planet_id).execute()
        bases_data = bases_res.data if bases_res and bases_res.data else []
        for base in bases_data:
            sid = base["sector_id"]
            if sid not in sector_occupants: sector_occupants[sid] = set()
            sector_occupants[sid].add(base["player_id"])

        # 1. Recuperar Sectores
        sectors_res = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
        sectors = sectors_res.data if sectors_res and sectors_res.data else []
        if not sectors:
            log_event("No hay sectores en el planeta.", player_id, is_error=True)
            return None

        # Contadores de slots
        sector_counts = {}
        for b in all_buildings:
            sid = b.get("sector_id")
            bt = b.get("building_type")
            consumes = BUILDING_TYPES.get(bt, {}).get("consumes_slots", True)
            if sid and consumes:
                sector_counts[sid] = sector_counts.get(sid, 0) + 1

        # Añadir Bases al conteo de slots
        for base in bases_data:
            sid = base["sector_id"]
            sector_counts[sid] = sector_counts.get(sid, 0) + 1

        for s in sectors:
            if 'max_slots' in s: s['slots'] = s['max_slots']
            s['buildings_count'] = sector_counts.get(s["id"], 0)

        # 2. Selección de Sector Objetivo y Validación de Bloqueo Local
        target_sector = None

        if sector_id:
            matches = [s for s in sectors if str(s["id"]) == str(sector_id)]
            if matches:
                target_sector = matches[0]
                allowed = definition.get("allowed_terrain")
                if allowed and target_sector["sector_type"] not in allowed:
                    log_event(f"Error de Construcción: Terreno {target_sector['sector_type']} incompatible con {definition['name']}.", player_id, is_error=True)
                    return None
        else:
            # Auto-selección (Legacy)
            candidates = []
            for s in sectors:
                if definition.get("consumes_slots", True) and s["buildings_count"] >= s["slots"]:
                    continue
                allowed = definition.get("allowed_terrain")
                if allowed and s["sector_type"] not in allowed:
                    continue
                occupants = sector_occupants.get(s["id"], set())
                if any(occ != player_id for occ in occupants):
                    continue

                candidates.append(s)

            if building_type == "orbital_station":
                orbital = [s for s in candidates if s.get("sector_type") == SECTOR_TYPE_ORBITAL]
                target_sector = orbital[0] if orbital else None
            else:
                target_sector = candidates[0] if candidates else None

        if not target_sector:
            log_event("No hay sectores disponibles o válidos (Bloqueo/Espacio/Tipo).", player_id, is_error=True)
            return None

        # --- VALIDACIONES ORBITALES ESPECÍFICAS (V6.4 y V9.2) ---
        if definition.get("is_orbital", False):
            is_surface_owner = (surface_owner_id == player_id)
            is_orbital_owner = (orbital_owner_id == player_id)

            if orbital_owner_id and orbital_owner_id != player_id:
                log_event("Construcción orbital bloqueada: Órbita controlada por enemigo.", player_id, is_error=True)
                return None

            if not is_surface_owner and not is_orbital_owner:
                log_event("Requisito Orbital: Se requiere control de superficie o flota en órbita.", player_id, is_error=True)
                return None
        else:
            # --- VALIDACIÓN DE PERMISOS DE CONSTRUCCIÓN CIVIL (V21.0) ---
            # Regla: Si tengo Soberanía Planetaria (is_sovereign_owner), puedo construir en cualquier sector libre.
            # Si NO tengo soberanía, necesito un "comando operativo" local (Base/HQ/Outpost) O que sea un Outpost.
            
            # Exceptuar estructuras de comando (Outpost/Base se autovalidan por lógica de expansión)
            is_command_structure = building_type in ['outpost', 'military_base']
            
            if not is_command_structure and not is_sovereign_owner:
                # Verificar presencia local de comando
                has_local_command = False
                
                # Check edificios propios en el sector
                my_local_buildings = [b for b in all_buildings if b["sector_id"] == target_sector["id"] and b["planet_asset_id"] == planet_asset_id]
                if any(b['building_type'] in ['outpost', 'military_base'] for b in my_local_buildings):
                    has_local_command = True
                
                # Check base militar independiente en el sector
                my_local_base = next((b for b in bases_data if b["sector_id"] == target_sector["id"] and b["player_id"] == player_id), None)
                if my_local_base:
                    has_local_command = True
                
                if not has_local_command:
                    log_event("Permiso denegado: Se requiere Soberanía Planetaria o un Puesto de Avanzada en el sector.", player_id, is_error=True)
                    return None

        # --- VALIDACIÓN DE OCUPANTES HOSTILES (Estricta) ---
        occupants = sector_occupants.get(target_sector["id"], set())
        if any(occ != player_id for occ in occupants):
            log_event("Construcción fallida: Sector ocupado por otra facción.", player_id, is_error=True)
            return None

        if definition.get("consumes_slots", True) and target_sector["buildings_count"] >= target_sector["slots"]:
            log_event("No hay espacio en el sector seleccionado.", player_id, is_error=True)
            return None
            
        # --- V23.0: VALIDACIÓN DE RECURSOS (Implícita o Explícita si UI no lo hace) ---
        # Asumimos que la lógica de cobro principal está en la capa de servicios, 
        # pero upgrade_structure (abajo) sí maneja cobros. 
        # Si se requiere cobro aquí, debería descomentarse la lógica de finanzas.
        
        # 3. Insertar Edificio
        world = get_world_state()
        current_tick = world.get("current_tick", 1)

        b_def = BUILDING_TYPES.get(building_type, {})
        pops_req = b_def.get("pops_required", 0)
        energy_cons = b_def.get("maintenance", {}).get("celulas_energia", 0)

        building_data = {
            "planet_asset_id": planet_asset_id,
            "player_id": player_id,
            "building_type": building_type,
            "building_tier": tier,
            "sector_id": target_sector["id"],
            "is_active": True,
            "built_at_tick": current_tick + 1, # Construcción diferida estándar (V23.0)
            "pops_required": pops_req,
            "energy_consumption": energy_cons
        }

        response = db.table("planet_buildings").insert(building_data).execute()
        if response and response.data:
            log_event(f"Construido {definition['name']} en {target_sector.get('sector_type', 'Sector')}", player_id)
            update_planet_sovereignty(planet_id)
            return response.data[0]
        return None
    except Exception as e:
        log_event(f"Error construyendo edificio: {e}", player_id, is_error=True)
        return None


def upgrade_structure(building_id: int, player_id: int) -> bool:
    """
    Mejora un edificio de Nivel 1 a Nivel 2.
    Aplica coste de 500 Créditos y 35 Materiales.
    El edificio se vuelve Nivel 2 pero la mejora tarda 1 tick (built_at_tick).
    """
    try:
        db = _get_db()
        
        # 1. Verificar Edificio y Propiedad
        b_res = db.table("planet_buildings").select("*").eq("id", building_id).maybe_single().execute()
        if not b_res.data:
            log_event("Edificio no encontrado para mejora.", player_id, is_error=True)
            return False
            
        building = b_res.data
        if building["player_id"] != player_id:
            log_event("No tienes permisos para mejorar este edificio.", player_id, is_error=True)
            return False
            
        # 2. Validar Tier Actual
        current_tier = building.get("building_tier", 1)
        if current_tier != 1:
            log_event(f"Solo se pueden mejorar edificios de Nivel 1 (Nivel actual: {current_tier}).", player_id, is_error=True)
            return False
            
        definition = BUILDING_TYPES.get(building["building_type"], {})
        max_tier = definition.get("max_tier", 1)
        if max_tier < 2:
            log_event("Este tipo de edificio no admite mejoras.", player_id, is_error=True)
            return False

        # 3. Validar Recursos y Cobrar
        cost_cr = CIVILIAN_UPGRADE_COST["creditos"]
        cost_mat = CIVILIAN_UPGRADE_COST["materiales"]
        
        finances = get_player_finances(player_id)
        if finances["creditos"] < cost_cr or finances["materiales"] < cost_mat:
            log_event(f"Recursos insuficientes para mejora. Requiere {cost_cr} CR y {cost_mat} Materiales.", player_id, is_error=True)
            return False
            
        # Descontar
        update_player_resources(player_id, {
            "creditos": finances["creditos"] - cost_cr,
            "materiales": finances["materiales"] - cost_mat
        })
        
        # 4. Aplicar Mejora Diferida
        world = get_world_state()
        current_tick = world.get("current_tick", 1)
        
        db.table("planet_buildings").update({
            "building_tier": 2,
            "built_at_tick": current_tick + 1
        }).eq("id", building_id).execute()
        
        log_event(f"Mejora iniciada para {definition.get('name', 'Edificio')}. Nivel 2 disponible en próximo ciclo.", player_id)
        return True

    except Exception as e:
        log_event(f"Error al mejorar edificio: {e}", player_id, is_error=True)
        return False


def demolish_building(building_id: int, player_id: int) -> bool:
    """Demuele y decrementa el contador del sector (Implícito). Actualiza soberanía."""
    # Importación local para evitar dependencia circular
    from .sovereignty import update_planet_sovereignty

    try:
        db = _get_db()
        # Verificar propiedad y obtener planet_id para update sovereignty
        b_res = db.table("planet_buildings")\
            .select("*, planet_assets(planet_id)")\
            .eq("id", building_id)\
            .single()\
            .execute()

        if not b_res or not b_res.data: return False

        planet_id = b_res.data.get("planet_assets", {}).get("planet_id")

        # Eliminar
        db.table("planet_buildings").delete().eq("id", building_id).execute()

        log_event(f"Edificio {building_id} demolido.", player_id)

        # --- V6.3: Actualizar Soberanía ---
        if planet_id:
            update_planet_sovereignty(planet_id)

        return True
    except Exception as e:
        log_event(f"Error demoliendo: {e}", player_id, is_error=True)
        return False


def get_luxury_extraction_sites_for_player(player_id: int) -> List[Dict[str, Any]]:
    """Obtiene sitios de extracción de lujo activos del jugador."""
    try:
        response = _get_db().table("luxury_extraction_sites")\
            .select("*")\
            .eq("player_id", player_id)\
            .eq("is_active", True)\
            .execute()
        return response.data if response and response.data else []
    except Exception as e:
        log_event(f"Error obteniendo sitios: {e}", player_id, is_error=True)
        return []


def batch_update_building_status(updates: List[Tuple[int, bool]]) -> Tuple[int, int]:
    """Actualiza el estado activo/inactivo de múltiples edificios en lote."""
    if not updates: return (0, 0)
    success, failed = 0, 0
    db = _get_db()
    for building_id, is_active in updates:
        try:
            res = db.table("planet_buildings").update({"is_active": is_active}).eq("id", building_id).execute()
            if res: success += 1
            else: failed += 1
        except Exception: failed += 1
    return (success, failed)