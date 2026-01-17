# data/planet_repository.py
"""
Repositorio de Planetas y Edificios.
Gestiona todas las operaciones de persistencia relacionadas con
activos planetarios, edificios y recursos de lujo.
"""

from typing import Dict, List, Any, Optional, Tuple
from data.database import get_supabase
from data.log_repository import log_event
from core.world_constants import BUILDING_TYPES


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


# --- GESTIÓN DE ACTIVOS PLANETARIOS ---

def get_planet_asset(planet_id: int, player_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene el activo planetario de un jugador en un planeta específico.

    Args:
        planet_id: ID del planeta procedural
        player_id: ID del jugador

    Returns:
        Diccionario con datos del activo o None si no existe
    """
    try:
        response = _get_db().table("planet_assets")\
            .select("*")\
            .eq("planet_id", planet_id)\
            .eq("player_id", player_id)\
            .single()\
            .execute()

        return response.data if response.data else None
    except Exception as e:
        log_event(f"Error obteniendo activo planetario: {e}", player_id, is_error=True)
        return None


def get_planet_asset_by_id(planet_asset_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene un activo planetario por su ID.

    Args:
        planet_asset_id: ID del activo planetario

    Returns:
        Diccionario con datos del activo o None
    """
    try:
        response = _get_db().table("planet_assets")\
            .select("*")\
            .eq("id", planet_asset_id)\
            .single()\
            .execute()

        return response.data if response.data else None
    except Exception:
        return None


def get_all_player_planets(player_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene todos los planetas colonizados por un jugador.

    Args:
        player_id: ID del jugador

    Returns:
        Lista de activos planetarios
    """
    try:
        response = _get_db().table("planet_assets")\
            .select("*")\
            .eq("player_id", player_id)\
            .execute()

        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo planetas del jugador: {e}", player_id, is_error=True)
        return []


def get_all_player_planets_with_buildings(player_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene todos los planetas del jugador con sus edificios precargados.
    Optimizado para el tick económico (una sola query).

    Args:
        player_id: ID del jugador

    Returns:
        Lista de planetas con campo 'buildings' incluido
    """
    try:
        # Obtener planetas
        planets_response = _get_db().table("planet_assets")\
            .select("*")\
            .eq("player_id", player_id)\
            .execute()

        planets = planets_response.data if planets_response.data else []

        if not planets:
            return []

        # Obtener IDs de planetas
        planet_ids = [p["id"] for p in planets]

        # Obtener todos los edificios de todos los planetas en una sola query
        buildings_response = _get_db().table("planet_buildings")\
            .select("*")\
            .in_("planet_asset_id", planet_ids)\
            .execute()

        buildings = buildings_response.data if buildings_response.data else []

        # Agrupar edificios por planeta
        buildings_by_planet: Dict[int, List[Dict]] = {}
        for building in buildings:
            pid = building["planet_asset_id"]
            if pid not in buildings_by_planet:
                buildings_by_planet[pid] = []
            buildings_by_planet[pid].append(building)

        # Añadir edificios a cada planeta
        for planet in planets:
            planet["buildings"] = buildings_by_planet.get(planet["id"], [])

        return planets

    except Exception as e:
        log_event(f"Error obteniendo planetas con edificios: {e}", player_id, is_error=True)
        return []


def create_planet_asset(
    planet_id: int,
    system_id: int,
    player_id: int,
    settlement_name: str = "Colonia Principal",
    initial_population: int = 1000
) -> Optional[Dict[str, Any]]:
    """
    Crea un nuevo activo planetario (colonización).

    Args:
        planet_id: ID del planeta procedural
        system_id: ID del sistema solar
        player_id: ID del jugador
        settlement_name: Nombre del asentamiento
        initial_population: Población inicial

    Returns:
        Datos del activo creado o None si falla
    """
    try:
        asset_data = {
            "planet_id": planet_id,
            "system_id": system_id,
            "player_id": player_id,
            "nombre_asentamiento": settlement_name,
            "poblacion": initial_population,
            "pops_activos": initial_population,
            "pops_desempleados": 0,
            "seguridad": 1.0,
            "infraestructura_defensiva": 0,
            "felicidad": 1.0
        }

        response = _get_db().table("planet_assets").insert(asset_data).execute()

        if response.data:
            log_event(f"Planeta colonizado: {settlement_name}", player_id)
            return response.data[0]
        return None

    except Exception as e:
        log_event(f"Error creando activo planetario: {e}", player_id, is_error=True)
        return None


def update_planet_asset(
    planet_asset_id: int,
    updates: Dict[str, Any]
) -> bool:
    """
    Actualiza campos de un activo planetario.

    Args:
        planet_asset_id: ID del activo
        updates: Diccionario con campos a actualizar

    Returns:
        True si se actualizó correctamente
    """
    try:
        _get_db().table("planet_assets").update(updates).eq("id", planet_asset_id).execute()
        return True
    except Exception as e:
        log_event(f"Error actualizando activo planetario ID {planet_asset_id}: {e}", is_error=True)
        return False


def batch_update_planet_security(updates: List[Tuple[int, float]]) -> bool:
    """
    Actualiza la seguridad de múltiples planetas en batch.

    Args:
        updates: Lista de tuplas (planet_asset_id, nuevo_valor_seguridad)

    Returns:
        True si todas las actualizaciones fueron exitosas
    """
    if not updates:
        return True

    try:
        db = _get_db()
        for planet_id, security in updates:
            db.table("planet_assets").update({
                "seguridad": security
            }).eq("id", planet_id).execute()
        return True
    except Exception as e:
        log_event(f"Error en batch update de seguridad: {e}", is_error=True)
        return False


# --- GESTIÓN DE EDIFICIOS ---

def get_planet_buildings(planet_asset_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene todos los edificios de un planeta.

    Args:
        planet_asset_id: ID del activo planetario

    Returns:
        Lista de edificios
    """
    try:
        response = _get_db().table("planet_buildings")\
            .select("*")\
            .eq("planet_asset_id", planet_asset_id)\
            .execute()

        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo edificios del planeta: {e}", is_error=True)
        return []


def get_buildings_for_planets(planet_asset_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
    """
    Obtiene edificios de múltiples planetas en una sola query.

    Args:
        planet_asset_ids: Lista de IDs de activos planetarios

    Returns:
        Diccionario {planet_asset_id: [lista de edificios]}
    """
    if not planet_asset_ids:
        return {}

    try:
        response = _get_db().table("planet_buildings")\
            .select("*")\
            .in_("planet_asset_id", planet_asset_ids)\
            .execute()

        buildings = response.data if response.data else []

        # Agrupar por planeta
        result: Dict[int, List[Dict]] = {pid: [] for pid in planet_asset_ids}
        for building in buildings:
            pid = building["planet_asset_id"]
            if pid in result:
                result[pid].append(building)

        return result

    except Exception as e:
        log_event(f"Error obteniendo edificios en batch: {e}", is_error=True)
        return {pid: [] for pid in planet_asset_ids}


def build_structure(
    planet_asset_id: int,
    player_id: int,
    building_type: str,
    tier: int = 1
) -> Optional[Dict[str, Any]]:
    """
    Construye un nuevo edificio en un planeta.

    Args:
        planet_asset_id: ID del activo planetario
        player_id: ID del jugador
        building_type: Tipo de edificio (debe estar en BUILDING_TYPES)
        tier: Nivel del edificio

    Returns:
        Datos del edificio construido o None si falla
    """
    # Validar que el tipo de edificio existe
    if building_type not in BUILDING_TYPES:
        log_event(f"Tipo de edificio inválido: {building_type}", player_id, is_error=True)
        return None

    definition = BUILDING_TYPES[building_type]

    try:
        db = _get_db()

        # Verificar si ya existe el edificio
        existing = db.table("planet_buildings")\
            .select("id")\
            .eq("planet_asset_id", planet_asset_id)\
            .eq("building_type", building_type)\
            .execute()

        if existing.data:
            log_event(f"El edificio {definition['name']} ya existe en este planeta.", player_id)
            return None

        # Obtener el tick actual
        from data.world_repository import get_world_state
        world_state = get_world_state()
        current_tick = world_state.get("current_tick", 1)

        # Crear edificio
        building_data = {
            "planet_asset_id": planet_asset_id,
            "player_id": player_id,
            "building_type": building_type,
            "building_tier": tier,
            "is_active": True,
            "pops_required": definition.get("pops_required", 0),
            "energy_consumption": definition.get("energy_cost", 0),
            "built_at_tick": current_tick
        }

        response = db.table("planet_buildings").insert(building_data).execute()

        if response.data:
            log_event(f"Edificio construido: {definition['name']}", player_id)
            return response.data[0]
        return None

    except Exception as e:
        log_event(f"Error construyendo edificio: {e}", player_id, is_error=True)
        return None


def demolish_building(building_id: int, player_id: int) -> bool:
    """
    Destruye un edificio permanentemente.

    Args:
        building_id: ID del edificio
        player_id: ID del jugador (para log)

    Returns:
        True si se demolió correctamente
    """
    try:
        _get_db().table("planet_buildings").delete().eq("id", building_id).execute()
        log_event(f"Edificio ID {building_id} demolido.", player_id)
        return True
    except Exception as e:
        log_event(f"Error demoliendo edificio: {e}", player_id, is_error=True)
        return False


def toggle_building_status(building_id: int, is_active: bool) -> bool:
    """
    Activa o desactiva un edificio manualmente.

    Args:
        building_id: ID del edificio
        is_active: Estado deseado

    Returns:
        True si se actualizó correctamente
    """
    try:
        _get_db().table("planet_buildings").update({
            "is_active": is_active
        }).eq("id", building_id).execute()
        return True
    except Exception as e:
        log_event(f"Error cambiando estado de edificio: {e}", is_error=True)
        return False


def batch_update_building_status(updates: List[Tuple[int, bool]]) -> Tuple[int, int]:
    """
    Actualiza el estado de múltiples edificios en batch.

    Args:
        updates: Lista de tuplas (building_id, is_active)

    Returns:
        Tupla (cantidad exitosa, cantidad fallida)
    """
    if not updates:
        return (0, 0)

    success = 0
    failed = 0
    db = _get_db()

    for building_id, is_active in updates:
        try:
            db.table("planet_buildings").update({
                "is_active": is_active
            }).eq("id", building_id).execute()
            success += 1
        except Exception:
            failed += 1

    return (success, failed)


# --- GESTIÓN DE RECURSOS DE LUJO ---

def get_luxury_extraction_sites_for_player(player_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene todos los sitios de extracción de lujo de un jugador.

    Args:
        player_id: ID del jugador

    Returns:
        Lista de sitios de extracción activos
    """
    try:
        response = _get_db().table("luxury_extraction_sites")\
            .select("*")\
            .eq("player_id", player_id)\
            .eq("is_active", True)\
            .execute()

        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo sitios de extracción: {e}", player_id, is_error=True)
        return []


def create_luxury_extraction_site(
    planet_asset_id: int,
    player_id: int,
    resource_key: str,
    resource_category: str,
    extraction_rate: int = 1,
    pops_required: int = 500
) -> Optional[Dict[str, Any]]:
    """
    Crea un sitio de extracción de recursos de lujo.

    Args:
        planet_asset_id: ID del activo planetario
        player_id: ID del jugador
        resource_key: Clave del recurso (ej: "superconductores")
        resource_category: Categoría (ej: "materiales_avanzados")
        extraction_rate: Unidades extraídas por turno
        pops_required: POPs necesarios para operar

    Returns:
        Datos del sitio creado o None si falla
    """
    try:
        db = _get_db()

        # Verificar si ya existe
        existing = db.table("luxury_extraction_sites")\
            .select("id")\
            .eq("planet_asset_id", planet_asset_id)\
            .eq("resource_key", resource_key)\
            .execute()

        if existing.data:
            log_event(f"Ya existe un sitio de extracción de {resource_key} en este planeta.", player_id)
            return None

        site_data = {
            "planet_asset_id": planet_asset_id,
            "player_id": player_id,
            "resource_key": resource_key,
            "resource_category": resource_category,
            "extraction_rate": extraction_rate,
            "is_active": True,
            "pops_required": pops_required
        }

        response = db.table("luxury_extraction_sites").insert(site_data).execute()

        if response.data:
            log_event(f"Sitio de extracción creado: {resource_key}", player_id)
            return response.data[0]
        return None

    except Exception as e:
        log_event(f"Error creando sitio de extracción: {e}", player_id, is_error=True)
        return None


def get_luxury_extraction_sites(planet_asset_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene todos los sitios de extracción de lujo de un planeta.

    Args:
        planet_asset_id: ID del activo planetario

    Returns:
        Lista de sitios de extracción
    """
    try:
        response = _get_db().table("luxury_extraction_sites")\
            .select("*")\
            .eq("planet_asset_id", planet_asset_id)\
            .execute()

        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo sitios de extracción: {e}", is_error=True)
        return []


def decommission_luxury_site(site_id: int, player_id: int) -> bool:
    """
    Desactiva un sitio de extracción de recursos de lujo.

    Args:
        site_id: ID del sitio
        player_id: ID del jugador (para log)

    Returns:
        True si se desactivó correctamente
    """
    try:
        _get_db().table("luxury_extraction_sites").delete().eq("id", site_id).execute()
        log_event(f"Sitio de extracción desmantelado.", player_id)
        return True
    except Exception as e:
        log_event(f"Error desmantelando sitio: {e}", player_id, is_error=True)
        return False
