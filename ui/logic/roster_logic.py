# ui/logic/roster_logic.py
"""
Lógica de datos para el Roster de Facción.
Contiene helpers de acceso seguro (Pydantic V2/Dict compatibility) y funciones de indexación.
Extraído de ui/faction_roster.py V17.0.
"""

from typing import Dict, List, Any, Optional, Set, Tuple

from core.models import LocationRing


# --- HELPERS DE ACCESO SEGURO (PYDANTIC V2 COMPATIBILITY) ---

def get_prop(obj: Any, key: str, default: Any = None) -> Any:
    """
    Obtiene una propiedad de forma segura ya sea de un Diccionario o de un Modelo Pydantic/Objeto.
    Reemplaza a obj.get(key, default).
    """
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def set_prop(obj: Any, key: str, value: Any) -> None:
    """
    Establece una propiedad de forma segura en un Diccionario o Modelo.
    """
    if isinstance(obj, dict):
        obj[key] = value
    else:
        # Asume que el objeto es mutable (Pydantic models por defecto lo son)
        if hasattr(obj, key):
            setattr(obj, key, value)
        else:
            # Si el modelo permite extra fields o es dinámico
            try:
                setattr(obj, key, value)
            except AttributeError:
                pass  # No se pudo setear, ignorar en modelos estrictos


def sort_key_by_prop(key: str, default: Any = 0):
    """
    Retorna una función lambda para usar en sorted() o .sort() compatible con Dict y Objetos.
    """
    return lambda x: getattr(x, key, default) if not isinstance(x, dict) else x.get(key, default)


# --- HELPERS DE DATOS ---

def get_assigned_entity_ids(units: List[Any]) -> Tuple[Set[int], Set[int]]:
    """Retorna sets de IDs de characters y troops asignados a unidades."""
    assigned_chars: Set[int] = set()
    assigned_troops: Set[int] = set()
    for unit in units:
        members = get_prop(unit, "members", [])
        for member in members:
            etype = get_prop(member, "entity_type")
            eid = get_prop(member, "entity_id")
            if etype == "character":
                assigned_chars.add(eid)
            elif etype == "troop":
                assigned_troops.add(eid)
    return assigned_chars, assigned_troops


def hydrate_unit_members(
    units: List[Any],
    char_map: Dict[int, str],
    troop_map: Dict[int, str]
) -> List[Any]:
    """Inyecta nombres reales en los miembros de cada unidad (Compatible Híbrido)."""
    for unit in units:
        members = get_prop(unit, "members", [])
        for member in members:
            eid = get_prop(member, "entity_id")
            etype = get_prop(member, "entity_type")

            name = f"{etype} {eid}"  # Fallback
            if etype == "character":
                name = char_map.get(eid, f"Personaje {eid}")
            elif etype == "troop":
                name = troop_map.get(eid, f"Tropa {eid}")

            # Set seguro usando helper
            set_prop(member, "name", name)

    return units


def get_systems_with_presence(
    location_index: dict,
    characters: List[Any],
    assigned_char_ids: Set[int]
) -> Set[int]:
    """Obtiene IDs de sistemas donde hay presencia del jugador."""
    system_ids: Set[int] = set()

    # Desde unidades por sector
    for sector_id, unit_list in location_index["units_by_sector"].items():
        for u in unit_list:
            sid = get_prop(u, "location_system_id")
            if sid:
                system_ids.add(sid)

    # Desde unidades por ring
    for (sys_id, ring), unit_list in location_index["units_by_system_ring"].items():
        if unit_list:
            system_ids.add(sys_id)

    # Desde personajes sueltos
    for char in characters:
        cid = get_prop(char, "id")
        if cid not in assigned_char_ids:
            sys_id = get_prop(char, "location_system_id")
            if sys_id:
                system_ids.add(sys_id)

    # Desde chars_by_sector (inferir sistema desde planeta)
    for sector_id, char_list in location_index["chars_by_sector"].items():
        for c in char_list:
            sys_id = get_prop(c, "location_system_id")
            if sys_id:
                system_ids.add(sys_id)

    # V17.0: Desde tropas sueltas por sector
    for sector_id, troop_list in location_index.get("troops_by_sector", {}).items():
        for t in troop_list:
            sys_id = get_prop(t, "location_system_id")
            if sys_id:
                system_ids.add(sys_id)

    # V17.0: Desde tropas sueltas por ring
    for (sys_id, _ring), troop_list in location_index.get("troops_by_system_ring", {}).items():
        if troop_list:
            system_ids.add(sys_id)

    return system_ids


def build_location_index(
    characters: List[Any],
    units: List[Any],
    assigned_char_ids: Set[int],
    troops: Optional[List[Any]] = None,
    assigned_troop_ids: Optional[Set[int]] = None
) -> Dict[str, Any]:
    """
    Construye índice de entidades por ubicación.
    Retorna dict con claves:
    - 'chars_by_sector': {sector_id: [chars]}
    - 'units_by_sector': {sector_id: [units]}
    - 'units_by_system_ring': {(system_id, ring): [units]}
    - 'units_in_transit': [units]
    - 'chars_by_system_ring': {(system_id, ring): [chars]} (V15.2 Fix)
    - 'troops_by_sector': {sector_id: [troops]} (V17.0 Tropas sueltas)
    - 'troops_by_system_ring': {(system_id, ring): [troops]} (V17.0 Tropas sueltas)
    """
    troops = troops or []
    assigned_troop_ids = assigned_troop_ids or set()

    chars_by_sector: Dict[int, List[Any]] = {}
    units_by_sector: Dict[int, List[Any]] = {}
    units_by_system_ring: Dict[Tuple[int, int], List[Any]] = {}
    units_in_transit: List[Any] = []

    # NEW V15.2: Soporte para chars sueltos en espacio
    chars_by_system_ring: Dict[Tuple[int, int], List[Any]] = {}

    # NEW V17.0: Soporte para tropas sueltas
    troops_by_sector: Dict[int, List[Any]] = {}
    troops_by_system_ring: Dict[Tuple[int, int], List[Any]] = {}

    # Personajes sueltos
    for char in characters:
        cid = get_prop(char, "id")
        if cid in assigned_char_ids:
            continue

        sector_id = get_prop(char, "location_sector_id")
        if sector_id:
            chars_by_sector.setdefault(sector_id, []).append(char)
        else:
            # Check si está en espacio (System + Ring sin sector)
            system_id = get_prop(char, "location_system_id")
            if system_id:
                ring = get_prop(char, "ring", 0)
                # Ensure value is int
                if isinstance(ring, LocationRing):
                    ring = ring.value
                chars_by_system_ring.setdefault((system_id, ring), []).append(char)

    # V17.0: Tropas sueltas (no asignadas a unidades)
    for troop in troops:
        tid = get_prop(troop, "id")
        if tid in assigned_troop_ids:
            continue

        sector_id = get_prop(troop, "location_sector_id")
        if sector_id:
            troops_by_sector.setdefault(sector_id, []).append(troop)
        else:
            # Check si está en espacio (System + Ring sin sector)
            system_id = get_prop(troop, "location_system_id")
            if system_id:
                ring = get_prop(troop, "ring", 0)
                if isinstance(ring, LocationRing):
                    ring = ring.value
                troops_by_system_ring.setdefault((system_id, ring), []).append(troop)

    # Unidades por ubicación
    for unit in units:
        status = get_prop(unit, "status", "GROUND")

        # V13.5: Lógica de agrupación corregida
        if status == "TRANSIT":
            origin = get_prop(unit, "transit_origin_system_id")
            dest = get_prop(unit, "transit_destination_system_id")

            # Tránsito Local (SCO): Se queda en el sistema
            if origin is not None and origin == dest:
                # Se asigna al sistema origen y al anillo actual
                ring_val = get_prop(unit, "ring", 0)
                if isinstance(ring_val, LocationRing):
                    ring_val = ring_val.value

                key = (origin, ring_val)
                units_by_system_ring.setdefault(key, []).append(unit)
                continue

            # Tránsito Interestelar: Va a la lista global de Starlanes
            units_in_transit.append(unit)
            continue

        sector_id = get_prop(unit, "location_sector_id")
        if sector_id:
            units_by_sector.setdefault(sector_id, []).append(unit)
        else:
            system_id = get_prop(unit, "location_system_id")
            ring = get_prop(unit, "ring", 0)
            if isinstance(ring, LocationRing):
                ring = ring.value

            if system_id:
                key = (system_id, ring)
                units_by_system_ring.setdefault(key, []).append(unit)

    return {
        "chars_by_sector": chars_by_sector,
        "units_by_sector": units_by_sector,
        "units_by_system_ring": units_by_system_ring,
        "units_in_transit": units_in_transit,
        "chars_by_system_ring": chars_by_system_ring,  # V15.2
        "troops_by_sector": troops_by_sector,  # V17.0
        "troops_by_system_ring": troops_by_system_ring,  # V17.0
    }


# --- CÁLCULOS DE CAPACIDAD DE UNIDAD ---

# Constantes de capacidad V16.0
BASE_CAPACITY = 4
MAX_CAPACITY = 12


def calculate_unit_display_capacity(members: List[Any]) -> int:
    """
    V16.0: Calcula la capacidad máxima de una unidad para display en UI.
    Basado en la habilidad de Liderazgo del líder.
    Fórmula: 4 + (skill_liderazgo // 10)
    """
    # Buscar el líder (is_leader=True y character)
    leader = None
    for m in members:
        if get_prop(m, "is_leader", False) and get_prop(m, "entity_type") == "character":
            leader = m
            break

    # Fallback: primer character si no hay líder explícito
    if not leader:
        for m in members:
            if get_prop(m, "entity_type") == "character":
                leader = m
                break

    if not leader:
        return BASE_CAPACITY

    # Obtener habilidad de Liderazgo del snapshot
    details = get_prop(leader, "details", {})
    if not details:
        return BASE_CAPACITY

    skills = details.get("habilidades", {})
    leadership_skill = skills.get("Liderazgo", 0)

    return min(MAX_CAPACITY, BASE_CAPACITY + (leadership_skill // 10))


def get_leader_capacity(char_obj: Any) -> Tuple[int, int]:
    """
    V16.0: Retorna (liderazgo_skill, max_capacity) para un personaje.
    Usado en la creación de unidades.
    """
    stats = get_prop(char_obj, "stats_json", {})
    if not stats or not isinstance(stats, dict):
        return 0, BASE_CAPACITY

    capacidades = stats.get("capacidades", {})
    attrs = capacidades.get("atributos", {})
    presencia = attrs.get("presencia", 5)
    voluntad = attrs.get("voluntad", 5)

    # Liderazgo = (presencia + voluntad) * 2
    leadership_skill = (presencia + voluntad) * 2
    # Capacidad = 4 + (Liderazgo // 10)
    capacity = min(MAX_CAPACITY, BASE_CAPACITY + (leadership_skill // 10))

    return leadership_skill, capacity
