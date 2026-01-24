# data/unit_repository.py (Completo)
"""
Repositorio para manejo de Unidades y Tropas.
Interactúa con las tablas 'units', 'troops' y 'unit_members'.
Implementa persistencia de composición y gestión de estado.
V9.0
"""

from typing import Optional, List, Dict, Any
from data.database import get_supabase
from core.models import UnitSchema, TroopSchema, UnitStatus

def create_troop(player_id: int, name: str, troop_type: str, level: int = 1) -> Optional[Dict[str, Any]]:
    """Crea una nueva tropa en la DB."""
    db = get_supabase()
    try:
        data = {
            "player_id": player_id,
            "name": name,
            "type": troop_type,
            "level": level,
            "combats_at_current_level": 0
        }
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

def delete_troop(troop_id: int) -> bool:
    """Elimina una tropa (Ej: Al ser promovida a Héroe)."""
    db = get_supabase()
    try:
        response = db.table("troops").delete().eq("id", troop_id).execute()
        return bool(response.data)
    except Exception as e:
        print(f"Error deleting troop {troop_id}: {e}")
        return False

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
            "location_sector_id": location_data.get("sector_id")
        }
        response = db.table("units").insert(data).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error creating unit: {e}")
        return None

def get_units_by_player(player_id: int) -> List[Dict[str, Any]]:
    """Obtiene todas las unidades del jugador con sus miembros."""
    db = get_supabase()
    try:
        # Obtenemos unidades
        units_resp = db.table("units").select("*").eq("player_id", player_id).execute()
        units = units_resp.data
        if not units:
            return []
        
        # Obtenemos miembros para estas unidades
        unit_ids = [u["id"] for u in units]
        members_resp = db.table("unit_members").select("*").in_("unit_id", unit_ids).execute()
        members_by_unit = {}
        
        # Agrupar miembros
        for m in members_resp.data:
            uid = m["unit_id"]
            if uid not in members_by_unit:
                members_by_unit[uid] = []
            
            # Hydrate simple name/details based on type could be done here 
            # or in a higher service layer. Repository just returns raw refs + data.
            members_by_unit[uid].append(m)
            
        # Attach to units
        for u in units:
            u["members"] = members_by_unit.get(u["id"], [])
            
        return units
    except Exception as e:
        print(f"Error fetching units for player {player_id}: {e}")
        return []

def get_unit_by_id(unit_id: int) -> Optional[Dict[str, Any]]:
    db = get_supabase()
    try:
        response = db.table("units").select("*").eq("id", unit_id).execute()
        if not response.data:
            return None
        
        unit = response.data[0]
        members_resp = db.table("unit_members").select("*").eq("unit_id", unit_id).execute()
        unit["members"] = members_resp.data
        return unit
    except Exception as e:
        print(f"Error fetching unit {unit_id}: {e}")
        return None

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