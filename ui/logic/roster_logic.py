# ui/logic/roster_logic.py
"""
Lógica y Helpers para el Roster de Facción.
Extraído de ui/faction_roster.py para modularización.
V19.0: Refactorización para Dashboard de Comando y Manejo de Errores Robusto.
"""

from typing import Dict, List, Any, Optional, Set, Tuple
import logging

# Configurar logger local
logger = logging.getLogger(__name__)

def get_prop(obj: Any, key: str, default: Any = None) -> Any:
    """
    Obtiene una propiedad de un objeto (dict o Pydantic model) de forma segura.
    
    Args:
        obj: Objeto fuente (dict o modelo)
        key: Nombre de la propiedad
        default: Valor a retornar si no existe
        
    Returns:
        Valor de la propiedad o default
    """
    if obj is None:
        return default
        
    try:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)
    except Exception as e:
        # Fallback silencioso en producción, log en debug
        # print(f"Warning: Error accessing {key}: {e}")
        return default


def get_assigned_entity_ids(units: List[Any]) -> Tuple[Set[int], Set[int]]:
    """
    Obtiene conjuntos de IDs de personajes y tropas que ya están asignados a unidades.
    
    Returns:
        Tuple[Set[int], Set[int]]: (assigned_char_ids, assigned_troop_ids)
    """
    assigned_chars = set()
    assigned_troops = set()

    if not units:
        return assigned_chars, assigned_troops

    for u in units:
        members = get_prop(u, "members", [])
        for m in members:
            # Manejo robusto de miembros que pueden ser dicts o modelos
            mid = get_prop(m, "id")
            etype = get_prop(m, "entity_type", "character")
            
            if mid is not None:
                if etype == "character":
                    assigned_chars.add(mid)
                elif etype == "troop":
                    assigned_troops.add(mid)

    return assigned_chars, assigned_troops


def hydrate_unit_members(
    units: List[Any], 
    char_map: Dict[int, str], 
    troop_map: Dict[int, str]
) -> List[Any]:
    """
    Rellena los nombres de los miembros de las unidades usando los mapas proporcionados.
    Modifica las unidades in-place (si son dicts) o retorna copias actualizadas.
    """
    # Si son modelos Pydantic, esto podría ser complejo sin .copy(), 
    # asumimos dicts o modelos mutables por ahora o que la vista los trata como solo lectura.
    # Para mayor seguridad, iteramos y modificamos estructuras internas si es posible.
    
    for u in units:
        members = get_prop(u, "members", [])
        for m in members:
            mid = get_prop(m, "id")
            etype = get_prop(m, "entity_type", "character")
            
            # Buscar nombre actual
            current_name = get_prop(m, "name")
            
            # Si no tiene nombre o queremos asegurar consistencia
            if mid is not None:
                new_name = "???"
                if etype == "character":
                    new_name = char_map.get(mid, f"Desconocido ({mid})")
                elif etype == "troop":
                    new_name = troop_map.get(mid, f"Tropa ({mid})")
                    
                # Actualizar el nombre en el miembro
                if isinstance(m, dict):
                    m["name"] = new_name
                elif hasattr(m, "name"):
                    try:
                        setattr(m, "name", new_name)
                    except AttributeError:
                        pass # Modelo inmutable
                        
    return units


def build_location_index(
    characters: List[Any], 
    units: List[Any], 
    assigned_char_ids: Set[int],
    troops: List[Any] = [], 
    assigned_troop_ids: Set[int] = set()
) -> Dict[str, Any]:
    """
    Construye un índice optimizado de ubicaciones para rendering rápido.
    Categoriza entidades por sistema, anillo y sector.
    """
    index = {
        "units_by_sector": {},       # {sector_id: [units]}
        "chars_by_sector": {},       # {sector_id: [chars]}
        "troops_by_sector": {},      # {sector_id: [troops]}
        "units_by_system_ring": {},  # {(sys_id, ring): [units]}
        "chars_by_system_ring": {},  # {(sys_id, ring): [chars]}
        "troops_by_system_ring": {}, # {(sys_id, ring): [troops]}
        "units_in_transit": [],      # [units]
        # Nuevos índices para Dashboard
        "systems_presence": set(),   # {sys_id}
        "space_forces": {},          # {sys_id: [units]}
        "ground_forces": {},         # {sys_id: [units]}
        "unlocated": [],             # [entities] - Fallback for items with no system_id
    }

    # 1. Indexar Unidades
    for u in units:
        status = get_prop(u, "status")
        
        # Filtro de Tránsito
        if status == "TRANSIT":
            index["units_in_transit"].append(u)
            continue
            
        sys_id = get_prop(u, "system_id")
        
        # Si no tiene sistema, es una unidad anómala o en limbo
        if sys_id is None:
            index["unlocated"].append(u)
            continue
            
        index["systems_presence"].add(sys_id)
        
        # Clasificar Espacio vs Tierra
        if status == "SPACE" or status == "CONSTRUCTING": # Asumimos space si construye naves, revisar lógica
             if sys_id not in index["space_forces"]: index["space_forces"][sys_id] = []
             index["space_forces"][sys_id].append(u)
        elif status == "GROUND":
             if sys_id not in index["ground_forces"]: index["ground_forces"][sys_id] = []
             index["ground_forces"][sys_id].append(u)

        # Indexado fino
        sector_id = get_prop(u, "sector_id")
        if sector_id:
            if sector_id not in index["units_by_sector"]:
                index["units_by_sector"][sector_id] = []
            index["units_by_sector"][sector_id].append(u)
            
        # Indexado por anillo (Space)
        ring = get_prop(u, "ring")
        if status == "SPACE" and ring is not None:
            key = (sys_id, ring)
            if key not in index["units_by_system_ring"]:
                index["units_by_system_ring"][key] = []
            index["units_by_system_ring"][key].append(u)

    # 2. Indexar Personajes Sueltos
    for c in characters:
        cid = get_prop(c, "id")
        # Solo procesar si no está asignado
        if cid in assigned_char_ids:
            continue
            
        loc = get_prop(c, "location", {})
        sys_id = get_prop(loc, "system_id")
        
        if not sys_id: 
            # Intentar fallback a unlocated si tiene alguna data
            index["unlocated"].append(c)
            continue
        
        index["systems_presence"].add(sys_id)
        
        sector_id = get_prop(loc, "sector_id")
        if sector_id:
            if sector_id not in index["chars_by_sector"]:
                index["chars_by_sector"][sector_id] = []
            index["chars_by_sector"][sector_id].append(c)
            
        # Ubicación orbital (ring)
        ring = get_prop(loc, "ring") # A veces location tiene ring directo
        if ring is not None:
            key = (sys_id, ring)
            if key not in index["chars_by_system_ring"]:
                 index["chars_by_system_ring"][key] = []
            index["chars_by_system_ring"][key].append(c)

    # 3. Indexar Tropas Sueltas
    for t in troops:
        tid = get_prop(t, "id")
        if tid in assigned_troop_ids:
            continue
            
        loc = get_prop(t, "location", {})
        sys_id = get_prop(loc, "system_id")
        
        if not sys_id: 
            index["unlocated"].append(t)
            continue
        
        index["systems_presence"].add(sys_id)
        
        sector_id = get_prop(loc, "sector_id")
        if sector_id:
            if sector_id not in index["troops_by_sector"]:
                index["troops_by_sector"][sector_id] = []
            index["troops_by_sector"][sector_id].append(t)
            
        # Ubicación orbital tropa (raro pero posible)
        ring = get_prop(loc, "ring")
        if ring is not None:
            key = (sys_id, ring)
            if key not in index["troops_by_system_ring"]:
                index["troops_by_system_ring"][key] = []
            index["troops_by_system_ring"][key].append(t)

    return index


def get_systems_with_presence(
    index: Dict[str, Any], 
    characters: List[Any], 
    assigned_chars: Set[int]
) -> List[int]:
    """
    Obtiene lista de IDs de sistemas donde el jugador tiene presencia (unidades o personal).
    """
    return list(index.get("systems_presence", set()))


def sort_key_by_prop(prop_name: str, default_val: Any = 0):
    """Retorna una función key para sort que usa get_prop."""
    return lambda obj: get_prop(obj, prop_name, default_val)


def calculate_unit_display_capacity(members: List[Any]) -> int:
    """
    Calcula la capacidad de mando efectiva de una unidad basada en el líder.
    Lógica duplicada de unit_service para visualización UI.
     Base: 2 + (Voluntad / 2) + Rango.
    """
    base_cap = 2
    
    if not members:
        return base_cap
        
    # Buscar líder
    leader = None
    for m in members:
        if get_prop(m, "is_leader", False) and get_prop(m, "entity_type") == "character":
            leader = m
            break
            
    if not leader:
        # Fallback al primer personaje
        for m in members:
             if get_prop(m, "entity_type") == "character":
                leader = m
                break
    
    if leader:
        # Intentar extraer info de skills/stats si está disponible en 'details' hidratado
        details = get_prop(leader, "details", {})
        attrs = details.get("atributos", {})
        voluntad = attrs.get("voluntad", 10) # Default 10 if missing
        
        # Rango bonus (simplificado)
        rango = details.get("rango", "Recluta")
        rango_bonus = 0
        if rango == "Oficial": rango_bonus = 2
        elif rango == "Comandante": rango_bonus = 4
        

# --- MISSING HELPERS RE-ADDED FOR COMPATIBILITY ---

BASE_CAPACITY = 2
MAX_CAPACITY = 10

def set_prop(obj: Any, key: str, value: Any) -> bool:
    """
    Establece una propiedad de un objeto (dict o Pydantic model) de forma segura.
    
    Args:
        obj: Objeto destino
        key: Nombre de la propiedad
        value: Valor a establecer
        
    Returns:
        True si fue exitoso, False si falló
    """
    if obj is None:
        return False
        
    try:
        if isinstance(obj, dict):
            obj[key] = value
            return True
        # Para objetos, intentamos setattr si tiene el atributo o si es dinámico
        setattr(obj, key, value)
        return True
    except Exception:
        return False


def get_leader_capacity(leader_obj: Any) -> Tuple[int, int]:
    """
    Calcula la habilidad de liderazgo y capacidad de mando de un personaje.
    
    Returns:
        Tuple[int, int]: (leadership_skill, max_capacity)
    """
    if not leader_obj:
        return 0, BASE_CAPACITY
        
    details = get_prop(leader_obj, "details", {})
    attrs = details.get("atributos", {})
    
    # Usar Presencia como proxy de habilidad de liderazgo para mostrar
    presencia = attrs.get("presencia", 10)
    voluntad = attrs.get("voluntad", 10)
    
    # Fórmula de Capacidad: Base + (Voluntad / 2) + Bono Rango
    rango = details.get("rango", "Recluta")
    rango_bonus = 0
    if rango == "Oficial": rango_bonus = 2
    elif rango == "Comandante": rango_bonus = 4
    
    cap = int(BASE_CAPACITY + (voluntad / 2) + rango_bonus)
    
    # Clamp
    cap = min(cap, MAX_CAPACITY)
    
    return presencia, cap

