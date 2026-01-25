# data/unit_repository.py (Completo)
"""
Repositorio para manejo de Unidades y Tropas.
Interactúa con las tablas 'units', 'troops' y 'unit_members'.
Implementa persistencia de composición y gestión de estado.
V9.0: Implementación inicial.
V10.0: Funciones de tránsito, ubicación avanzada y detección.
V11.1: Persistencia de ubicación en Tropas y lógica de disolución segura.
V11.2: Hidratación de nombres en miembros de unidad (Fix Schema Validation).
V11.3: Soporte para local_moves_count (movimientos locales limitados).
"""

from typing import Optional, List, Dict, Any
from data.database import get_supabase
from core.models import UnitSchema, TroopSchema, UnitStatus, LocationRing

# --- HELPER FUNCTIONS (INTERNAL) ---

def _hydrate_member_names(members: List[Dict[str, Any]]) -> None:
    """
    Hidrata una lista de miembros de unidad con el nombre de la entidad.
    Realiza consultas en lote para optimizar rendimiento.
    Modifica la lista in-place agregando el campo 'name'.
    """
    if not members:
        return

    db = get_supabase()
    
    # 1. Recolectar IDs únicos por tipo
    char_ids = list({m["entity_id"] for m in members if m["entity_type"] == "character"})
    troop_ids = list({m["entity_id"] for m in members if m["entity_type"] == "troop"})
    
    char_map = {}
    troop_map = {}

    # 2. Consultar Nombres de Personajes
    if char_ids:
        try:
            # Characters usa la columna 'nombre'
            resp = db.table("characters").select("id, nombre").in_("id", char_ids).execute()
            if resp.data:
                char_map = {item["id"]: item["nombre"] for item in resp.data}
        except Exception as e:
            print(f"Error hydrating characters batch: {e}")

    # 3. Consultar Nombres de Tropas
    if troop_ids:
        try:
            # Troops usa la columna 'name'
            resp = db.table("troops").select("id, name").in_("id", troop_ids).execute()
            if resp.data:
                troop_map = {item["id"]: item["name"] for item in resp.data}
        except Exception as e:
            print(f"Error hydrating troops batch: {e}")

    # 4. Asignar nombres a los miembros
    for m in members:
        e_id = m["entity_id"]
        e_type = m["entity_type"]
        
        assigned_name = "Entidad Desconocida"
        
        if e_type == "character":
            assigned_name = char_map.get(e_id, f"Personaje {e_id} (No encontrado)")
        elif e_type == "troop":
            assigned_name = troop_map.get(e_id, f"Tropa {e_id} (No encontrada)")
            
        m["name"] = assigned_name


# --- TROOPS ---

def create_troop(
    player_id: int, 
    name: str, 
    troop_type: str, 
    level: int = 1,
    location_data: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Crea una nueva tropa en la DB.
    Args:
        location_data: Dict opcional con system_id, planet_id, sector_id, ring.
    """
    db = get_supabase()
    try:
        data = {
            "player_id": player_id,
            "name": name,
            "type": troop_type,
            "level": level,
            "combats_at_current_level": 0,
            "ring": 0 # Default safe value
        }
        
        # V11.1: Asignar ubicación si se provee
        if location_data:
            data["location_system_id"] = location_data.get("system_id")
            data["location_planet_id"] = location_data.get("planet_id")
            data["location_sector_id"] = location_data.get("sector_id")
            data["ring"] = location_data.get("ring", 0)

        response = db.table("troops").insert(data).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error creating troop: {e}")
        return None

def get_troop_by_id(troop_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene una tropa por ID."""
    db = get_supabase()
    try:
        response = db.table("troops").select("*").eq("id", troop_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error fetching troop {troop_id}: {e}")
        return None

def update_troop_stats(troop_id: int, combats: int, level: Optional[int] = None) -> bool:
    """Actualiza contadores de combate y nivel de una tropa."""
    db = get_supabase()
    try:
        update_data = {"combats_at_current_level": combats}
        if level is not None:
            update_data["level"] = level
            
        response = db.table("troops").update(update_data).eq("id", troop_id).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error updating troop {troop_id}: {e}")
        return False

def update_troop_location(troop_id: int, location_data: Dict[str, Any]) -> bool:
    """
    V11.1: Actualiza la ubicación de una tropa individual.
    """
    db = get_supabase()
    try:
        data = {
            "location_system_id": location_data.get("system_id"),
            "location_planet_id": location_data.get("planet_id"),
            "location_sector_id": location_data.get("sector_id"),
            "ring": location_data.get("ring", 0)
        }
        response = db.table("troops").update(data).eq("id", troop_id).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error updating troop location {troop_id}: {e}")
        return False

def delete_troop(troop_id: int) -> bool:
    """Elimina una tropa (Ej: Al ser promovida a Héroe)."""
    db = get_supabase()
    try:
        response = db.table("troops").delete().eq("id", troop_id).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error deleting troop {troop_id}: {e}")
        return False

# --- TROOPS (EXTENDED) ---

def get_troops_by_player(player_id: int) -> List[Dict[str, Any]]:
    """Obtiene todas las tropas del jugador."""
    db = get_supabase()
    try:
        response = db.table("troops").select("*").eq("player_id", player_id).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error fetching troops for player {player_id}: {e}")
        return []


# --- UNITS ---

def create_unit(
    player_id: int, 
    name: str, 
    location_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Crea una Unidad vacía.
    location_data debe contener: system_id, planet_id (opcional), sector_id (opcional).
    """
    db = get_supabase()
    try:
        data = {
            "player_id": player_id,
            "name": name,
            "status": UnitStatus.GROUND.value,
            "location_system_id": location_data.get("system_id"),
            "location_planet_id": location_data.get("planet_id"),
            "location_sector_id": location_data.get("sector_id"),
            "ring": location_data.get("ring", 0),
            "local_moves_count": 0
        }
        response = db.table("units").insert(data).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error creating unit: {e}")
        return None

def get_units_by_player(player_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene todas las unidades del jugador con sus miembros.
    V11.2: Hidrata los miembros con el campo 'name' para cumplir con UnitMemberSchema.
    """
    db = get_supabase()
    try:
        # 1. Obtenemos unidades
        units_resp = db.table("units").select("*").eq("player_id", player_id).execute()
        units = units_resp.data
        if not units:
            return []
        
        # 2. Obtenemos miembros para estas unidades
        unit_ids = [u["id"] for u in units]
        members_resp = db.table("unit_members").select("*").in_("unit_id", unit_ids).execute()
        
        all_members = members_resp.data if members_resp.data else []
        
        # 3. Hidratación de nombres (V11.2)
        if all_members:
            _hydrate_member_names(all_members)

        # 4. Agrupar miembros por unidad
        members_by_unit = {}
        for m in all_members:
            uid = m["unit_id"]
            if uid not in members_by_unit:
                members_by_unit[uid] = []
            members_by_unit[uid].append(m)
            
        # 5. Adjuntar a unidades
        for u in units:
            u["members"] = members_by_unit.get(u["id"], [])
            
        return units
    except Exception as e:
        print(f"Error fetching units for player {player_id}: {e}")
        return []

def get_unit_by_id(unit_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene una unidad por ID y sus miembros hidratados.
    V11.2: Implementa hidratación de nombres.
    """
    db = get_supabase()
    try:
        response = db.table("units").select("*").eq("id", unit_id).execute()
        if not response.data:
            return None
        
        unit = response.data[0]
        
        # Obtener miembros
        members_resp = db.table("unit_members").select("*").eq("unit_id", unit_id).execute()
        members = members_resp.data if members_resp.data else []
        
        # Hidratar miembros (V11.2)
        if members:
            _hydrate_member_names(members)
            
        unit["members"] = members
        return unit
    except Exception as e:
        print(f"Error fetching unit {unit_id}: {e}")
        return None

def rename_unit(unit_id: int, new_name: str, player_id: int) -> bool:
    """Renombra una unidad existente. Verifica propiedad."""
    db = get_supabase()
    try:
        unit = db.table("units").select("player_id").eq("id", unit_id).single().execute()
        if not unit.data or unit.data.get("player_id") != player_id:
            return False
        response = db.table("units").update({"name": new_name}).eq("id", unit_id).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error renaming unit {unit_id}: {e}")
        return False


def delete_unit(unit_id: int, player_id: int) -> bool:
    """
    Disuelve una unidad.
    V11.1 UPDATE: Antes de borrar, transfiere la ubicación de la unidad a las tropas miembros.
    Esto previene que las tropas queden 'huérfanas' de ubicación en la DB.
    """
    db = get_supabase()
    try:
        # 1. Obtener la unidad para verificar propiedad y obtener ubicación
        unit_resp = db.table("units").select("*").eq("id", unit_id).single().execute()
        if not unit_resp.data or unit_resp.data.get("player_id") != player_id:
            return False
        
        unit = unit_resp.data
        
        # 2. Obtener miembros tipo 'troop'
        members_resp = db.table("unit_members")\
            .select("*")\
            .eq("unit_id", unit_id)\
            .eq("entity_type", "troop")\
            .execute()
        
        troop_ids = [m["entity_id"] for m in members_resp.data] if members_resp.data else []
        
        # 3. Si hay tropas, actualizar su ubicación a la de la unidad actual
        if troop_ids:
            location_update = {
                "location_system_id": unit.get("location_system_id"),
                "location_planet_id": unit.get("location_planet_id"),
                "location_sector_id": unit.get("location_sector_id"),
                "ring": unit.get("ring", 0)
            }
            # Bulk update de tropas
            db.table("troops").update(location_update).in_("id", troop_ids).execute()
            
        # 4. Eliminar miembros (romper vínculo)
        db.table("unit_members").delete().eq("unit_id", unit_id).execute()
        
        # 5. Eliminar unidad
        response = db.table("units").delete().eq("id", unit_id).execute()
        return bool(response.data)

    except Exception as e:
        print(f"Error deleting unit {unit_id}: {e}")
        return False


def update_unit_status(unit_id: int, status: UnitStatus) -> bool:
    db = get_supabase()
    try:
        response = db.table("units").update({"status": status.value}).eq("id", unit_id).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error updating unit status {unit_id}: {e}")
        return False

def update_unit_location(unit_id: int, location_data: Dict[str, Any]) -> bool:
    db = get_supabase()
    try:
        data = {
            "location_system_id": location_data.get("system_id"),
            "location_planet_id": location_data.get("planet_id"),
            "location_sector_id": location_data.get("sector_id")
        }
        # Si se pasa ring, actualizarlo también
        if "ring" in location_data:
            data["ring"] = location_data["ring"]
            
        response = db.table("units").update(data).eq("id", unit_id).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error updating unit location {unit_id}: {e}")
        return False

# --- UNIT MEMBERS ---

def add_unit_member(unit_id: int, entity_type: str, entity_id: int, slot_index: int) -> bool:
    """Asigna una entidad (character/troop) a una unidad."""
    db = get_supabase()
    try:
        data = {
            "unit_id": unit_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "slot_index": slot_index
        }
        response = db.table("unit_members").insert(data).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error adding member to unit {unit_id}: {e}")
        return False

def remove_unit_member(unit_id: int, slot_index: int) -> bool:
    """Remueve un miembro de un slot específico."""
    db = get_supabase()
    try:
        response = db.table("unit_members")\
            .delete()\
            .match({"unit_id": unit_id, "slot_index": slot_index})\
            .execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error removing member from unit {unit_id} slot {slot_index}: {e}")
        return False

def get_active_transit_units_count(player_id: int) -> int:
    """Cuenta cuántas unidades están en estado TRANSIT para el jugador."""
    db = get_supabase()
    try:
        response = db.table("units")\
            .select("id", count="exact")\
            .eq("player_id", player_id)\
            .eq("status", "TRANSIT")\
            .execute()
        return response.count or 0
    except Exception:
        return 0

def get_troops_in_transit_count(player_id: int) -> int:
    """
    Cuenta el total de tropas (no characters) dentro de unidades en TRANSITO.
    Query compleja optimizada.
    """
    db = get_supabase()
    try:
        # 1. Obtener IDs de unidades en tránsito
        units_resp = db.table("units").select("id").eq("player_id", player_id).eq("status", "TRANSIT").execute()
        if not units_resp.data:
            return 0

        unit_ids = [u["id"] for u in units_resp.data]

        # 2. Contar miembros tipo 'troop' en esas unidades
        members_resp = db.table("unit_members")\
            .select("unit_id", count="exact")\
            .in_("unit_id", unit_ids)\
            .eq("entity_type", "troop")\
            .execute()

        return members_resp.count or 0
    except Exception as e:
        print(f"Error counting troops in transit: {e}")
        return 0


# --- V10.0: FUNCIONES DE TRÁNSITO Y MOVIMIENTO ---

def start_unit_transit(
    unit_id: int,
    destination_data: Dict[str, Any],
    ticks_required: int,
    current_tick: int,
    starlane_id: Optional[int] = None,
    movement_type: str = "starlane"
) -> bool:
    """
    Inicia el tránsito de una unidad.
    Actualiza estado a TRANSIT y registra datos de viaje.

    Args:
        unit_id: ID de la unidad
        destination_data: Dict con system_id, planet_id, sector_id, ring del destino
        ticks_required: Número de ticks para completar el viaje
        current_tick: Tick actual del juego
        starlane_id: ID de starlane si aplica (None para Warp)
        movement_type: Tipo de movimiento ('starlane', 'warp', 'inter_ring', etc.)
    """
    db = get_supabase()
    try:
        # Obtener datos actuales de la unidad (origen)
        current = db.table("units").select("*").eq("id", unit_id).single().execute()
        if not current.data:
            return False

        origin_data = current.data

        # Actualizar unidad a estado de tránsito
        update_data = {
            "status": UnitStatus.TRANSIT.value,
            "transit_end_tick": current_tick + ticks_required,
            "transit_ticks_remaining": ticks_required,
            "transit_origin_system_id": origin_data.get("location_system_id"),
            "transit_destination_system_id": destination_data.get("system_id"),
            "starlane_id": starlane_id,
            "movement_locked": True
        }

        response = db.table("units").update(update_data).eq("id", unit_id).execute()

        if response.data:
            # Registrar en historial de tránsitos
            _log_transit_start(
                unit_id=unit_id,
                player_id=origin_data.get("player_id"),
                origin_data=origin_data,
                destination_data=destination_data,
                starlane_id=starlane_id,
                movement_type=movement_type,
                ticks_required=ticks_required,
                current_tick=current_tick
            )
            return True
        return False
    except Exception as e:
        print(f"Error starting transit for unit {unit_id}: {e}")
        return False


def complete_unit_transit(unit_id: int, current_tick: int) -> bool:
    """
    Completa el tránsito de una unidad.
    Actualiza ubicación al destino y limpia datos de tránsito.
    """
    db = get_supabase()
    try:
        # Obtener datos de tránsito
        unit = db.table("units").select("*").eq("id", unit_id).single().execute()
        if not unit.data:
            return False

        unit_data = unit.data
        dest_system = unit_data.get("transit_destination_system_id")

        # La unidad llega al sector estelar (ring 0) del sistema destino
        update_data = {
            "status": UnitStatus.SPACE.value,
            "location_system_id": dest_system,
            "location_planet_id": None,
            "location_sector_id": None,
            "ring": 0,  # Sector estelar
            "transit_end_tick": None,
            "transit_ticks_remaining": 0,
            "transit_origin_system_id": None,
            "transit_destination_system_id": None,
            "starlane_id": None,
            "movement_locked": False
        }

        response = db.table("units").update(update_data).eq("id", unit_id).execute()

        if response.data:
            # Actualizar historial de tránsitos
            _log_transit_complete(unit_id, current_tick)
            return True
        return False
    except Exception as e:
        print(f"Error completing transit for unit {unit_id}: {e}")
        return False


def get_units_in_transit_arriving_at_tick(tick: int) -> List[Dict[str, Any]]:
    """Obtiene unidades cuyo tránsito termina en el tick especificado."""
    db = get_supabase()
    try:
        response = db.table("units")\
            .select("*")\
            .eq("status", "TRANSIT")\
            .eq("transit_end_tick", tick)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error fetching units arriving at tick {tick}: {e}")
        return []


def get_units_at_location(
    system_id: int,
    planet_id: Optional[int] = None,
    sector_id: Optional[int] = None,
    ring: Optional[int] = None,
    exclude_player_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Obtiene unidades en una ubicación específica.
    Usado para detección de encuentros.
    """
    db = get_supabase()
    try:
        query = db.table("units")\
            .select("*")\
            .eq("location_system_id", system_id)\
            .neq("status", "TRANSIT")

        if planet_id is not None:
            query = query.eq("location_planet_id", planet_id)
        if sector_id is not None:
            query = query.eq("location_sector_id", sector_id)
        if ring is not None:
            query = query.eq("ring", ring)
        if exclude_player_id is not None:
            query = query.neq("player_id", exclude_player_id)

        response = query.execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error fetching units at location: {e}")
        return []


def get_units_on_starlane(starlane_id: int) -> List[Dict[str, Any]]:
    """Obtiene unidades viajando por una starlane específica."""
    db = get_supabase()
    try:
        response = db.table("units")\
            .select("*")\
            .eq("starlane_id", starlane_id)\
            .eq("status", "TRANSIT")\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error fetching units on starlane {starlane_id}: {e}")
        return []


def update_unit_movement_lock(unit_id: int, locked: bool) -> bool:
    """Actualiza el estado de bloqueo de movimiento de una unidad."""
    db = get_supabase()
    try:
        response = db.table("units")\
            .update({"movement_locked": locked})\
            .eq("id", unit_id)\
            .execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error updating movement lock for unit {unit_id}: {e}")
        return False


def update_unit_location_advanced(
    unit_id: int,
    system_id: Optional[int],
    planet_id: Optional[int],
    sector_id: Optional[int],
    ring: int = 0,
    status: Optional[UnitStatus] = None
) -> bool:
    """
    V10.0: Actualiza ubicación completa de una unidad incluyendo anillo.
    """
    db = get_supabase()
    try:
        data = {
            "location_system_id": system_id,
            "location_planet_id": planet_id,
            "location_sector_id": sector_id,
            "ring": ring
        }
        if status is not None:
            data["status"] = status.value

        response = db.table("units").update(data).eq("id", unit_id).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error updating unit location {unit_id}: {e}")
        return False


def cancel_unit_transit(unit_id: int, current_tick: int) -> bool:
    """
    Cancela el tránsito de una unidad (ej: por interdicción).
    La unidad permanece en la starlane pero ya no está en tránsito activo.
    """
    db = get_supabase()
    try:
        # Obtener datos actuales
        unit = db.table("units").select("*").eq("id", unit_id).single().execute()
        if not unit.data:
            return False

        update_data = {
            "status": UnitStatus.SPACE.value,
            "transit_end_tick": None,
            "transit_ticks_remaining": 0,
            "movement_locked": True  # Bloqueado por interdicción
        }

        response = db.table("units").update(update_data).eq("id", unit_id).execute()

        if response.data:
            # Marcar tránsito como INTERDICTED en historial
            _log_transit_interdicted(unit_id, current_tick)
            return True
        return False
    except Exception as e:
        print(f"Error cancelling transit for unit {unit_id}: {e}")
        return False


def reset_all_movement_locks() -> int:
    """
    Resetea movement_locked a False y local_moves_count a 0.
    Llamado al inicio de cada tick.
    """
    db = get_supabase()
    try:
        # Update masivo o condicional para resetear contadores de turno
        # Se asume que Supabase permite updates sin where explícito en esta configuración,
        # o usamos un filtro que abarque a los afectados.
        response = db.table("units")\
            .update({"movement_locked": False, "local_moves_count": 0})\
            .or_("movement_locked.eq.true,local_moves_count.gt.0")\
            .execute()
        return len(response.data) if response.data else 0
    except Exception as e:
        print(f"Error resetting movement locks: {e}")
        return 0

def increment_unit_local_moves(unit_id: int) -> bool:
    """
    Incrementa el contador de movimientos locales de una unidad en 1.
    Retorna True si la operación fue exitosa.
    """
    db = get_supabase()
    try:
        # Fetch current
        unit = db.table("units").select("local_moves_count").eq("id", unit_id).single().execute()
        if not unit.data: 
            return False
            
        current = unit.data.get("local_moves_count", 0)
        
        # Update
        resp = db.table("units").update({"local_moves_count": current + 1}).eq("id", unit_id).execute()
        return bool(resp.data)
    except Exception as e:
        print(f"Error incrementing moves for unit {unit_id}: {e}")
        return False

def decrement_transit_ticks() -> int:
    """
    Decrementa transit_ticks_remaining en 1 para todas las unidades en tránsito.
    Retorna número de unidades actualizadas.
    """
    db = get_supabase()
    try:
        # Supabase no soporta decrement directo, necesitamos obtener y actualizar
        units = db.table("units")\
            .select("id, transit_ticks_remaining")\
            .eq("status", "TRANSIT")\
            .gt("transit_ticks_remaining", 0)\
            .execute()

        if not units.data:
            return 0

        updated = 0
        for unit in units.data:
            new_ticks = unit["transit_ticks_remaining"] - 1
            db.table("units")\
                .update({"transit_ticks_remaining": new_ticks})\
                .eq("id", unit["id"])\
                .execute()
            updated += 1

        return updated
    except Exception as e:
        print(f"Error decrementing transit ticks: {e}")
        return 0


# --- V10.0: FUNCIONES AUXILIARES DE HISTORIAL ---

def _log_transit_start(
    unit_id: int,
    player_id: int,
    origin_data: Dict[str, Any],
    destination_data: Dict[str, Any],
    starlane_id: Optional[int],
    movement_type: str,
    ticks_required: int,
    current_tick: int
) -> None:
    """Registra el inicio de un tránsito en la tabla de historial."""
    db = get_supabase()
    try:
        data = {
            "unit_id": unit_id,
            "player_id": player_id,
            "origin_system_id": origin_data.get("location_system_id"),
            "origin_planet_id": origin_data.get("location_planet_id"),
            "origin_sector_id": origin_data.get("location_sector_id"),
            "origin_ring": origin_data.get("ring", 0),
            "destination_system_id": destination_data.get("system_id"),
            "destination_planet_id": destination_data.get("planet_id"),
            "destination_sector_id": destination_data.get("sector_id"),
            "destination_ring": destination_data.get("ring", 0),
            "starlane_id": starlane_id,
            "movement_type": movement_type,
            "started_at_tick": current_tick,
            "ticks_required": ticks_required,
            "status": "IN_PROGRESS"
        }
        db.table("unit_transits").insert(data).execute()
    except Exception as e:
        print(f"Error logging transit start: {e}")


def _log_transit_complete(unit_id: int, current_tick: int) -> None:
    """Marca un tránsito como completado en el historial."""
    db = get_supabase()
    try:
        db.table("unit_transits")\
            .update({
                "status": "COMPLETED",
                "completed_at_tick": current_tick
            })\
            .eq("unit_id", unit_id)\
            .eq("status", "IN_PROGRESS")\
            .execute()
    except Exception as e:
        print(f"Error logging transit complete: {e}")


def _log_transit_interdicted(unit_id: int, current_tick: int) -> None:
    """Marca un tránsito como interdictado en el historial."""
    db = get_supabase()
    try:
        db.table("unit_transits")\
            .update({
                "status": "INTERDICTED",
                "completed_at_tick": current_tick
            })\
            .eq("unit_id", unit_id)\
            .eq("status", "IN_PROGRESS")\
            .execute()
    except Exception as e:
        print(f"Error logging transit interdiction: {e}")