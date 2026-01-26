# services/unit_service.py (Completo)
"""
Servicio de Gestión de Unidades V10.0.
Operaciones de alto nivel para agrupamiento, transferencia y gestión de unidades.
Actualizado V14.2: Gestión de Modo Sigilo y Resolución de Escapes.
"""

from typing import Optional, Dict, Any, List, Tuple
from core.models import UnitSchema, UnitMemberSchema, UnitStatus
from core.movement_constants import MAX_UNIT_SLOTS, MIN_CHARACTERS_PER_UNIT
from data.unit_repository import (
    create_unit,
    get_unit_by_id,
    get_units_by_player,
    add_unit_member,
    remove_unit_member,
    update_unit_status
)
from data.character_repository import get_character_by_id
from data.log_repository import log_event
from data.database import get_supabase


def agile_grouping(
    source_unit_ids: List[int],
    target_unit_id: int,
    member_transfers: List[Dict[str, Any]],
    player_id: int
) -> Dict[str, Any]:
    """
    Reagrupamiento ágil: Mueve tropas/personajes entre unidades.
    REQUISITO: Todas las unidades deben estar en el mismo sector/planeta.
    Efecto: INSTANTÁNEO (0 ticks).

    Args:
        source_unit_ids: IDs de unidades de origen
        target_unit_id: ID de unidad destino
        member_transfers: Lista de dicts con {source_unit_id, entity_type, entity_id}
        player_id: ID del jugador

    Returns:
        Dict con status y detalles de la operación
    """
    result = {
        "success": False,
        "moved_count": 0,
        "errors": [],
        "warnings": []
    }

    # 1. Validar unidad destino
    target_unit_data = get_unit_by_id(target_unit_id)
    if not target_unit_data:
        result["errors"].append("Unidad destino no encontrada")
        return result

    target_unit = UnitSchema.from_dict(target_unit_data)

    if target_unit.player_id != player_id:
        result["errors"].append("No tienes control de la unidad destino")
        return result

    if target_unit.status == UnitStatus.TRANSIT:
        result["errors"].append("No puedes reagrupar unidades en tránsito")
        return result

    target_location = (
        target_unit.location_system_id,
        target_unit.location_planet_id,
        target_unit.location_sector_id
    )

    # 2. Validar unidades fuente y ubicaciones
    source_units = {}
    for src_id in source_unit_ids:
        src_data = get_unit_by_id(src_id)
        if not src_data:
            result["errors"].append(f"Unidad origen {src_id} no encontrada")
            continue

        src_unit = UnitSchema.from_dict(src_data)

        if src_unit.player_id != player_id:
            result["errors"].append(f"No tienes control de la unidad {src_id}")
            continue

        if src_unit.status == UnitStatus.TRANSIT:
            result["errors"].append(f"Unidad {src_id} está en tránsito")
            continue

        src_location = (
            src_unit.location_system_id,
            src_unit.location_planet_id,
            src_unit.location_sector_id
        )

        if src_location != target_location:
            result["errors"].append(f"Unidad {src_id} no está en la misma ubicación")
            continue

        source_units[src_id] = src_unit

    if not source_units:
        result["errors"].append("No hay unidades fuente válidas")
        return result

    # 3. Validar capacidad de la unidad destino
    current_members = len(target_unit.members)
    available_slots = MAX_UNIT_SLOTS - current_members

    if len(member_transfers) > available_slots:
        result["errors"].append(f"Slots insuficientes. Disponibles: {available_slots}, solicitados: {len(member_transfers)}")
        return result

    # 4. Validar que las transferencias no dejen unidades sin líder
    transfers_by_source = {}
    for transfer in member_transfers:
        src_id = transfer.get("source_unit_id")
        if src_id not in transfers_by_source:
            transfers_by_source[src_id] = []
        transfers_by_source[src_id].append(transfer)

    for src_id, transfers in transfers_by_source.items():
        if src_id not in source_units:
            continue

        src_unit = source_units[src_id]
        characters_leaving = sum(
            1 for t in transfers if t.get("entity_type") == "character"
        )
        current_characters = sum(
            1 for m in src_unit.members if m.entity_type == "character"
        )

        remaining_characters = current_characters - characters_leaving
        remaining_members = len(src_unit.members) - len(transfers)

        # Si quedan miembros pero no hay líder, es inválido
        if remaining_members > 0 and remaining_characters < MIN_CHARACTERS_PER_UNIT:
            result["errors"].append(
                f"La unidad {src_id} quedaría sin líder. Transfiere todos los miembros o deja al menos 1 personaje."
            )
            return result

    # 5. Ejecutar transferencias
    next_slot = current_members
    for transfer in member_transfers:
        src_id = transfer.get("source_unit_id")
        entity_type = transfer.get("entity_type")
        entity_id = transfer.get("entity_id")

        if src_id not in source_units:
            continue

        src_unit = source_units[src_id]

        # Buscar el slot actual del miembro en la unidad fuente
        source_slot = None
        for member in src_unit.members:
            if member.entity_type == entity_type and member.entity_id == entity_id:
                source_slot = member.slot_index
                break

        if source_slot is None:
            result["warnings"].append(f"Miembro {entity_type}:{entity_id} no encontrado en unidad {src_id}")
            continue

        # Remover de fuente
        remove_success = remove_unit_member(src_id, source_slot)
        if not remove_success:
            result["warnings"].append(f"Error removiendo miembro de unidad {src_id}")
            continue

        # Añadir a destino
        add_success = add_unit_member(target_unit_id, entity_type, entity_id, next_slot)
        if not add_success:
            result["warnings"].append(f"Error añadiendo miembro a unidad destino")
            # Intentar revertir
            add_unit_member(src_id, entity_type, entity_id, source_slot)
            continue

        next_slot += 1
        result["moved_count"] += 1

    result["success"] = result["moved_count"] > 0

    if result["success"]:
        log_event(f"✅ Reagrupamiento: {result['moved_count']} miembros transferidos", player_id)

    return result


def split_unit(
    source_unit_id: int,
    new_unit_name: str,
    member_ids: List[Dict[str, Any]],
    player_id: int
) -> Dict[str, Any]:
    """
    Divide una unidad en dos.
    Crea una nueva unidad con los miembros especificados.

    Args:
        source_unit_id: ID de la unidad a dividir
        new_unit_name: Nombre de la nueva unidad
        member_ids: Lista de dicts con {entity_type, entity_id} a transferir
        player_id: ID del jugador

    Returns:
        Dict con la nueva unidad creada o error
    """
    result = {
        "success": False,
        "new_unit_id": None,
        "error": None
    }

    # Validar unidad fuente
    source_data = get_unit_by_id(source_unit_id)
    if not source_data:
        result["error"] = "Unidad no encontrada"
        return result

    source_unit = UnitSchema.from_dict(source_data)

    if source_unit.player_id != player_id:
        result["error"] = "No tienes control de esta unidad"
        return result

    if source_unit.status == UnitStatus.TRANSIT:
        result["error"] = "No puedes dividir una unidad en tránsito"
        return result

    # Validar que se especifica al menos un personaje para la nueva unidad
    has_character = any(m.get("entity_type") == "character" for m in member_ids)
    if not has_character:
        result["error"] = "La nueva unidad debe tener al menos un personaje como líder"
        return result

    # Validar que la unidad original mantiene un líder
    characters_leaving = sum(1 for m in member_ids if m.get("entity_type") == "character")
    current_characters = sum(1 for m in source_unit.members if m.entity_type == "character")

    if current_characters - characters_leaving < MIN_CHARACTERS_PER_UNIT:
        remaining = len(source_unit.members) - len(member_ids)
        if remaining > 0:
            result["error"] = "La unidad original quedaría sin líder"
            return result

    # Crear nueva unidad
    location_data = {
        "system_id": source_unit.location_system_id,
        "planet_id": source_unit.location_planet_id,
        "sector_id": source_unit.location_sector_id
    }

    new_unit_data = create_unit(player_id, new_unit_name, location_data)
    if not new_unit_data:
        result["error"] = "Error creando nueva unidad"
        return result

    new_unit_id = new_unit_data.get("id")
    
    # Asignar anillo correcto (create_unit por defecto usa Stellar/0)
    origin_ring = source_unit.ring.value if hasattr(source_unit.ring, 'value') else source_unit.ring
    if origin_ring != 0:
        db = get_supabase()
        db.table("units").update({"ring": origin_ring}).eq("id", new_unit_id).execute()

    # Transferir miembros
    slot = 0
    for member_spec in member_ids:
        entity_type = member_spec.get("entity_type")
        entity_id = member_spec.get("entity_id")

        # Buscar slot en unidad fuente
        source_slot = None
        for member in source_unit.members:
            if member.entity_type == entity_type and member.entity_id == entity_id:
                source_slot = member.slot_index
                break

        if source_slot is None:
            continue

        # Transferir
        remove_unit_member(source_unit_id, source_slot)
        add_unit_member(new_unit_id, entity_type, entity_id, slot)
        slot += 1

    result["success"] = True
    result["new_unit_id"] = new_unit_id

    log_event(f"✂️ Unidad dividida: Nueva unidad '{new_unit_name}' creada", player_id)

    return result


def merge_units(
    unit_ids: List[int],
    merged_unit_name: str,
    player_id: int
) -> Dict[str, Any]:
    """
    Fusiona múltiples unidades en una sola.
    Todas las unidades deben estar en la misma ubicación.

    Args:
        unit_ids: IDs de las unidades a fusionar
        merged_unit_name: Nombre de la unidad fusionada
        player_id: ID del jugador

    Returns:
        Dict con la unidad fusionada o error
    """
    result = {
        "success": False,
        "merged_unit_id": None,
        "error": None,
        "dissolved_units": []
    }

    if len(unit_ids) < 2:
        result["error"] = "Se necesitan al menos 2 unidades para fusionar"
        return result

    # Validar todas las unidades
    units = []
    reference_location = None
    total_members = 0

    for uid in unit_ids:
        unit_data = get_unit_by_id(uid)
        if not unit_data:
            result["error"] = f"Unidad {uid} no encontrada"
            return result

        unit = UnitSchema.from_dict(unit_data)

        if unit.player_id != player_id:
            result["error"] = f"No tienes control de la unidad {uid}"
            return result

        if unit.status == UnitStatus.TRANSIT:
            result["error"] = f"Unidad {uid} está en tránsito"
            return result

        location = (
            unit.location_system_id,
            unit.location_planet_id,
            unit.location_sector_id
        )

        if reference_location is None:
            reference_location = location
        elif location != reference_location:
            result["error"] = "Las unidades no están en la misma ubicación"
            return result

        total_members += len(unit.members)
        units.append(unit)

    # Validar capacidad
    if total_members > MAX_UNIT_SLOTS:
        result["error"] = f"Demasiados miembros ({total_members}). Máximo: {MAX_UNIT_SLOTS}"
        return result

    # Usar la primera unidad como base y renombrarla
    base_unit = units[0]
    base_unit_id = base_unit.id

    # Renombrar (esto requeriría una función adicional en el repositorio)
    # Por ahora, usamos la unidad base tal cual

    # Transferir miembros de las otras unidades a la base
    slot = len(base_unit.members)
    for unit in units[1:]:
        for member in unit.members:
            add_unit_member(base_unit_id, member.entity_type, member.entity_id, slot)
            slot += 1

        # Marcar unidad original como disuelta (eliminar miembros y actualizar status)
        for member in unit.members:
            remove_unit_member(unit.id, member.slot_index)

        result["dissolved_units"].append(unit.id)

    result["success"] = True
    result["merged_unit_id"] = base_unit_id

    log_event(f"🔗 Unidades fusionadas en '{merged_unit_name}'", player_id)

    return result


def get_unit_summary(unit_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene un resumen de una unidad para la UI.
    """
    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        return None

    unit = UnitSchema.from_dict(unit_data)

    # Contar tipos de miembros
    characters = sum(1 for m in unit.members if m.entity_type == 'character')
    troops = sum(1 for m in unit.members if m.entity_type == 'troop')

    return {
        "id": unit.id,
        "name": unit.name,
        "status": unit.status.value,
        "location": {
            "system_id": unit.location_system_id,
            "planet_id": unit.location_planet_id,
            "sector_id": unit.location_sector_id,
            "ring": unit.ring.value if hasattr(unit.ring, 'value') else unit.ring
        },
        "composition": {
            "total": len(unit.members),
            "characters": characters,
            "troops": troops,
            "available_slots": MAX_UNIT_SLOTS - len(unit.members)
        },
        "transit": {
            "in_transit": unit.status == UnitStatus.TRANSIT,
            "end_tick": unit.transit_end_tick,
            "ticks_remaining": unit.transit_ticks_remaining,
            "destination_system_id": unit.transit_destination_system_id
        },
        "movement_locked": unit.movement_locked
    }


# --- V14.2: LÓGICA DE SIGILO Y ESCAPE ---

def toggle_stealth_mode(unit_id: int, player_id: int) -> Dict[str, Any]:
    """
    Alterna el modo de sigilo (STEALTH_MODE) de una unidad.
    - Si está en GROUND/SPACE -> Pasa a STEALTH_MODE.
    - Si está en STEALTH_MODE -> Pasa a GROUND/SPACE (según si tiene sector_id).
    
    Restricciones:
    - No puede cambiar si está en tránsito.
    - Requiere ser dueño de la unidad.
    """
    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        return {"success": False, "error": "Unidad no encontrada"}
    
    unit = UnitSchema.from_dict(unit_data)
    
    if unit.player_id != player_id:
        return {"success": False, "error": "No tienes control de la unidad"}
    
    if unit.status == UnitStatus.TRANSIT:
        return {"success": False, "error": "No puedes activar sigilo en tránsito"}
    
    new_status = None
    message = ""
    
    if unit.status == UnitStatus.STEALTH_MODE:
        # Desactivar sigilo
        if unit.location_sector_id is not None:
            new_status = UnitStatus.GROUND
        else:
            new_status = UnitStatus.SPACE
        message = f"📡 Modo Sigilo DESACTIVADO para '{unit.name}'"
    else:
        # Activar sigilo
        new_status = UnitStatus.STEALTH_MODE
        message = f"🥷 Modo Sigilo ACTIVADO para '{unit.name}'"
        
    # Actualizar DB
    # FIX V14.2.1: Pasar el objeto Enum completo, no el value.
    # El repositorio (update_unit_status) se encarga de extraer .value.
    success = update_unit_status(unit_id, new_status)
    
    if success:
        log_event(message, player_id)
        return {"success": True, "new_status": new_status.value}
    
    return {"success": False, "error": "Error actualizando estado"}


def apply_escape_results(
    source_unit_id: int,
    pursuer_unit_id: int,
    escape_results: Tuple[List[UnitMemberSchema], List[UnitMemberSchema]],
    player_id: int
) -> Dict[str, Any]:
    """
    Aplica los resultados de una maniobra de escape/caza.
    
    Args:
        source_unit_id: Unidad original que intenta escapar.
        pursuer_unit_id: Unidad cazadora.
        escape_results: Tupla (escaped_members, captured_members).
        player_id: Dueño de la unidad que escapa.
        
    Acciones:
    1. Miembros escapados -> Se mueven a una NUEVA unidad con movimiento libre.
    2. Miembros capturados (remanente) -> Se quedan en unidad original, quedan DESORIENTADOS.
    3. Unidad cazadora -> Queda DESORIENTADA (fatiga de persecución).
    """
    escaped_members, captured_members = escape_results
    
    result_log = {
        "escaped_unit_id": None,
        "captured_unit_id": source_unit_id,
        "pursuer_unit_id": pursuer_unit_id
    }
    
    db = get_supabase()
    
    # 1. Procesar Escapados
    if escaped_members:
        # Preparar lista para split_unit
        members_to_split = [
            {"entity_type": m.entity_type, "entity_id": m.entity_id}
            for m in escaped_members
        ]
        
        # Validar líder para la nueva unidad
        has_leader = any(m.entity_type == 'character' for m in escaped_members)
        if not has_leader:
            # Caso borde: Si escapan solo tropas, no pueden formar unidad válida por reglas actuales.
            # En V14.2, si esto pasa, se considera que se dispersan y regresan a la reserva (o se pierden).
            # Por simplicidad del MVP, forzamos que se queden capturados si no hay líder.
            log_event(f"⚠️ Tropas escaparon pero sin líder. Regresan a la formación.", player_id)
            captured_members.extend(escaped_members)
            escaped_members.clear()
        else:
            unit_name_source = get_unit_by_id(source_unit_id).get('name', 'Unidad')
            new_name = f"{unit_name_source} (Remanente)"
            
            split_res = split_unit(source_unit_id, new_name, members_to_split, player_id)
            
            if split_res["success"]:
                new_unit_id = split_res["new_unit_id"]
                result_log["escaped_unit_id"] = new_unit_id
                
                # Regla V14.2: Unidad escapada tiene movimiento gratis (movement_locked=False, local_moves=0)
                # Actualización directa por DB ya que no hay función específica en repo para esto
                db.table("units").update({
                    "movement_locked": False,
                    "local_moves_count": 0,
                    "disoriented": False # Escaparon bien
                }).eq("id", new_unit_id).execute()
                
                log_event(f"💨 '{new_name}' ha escapado con éxito y se reagrupa.", player_id)
    
    # 2. Procesar Capturados (Unidad Original)
    if captured_members:
        # Se quedan en la unidad original, que queda DESORIENTADA
        db.table("units").update({
            "disoriented": True
        }).eq("id", source_unit_id).execute()
        
        unit_name = get_unit_by_id(source_unit_id).get('name', 'Unidad')
        log_event(f"😵 Unidad '{unit_name}' no logró evadir totalmente y queda DESORIENTADA.", player_id)
        
    # 3. Procesar Cazadores
    # Regla V14.2: La persecución agota, los cazadores también quedan DESORIENTADOS
    db.table("units").update({
        "disoriented": True
    }).eq("id", pursuer_unit_id).execute()
    
    pursuer = get_unit_by_id(pursuer_unit_id)
    if pursuer:
        log_event(f"😓 Unidad '{pursuer.get('name')}' queda DESORIENTADA tras la persecución.", pursuer.get('player_id'))

    return result_log