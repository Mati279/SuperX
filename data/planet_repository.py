# data/planet_repository.py (Completo)
"""
Repositorio de Planetas y Edificios.
Gestiona activos planetarios, edificios, recursos y mejoras de base.
Refactorizado para MMFR V2: Seguridad dinámica (0-100) y Mantenimiento.
Actualizado v4.3.0: Integración completa de Planetología Avanzada (Sectores).
Actualizado v4.4.0: Persistencia de Seguridad Galáctica.
Corrección v4.4.1: Consultas seguras (maybe_single) para assets opcionales.
Actualizado v4.7.0: Estandarización de Capitales (Población Inicial).
Actualizado v4.8.1: Eliminación definitiva de 'security_breakdown' para sincronización con DB.
Refactorizado v5.3: Limpieza de redundancia 'slots' en Planeta.
Corrección v5.4: Protecciones robustas contra respuestas 'NoneType' de Supabase.
Corrección v5.5: Persistencia de 'poblacion' en tabla global 'planets'.
Corrección v5.6: Join con tabla 'planets' para obtener seguridad real.
Refactor v5.7: Estandarización de nomenclatura 'population' (Fix poblacion).
Refactor v5.8: Limpieza integral de consultas y campos expandidos.
Corrección v5.9: Fix columna 'sector_type' en tabla sectors.
Refactor v6.0: Eliminación de columna redundante 'buildings_count' en sectors (Cálculo dinámico).
Corrección v6.1: Fix crítico de tipos en seguridad (soporte Dict/Float) y persistencia de breakdown.
Corrección v6.2: Mapeo explícito de 'population' en assets para el motor económico.
Actualizado v6.3: Implementación de Soberanía Dinámica y Control de Construcción (Slots/Bloqueos).
Actualizado v7.2: Soporte para Niebla de Superficie (grant_sector_knowledge).
Actualizado v7.3: Inicialización garantizada de Sectores Urbanos para Protocolo Génesis.
Actualizado v7.4: Nueva función add_initial_building() para edificio inicial en Génesis.
                  Fix claim_genesis_sector: Eliminadas columnas inexistentes (owner_id, has_outpost).
                  initialize_planet_sectors ahora retorna List[Dict] con sectores creados/existentes.
Actualizado v7.4.1: Fix de integridad en initialize_planet_sectors para inyectar sector Urbano si falta.
Actualizado v7.5.0: Implementación de Sector Orbital y Lógica de Soberanía Espacial (V6.4 Specs).
Actualizado v7.5.1: Fix Soberanía Inicial (Sincronización Orbital en Creación).
Actualizado v7.6.0: Fix Crítico de IDs y Transformación de Sectores en initialize_planet_sectors.
Actualizado v7.6.1: Fix Crítico SQL en initialize_planet_sectors (sync planet_id) y limpieza de retorno.
Actualizado v7.7.1: Restauración de updates secuenciales en create_planet_asset para evitar Race Condition con Triggers.
Actualizado v7.7.2: Fix PGRST204 delegando 'base_tier' al default de la base de datos.
Actualizado v7.8.0: Join con Facciones para resolver nombres de Soberanía (Surface/Orbital) en get_planet_by_id.
Hotfix v7.8.1: Estrategia Fail-Safe para get_planet_by_id (Recuperación en 2 pasos) para evitar errores de sintaxis PostgREST.
Actualizado v7.9.0: Cambio de fuente de nombre de facción a 'players.faccion_nombre'.
Actualizado v8.1.0: Robustez en resolución de nombres de soberanía (Fail-Safe Desconocido).
Actualizado v8.2.0: Fix build_structure (Ghost Buildings Check & ID types).
Actualizado v8.2.1: Fix Not-Null Constraint (Inyección de pops_required y energy_consumption).
Actualizado v8.3.0: Business Logic para HQ Único (Reemplazo de Constraint DB).
Actualizado v9.1.0: Implementación de Seguridad de Sistema (Recálculo automático en cascada).
Actualizado v9.2.0: Reglas de Soberanía Conflictiva y Excepción de Construcción Orbital (Bypass de Flota).
Actualizado v10.0: Helper get_player_base_coordinates para Ubicación SQL.
Actualizado v10.3: Helper get_sector_by_id para exploración táctica.
Actualizado v10.4: Soberanía Diferida (Filtro por built_at_tick).
Refactor v11.0: INTEGRACIÓN DE SISTEMA DE BASES MILITARES (Tabla 'bases').
Refactor v11.2: INTEGRACIÓN UI VISUAL DE BASES.
                - get_all_player_planets_with_buildings: Inyección de base como edificio virtual.
                - get_planet_buildings: Inyección de base como edificio virtual.
                - get_planet_sectors_status: Conteo de slots de base.
                - initialize_player_base: Fix niveles iniciales (1).
"""

from typing import Dict, List, Any, Optional, Tuple
import random 
import traceback # Importado para debug crítico
from .database import get_supabase
from .log_repository import log_event
from .world_repository import get_world_state, update_system_controller, update_system_security
from core.world_constants import (
    BUILDING_TYPES, 
    BASE_TIER_COSTS, 
    ECONOMY_RATES, 
    PLANET_MASS_CLASSES,
    SECTOR_SLOTS_CONFIG,
    SECTOR_TYPE_URBAN,
    SECTOR_TYPE_PLAIN,
    SECTOR_TYPE_MOUNTAIN,
    SECTOR_TYPE_INHOSPITABLE,
    SECTOR_TYPE_ORBITAL
)
from core.rules import calculate_planet_security


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


# --- CONSULTA DE PLANETAS (TABLA MUNDIAL) ---

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


# --- GESTIÓN DE ACTIVOS PLANETARIOS ---

def get_planet_asset(planet_id: int, player_id: int) -> Optional[Dict[str, Any]]:
    try:
        response = _get_db().table("planet_assets")\
            .select("*")\
            .eq("planet_id", planet_id)\
            .eq("player_id", player_id)\
            .maybe_single()\
            .execute()
        return response.data if response and response.data else None
    except Exception as e:
        log_event(f"Error obteniendo activo planetario: {e}", player_id, is_error=True)
        return None


def get_planet_asset_by_id(planet_asset_id: int) -> Optional[Dict[str, Any]]:
    try:
        response = _get_db().table("planet_assets")\
            .select("*")\
            .eq("id", planet_asset_id)\
            .single()\
            .execute()
        return response.data if response and response.data else None
    except Exception:
        return None


def get_all_player_planets(player_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene todos los activos planetarios del jugador.
    Fix V5.6: JOIN con 'planets' para obtener 'security' (Source of Truth).
    Refactor V5.7: Actualizado a 'population'.
    """
    try:
        response = _get_db().table("planet_assets")\
            .select("*, planets(security, population, system_id, name)")\
            .eq("player_id", player_id)\
            .execute()
        return response.data if response and response.data else []
    except Exception as e:
        log_event(f"Error obteniendo planetas del jugador: {e}", player_id, is_error=True)
        return []


def get_player_base_coordinates(player_id: int) -> Dict[str, Any]:
    """
    Obtiene las coordenadas (System, Planet, Sector) de la base principal del jugador.
    Prioriza el Sector Urbano del primer planeta colonizado.
    Helper para la refactorización de ubicación (V10).
    """
    coords = {
        "system_id": None,
        "planet_id": None,
        "sector_id": None,
        "nombre_asentamiento": None
    }
    
    try:
        # 1. Obtener activos del jugador (Asumimos el primero como base principal)
        assets = get_all_player_planets(player_id)
        if not assets:
            return coords
            
        base_asset = assets[0]
        planet_id = base_asset.get("planet_id")
        
        # Extraer datos del activo y del planeta (JOIN)
        coords["planet_id"] = planet_id
        coords["nombre_asentamiento"] = base_asset.get("nombre_asentamiento", "Base Principal")
        
        # Datos del sistema (desde el join con planets o directo)
        planet_data = base_asset.get("planets", {})
        coords["system_id"] = planet_data.get("system_id") or base_asset.get("system_id")
        
        # 2. Buscar Sector Urbano para spawn preciso
        if planet_id:
            db = _get_db()
            sector_res = db.table("sectors")\
                .select("id")\
                .eq("planet_id", planet_id)\
                .eq("sector_type", SECTOR_TYPE_URBAN)\
                .maybe_single()\
                .execute()
                
            if sector_res and sector_res.data:
                coords["sector_id"] = sector_res.data.get("id")
            else:
                # Fallback: Cualquier sector del planeta
                fallback = db.table("sectors").select("id").eq("planet_id", planet_id).limit(1).execute()
                if fallback and fallback.data:
                    coords["sector_id"] = fallback.data[0].get("id")

        return coords

    except Exception as e:
        log_event(f"Error obteniendo coordenadas base: {e}", player_id, is_error=True)
        return coords


def get_all_player_planets_with_buildings(player_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene planetas del jugador con edificios y datos de sectores precargados.
    Refactor V5.7: Actualizado a 'population'.
    Fix V5.9: Corrección de nombre de columna 'sector_type'.
    Refactor V6.0: Cálculo dinámico de 'buildings_count'.
    Actualizado V11.2: Fusión de 'planet_buildings' y 'bases' para la UI.
    """
    try:
        db = _get_db()
        planets_response = db.table("planet_assets")\
            .select("*, planets(orbital_owner_id, surface_owner_id, is_disputed, biome, security, population)")\
            .eq("player_id", player_id)\
            .execute()

        if not planets_response or not planets_response.data:
            return []
            
        assets = planets_response.data
        planet_ids = [a["planet_id"] for a in assets]
        asset_ids = [a["id"] for a in assets]

        # 1. Obtener Edificios Estándar
        buildings_response = db.table("planet_buildings")\
            .select("*")\
            .in_("planet_asset_id", asset_ids)\
            .execute()
        buildings = buildings_response.data if buildings_response and buildings_response.data else []

        # 2. Obtener Bases Militares (Tabla 'bases')
        bases_response = db.table("bases")\
            .select("*")\
            .eq("player_id", player_id)\
            .execute()
        bases = bases_response.data if bases_response and bases_response.data else []

        # 3. Obtener Sectores
        sectors_response = db.table("sectors")\
            .select("id, sector_type, planet_id, max_slots, resource_category, is_known")\
            .in_("planet_id", planet_ids)\
            .execute()
        sectors_data = sectors_response.data if sectors_response and sectors_response.data else []
        
        # Mapa de sectores para acceso rápido
        sector_map = {}
        for s in sectors_data:
            if 'slots' not in s and 'max_slots' in s:
                s['slots'] = s['max_slots']
            s['buildings_count'] = 0 # Inicializar contador dinámico
            sector_map[s["id"]] = s
        
        buildings_by_asset: Dict[int, List[Dict]] = {}
        
        # A. Procesar Edificios Estándar
        for building in buildings:
            aid = building["planet_asset_id"]
            if aid not in buildings_by_asset: buildings_by_asset[aid] = []
            
            sec_id = building.get("sector_id")
            sector = sector_map.get(sec_id)
            
            # Asignar info del sector y actualizar contador
            building["sector_type"] = sector.get("sector_type") if sector else "Desconocido"
            building["sector_info"] = sector
            
            # Consumo Dinámico de Slots
            b_type = building.get("building_type")
            consumes_slots = BUILDING_TYPES.get(b_type, {}).get("consumes_slots", True)
            
            if sector and consumes_slots:
                sector['buildings_count'] += 1
            
            buildings_by_asset[aid].append(building)

        # B. Procesar Bases Militares (Inyección Virtual)
        # Necesitamos mapear planet_id -> asset_id
        asset_map_by_planet = {a["planet_id"]: a["id"] for a in assets}

        for base in bases:
            p_id = base.get("planet_id")
            target_asset_id = asset_map_by_planet.get(p_id)
            
            if target_asset_id:
                if target_asset_id not in buildings_by_asset: buildings_by_asset[target_asset_id] = []

                # Crear el objeto edificio virtual para la UI
                virtual_base = {
                    "id": base["id"], # ID de la tabla bases (único)
                    "building_type": "military_base", # Tipo especial para UI
                    "building_tier": base.get("tier", 1),
                    "sector_id": base["sector_id"],
                    "planet_asset_id": target_asset_id,
                    "is_active": True,
                    "built_at_tick": base.get("created_at_tick", 0),
                    "is_virtual": True # Flag opcional para depuración
                }
                
                sec_id = base.get("sector_id")
                sector = sector_map.get(sec_id)
                virtual_base["sector_type"] = sector.get("sector_type") if sector else "Urbano"
                virtual_base["sector_info"] = sector
                
                # La base SIEMPRE consume slot
                if sector:
                    sector['buildings_count'] += 1
                
                buildings_by_asset[target_asset_id].append(virtual_base)

        for asset in assets:
            planet_data = asset.get("planets", {})
            asset["orbital_owner_id"] = planet_data.get("orbital_owner_id")
            asset["surface_owner_id"] = planet_data.get("surface_owner_id")
            asset["is_disputed"] = planet_data.get("is_disputed", False)
            asset["biome"] = planet_data.get("biome", "Desconocido")
            
            # FIX V6.2: Mapeo explícito de population para el motor económico
            asset["population"] = planet_data.get("population", 0.0)
            
            if "security" in planet_data: asset["security_from_planet"] = planet_data["security"]

            asset["buildings"] = buildings_by_asset.get(asset["id"], [])
            asset["sectors"] = [s for s in sectors_data if s["planet_id"] == asset["planet_id"]]

        return assets
    except Exception as e:
        log_event(f"Error obteniendo planetas full data: {e}", player_id, is_error=True)
        return []


def create_planet_asset(
    planet_id: int,
    system_id: int,
    player_id: int,
    settlement_name: str = "Colonia Principal",
    initial_population: float = 1.0 
) -> Optional[Dict[str, Any]]:
    """Crea una colonia con seguridad inicial basada en población."""
    try:
        db = _get_db()
        existing_assets = get_all_player_planets(player_id)
        if not existing_assets:
            if initial_population == 1.0: 
                initial_population = random.uniform(1.5, 1.7)

        # --- FIX SEGURIDAD (V5.9) ---
        planet_data = get_planet_by_id(planet_id)
        
        initial_security = 20.0 
        if planet_data:
            base_def = planet_data.get("base_defense", 10) or 10
            ring = planet_data.get("orbital_ring", 3) or 3
            
            initial_security = calculate_planet_security(
                base_stat=base_def,
                pop_count=initial_population,
                infrastructure_defense=0,
                orbital_ring=ring,
                is_player_owned=True 
            )

        asset_data = {
            "planet_id": planet_id,
            "system_id": system_id,
            "player_id": player_id,
            "nombre_asentamiento": settlement_name,
            "population": initial_population,
            "pops_activos": initial_population,
            "pops_desempleados": 0.0,
            "infraestructura_defensiva": 0
        }
        
        response = db.table("planet_assets").insert(asset_data).execute()
        
        if response and response.data:
            # --- FIX CRÍTICO V6.1: Soporte dual para Float/Dict en Security ---
            sec_value = initial_security
            sec_breakdown = {}
            
            if isinstance(initial_security, dict):
                sec_value = initial_security.get("total", 20.0)
                sec_breakdown = initial_security
            
            # Paso 1: Asignar Dueños y Población
            db.table("planets").update({
                "surface_owner_id": player_id,
                "orbital_owner_id": player_id, 
                "population": initial_population
            }).eq("id", planet_id).execute()
            
            # Paso 2: Asignar Seguridad Calculada 
            db.table("planets").update({
                "security": sec_value,
                "security_breakdown": sec_breakdown
            }).eq("id", planet_id).execute()
            
            # --- FAIL-SAFE DE SECTORES (V5.9) ---
            sectors_check = db.table("sectors").select("id").eq("planet_id", planet_id).execute()
            if not sectors_check.data:
                emergency_sector = {
                    "id": (planet_id * 1000) + 1,
                    "planet_id": planet_id,
                    "name": "Sector Urbano (Emergencia)",
                    "sector_type": SECTOR_TYPE_URBAN, 
                    "max_slots": 5,
                    "is_known": True
                }
                db.table("sectors").insert(emergency_sector).execute()
                log_event(f"Sector de emergencia creado para {planet_id}", player_id, is_error=True)

            log_event(f"Planeta colonizado: {settlement_name} (Seguridad inicial: {sec_value:.1f})", player_id)
            
            recalculate_system_security(system_id)
            
            return response.data[0]
        return None
    except Exception as e:
        print("\n💥 CRITICAL ERROR IN CREATE_PLANET_ASSET:")
        traceback.print_exc()
        log_event(f"Error creando activo planetario: {e}", player_id, is_error=True)
        return None


# --- GESTIÓN DE BASE Y SECTORES ---

def get_base_slots_info(planet_asset_id: int) -> Dict[str, int]:
    """Calcula slots totales sumando los de todos los sectores del planeta."""
    try:
        db = _get_db()
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return {"total": 0, "used": 0, "free": 0}
        
        planet_id = asset.get("planet_id")
        total_slots = 0
        try:
            sectors_res = db.table("sectors").select("max_slots").eq("planet_id", planet_id).execute()
            if sectors_res and sectors_res.data:
                total_slots = sum(s["max_slots"] for s in sectors_res.data)
        except:
            sectors_res = db.table("sectors").select("slots").eq("planet_id", planet_id).execute()
            if sectors_res and sectors_res.data:
                total_slots = sum(s["slots"] for s in sectors_res.data)
        
        # 1. Contar edificios estándar
        buildings_res = db.table("planet_buildings")\
            .select("id, building_type")\
            .eq("planet_asset_id", planet_asset_id)\
            .execute()
        
        used = 0
        if buildings_res and buildings_res.data:
            for b in buildings_res.data:
                bt = b.get("building_type")
                if BUILDING_TYPES.get(bt, {}).get("consumes_slots", True):
                    used += 1
        
        # 2. Contar Bases Militares (Siempre usan slot)
        bases_res = db.table("bases").select("id").eq("planet_id", planet_id).execute()
        if bases_res and bases_res.data:
            used += len(bases_res.data)
        
        return {"total": total_slots, "used": used, "free": max(0, total_slots - used)}
    except Exception as e:
        log_event(f"Error calculando slots por sectores: {e}", is_error=True)
        return {"total": 0, "used": 0, "free": 0}


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
            if sid and BUILDING_TYPES.get(bt, {}).get("consumes_slots", True):
                counts[sid] = counts.get(sid, 0) + 1

        # 2b. Contar Bases Militares (Siempre ocupan slot en su sector)
        base_response = db.table("bases")\
            .select("sector_id")\
            .eq("planet_id", planet_id)\
            .execute()
            
        bases = base_response.data if base_response and base_response.data else []
        for base in bases:
            sid = base.get("sector_id")
            if sid:
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
        base_res = db.table("bases").select("tier").eq("sector_id", sector_id).maybe_single().execute()
        if base_res and base_res.data:
            names.append(f"Base Militar (T{base_res.data['tier']})")
        
        sector["buildings_list"] = names
        return sector
    except Exception:
        return None

# --- V7.2: GESTIÓN DE NIEBLA DE SUPERFICIE ---

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


def upgrade_base_tier(planet_asset_id: int, player_id: int) -> bool:
    try:
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return False
        current_tier = asset.get('base_tier', 1)
        if current_tier >= 4: return False 
        
        response = _get_db().table("planet_assets").update({
            "base_tier": current_tier + 1
        }).eq("id", planet_asset_id).execute()
        
        if response:
            log_event(f"Base Principal mejorada a Tier {current_tier + 1}", player_id)
            return True
        return False
    except Exception as e:
        log_event(f"Error upgrade base: {e}", player_id, is_error=True)
        return False


def upgrade_infrastructure_module(planet_asset_id: int, module_key: str, player_id: int) -> str:
    try:
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return "Asset no encontrado"
        
        base_tier = asset.get('base_tier', 1)
        current_level = asset.get(f"module_{module_key}", 0)
        
        max_allowed = base_tier + 1
        if current_level >= max_allowed:
            return f"Límite Tecnológico. Mejora la Base a Tier {base_tier + 1}."
            
        response = _get_db().table("planet_assets").update({
            f"module_{module_key}": current_level + 1
        }).eq("id", planet_asset_id).execute()
        
        if response:
            log_event(f"Módulo {module_key} mejorado a nivel {current_level + 1}", player_id)
            return "OK"
        return "Error en la base de datos"
    except Exception as e:
        log_event(f"Error upgrade module: {e}", player_id, is_error=True)
        return f"Error: {e}"


# --- GESTIÓN DE EDIFICIOS ---

def get_planet_buildings(planet_asset_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene los edificios de un asset planetario.
    Actualizado V11.2: Inyecta 'bases' como edificios virtuales de tipo 'military_base'.
    """
    try:
        db = _get_db()
        
        # 1. Edificios Estándar
        response = db.table("planet_buildings")\
            .select("*")\
            .eq("planet_asset_id", planet_asset_id)\
            .execute()
        
        buildings = response.data if response and response.data else []
        
        # 2. Inyectar Bases Militares
        asset = get_planet_asset_by_id(planet_asset_id)
        if asset:
            planet_id = asset["planet_id"]
            player_id = asset["player_id"]
            
            bases_res = db.table("bases")\
                .select("*")\
                .eq("planet_id", planet_id)\
                .eq("player_id", player_id)\
                .execute()
            
            if bases_res and bases_res.data:
                for base in bases_res.data:
                    virtual_base = {
                        "id": base["id"], 
                        "building_type": "military_base", 
                        "building_tier": base.get("tier", 1),
                        "sector_id": base["sector_id"],
                        "planet_asset_id": planet_asset_id,
                        "is_active": True,
                        "built_at_tick": base.get("created_at_tick", 0),
                        "is_virtual": True
                    }
                    buildings.append(virtual_base)
                    
        return buildings
    except Exception as e:
        log_event(f"Error obteniendo edificios: {e}", is_error=True)
        return []

# --- V6.3 y V6.4: GESTIÓN DE SOBERANÍA Y CONSTRUCCIÓN ---

def update_planet_sovereignty(planet_id: int, enemy_fleet_owner_id: Optional[int] = None):
    """
    Recalcula y actualiza la soberanía de superficie y orbital.

    Refactor V11.0: Integración de tabla 'bases'.
    """
    try:
        db = _get_db()

        # 0. Obtener info del planeta
        planet_info_res = db.table("planets").select("system_id, population").eq("id", planet_id).single().execute()
        if not planet_info_res or not planet_info_res.data:
            return
            
        system_id = planet_info_res.data.get("system_id")
        population = planet_info_res.data.get("population", 0.0)

        # 1. Obtener Bases Militares (Nueva Lógica de Soberanía Civil/Militar)
        bases_res = db.table("bases")\
            .select("player_id, sector_id")\
            .eq("planet_id", planet_id)\
            .execute()
        
        bases = bases_res.data if bases_res and bases_res.data else []
        
        base_owner_id = bases[0]["player_id"] if bases else None

        # 2. Obtener Edificios (Para Outposts y Estaciones Orbitales)
        assets_res = db.table("planet_assets").select("id, player_id").eq("planet_id", planet_id).execute()
        
        if not bases and (not assets_res or not assets_res.data):
            db.table("planets").update({"surface_owner_id": None, "orbital_owner_id": enemy_fleet_owner_id}).eq("id", planet_id).execute()
            if system_id:
                recalculate_system_ownership(system_id)
            return

        assets = assets_res.data if assets_res and assets_res.data else []
        player_map = {a["id"]: a["player_id"] for a in assets}
        asset_ids = list(player_map.keys())

        # Consultar edificios relevantes en planet_buildings
        buildings = []
        if asset_ids:
             # --- V10.4: Filtrar edificios en construcción ---
            world = get_world_state()
            current_tick = world.get("current_tick", 1)

            buildings_res = db.table("planet_buildings")\
                .select("building_type, planet_asset_id, is_active, built_at_tick")\
                .in_("planet_asset_id", asset_ids)\
                .execute()
            
            raw_buildings = buildings_res.data if buildings_res and buildings_res.data else []
            buildings = [b for b in raw_buildings if b.get("built_at_tick", 0) <= current_tick]

        outpost_owners = set()
        orbital_station_owner = None

        for b in buildings:
            b_type = b.get("building_type")
            pid = player_map.get(b.get("planet_asset_id"))
            is_active = b.get("is_active", True)

            if b_type == "outpost":
                outpost_owners.add(pid)
            elif b_type == "orbital_station" and is_active:
                orbital_station_owner = pid

        # --- DETERMINAR SOBERANÍA DE SUPERFICIE ---
        new_surface_owner = None
        
        if population > 0:
            # Regla V11: Si hay población, manda la Base Militar (Tabla 'bases')
            new_surface_owner = base_owner_id
        else:
            if base_owner_id:
                 new_surface_owner = base_owner_id
            elif len(outpost_owners) == 1:
                new_surface_owner = list(outpost_owners)[0]
            else:
                new_surface_owner = None

        # --- DETERMINAR SOBERANÍA ORBITAL ---
        new_orbital_owner = None
        if orbital_station_owner:
            new_orbital_owner = orbital_station_owner  
        elif enemy_fleet_owner_id:
            new_orbital_owner = enemy_fleet_owner_id  
        else:
            new_orbital_owner = new_surface_owner  

        # Actualizar Planeta
        db.table("planets").update({
            "surface_owner_id": new_surface_owner,
            "orbital_owner_id": new_orbital_owner,
            "is_disputed": (new_surface_owner is None and len(outpost_owners) > 1)
        }).eq("id", planet_id).execute()

        # V9.0: Recalcular control del sistema en cascada
        if system_id:
            recalculate_system_ownership(system_id)

    except Exception as e:
        log_event(f"Error actualizando soberanía planet {planet_id}: {e}", is_error=True)


def build_structure(
    planet_asset_id: int,
    player_id: int,
    building_type: str,
    tier: int = 1,
    sector_id: Optional[int] = None 
) -> Optional[Dict[str, Any]]:
    """Construye validando espacio, bloqueos y presencia para edificios orbitales."""
    if building_type not in BUILDING_TYPES: return None
    definition = BUILDING_TYPES[building_type]
    db = _get_db()

    try:
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return None
        planet_id = asset["planet_id"]

        # --- Validaciones Generales ---
        
        all_assets = db.table("planet_assets").select("id, player_id").eq("planet_id", planet_id).execute().data
        all_asset_ids = [a["id"] for a in all_assets]
        
        all_buildings = db.table("planet_buildings")\
            .select("sector_id, building_type, planet_asset_id")\
            .in_("planet_asset_id", all_asset_ids)\
            .execute().data or []
            
        my_buildings = [b for b in all_buildings if b["planet_asset_id"] == planet_asset_id]

        # Mapa de ocupación
        sector_occupants = {} 
        
        for b in all_buildings:
            owner = next((a["player_id"] for a in all_assets if a["id"] == b["planet_asset_id"]), None)
            sid = b.get("sector_id")
            if sid:
                if sid not in sector_occupants: sector_occupants[sid] = set()
                if owner is not None:
                    sector_occupants[sid].add(owner)
        
        # Inyectar Bases Militares como ocupantes
        bases_res = db.table("bases").select("sector_id, player_id").eq("planet_id", planet_id).execute()
        bases_data = bases_res.data if bases_res and bases_res.data else []
        for base in bases_data:
            sid = base["sector_id"]
            if sid not in sector_occupants: sector_occupants[sid] = set()
            sector_occupants[sid].add(base["player_id"])

        # 1. Recuperar Sectores
        sectors_res = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
        sectors = sectors_res.data if sectors_res and sectors_res.data else []
        if not sectors:
            log_event("No hay sectores en el planeta.", player_id, is_error=True)
            return None

        # Contadores de slots
        sector_counts = {}
        for b in all_buildings: # FIX V11.1: Usar all_buildings para conteo global correcto
            sid = b.get("sector_id")
            bt = b.get("building_type")
            consumes = BUILDING_TYPES.get(bt, {}).get("consumes_slots", True)
            if sid and consumes: 
                sector_counts[sid] = sector_counts.get(sid, 0) + 1
        
        # Añadir Bases al conteo de slots
        for base in bases_data:
            sid = base["sector_id"]
            sector_counts[sid] = sector_counts.get(sid, 0) + 1

        for s in sectors:
            if 'max_slots' in s: s['slots'] = s['max_slots']
            s['buildings_count'] = sector_counts.get(s["id"], 0)
            
        # --- V8.3 / V11.0: VALIDACIÓN DE REGLAS DE NEGOCIO (Base vs HQ) ---
        if building_type == 'hq':
             existing_base = db.table("bases").select("id").eq("player_id", player_id).eq("planet_id", planet_id).maybe_single().execute()
             if existing_base and existing_base.data:
                 log_event("Ya posees una Base Militar en este planeta.", player_id, is_error=True)
                 return None

        # 2. Selección de Sector Objetivo y Validación de Bloqueo Local
        target_sector = None
        
        if sector_id:
            matches = [s for s in sectors if str(s["id"]) == str(sector_id)]
            if matches: 
                target_sector = matches[0]
                allowed = definition.get("allowed_terrain")
                if allowed and target_sector["sector_type"] not in allowed:
                    log_event(f"Error de Construcción: Terreno {target_sector['sector_type']} incompatible con {definition['name']}.", player_id, is_error=True)
                    return None
        else:
            candidates = []
            for s in sectors:
                if definition.get("consumes_slots", True) and s["buildings_count"] >= s["slots"]:
                    continue
                allowed = definition.get("allowed_terrain")
                if allowed and s["sector_type"] not in allowed:
                    continue
                occupants = sector_occupants.get(s["id"], set())
                if any(occ != player_id for occ in occupants):
                    continue 

                candidates.append(s)
            
            if building_type == "hq":
                urban = [s for s in candidates if s.get("sector_type") == SECTOR_TYPE_URBAN]
                target_sector = urban[0] if urban else None
            elif building_type == "orbital_station":
                orbital = [s for s in candidates if s.get("sector_type") == SECTOR_TYPE_ORBITAL]
                target_sector = orbital[0] if orbital else None
            else:
                target_sector = candidates[0] if candidates else None

        if not target_sector:
            log_event("No hay sectores disponibles o válidos (Bloqueo/Espacio/Tipo).", player_id, is_error=True)
            return None

        # --- VALIDACIONES ORBITALES ESPECÍFICAS (V6.4 y V9.2) ---
        if definition.get("is_orbital", False):
            planet_info = get_planet_by_id(planet_id)
            if planet_info:
                surface_owner = planet_info.get("surface_owner_id")
                orbital_owner = planet_info.get("orbital_owner_id")
                
                is_surface_owner = (surface_owner == player_id)
                is_orbital_owner = (orbital_owner == player_id)
                
                if orbital_owner and orbital_owner != player_id:
                     log_event("Construcción orbital bloqueada: Órbita controlada por enemigo.", player_id, is_error=True)
                     return None
                
                if not is_surface_owner and not is_orbital_owner:
                     log_event("Requisito Orbital: Se requiere control de superficie o flota en órbita.", player_id, is_error=True)
                     return None

        occupants = sector_occupants.get(target_sector["id"], set())
        if any(occ != player_id for occ in occupants):
            log_event("Construcción fallida: Sector ocupado por otra facción.", player_id, is_error=True)
            return None
            
        if definition.get("consumes_slots", True) and target_sector["buildings_count"] >= target_sector["slots"]:
             log_event("No hay espacio en el sector seleccionado.", player_id, is_error=True)
             return None

        # 3. Insertar Edificio
        world = get_world_state()
        
        b_def = BUILDING_TYPES.get(building_type, {})
        pops_req = b_def.get("pops_required", 0)
        energy_cons = b_def.get("maintenance", {}).get("celulas_energia", 0)
        
        building_data = {
            "planet_asset_id": planet_asset_id,
            "player_id": player_id,
            "building_type": building_type,
            "building_tier": tier,
            "sector_id": target_sector["id"],
            "is_active": True,
            "built_at_tick": world.get("current_tick", 1),
            "pops_required": pops_req,
            "energy_consumption": energy_cons
        }

        response = db.table("planet_buildings").insert(building_data).execute()
        if response and response.data:
            log_event(f"Construido {definition['name']} en {target_sector.get('sector_type', 'Sector')}", player_id)
            update_planet_sovereignty(planet_id)
            return response.data[0]
        return None
    except Exception as e:
        log_event(f"Error construyendo edificio: {e}", player_id, is_error=True)
        return None


def demolish_building(building_id: int, player_id: int) -> bool:
    """Demuele y decrementa el contador del sector (Implícito). Actualiza soberanía."""
    try:
        db = _get_db()
        # Verificar propiedad y obtener planet_id para update sovereignty
        b_res = db.table("planet_buildings")\
            .select("*, planet_assets(planet_id)")\
            .eq("id", building_id)\
            .single()\
            .execute()
            
        if not b_res or not b_res.data: return False
        
        planet_id = b_res.data.get("planet_assets", {}).get("planet_id")
        
        # Eliminar
        db.table("planet_buildings").delete().eq("id", building_id).execute()
        
        log_event(f"Edificio {building_id} demolido.", player_id)
        
        # --- V6.3: Actualizar Soberanía ---
        if planet_id:
            update_planet_sovereignty(planet_id)

        return True
    except Exception as e:
        log_event(f"Error demoliendo: {e}", player_id, is_error=True)
        return False


def get_luxury_extraction_sites_for_player(player_id: int) -> List[Dict[str, Any]]:
    try:
        response = _get_db().table("luxury_extraction_sites")\
            .select("*")\
            .eq("player_id", player_id)\
            .eq("is_active", True)\
            .execute()
        return response.data if response and response.data else []
    except Exception as e:
        log_event(f"Error obteniendo sitios: {e}", player_id, is_error=True)
        return []


def batch_update_planet_security(updates: List[Tuple[int, float]]) -> bool:
    """Actualiza la seguridad en lote en la tabla 'planets' y recalcula sistemas afectados."""
    if not updates: return True
    try:
        db = _get_db()
        affected_systems = set()
        
        # Actualización de planetas
        for planet_id, security in updates:
            db.table("planets").update({"security": security}).eq("id", planet_id).execute()
            
        # V9.1: Recálculo de Sistemas Afectados
        planet_ids = [u[0] for u in updates]
        if planet_ids:
            sys_res = db.table("planets").select("system_id").in_("id", planet_ids).execute()
            if sys_res and sys_res.data:
                for row in sys_res.data:
                    sid = row.get("system_id")
                    if sid: affected_systems.add(sid)
        
        # Recalculamos la seguridad de cada sistema afectado
        for sid in affected_systems:
            recalculate_system_security(sid)

        return True
    except Exception as e:
        log_event(f"Error batch security update: {e}", is_error=True)
        return False


def batch_update_building_status(updates: List[Tuple[int, bool]]) -> Tuple[int, int]:
    if not updates: return (0, 0)
    success, failed = 0, 0
    db = _get_db()
    for building_id, is_active in updates:
        try:
            res = db.table("planet_buildings").update({"is_active": is_active}).eq("id", building_id).execute()
            if res: success += 1
            else: failed += 1
        except Exception: failed += 1
    return (success, failed)


def update_planet_asset(planet_asset_id: int, updates: Dict[str, Any]) -> bool:
    try:
        response = _get_db().table("planet_assets").update(updates).eq("id", planet_asset_id).execute()
        return True if response else False
    except Exception as e:
        log_event(f"Error actualizando activo {planet_asset_id}: {e}", is_error=True)
        return False

# --- V9.0: CONTROL DEL SISTEMA ESTELAR (Basado en Jugadores) ---

def recalculate_system_ownership(system_id: int) -> Optional[int]:
    """
    Recalcula y actualiza el controlador de un sistema basado en mayoría de planetas.
    """
    try:
        db = _get_db()

        # 1. Obtener todos los planetas del sistema
        planets_res = db.table("planets").select("id, surface_owner_id").eq("system_id", system_id).execute()
        planets = planets_res.data if planets_res and planets_res.data else []

        total_planets = len(planets)

        if total_planets == 0:
            update_system_controller(system_id, None)
            return None

        # 2. Contar planetas por propietario
        owner_counts: Dict[int, int] = {}
        for planet in planets:
            owner_id = planet.get("surface_owner_id")
            if owner_id is not None:
                owner_counts[owner_id] = owner_counts.get(owner_id, 0) + 1

        # 3. Determinar si alguien tiene mayoría (> 50%)
        new_controller_id: Optional[int] = None
        majority_threshold = total_planets / 2.0

        for player_id, count in owner_counts.items():
            if count > majority_threshold:
                new_controller_id = player_id
                break

        update_system_controller(system_id, new_controller_id)

        return new_controller_id

    except Exception as e:
        log_event(f"Error recalculando propiedad del sistema {system_id}: {e}", is_error=True)
        return None

def recalculate_system_security(system_id: int) -> float:
    """
    V9.1: Recalcula el promedio de seguridad de todos los planetas del sistema
    y actualiza la tabla systems.
    """
    try:
        db = _get_db()
        response = db.table("planets")\
            .select("security")\
            .eq("system_id", system_id)\
            .execute()
        
        planets = response.data if response and response.data else []
        if not planets:
            update_system_security(system_id, 0.0)
            return 0.0

        total_security = sum(p.get("security", 0.0) for p in planets)
        avg_security = total_security / len(planets)
        
        update_system_security(system_id, avg_security)
        
        return avg_security
    except Exception as e:
        log_event(f"Error recalculando seguridad sistema {system_id}: {e}", is_error=True)
        return 0.0

def check_system_majority_control(system_id: int, player_id: int) -> bool:
    try:
        db = _get_db()

        all_planets_res = db.table("planets").select("id").eq("system_id", system_id).execute()
        all_planets = all_planets_res.data if all_planets_res and all_planets_res.data else []
        total_planets = len(all_planets)

        if total_planets == 0:
            return False

        my_planets_res = db.table("planets").select("id")\
            .eq("system_id", system_id)\
            .eq("surface_owner_id", player_id)\
            .execute()

        my_count = len(my_planets_res.data) if my_planets_res and my_planets_res.data else 0
        has_majority = my_count > (total_planets / 2.0)

        return has_majority

    except Exception as e:
        print(f"Error checking system control: {e}")
        return False

# --- V4.4: SEGURIDAD GALÁCTICA ---

def update_planet_security_value(planet_id: int, value: float) -> bool:
    """Actualiza la seguridad física del planeta en la tabla mundial."""
    try:
        response = _get_db().table("planets").update({"security": value}).eq("id", planet_id).execute()
        return True if response else False
    except Exception as e:
        log_event(f"Error actualizando seguridad del planeta {planet_id}: {e}", is_error=True)
        return False

def update_planet_security_data(planet_id: int, security: float, breakdown: Dict[str, Any]) -> bool:
    """Actualiza la seguridad en la tabla 'planets' y recalcula la del sistema."""
    try:
        db = _get_db()
        # V6.1: Persistencia explícita de breakdown
        response = db.table("planets").update({
            "security": security,
            "security_breakdown": breakdown
        }).eq("id", planet_id).execute()
        
        if response:
            p_res = db.table("planets").select("system_id").eq("id", planet_id).single().execute()
            if p_res and p_res.data and p_res.data.get("system_id"):
                recalculate_system_security(p_res.data.get("system_id"))
            return True
        return False
    except Exception as e:
        log_event(f"Error actualizando seguridad planeta {planet_id}: {e}", is_error=True)
        return False

def get_all_colonized_system_ids() -> List[int]:
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

# --- V7.3: INICIALIZACIÓN DE SECTORES (GENESIS) ---

def initialize_planet_sectors(planet_id: int, biome: str, mass_class: str = 'Estándar') -> List[Dict[str, Any]]:
    """
    Garantiza que un planeta tenga sectores inicializados, INCLUYENDO LA ÓRBITA.
    Corrige IDs faltantes y transforma sectores existentes si es necesario.
    """
    try:
        db = _get_db()
        # 1. Verificar existencia
        check = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
        existing_sectors = check.data if check and check.data else []
        
        sectors_to_create = []
        sectors_updated = False

        # A. Verificar Urbano
        urban_sector = next((s for s in existing_sectors if s.get("sector_type") == SECTOR_TYPE_URBAN), None)

        if not urban_sector:
            # CASO 1: Transformación
            if existing_sectors:
                candidate = next((s for s in existing_sectors if s.get("sector_type") != SECTOR_TYPE_ORBITAL), None)
                
                if candidate:
                    u_slots = SECTOR_SLOTS_CONFIG.get(SECTOR_TYPE_URBAN, 3)
                    try:
                        res = db.table("sectors").update({
                            "sector_type": SECTOR_TYPE_URBAN,
                            "name": "Distrito Central",
                            "max_slots": u_slots,
                        }).eq("id", candidate["id"]).execute()
                        
                        if res and res.data:
                            candidate["sector_type"] = SECTOR_TYPE_URBAN
                            candidate["name"] = "Distrito Central"
                            candidate["max_slots"] = u_slots
                            sectors_updated = True
                    except Exception as e:
                        print(f"Error transformando sector {candidate['id']}: {e}")
            
            # CASO 2: Inicialización desde cero
            else:
                urban_id = (planet_id * 1000) + 1
                sectors_to_create.append({
                    "id": urban_id,
                    "planet_id": planet_id,
                    "name": "Distrito Central",
                    "sector_type": SECTOR_TYPE_URBAN,
                    "max_slots": SECTOR_SLOTS_CONFIG.get(SECTOR_TYPE_URBAN, 3),
                    "is_known": False,
                    "resource_category": "influencia"
                })

        # B. Verificar Orbital
        orbital_sector = next((s for s in existing_sectors if s.get("sector_type") == SECTOR_TYPE_ORBITAL), None)
        orbital_pending = next((s for s in sectors_to_create if s.get("sector_type") == SECTOR_TYPE_ORBITAL), None)

        if not orbital_sector and not orbital_pending:
            orbital_id = (planet_id * 1000) + 99
            sectors_to_create.append({
                "id": orbital_id,
                "planet_id": planet_id,
                "name": "Órbita Geoestacionaria",
                "sector_type": SECTOR_TYPE_ORBITAL,
                "max_slots": SECTOR_SLOTS_CONFIG.get(SECTOR_TYPE_ORBITAL, 1),
                "is_known": True,
                "resource_category": None
            })

        # C. Rellenar resto de sectores
        if not existing_sectors and sectors_to_create:
            target_count = PLANET_MASS_CLASSES.get(mass_class, 4)
            valid_types = [SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN]
            
            for i in range(2, target_count + 1):
                new_id = (planet_id * 1000) + i
                sType = random.choice(valid_types)
                sectors_to_create.append({
                    "id": new_id,
                    "planet_id": planet_id,
                    "name": f"Sector {i} ({sType})",
                    "sector_type": sType,
                    "max_slots": SECTOR_SLOTS_CONFIG.get(sType, 3),
                    "is_known": False,
                    "resource_category": "materiales"
                })

        if sectors_to_create:
            res = db.table("sectors").insert(sectors_to_create).execute()
            if res and res.data:
                existing_sectors.extend(res.data)
                sectors_updated = True 
                
        if sectors_updated:
             final_check = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
             return final_check.data if final_check and final_check.data else []

        return existing_sectors

    except Exception as e:
        log_event(f"Error critical initializing sectors for planet {planet_id}: {e}", is_error=True)
        try:
             return db.table("sectors").select("*").eq("planet_id", planet_id).execute().data or []
        except:
             return []

def claim_genesis_sector(sector_id: int, player_id: int) -> bool:
    """Marca un sector como conocido para el aterrizaje inicial (Génesis)."""
    try:
        _get_db().table("sectors").update({
            "is_known": True
        }).eq("id", sector_id).execute()
        return True
    except Exception as e:
        log_event(f"Error claiming genesis sector {sector_id}: {e}", player_id, is_error=True)
        return False


def add_initial_building(
    player_id: int,
    planet_asset_id: int,
    sector_id: int,
    building_type: str = 'hq'
) -> bool:
    """Legacy: Mantenido para compatibilidad."""
    try:
        db = _get_db()
        building_def = BUILDING_TYPES.get(building_type)
        if not building_def: return False
        world = get_world_state()
        current_tick = world.get("current_tick", 1) if world else 1

        building_data = {
            "planet_asset_id": planet_asset_id,
            "player_id": player_id,
            "building_type": building_type,
            "building_tier": 1,
            "sector_id": sector_id,
            "is_active": True,
            "pops_required": building_def.get("pops_required", 0),
            "energy_consumption": building_def.get("maintenance", {}).get("celulas_energia", 0),
            "built_at_tick": current_tick
        }

        response = db.table("planet_buildings").insert(building_data).execute()
        if response and response.data:
            update_planet_sovereignty(get_planet_asset_by_id(planet_asset_id)["planet_id"])
            return True
        return False
    except Exception as e:
        log_event(f"Error crítico en add_initial_building: {e}", player_id, is_error=True)
        return False


# --- V11.0: NUEVAS FUNCIONES PARA SISTEMA DE BASES ---

def initialize_player_base(player_id: int, planet_id: int, sector_id: int) -> bool:
    """
    Crea la Base Militar inicial (HQ) en la tabla 'bases'.
    Utilizado por Protocolo Génesis para despliegue gratuito.
    Actualizado V11.2: Inicialización de módulos a Nivel 1.
    """
    try:
        db = _get_db()
        world = get_world_state()
        current_tick = world.get("current_tick", 1)

        base_data = {
            "player_id": player_id,
            "planet_id": planet_id,
            "sector_id": sector_id,
            "tier": 1,
            "created_at_tick": current_tick,
            # FIX V11.2: Inicializar módulos en Nivel 1
            "module_sensor_planetary": 1,
            "module_sensor_orbital": 1,
            "module_defense_ground": 1,
            "module_bunker": 1
        }

        response = db.table("bases").insert(base_data).execute()
        
        if response and response.data:
            log_event(f"✅ Base Militar establecida en sector {sector_id}", player_id)
            # Recalcular soberanía inmediatamente (La base otorga control)
            update_planet_sovereignty(planet_id)
            return True
        
        log_event(f"Fallo al crear Base Militar en sector {sector_id}", player_id, is_error=True)
        return False

    except Exception as e:
        log_event(f"Error crítico en initialize_player_base: {e}", player_id, is_error=True)
        return False

def rename_settlement(planet_asset_id: int, player_id: int, new_name: str) -> bool:
    """Permite al jugador renombrar su colonia/asentamiento."""
    if not new_name or len(new_name) < 3:
        return False
        
    try:
        response = _get_db().table("planet_assets").update({
            "nombre_asentamiento": new_name
        }).eq("id", planet_asset_id).eq("player_id", player_id).execute()
        
        if response and response.data:
            log_event(f"Asentamiento renombrado a '{new_name}'", player_id)
            return True
        return False
    except Exception as e:
        log_event(f"Error renombrando asentamiento: {e}", player_id, is_error=True)
        return False