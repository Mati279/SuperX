# data/planet_repository.py
from typing import Dict, List, Any, Optional
from data.database import supabase
from data.log_repository import log_event
from core.world_constants import BUILDING_TYPES


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
        response = supabase.table("planet_assets")\
            .select("*")\
            .eq("planet_id", planet_id)\
            .eq("player_id", player_id)\
            .single()\
            .execute()

        return response.data if response.data else None
    except Exception as e:
        log_event(f"Error obteniendo activo planetario: {e}", player_id, is_error=True)
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
        response = supabase.table("planet_assets")\
            .select("*")\
            .eq("player_id", player_id)\
            .execute()

        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo planetas del jugador: {e}", player_id, is_error=True)
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

        response = supabase.table("planet_assets").insert(asset_data).execute()

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
        supabase.table("planet_assets").update(updates).eq("id", planet_asset_id).execute()
        return True
    except Exception as e:
        log_event(f"Error actualizando activo planetario ID {planet_asset_id}: {e}", is_error=True)
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
        response = supabase.table("planet_buildings")\
            .select("*")\
            .eq("planet_asset_id", planet_asset_id)\
            .execute()

        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo edificios del planeta: {e}", is_error=True)
        return []


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
        # Verificar si ya existe el edificio
        existing = supabase.table("planet_buildings")\
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

        response = supabase.table("planet_buildings").insert(building_data).execute()

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
        supabase.table("planet_buildings").delete().eq("id", building_id).execute()
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
        supabase.table("planet_buildings").update({
            "is_active": is_active
        }).eq("id", building_id).execute()
        return True
    except Exception as e:
        log_event(f"Error cambiando estado de edificio: {e}", is_error=True)
        return False


# --- GESTIÓN DE RECURSOS DE LUJO ---

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
        # Verificar si ya existe
        existing = supabase.table("luxury_extraction_sites")\
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

        response = supabase.table("luxury_extraction_sites").insert(site_data).execute()

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
        response = supabase.table("luxury_extraction_sites")\
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
        supabase.table("luxury_extraction_sites").delete().eq("id", site_id).execute()
        log_event(f"Sitio de extracción desmantelado.", player_id)
        return True
    except Exception as e:
        log_event(f"Error desmantelando sitio: {e}", player_id, is_error=True)
        return False
