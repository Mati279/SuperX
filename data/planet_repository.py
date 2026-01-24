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


def get_all_player_planets_with_buildings(player_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene planetas del jugador con edificios y datos de sectores precargados.
    Refactor V5.7: Actualizado a 'population'.
    Fix V5.9: Corrección de nombre de columna 'sector_type'.
    Refactor V6.0: Cálculo dinámico de 'buildings_count'.
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

        # Obtener Edificios
        buildings_response = db.table("planet_buildings")\
            .select("*")\
            .in_("planet_asset_id", asset_ids)\
            .execute()
        buildings = buildings_response.data if buildings_response and buildings_response.data else []

        # Obtener Sectores (Sin buildings_count)
        sectors_response = db.table("sectors")\
            .select("id, sector_type, planet_id, max_slots, resource_category, is_known")\
            .in_("planet_id", planet_ids)\
            .execute()
        sectors_data = sectors_response.data if sectors_response and sectors_response.data else []
        
        # Corrección de campo legacy 'slots' -> 'max_slots' e inicializar count
        sector_map = {}
        for s in sectors_data:
            if 'slots' not in s and 'max_slots' in s:
                s['slots'] = s['max_slots']
            s['buildings_count'] = 0 # Inicializar contador dinámico
            sector_map[s["id"]] = s
        
        buildings_by_asset: Dict[int, List[Dict]] = {}
        for building in buildings:
            aid = building["planet_asset_id"]
            if aid not in buildings_by_asset: buildings_by_asset[aid] = []
            
            sec_id = building.get("sector_id")
            sector = sector_map.get(sec_id)
            
            # Asignar info del sector y actualizar contador
            building["sector_type"] = sector.get("sector_type") if sector else "Desconocido"
            building["sector_info"] = sector
            
            # --- V6.3: Consumo Dinámico de Slots ---
            # Solo contamos edificios que consumen slots (Default True)
            b_type = building.get("building_type")
            consumes_slots = BUILDING_TYPES.get(b_type, {}).get("consumes_slots", True)
            
            if sector and consumes_slots:
                sector['buildings_count'] += 1
            
            buildings_by_asset[aid].append(building)

        for asset in assets:
            planet_data = asset.get("planets", {})
            asset["orbital_owner_id"] = planet_data.get("orbital_owner_id")
            asset["surface_owner_id"] = planet_data.get("surface_owner_id")
            asset["is_disputed"] = planet_data.get("is_disputed", False)
            asset["biome"] = planet_data.get("biome", "Desconocido")
            
            # FIX V6.2: Mapeo explícito de population para el motor económico
            asset["population"] = planet_data.get("population", 0.0)
            
            # Ensure planet data is accessible
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
            # Boost para la primera colonia
            # NOTA: Si se pasa initial_population (ej. desde Genesis Engine), esto se ignora/sobrescribe si el caller no tiene cuidado.
            # Pero Genesis Engine ya calcula y pasa el random correcto.
            if initial_population == 1.0: # Solo aplicar random default si viene el valor por defecto
                initial_population = random.uniform(1.5, 1.7)

        # --- FIX SEGURIDAD (V5.9) ---
        # Obtener datos reales del planeta para calcular seguridad correcta
        planet_data = get_planet_by_id(planet_id)
        
        initial_security = 20.0 # Fallback seguro
        if planet_data:
            base_def = planet_data.get("base_defense", 10) or 10
            ring = planet_data.get("orbital_ring", 3) or 3
            
            # Usamos la regla centralizada con flag de propiedad
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
            # Refactor V5.7: population en lugar de poblacion
            "population": initial_population,
            "pops_activos": initial_population,
            "pops_desempleados": 0.0,
            "infraestructura_defensiva": 0
            # FIX V7.7.2: Eliminado 'base_tier' explícito para evitar PGRST204.
            # Se delega al valor DEFAULT 1 en la base de datos.
        }
        
        response = db.table("planet_assets").insert(asset_data).execute()
        
        if response and response.data:
            # --- FIX CRÍTICO V6.1: Soporte dual para Float/Dict en Security ---
            sec_value = initial_security
            sec_breakdown = {}
            
            if isinstance(initial_security, dict):
                sec_value = initial_security.get("total", 20.0)
                sec_breakdown = initial_security
            
            # --- FIX RACE CONDITION (V7.7.1) ---
            # Separamos los updates para evitar conflictos con Triggers DB que calculan seguridad/producción.
            
            # Paso 1: Asignar Dueños y Población
            db.table("planets").update({
                "surface_owner_id": player_id,
                "orbital_owner_id": player_id, # FIX CRÍTICO DE SOBERANÍA
                "population": initial_population
            }).eq("id", planet_id).execute()
            
            # Paso 2: Asignar Seguridad Calculada (Sobrescribiendo posibles triggers)
            db.table("planets").update({
                "security": sec_value,
                "security_breakdown": sec_breakdown
            }).eq("id", planet_id).execute()
            
            # --- FAIL-SAFE DE SECTORES (V5.9) ---
            # Verificar si existen sectores. Si no, crear uno de emergencia.
            sectors_check = db.table("sectors").select("id").eq("planet_id", planet_id).execute()
            if not sectors_check.data:
                # Crear sector de emergencia
                emergency_sector = {
                    "id": (planet_id * 1000) + 1,
                    "planet_id": planet_id,
                    "name": "Sector Urbano (Emergencia)",
                    "sector_type": SECTOR_TYPE_URBAN, 
                    "max_slots": 5,
                    "is_known": True
                    # V6.0: Eliminado 'buildings_count'
                }
                db.table("sectors").insert(emergency_sector).execute()
                log_event(f"Sector de emergencia creado para {planet_id}", player_id, is_error=True)

            log_event(f"Planeta colonizado: {settlement_name} (Seguridad inicial: {sec_value:.1f})", player_id)
            
            # --- V9.1: Recalcular Seguridad del Sistema ---
            recalculate_system_security(system_id)
            
            return response.data[0]
        return None
    except Exception as e:
        # --- DEBUG CRÍTICO ---
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
        
        # V6.3: Filtrar edificios que no consumen slots
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
        
        return {"total": total_slots, "used": used, "free": max(0, total_slots - used)}
    except Exception as e:
        log_event(f"Error calculando slots por sectores: {e}", is_error=True)
        return {"total": 0, "used": 0, "free": 0}


def get_planet_sectors_status(planet_id: int, player_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Consulta el estado actual de los sectores de un planeta, calculando ocupación dinámica.
    V7.2: Soporta filtrado por conocimiento de jugador (is_explored_by_player).
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

        # 2. Contar edificios dinámicamente (Filtrando consumo de slots)
        b_response = db.table("planet_buildings")\
            .select("sector_id, building_type")\
            .in_("sector_id", sector_ids)\
            .execute()
        
        buildings = b_response.data if b_response and b_response.data else []
        counts = {}
        for b in buildings:
            sid = b.get("sector_id")
            bt = b.get("building_type")
            # V6.3: Solo contar si consume slot
            if sid and BUILDING_TYPES.get(bt, {}).get("consumes_slots", True):
                counts[sid] = counts.get(sid, 0) + 1

        # 3. Validar conocimiento del jugador (V7.2)
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
                pass # Fail safe si la tabla no existe o error de conexión

        # 4. Mapear resultados
        for s in sectors:
            s['slots'] = s.get('max_slots', 2)
            s['buildings_count'] = counts.get(s["id"], 0)
            # Flag de UI para niebla: Órbita siempre es conocida, otros depende de tabla
            if s.get("sector_type") == SECTOR_TYPE_ORBITAL:
                s['is_explored_by_player'] = True
            else:
                s['is_explored_by_player'] = (s["id"] in known_sector_ids)
            
        return sectors
    except Exception:
        return []


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
    try:
        response = _get_db().table("planet_buildings")\
            .select("*")\
            .eq("planet_asset_id", planet_asset_id)\
            .execute()
        return response.data if response and response.data else []
    except Exception as e:
        log_event(f"Error obteniendo edificios: {e}", is_error=True)
        return []

# --- V6.3 y V6.4: GESTIÓN DE SOBERANÍA Y CONSTRUCCIÓN ---

def update_planet_sovereignty(planet_id: int, enemy_fleet_owner_id: Optional[int] = None):
    """
    Recalcula y actualiza la soberanía de superficie y orbital basada en edificios y flotas.

    Reglas V6.4 (Prioridad Orbital):
    1. Dueño de 'orbital_station' activa.
    2. Si no hay estación, 'enemy_fleet_owner_id' (ocupación por flota).
    3. Si no hay estación ni flota enemiga, 'surface_owner_id' (herencia).

    Reglas V9.2 (Soberanía Superficie Conflictiva):
    - Si Población > 0: El soberano es el dueño del HQ (Base en Sector Urbano).
    - Si Población == 0:
      * 1 Jugador con Outposts -> Soberano.
      * > 1 Jugador con Outposts (Conflicto) -> None (Tierra de nadie).
      
    V9.0: Al final, recalcula automáticamente el controlador del sistema (cascada).
    """
    try:
        db = _get_db()

        # 0. Obtener system_id y poblacion para reglas
        planet_info_res = db.table("planets").select("system_id, population").eq("id", planet_id).single().execute()
        if not planet_info_res or not planet_info_res.data:
            return
            
        system_id = planet_info_res.data.get("system_id")
        population = planet_info_res.data.get("population", 0.0)

        # 1. Obtener todos los edificios del planeta
        assets_res = db.table("planet_assets").select("id, player_id").eq("planet_id", planet_id).execute()
        if not assets_res or not assets_res.data:
            # Nadie en el planeta
            db.table("planets").update({"surface_owner_id": None, "orbital_owner_id": enemy_fleet_owner_id}).eq("id", planet_id).execute()
            if system_id:
                recalculate_system_ownership(system_id)
            return

        assets = assets_res.data
        asset_ids = [a["id"] for a in assets]
        player_map = {a["id"]: a["player_id"] for a in assets}

        # Obtener edificios relevantes
        buildings_res = db.table("planet_buildings")\
            .select("building_type, planet_asset_id, is_active")\
            .in_("planet_asset_id", asset_ids)\
            .execute()

        buildings = buildings_res.data if buildings_res and buildings_res.data else []

        hq_owner = None
        outpost_owners = set()
        orbital_station_owner = None

        for b in buildings:
            b_type = b.get("building_type")
            pid = player_map.get(b.get("planet_asset_id"))
            is_active = b.get("is_active", True)

            if b_type == "hq":
                hq_owner = pid
            elif b_type == "outpost":
                outpost_owners.add(pid)
            elif b_type == "orbital_station" and is_active:
                orbital_station_owner = pid

        # Lógica de Soberanía Superficie (V9.2)
        new_surface_owner = None
        
        if population > 0:
            # Regla: Si hay población, manda el HQ (Base Urbana)
            # Si se destruyó el HQ pero queda población, se pierde soberanía hasta reconstruirlo
            new_surface_owner = hq_owner 
        else:
            # Regla: Planeta Salvaje / Puestos de Avanzada
            if len(outpost_owners) == 1:
                new_surface_owner = list(outpost_owners)[0]
            else:
                # 0 owners OR > 1 (Conflicto de Puestos)
                new_surface_owner = None

        # Lógica de Soberanía Orbital (V6.4)
        new_orbital_owner = None
        if orbital_station_owner:
            new_orbital_owner = orbital_station_owner  # Prioridad 1
        elif enemy_fleet_owner_id:
            new_orbital_owner = enemy_fleet_owner_id  # Prioridad 2
        else:
            new_orbital_owner = new_surface_owner  # Prioridad 3 (Herencia)

        # Actualizar Planeta
        db.table("planets").update({
            "surface_owner_id": new_surface_owner,
            "orbital_owner_id": new_orbital_owner,
            # Disputa: Si no hay soberano de superficie definido pero hay múltiples outposts
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
            
        # V8.3: Filtrar mis edificios para validación de HQ
        my_buildings = [b for b in all_buildings if b["planet_asset_id"] == planet_asset_id]

        # Mapa de ocupación
        sector_occupants = {} 
        
        for b in all_buildings:
            owner = next((a["player_id"] for a in all_assets if a["id"] == b["planet_asset_id"]), None)
            sid = b.get("sector_id")
            if sid:
                if sid not in sector_occupants: sector_occupants[sid] = set()
                # V8.2 Fix: Solo agregar owners válidos (Ghost Building Protection)
                if owner is not None:
                    sector_occupants[sid].add(owner)
            
        # 1. Recuperar Sectores
        sectors_res = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
        sectors = sectors_res.data if sectors_res and sectors_res.data else []
        if not sectors:
            log_event("No hay sectores en el planeta.", player_id, is_error=True)
            return None

        # Contadores de slots
        sector_counts = {}
        for b in my_buildings:
            sid = b.get("sector_id")
            bt = b.get("building_type")
            consumes = BUILDING_TYPES.get(bt, {}).get("consumes_slots", True)
            if sid and consumes: 
                sector_counts[sid] = sector_counts.get(sid, 0) + 1

        for s in sectors:
            if 'max_slots' in s: s['slots'] = s['max_slots']
            s['buildings_count'] = sector_counts.get(s["id"], 0)
            
        # --- V8.3: VALIDACIÓN DE REGLAS DE NEGOCIO (HQ Único) ---
        # Como hemos eliminado la restricción DB 'unique_building_per_planet', 
        # debemos asegurar que no se construyan múltiples HQs por código.
        if building_type == 'hq':
             existing_hq = next((b for b in my_buildings if b["building_type"] == "hq"), None)
             if existing_hq:
                 log_event("Solo puedes tener un Comando Central por colonia.", player_id, is_error=True)
                 return None

        # 2. Selección de Sector Objetivo y Validación de Bloqueo Local
        target_sector = None
        
        if sector_id:
            # V8.2: Asegurar comparación de tipos (str vs int)
            matches = [s for s in sectors if str(s["id"]) == str(sector_id)]
            if matches: 
                target_sector = matches[0]
                
                # V9.2: Re-validar Allowed Terrain si se pasa ID explícito (HARD-LOCK)
                allowed = definition.get("allowed_terrain")
                if allowed and target_sector["sector_type"] not in allowed:
                    log_event(f"Error de Construcción: Terreno {target_sector['sector_type']} incompatible con {definition['name']}.", player_id, is_error=True)
                    return None
        else:
            # Auto-asignación inteligente
            # Priorizar Urbano para HQ, Orbital para Estación, etc.
            candidates = []
            for s in sectors:
                # Chequeo de slots
                if definition.get("consumes_slots", True) and s["buildings_count"] >= s["slots"]:
                    continue
                
                # REGLA V6.4 / V9.2: Validar Allowed Terrain explícito (HARD-LOCK)
                allowed = definition.get("allowed_terrain")
                if allowed and s["sector_type"] not in allowed:
                    continue

                # REGLA: Bloqueo de Facción
                occupants = sector_occupants.get(s["id"], set())
                if any(occ != player_id for occ in occupants):
                    continue 

                candidates.append(s)
            
            # Prioridad específica
            if building_type == "hq":
                urban = [s for s in candidates if s.get("sector_type") == SECTOR_TYPE_URBAN]
                target_sector = urban[0] if urban else None
            elif building_type == "orbital_station":
                orbital = [s for s in candidates if s.get("sector_type") == SECTOR_TYPE_ORBITAL]
                target_sector = orbital[0] if orbital else None
            else:
                target_sector = candidates[0] if candidates else None

        # Validación final del target
        if not target_sector:
            log_event("No hay sectores disponibles o válidos (Bloqueo/Espacio/Tipo).", player_id, is_error=True)
            return None

        # --- VALIDACIONES ORBITALES ESPECÍFICAS (V6.4 y V9.2) ---
        if definition.get("is_orbital", False):
            # Verificar presencia: Dueño de Superficie o Control Orbital actual (Flota/Estación)
            planet_info = get_planet_by_id(planet_id)
            if planet_info:
                surface_owner = planet_info.get("surface_owner_id")
                orbital_owner = planet_info.get("orbital_owner_id")
                
                # V9.2 EXCEPCIÓN DE CONSTRUCCIÓN ORBITAL:
                # Si soy dueño de la superficie, NO necesito flota en órbita (orbital_owner puede ser None).
                is_surface_owner = (surface_owner == player_id)
                is_orbital_owner = (orbital_owner == player_id)
                
                # Regla de Bloqueo:
                # Si hay un dueño orbital diferente a mí, NO puedo construir (independientemente de la superficie)
                if orbital_owner and orbital_owner != player_id:
                     log_event("Construcción orbital bloqueada: Órbita controlada por enemigo.", player_id, is_error=True)
                     return None
                
                # Regla de Requisito:
                # Debo ser dueño de la superficie O dueño orbital (flota).
                # Si orbital_owner es None, solo paso si is_surface_owner es True.
                if not is_surface_owner and not is_orbital_owner:
                     log_event("Requisito Orbital: Se requiere control de superficie o flota en órbita.", player_id, is_error=True)
                     return None

        # Validación explícita de bloqueo en target
        occupants = sector_occupants.get(target_sector["id"], set())
        if any(occ != player_id for occ in occupants):
            log_event("Construcción fallida: Sector ocupado por otra facción.", player_id, is_error=True)
            return None
            
        if definition.get("consumes_slots", True) and target_sector["buildings_count"] >= target_sector["slots"]:
             log_event("No hay espacio en el sector seleccionado.", player_id, is_error=True)
             return None

        # 3. Insertar Edificio
        world = get_world_state()
        
        # FIX V8.2.1: Inyección de datos requeridos por la base de datos (Not Null constraints)
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
            
            # --- V6.3: Actualizar Soberanía ---
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
        # Consultamos los sistemas de todos los planetas actualizados
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

    V9.0: Migración de Facciones a Jugadores.

    Lógica:
    1. Obtiene todos los planetas del sistema.
    2. Cuenta cuántos planetas tiene cada surface_owner_id (ignora None).
    3. Si un player_id posee > 50% de los planetas, es el nuevo controlador.
    4. Si nadie cumple la condición, el controlador es None (Neutral/Disputado).
    5. Actualiza la columna controlling_player_id en la tabla systems.

    Returns:
        El player_id del nuevo controlador o None si es neutral/disputado.
    """
    try:
        db = _get_db()

        # 1. Obtener todos los planetas del sistema
        planets_res = db.table("planets").select("id, surface_owner_id").eq("system_id", system_id).execute()
        planets = planets_res.data if planets_res and planets_res.data else []

        total_planets = len(planets)

        # Si no hay planetas, el sistema es neutral
        if total_planets == 0:
            update_system_controller(system_id, None)
            return None

        # 2. Contar planetas por propietario (ignorando None)
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

        # 4. Actualizar el controlador del sistema
        update_system_controller(system_id, new_controller_id)

        return new_controller_id

    except Exception as e:
        log_event(f"Error recalculando propiedad del sistema {system_id}: {e}", is_error=True)
        return None

def recalculate_system_security(system_id: int) -> float:
    """
    V9.1: Recalcula el promedio de seguridad de todos los planetas del sistema
    y actualiza la tabla systems.
    
    Lógica:
    - Suma de security de todos los planetas (incluyendo 0.0)
    - División por número de planetas
    - Actualización en tabla systems
    """
    try:
        db = _get_db()
        # 1. Obtener seguridad de todos los planetas del sistema
        # Importante: Incluir todos los planetas, incluso con seguridad 0
        response = db.table("planets")\
            .select("security")\
            .eq("system_id", system_id)\
            .execute()
        
        planets = response.data if response and response.data else []
        if not planets:
            # Si no hay planetas, seguridad 0
            update_system_security(system_id, 0.0)
            return 0.0

        total_security = sum(p.get("security", 0.0) for p in planets)
        avg_security = total_security / len(planets)
        
        # 2. Actualizar sistema
        update_system_security(system_id, avg_security)
        
        return avg_security
    except Exception as e:
        log_event(f"Error recalculando seguridad sistema {system_id}: {e}", is_error=True)
        return 0.0

def check_system_majority_control(system_id: int, player_id: int) -> bool:
    """
    Verifica si un jugador tiene 'Control de Sistema' (> 50% de planetas).
    LEGACY: Usar recalculate_system_ownership para actualizar la DB automáticamente.
    """
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
            # V9.1: Trigger automático de Sistema
            # Necesitamos el system_id para el recálculo
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
            # CASO 1: Transformación (Planeta ya poblado de sectores pero sin Urbano)
            if existing_sectors:
                # Buscar candidato: Primer sector NO orbital
                candidate = next((s for s in existing_sectors if s.get("sector_type") != SECTOR_TYPE_ORBITAL), None)
                
                if candidate:
                    # Definir slots
                    u_slots = SECTOR_SLOTS_CONFIG.get(SECTOR_TYPE_URBAN, 3)
                    
                    # Ejecutar Update
                    try:
                        res = db.table("sectors").update({
                            "sector_type": SECTOR_TYPE_URBAN,
                            "name": "Distrito Central",
                            "max_slots": u_slots,
                            # "is_known": True # Dejamos que claim_genesis_sector lo haga o lo forzamos? 
                            # El prompt dice: "Actualiza el objeto en memoria".
                        }).eq("id", candidate["id"]).execute()
                        
                        if res and res.data:
                            # Actualizar en memoria
                            candidate["sector_type"] = SECTOR_TYPE_URBAN
                            candidate["name"] = "Distrito Central"
                            candidate["max_slots"] = u_slots
                            sectors_updated = True
                            # log_event no tiene player_id aqui, usamos print o log genérico si existiera
                    except Exception as e:
                        print(f"Error transformando sector {candidate['id']}: {e}")
            
            # CASO 2: Inicialización desde cero (Planeta vacío)
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

        # B. Verificar Orbital (Siempre debe existir con ID fijo 99)
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

        # C. Rellenar resto de sectores si estaba vacío (Solo si creamos el Urbano nuevo)
        # Si ya existían sectores (Caso 1), asumimos que la masa ya estaba cubierta.
        if not existing_sectors and sectors_to_create:
            target_count = PLANET_MASS_CLASSES.get(mass_class, 4)
            # Tenemos Urbano (index 1) y Orbital (index 99). 
            # Faltan (target_count - 1) sectores de superficie.
            
            valid_types = [SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN]
            
            # Generar IDs 2, 3, ...
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

        # Insertar nuevos
        if sectors_to_create:
            res = db.table("sectors").insert(sectors_to_create).execute()
            if res and res.data:
                existing_sectors.extend(res.data)
                sectors_updated = True # Marcar para forzar re-fetch
                
        # FIX FINAL (V7.6.1): Asegurar consistencia total si hubo cambios
        # La corrección crítica aquí es usar eq("planet_id", ...) NO eq("id", ...)
        # Y siempre devolver lo que está en DB para asegurar que Genesis Engine obtenga los datos frescos.
        if sectors_updated:
             final_check = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
             return final_check.data if final_check and final_check.data else []

        return existing_sectors

    except Exception as e:
        log_event(f"Error critical initializing sectors for planet {planet_id}: {e}", is_error=True)
        # Devolver lo que haya para no romper flujo
        try:
             return db.table("sectors").select("*").eq("planet_id", planet_id).execute().data or []
        except:
             return []

def claim_genesis_sector(sector_id: int, player_id: int) -> bool:
    """
    Marca un sector como conocido para el aterrizaje inicial (Génesis).
    NOTA V7.4: La tabla 'sectors' no tiene owner_id ni has_outpost.
    La propiedad se deriva de la presencia de edificios en el sector.
    Esta función solo asegura que el sector sea visible (is_known=True).
    """
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
    """
    Inserta el edificio inicial (HQ por defecto) para el Protocolo Génesis.
    Usa los valores de BUILDING_TYPES para pops_required y energy_consumption.
    """
    try:
        db = _get_db()

        # Obtener definición del edificio
        building_def = BUILDING_TYPES.get(building_type)
        if not building_def:
            log_event(f"Tipo de edificio desconocido: {building_type}", player_id, is_error=True)
            return False

        # Obtener tick actual para built_at_tick
        world = get_world_state()
        current_tick = world.get("current_tick", 1) if world else 1

        # Preparar datos del edificio
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
            log_event(
                f"Edificio inicial '{building_def.get('name', building_type)}' "
                f"construido en sector {sector_id} para jugador {player_id}",
                player_id
            )
            
            # --- V7.5.1: Asegurar Sincronización de Soberanía ---
            # Aunque create_planet_asset ya asignó los dueños, esto recalcula basado en el edificio real (HQ)
            # garantizando integridad total.
            asset = get_planet_asset_by_id(planet_asset_id)
            if asset:
                 update_planet_sovereignty(asset["planet_id"])
                 
            return True

        log_event(f"Fallo al insertar edificio inicial en sector {sector_id}", player_id, is_error=True)
        return False

    except Exception as e:
        log_event(f"Error crítico en add_initial_building: {e}", player_id, is_error=True)
        return False