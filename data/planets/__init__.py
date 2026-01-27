# data/planets/__init__.py
"""
Paquete de Gestión de Planetas.
Estructura modular para mantener el principio de responsabilidad única.

Módulos:
    - core: Consultas básicas a la tabla mundial 'planets'
    - assets: Gestión de planet_assets (colonización, población)
    - sectors: Gestión de sectores y Fog of War
    - buildings: Construcción y demolición de edificios
    - sovereignty: Motores de cálculo de soberanía y seguridad
    - genesis: Funciones de inicialización (Protocolo Génesis)
"""

# Core
from .core import (
    _get_db,
    get_planet_by_id,
    get_all_colonized_system_ids,
)

# Assets
from .assets import (
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

# Sectors
from .sectors import (
    get_planet_sectors_status,
    get_sector_by_id,
    get_sector_details,
    grant_sector_knowledge,
)

# Buildings
from .buildings import (
    get_planet_buildings,
    build_structure,
    demolish_building,
    get_luxury_extraction_sites_for_player,
    batch_update_building_status,
)

# Sovereignty
from .sovereignty import (
    update_planet_sovereignty,
    recalculate_system_ownership,
    recalculate_system_security,
    check_system_majority_control,
    batch_update_planet_security,
    update_planet_security_value,
    update_planet_security_data,
)

# Genesis
from .genesis import (
    initialize_planet_sectors,
    claim_genesis_sector,
    add_initial_building,
    initialize_player_base,
)

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
