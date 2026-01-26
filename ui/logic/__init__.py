# ui/logic/__init__.py
"""Módulo de lógica de negocio para la UI."""

from ui.logic.roster_logic import (
    get_prop,
    set_prop,
    sort_key_by_prop,
    get_assigned_entity_ids,
    hydrate_unit_members,
    get_systems_with_presence,
    build_location_index,
    calculate_unit_display_capacity,
    get_leader_capacity,
    BASE_CAPACITY,
    MAX_CAPACITY,
)

__all__ = [
    "get_prop",
    "set_prop",
    "sort_key_by_prop",
    "get_assigned_entity_ids",
    "hydrate_unit_members",
    "get_systems_with_presence",
    "build_location_index",
    "calculate_unit_display_capacity",
    "get_leader_capacity",
    "BASE_CAPACITY",
    "MAX_CAPACITY",
]
