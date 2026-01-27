# data/planet_repository.py
"""
BARREL DE EXPORTACIÓN - Repositorio de Planetas y Edificios.

Este archivo actúa como proxy de compatibilidad hacia atrás.
Toda la lógica ha sido refactorizada en el paquete 'data.planets'.

Estructura del paquete:
    data/planets/
    ├── __init__.py      # Exportaciones del paquete
    ├── core.py          # Consultas básicas (get_planet_by_id, etc.)
    ├── assets.py        # Gestión de planet_assets
    ├── sectors.py       # Gestión de sectores y Fog of War
    ├── buildings.py     # Construcción y demolición
    ├── sovereignty.py   # Motores de soberanía y seguridad
    └── genesis.py       # Inicialización (Protocolo Génesis)

USO:
    Las importaciones existentes como:
        from data.planet_repository import get_planet_by_id

    Siguen funcionando sin cambios gracias a este barrel.

    Para nuevas importaciones, se recomienda usar el paquete directamente:
        from data.planets import get_planet_by_id
        # O de forma más específica:
        from data.planets.core import get_planet_by_id
"""

# =============================================================================
# RE-EXPORTACIÓN COMPLETA DEL PAQUETE 'planets'
# =============================================================================

# --- CORE: Consultas básicas a la tabla mundial 'planets' ---
from .planets.core import (
    _get_db,
    get_planet_by_id,
    get_all_colonized_system_ids,
)

# --- ASSETS: Gestión de planet_assets (colonización, población) ---
from .planets.assets import (
    get_planet_asset,
    get_planet_asset_by_id,
    get_all_player_planets,
    get_player_base_coordinates,
    get_all_player_planets_with_buildings,
    create_planet_asset,
    update_planet_asset,
    upgrade_base_tier,
    upgrade_infrastructure_module,
    rename_settlement,
    get_base_slots_info,
)

# --- SECTORS: Gestión de sectores y Fog of War ---
from .planets.sectors import (
    get_planet_sectors_status,
    get_sector_by_id,
    get_sector_details,
    grant_sector_knowledge,
    has_urban_sector,
)

# --- BUILDINGS: Construcción y demolición de edificios ---
from .planets.buildings import (
    get_planet_buildings,
    build_structure,
    demolish_building,
    get_luxury_extraction_sites_for_player,
    batch_update_building_status,
)

# --- SOVEREIGNTY: Motores de cálculo de soberanía y seguridad ---
from .planets.sovereignty import (
    update_planet_sovereignty,
    recalculate_system_ownership,
    recalculate_system_security,
    check_system_majority_control,
    batch_update_planet_security,
    update_planet_security_value,
    update_planet_security_data,
)

# --- GENESIS: Funciones de inicialización (Protocolo Génesis) ---
from .planets.genesis import (
    initialize_planet_sectors,
    claim_genesis_sector,
    add_initial_building,
    initialize_player_base,
)

# =============================================================================
# LISTADO EXPLÍCITO DE EXPORTACIONES PÚBLICAS
# =============================================================================

__all__ = [
    # Core
    "_get_db",
    "get_planet_by_id",
    "get_all_colonized_system_ids",
    # Assets
    "get_planet_asset",
    "get_planet_asset_by_id",
    "get_all_player_planets",
    "get_player_base_coordinates",
    "get_all_player_planets_with_buildings",
    "create_planet_asset",
    "update_planet_asset",
    "upgrade_base_tier",
    "upgrade_infrastructure_module",
    "rename_settlement",
    "get_base_slots_info",
    # Sectors
    "get_planet_sectors_status",
    "get_sector_by_id",
    "get_sector_details",
    "grant_sector_knowledge",
    "has_urban_sector",
    # Buildings
    "get_planet_buildings",
    "build_structure",
    "demolish_building",
    "get_luxury_extraction_sites_for_player",
    "batch_update_building_status",
    # Sovereignty
    "update_planet_sovereignty",
    "recalculate_system_ownership",
    "recalculate_system_security",
    "check_system_majority_control",
    "batch_update_planet_security",
    "update_planet_security_value",
    "update_planet_security_data",
    # Genesis
    "initialize_planet_sectors",
    "claim_genesis_sector",
    "add_initial_building",
    "initialize_player_base",
]