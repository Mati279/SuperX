# data/planets/core.py
"""
Consultas básicas de planetas (tabla mundial 'planets').
Hotfix v7.8.1: Estrategia Fail-Safe para resolución de nombres de soberanía.
Actualizado v8.1.0: Robustez en resolución de nombres (Fail-Safe Desconocido).
"""

from typing import Dict, List, Any, Optional
import traceback

from ..database import get_supabase
from ..log_repository import log_event


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


def get_planet_by_id(planet_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene información de un planeta de la tabla mundial 'planets'.
    Actualizado V7.8.1: Implementación ROBUSTA (Fail-Safe).
    Recupera datos crudos primero y resuelve nombres en query separada para evitar fallos de JOIN.
    Actualizado V7.9.0: Uso de 'faccion_nombre' directo de la tabla players.
    Actualizado V8.1.0: Resolución estricta de 'Desconocido' si falla el nombre.
    """
    try:
        db = _get_db()

        # 1. Recuperación Segura de Datos Base
        # Volvemos a 'select(*)' para garantizar que no falle por sintaxis de embedding
        response = db.table("planets").select("*").eq("id", planet_id).single().execute()

        if not response or not response.data:
            return None

        planet_data = response.data

        # 2. Resolución de Nombres de Soberanía (Query Auxiliar)
        # Valores por defecto iniciales (se sobrescriben si hay ID válido)
        planet_data["surface_owner_name"] = "Neutral"
        planet_data["orbital_owner_name"] = "Neutral"

        s_id = planet_data.get("surface_owner_id")
        o_id = planet_data.get("orbital_owner_id")

        # Recopilar IDs únicos para consultar
        ids_to_fetch = []
        if s_id: ids_to_fetch.append(s_id)
        if o_id: ids_to_fetch.append(o_id)

        if ids_to_fetch:
            # Consultamos la tabla de jugadores y facciones de forma segura
            try:
                # Nota: Ahora usamos 'faccion_nombre' directo de la tabla players
                players_res = db.table("players")\
                    .select("id, faccion_nombre")\
                    .in_("id", ids_to_fetch)\
                    .execute()

                if players_res and players_res.data:
                    # Crear mapa {player_id: faccion_nombre}
                    player_faction_map = {}
                    for p in players_res.data:
                        # Obtenemos el nombre directo
                        f_name = p.get("faccion_nombre")

                        # V8.1: Validación estricta. Si es None o string vacío, asignar "Desconocido".
                        if not f_name or str(f_name).strip() == "":
                            f_name = "Desconocido"

                        player_faction_map[p["id"]] = f_name

                    # Asignar nombres al objeto planeta usando el mapa
                    # Si el ID existe en el mapa, usa el nombre. Si no (ej. usuario borrado), usa "Desconocido".
                    if s_id:
                        planet_data["surface_owner_name"] = player_faction_map.get(s_id, "Desconocido")
                    if o_id:
                        planet_data["orbital_owner_name"] = player_faction_map.get(o_id, "Desconocido")
                else:
                    # Si la query no devuelve nada pero había IDs (caso raro de fallo total), asignar Desconocido
                    if s_id: planet_data["surface_owner_name"] = "Desconocido"
                    if o_id: planet_data["orbital_owner_name"] = "Desconocido"

            except Exception as e:
                # Si falla la resolución de nombres, NO bloqueamos la carga del planeta
                print(f"Warning: Fallo resolución de nombres soberanía: {e}")
                # Mantenemos los valores por defecto o IDs como fallback visual
                if s_id and planet_data["surface_owner_name"] == "Neutral":
                    planet_data["surface_owner_name"] = "Desconocido"
                if o_id and planet_data["orbital_owner_name"] == "Neutral":
                    planet_data["orbital_owner_name"] = "Desconocido"

        return planet_data

    except Exception as e:
        # Logueo explícito del error para debug en UI
        import streamlit as st
        st.error(f"Error CRÍTICO cargando planeta {planet_id}: {e}")
        traceback.print_exc()
        return None


def get_all_colonized_system_ids() -> List[int]:
    """Obtiene todos los IDs de sistemas con al menos un planeta colonizado."""
    try:
        response = _get_db().table("planets")\
            .select("system_id")\
            .not_.is_("surface_owner_id", "null")\
            .execute()

        if not response or not response.data:
            return []

        system_ids = list(set([p["system_id"] for p in response.data if p.get("system_id")]))
        return system_ids
    except Exception as e:
        log_event(f"Error obteniendo sistemas colonizados: {e}", is_error=True)
        return []
