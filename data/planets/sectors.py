# data/planets/sectors.py
"""
Gestión de Sectores Planetarios.
Incluye consultas de estado, conocimiento de jugador y Fog of War.
Actualizado v7.2: Soporte para Niebla de Superficie (grant_sector_knowledge).
Actualizado v10.3: Helper get_sector_by_id para exploración táctica.
Actualizado v11.2: Conteo de slots de base en get_planet_sectors_status.
Refactor v12.0: Validación estricta de slots ocupados por bases militares.
"""

from typing import Dict, List, Any, Optional

from ..log_repository import log_event
from core.world_constants import (
    BUILDING_TYPES,
    SECTOR_TYPE_ORBITAL,
)

from .core import _get_db


def get_planet_sectors_status(planet_id: int, player_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Consulta el estado actual de los sectores de un planeta, calculando ocupación dinámica.
    V7.2: Soporta filtrado por conocimiento de jugador (is_explored_by_player).
    V10.2: Añadido campo 'is_discovered' para Fog of War.
    V11.2: Incluye 'bases' en el conteo de slots ocupados.
    """
    try:
        db = _get_db()
        # 1. Obtener Sectores
        response = db.table("sectors")\
            .select("id, sector_type, max_slots, resource_category, is_known, luxury_resource")\
            .eq("planet_id", planet_id)\
            .execute()

        sectors = response.data if response and response.data else []
        if not sectors: return []

        sector_ids = [s["id"] for s in sectors]
        counts = {}

        # 2a. Contar edificios estándar (Filtrando consumo de slots)
        b_response = db.table("planet_buildings")\
            .select("sector_id, building_type")\
            .in_("sector_id", sector_ids)\
            .execute()

        buildings = b_response.data if b_response and b_response.data else []
        for b in buildings:
            sid = b.get("sector_id")
            bt = b.get("building_type")
            # Verificar si el tipo de edificio consume slot
            if sid and BUILDING_TYPES.get(bt, {}).get("consumes_slots", True):
                counts[sid] = counts.get(sid, 0) + 1

        # 2b. Contar Bases Militares (Siempre ocupan slot en su sector)
        # NOTA: Las bases se almacenan en tabla 'bases', no en 'planet_buildings'.
        base_response = db.table("bases")\
            .select("sector_id")\
            .eq("planet_id", planet_id)\
            .execute()

        bases = base_response.data if base_response and base_response.data else []
        for base in bases:
            sid = base.get("sector_id")
            if sid:
                # La base militar ocupa 1 slot físico
                counts[sid] = counts.get(sid, 0) + 1

        # 3. Validar conocimiento del jugador
        known_sector_ids = set()
        if player_id:
            try:
                k_res = db.table("player_sector_knowledge")\
                    .select("sector_id")\
                    .eq("player_id", player_id)\
                    .in_("sector_id", sector_ids)\
                    .execute()
                if k_res and k_res.data:
                    known_sector_ids = {row["sector_id"] for row in k_res.data}
            except Exception:
                pass

        # 4. Mapear resultados
        for s in sectors:
            s['slots'] = s.get('max_slots', 2)
            # El conteo ya incluye Edificios + Bases
            s['buildings_count'] = counts.get(s["id"], 0)

            is_orbital = s.get("sector_type") == SECTOR_TYPE_ORBITAL
            is_in_knowledge_table = s["id"] in known_sector_ids

            s['is_discovered'] = is_orbital or is_in_knowledge_table
            s['is_explored_by_player'] = s['is_discovered']

        return sectors
    except Exception:
        return []


def get_sector_by_id(sector_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene los datos de un sector por ID.
    Incluye join con planets para obtener el nombre del planeta (necesario para exploración).
    """
    try:
        response = _get_db().table("sectors")\
            .select("*, planets(name)")\
            .eq("id", sector_id)\
            .maybe_single()\
            .execute()
        return response.data if response and response.data else None
    except Exception as e:
        log_event(f"Error obteniendo sector {sector_id}: {e}", is_error=True)
        return None


def get_sector_details(sector_id: int) -> Optional[Dict[str, Any]]:
    """Retorna información detallada de un sector y sus edificios."""
    try:
        db = _get_db()
        response = db.table("sectors").select("*").eq("id", sector_id).single().execute()
        if not response or not response.data: return None

        sector = response.data
        if 'max_slots' in sector:
            sector['slots'] = sector['max_slots']

        buildings_res = db.table("planet_buildings")\
            .select("building_type, building_tier")\
            .eq("sector_id", sector_id)\
            .execute()

        names = []
        if buildings_res and buildings_res.data:
            for b in buildings_res.data:
                name = BUILDING_TYPES.get(b["building_type"], {}).get("name", "Estructura")
                names.append(f"{name} (T{b['building_tier']})")

        # Incluir Base Militar si existe en el sector
        base_res = db.table("bases").select("tier, name").eq("sector_id", sector_id).maybe_single().execute()
        if base_res and base_res.data:
            base_name = base_res.data.get("name") or "Base Militar"
            names.append(f"{base_name} (T{base_res.data['tier']})")

        sector["buildings_list"] = names
        return sector
    except Exception:
        return None


def grant_sector_knowledge(player_id: int, sector_id: int) -> bool:
    """Registra que un jugador ha explorado un sector específico."""
    try:
        _get_db().table("player_sector_knowledge").upsert(
            {"player_id": player_id, "sector_id": sector_id},
            on_conflict="player_id, sector_id"
        ).execute()
        return True
    except Exception as e:
        log_event(f"Error otorgando conocimiento de sector {sector_id}: {e}", player_id, is_error=True)
        return False