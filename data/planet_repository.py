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
"""

from typing import Dict, List, Any, Optional, Tuple
import random 
from .database import get_supabase
from .log_repository import log_event
from .world_repository import get_world_state
from core.world_constants import (
    BUILDING_TYPES, 
    BASE_TIER_COSTS, 
    ECONOMY_RATES, 
    PLANET_MASS_CLASSES,
    SECTOR_SLOTS_CONFIG,
    SECTOR_TYPE_URBAN,
    SECTOR_TYPE_PLAIN,
    SECTOR_TYPE_MOUNTAIN,
    SECTOR_TYPE_INHOSPITABLE
)
from core.rules import calculate_planet_security


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


# --- CONSULTA DE PLANETAS (TABLA MUNDIAL) ---

def get_planet_by_id(planet_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene información de un planeta de la tabla mundial 'planets'.
    Actualizado V5.8: Recuperación explícita de population y breakdown.
    """
    try:
        response = _get_db().table("planets")\
            .select("id, name, system_id, biome, mass_class, orbital_ring, is_habitable, surface_owner_id, orbital_owner_id, is_disputed, security, population, security_breakdown, base_defense")\
            .eq("id", planet_id)\
            .single()\
            .execute()
        return response.data if response and response.data else None
    except Exception:
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
            "infraestructura_defensiva": 0,
            "base_tier": 1
        }
        
        response = db.table("planet_assets").insert(asset_data).execute()
        
        if response and response.data:
            # --- FIX CRÍTICO V6.1: Soporte dual para Float/Dict en Security ---
            sec_value = initial_security
            sec_breakdown = {}
            
            if isinstance(initial_security, dict):
                sec_value = initial_security.get("total", 20.0)
                sec_breakdown = initial_security
            
            # Sincronizar tabla PLANETS con desglose explícito
            # V6.3: Se actualiza surface_owner_id aquí inicialmente, pero update_planet_sovereignty lo confirmará luego
            db.table("planets").update({
                "surface_owner_id": player_id,
                "security": sec_value,
                "security_breakdown": sec_breakdown,
                "population": initial_population
            }).eq("id", planet_id).execute()
            
            # --- FAIL-SAFE DE SECTORES (V5.9) ---
            # Verificar si existen sectores. Si no, crear uno de emergencia.
            # NOTA: Genesis Engine V7.3 ahora maneja esto mejor, pero mantenemos el fallback.
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
            return response.data[0]
        return None
    except Exception as e:
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
            # Flag de UI para niebla
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

# --- V6.3: GESTIÓN DE SOBERANÍA Y CONSTRUCCIÓN ---

def update_planet_sovereignty(planet_id: int):
    """
    Recalcula y actualiza la soberanía de superficie y orbital basada en edificios.
    Soberanía Superficie: Dueño de HQ > Dueño único de Outposts > Null.
    Soberanía Orbital: Dueño de Orbital Station > Surface Owner (Default).
    """
    try:
        db = _get_db()
        
        # 1. Obtener todos los edificios del planeta (de todos los jugadores)
        # Necesitamos unir planet_buildings -> planet_assets para saber el planeta
        # Pero Supabase no permite joins complejos en delete/update triggers facilmente,
        # así que hacemos query manual.
        
        # Obtener todos los assets del planeta
        assets_res = db.table("planet_assets").select("id, player_id").eq("planet_id", planet_id).execute()
        if not assets_res or not assets_res.data:
            # Nadie en el planeta
            db.table("planets").update({"surface_owner_id": None, "orbital_owner_id": None}).eq("id", planet_id).execute()
            return

        assets = assets_res.data
        asset_ids = [a["id"] for a in assets]
        player_map = {a["id"]: a["player_id"] for a in assets}

        # Obtener edificios relevantes (HQ, Outpost, Orbital Station)
        buildings_res = db.table("planet_buildings")\
            .select("building_type, planet_asset_id")\
            .in_("planet_asset_id", asset_ids)\
            .execute()
        
        buildings = buildings_res.data if buildings_res and buildings_res.data else []

        hq_owner = None
        outpost_owners = set()
        orbital_station_owner = None

        for b in buildings:
            b_type = b.get("building_type")
            pid = player_map.get(b.get("planet_asset_id"))
            
            if b_type == "hq":
                hq_owner = pid # Asumimos uno solo o el ultimo gana (Regla: HQ en Urbano)
            elif b_type == "outpost":
                outpost_owners.add(pid)
            elif b_type == "orbital_station":
                orbital_station_owner = pid

        # Lógica de Soberanía Superficie
        new_surface_owner = None
        if hq_owner:
            new_surface_owner = hq_owner
        elif len(outpost_owners) == 1:
            new_surface_owner = list(outpost_owners)[0]
        else:
            # Nadie o disputa de outposts sin HQ
            new_surface_owner = None

        # Lógica de Soberanía Orbital
        new_orbital_owner = None
        if orbital_station_owner:
            new_orbital_owner = orbital_station_owner
        else:
            # Fallback a Surface Owner
            new_orbital_owner = new_surface_owner

        # Actualizar Planeta
        db.table("planets").update({
            "surface_owner_id": new_surface_owner,
            "orbital_owner_id": new_orbital_owner,
            # Reset disputa si hay dueño claro de superficie, o marcar disputa si hay multiples outposts?
            # Por ahora mantenemos is_disputed manual o por lógica de combate. 
            # Pero si hay HQs rivales (improbable por bloqueo) o Outposts rivales:
            "is_disputed": (hq_owner is None and len(outpost_owners) > 1)
        }).eq("id", planet_id).execute()

    except Exception as e:
        log_event(f"Error actualizando soberanía planet {planet_id}: {e}", is_error=True)


def build_structure(
    planet_asset_id: int,
    player_id: int,
    building_type: str,
    tier: int = 1,
    sector_id: Optional[int] = None 
) -> Optional[Dict[str, Any]]:
    """Construye validando espacio en sectores y reglas de bloqueo de facción (V6.3)."""
    if building_type not in BUILDING_TYPES: return None
    definition = BUILDING_TYPES[building_type]
    db = _get_db()

    try:
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return None
        planet_id = asset["planet_id"]

        # --- V6.3: Validaciones de Bloqueo y Unicidad ---
        
        # 0. Obtener todos los edificios del planeta para validaciones globales
        # (Esto podría optimizarse pero es seguro para consistencia)
        all_assets = db.table("planet_assets").select("id, player_id").eq("planet_id", planet_id).execute().data
        all_asset_ids = [a["id"] for a in all_assets]
        
        all_buildings = db.table("planet_buildings")\
            .select("sector_id, building_type, planet_asset_id")\
            .in_("planet_asset_id", all_asset_ids)\
            .execute().data or []

        # Mapa de dueños de edificios
        building_owners = {} # building_index -> player_id (No tenemos ID único aqui facil, usamos logica de sector)
        sector_occupants = {} # sector_id -> set(player_ids)
        
        has_orbital_station = False
        orbital_station_owner = None

        for b in all_buildings:
            owner = next((a["player_id"] for a in all_assets if a["id"] == b["planet_asset_id"]), None)
            sid = b.get("sector_id")
            bt = b.get("building_type")
            
            if sid:
                if sid not in sector_occupants: sector_occupants[sid] = set()
                sector_occupants[sid].add(owner)
            
            if bt == "orbital_station":
                has_orbital_station = True
                orbital_station_owner = owner

        # Regla 1: Bloqueo Orbital (Solo una estación por planeta, o al menos no de otro jugador si queremos exclusividad)
        # La regla dice: "verifica si ya existe una de otro jugador".
        if building_type == "orbital_station":
            if has_orbital_station and orbital_station_owner != player_id:
                log_event("Construcción bloqueada: Ya existe una Estación Orbital enemiga.", player_id, is_error=True)
                return None

        # 1. Recuperar Sectores
        sectors_res = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
        sectors = sectors_res.data if sectors_res and sectors_res.data else []
        if not sectors:
            log_event("No hay sectores en el planeta.", player_id, is_error=True)
            return None

        # Preparar contadores de slots (Solo de este jugador para limites, pero chequear ocupacion enemiga)
        my_buildings = [b for b in all_buildings if b["planet_asset_id"] == planet_asset_id]
        
        sector_counts = {}
        for b in my_buildings:
            sid = b.get("sector_id")
            bt = b.get("building_type")
            # V6.3: Solo contar si consume slots
            consumes = BUILDING_TYPES.get(bt, {}).get("consumes_slots", True)
            if sid and consumes: 
                sector_counts[sid] = sector_counts.get(sid, 0) + 1

        for s in sectors:
            if 'max_slots' in s: s['slots'] = s['max_slots']
            s['buildings_count'] = sector_counts.get(s["id"], 0)

        # 2. Selección de Sector Objetivo y Validación de Bloqueo Local
        target_sector = None
        
        if sector_id:
            matches = [s for s in sectors if s["id"] == sector_id]
            if matches: target_sector = matches[0]
        else:
            # Auto-asignación inteligente
            # Priorizar Urbano para HQ, o donde quepa
            allowed = definition.get("allowed_terrain", []) # Si es None/Empty asume todos menos prohibidos? 
            # Mejor usar lógica inversa: Si building tiene allowed_terrain explícito (HQ, Outpost), filtrar.
            
            candidates = []
            for s in sectors:
                # Chequeo de slots (si consume)
                if definition.get("consumes_slots", True) and s["buildings_count"] >= s["slots"]:
                    continue
                
                # Chequeo de terreno permitido (Simple check)
                # HQ -> Urbano
                # Outpost -> No Urbano, No Inhospito (Validar con lista de constants)
                # Otros -> No Inhospito
                
                # Implementación rápida de allowed_terrain si existe en definition
                if "allowed_terrain" in definition:
                    if s["sector_type"] not in definition["allowed_terrain"]:
                        # Caso especial: Resources maps to allowed names? 
                        # Simplificación: Chequear nombre o tipo.
                        # El sector_type en DB suele ser "Urbano", "Llanura", "Montañoso"
                        # o el nombre del recurso si es especial.
                        # Para Outpost: plain/mountain/resources.
                        pass # Asumimos que el front manda sector_id valido o filtramos aqui mejor
                
                # REGLA CRÍTICA V6.3: Bloqueo de Facción
                # Si el sector tiene ocupantes que NO son yo -> Bloqueado
                occupants = sector_occupants.get(s["id"], set())
                if any(occ != player_id for occ in occupants):
                    continue 

                candidates.append(s)
            
            # Priorizar Urbano si es HQ
            if building_type == "hq":
                urban = [s for s in candidates if s.get("sector_type") == 'Urbano']
                target_sector = urban[0] if urban else None
            else:
                target_sector = candidates[0] if candidates else None

        # Validación final del target
        if not target_sector:
            log_event("No hay sectores disponibles o válidos (Bloqueo/Espacio).", player_id, is_error=True)
            return None

        # Validación explícita de bloqueo en target seleccionado por ID
        occupants = sector_occupants.get(target_sector["id"], set())
        if any(occ != player_id for occ in occupants):
            log_event("Construcción fallida: Sector ocupado por otra facción.", player_id, is_error=True)
            return None
            
        # Validación de slots si fue por ID
        if definition.get("consumes_slots", True) and target_sector["buildings_count"] >= target_sector["slots"]:
             log_event("No hay espacio en el sector seleccionado.", player_id, is_error=True)
             return None

        # 3. Insertar Edificio
        world = get_world_state()
        building_data = {
            "planet_asset_id": planet_asset_id,
            "player_id": player_id,
            "building_type": building_type,
            "building_tier": tier,
            "sector_id": target_sector["id"],
            "is_active": True,
            "built_at_tick": world.get("current_tick", 1)
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
    """Actualiza la seguridad en lote en la tabla 'planets'."""
    if not updates: return True
    try:
        db = _get_db()
        for planet_id, security in updates:
            db.table("planets").update({"security": security}).eq("id", planet_id).execute()
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

# --- V4.3: CONTROL DEL SISTEMA ESTELAR ---

def check_system_majority_control(system_id: int, faction_id: int) -> bool:
    """Verifica si una facción tiene 'Control de Sistema'."""
    try:
        db = _get_db()
        
        all_planets_res = db.table("planets").select("id").eq("system_id", system_id).execute()
        all_planets = all_planets_res.data if all_planets_res and all_planets_res.data else []
        total_planets = len(all_planets)
        
        if total_planets == 0:
            return False
            
        my_planets_res = db.table("planets").select("id")\
            .eq("system_id", system_id)\
            .eq("surface_owner_id", faction_id)\
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
    """Actualiza la seguridad en la tabla 'planets'."""
    try:
        # V6.1: Persistencia explícita de breakdown
        response = _get_db().table("planets").update({
            "security": security,
            "security_breakdown": breakdown
        }).eq("id", planet_id).execute()
        return True if response else False
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
    Garantiza que un planeta tenga sectores inicializados.
    Crea siempre un sector Urbano y rellena el resto según tamaño y constantes.

    Args:
        planet_id: ID del planeta
        biome: Bioma del planeta (para nombres temáticos)
        mass_class: Clase de masa del planeta (determina cantidad de sectores)

    Returns:
        List[Dict]: Lista de sectores creados/existentes con sus IDs.
                    Lista vacía en caso de error crítico.
    """
    try:
        db = _get_db()
        # 1. Verificar existencia
        check = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
        if check and check.data:
            existing_sectors = check.data
            
            # --- FIX V7.4.1: Garantizar Sector Urbano para HQ ---
            # Si el planeta ya tenía sectores (por scripts de población o generación parcial)
            # pero ninguno es Urbano, el Protocolo Génesis fallaba.
            has_urban = any(s.get("sector_type") == SECTOR_TYPE_URBAN for s in existing_sectors)
            
            if not has_urban:
                urban_slots = SECTOR_SLOTS_CONFIG.get(SECTOR_TYPE_URBAN, 2)
                urban_sector = {
                    "planet_id": planet_id,
                    "name": "Distrito Central",
                    "sector_type": SECTOR_TYPE_URBAN,
                    "max_slots": urban_slots,
                    "is_known": False,
                    "resource_category": "influencia"
                }
                
                # Insertar y recuperar el ID generado
                res = db.table("sectors").insert(urban_sector).execute()
                if res and res.data:
                    existing_sectors.append(res.data[0])
            
            return existing_sectors

        # 2. Calcular cantidad y configuración
        num_sectors = PLANET_MASS_CLASSES.get(mass_class, 4)
        sectors_data = []

        # Sector 0: Distrito Central (Urbano) - Siempre presente para HQs
        urban_slots = SECTOR_SLOTS_CONFIG.get(SECTOR_TYPE_URBAN, 2)
        sectors_data.append({
            "planet_id": planet_id,
            "name": "Distrito Central",
            "sector_type": SECTOR_TYPE_URBAN,
            "max_slots": urban_slots,
            "is_known": False,
            "resource_category": "influencia"
        })

        # Sectores Adicionales: Mezcla segura de tipos básicos
        valid_types = [SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN]

        for i in range(1, num_sectors):
            sType = random.choice(valid_types)
            slots = SECTOR_SLOTS_CONFIG.get(sType, 3)

            # Ajuste simple de recursos según tipo
            res_cat = "materiales" if sType == SECTOR_TYPE_MOUNTAIN else "componentes"

            sectors_data.append({
                "planet_id": planet_id,
                "name": f"Sector {i+1} ({sType})",
                "sector_type": sType,
                "max_slots": slots,
                "is_known": False,
                "resource_category": res_cat
            })

        # 3. Inserción en lote con retorno de datos
        res = db.table("sectors").insert(sectors_data).execute()

        if res and res.data:
            return res.data  # Retornar sectores recién creados con sus IDs

        # Fallback: Intentar recuperar lo insertado
        fallback = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
        return fallback.data if fallback and fallback.data else []

    except Exception as e:
        log_event(f"Error critical initializing sectors for planet {planet_id}: {e}", is_error=True)
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

    Args:
        player_id: ID del jugador propietario
        planet_asset_id: ID del asset planetario (planet_assets.id)
        sector_id: ID del sector donde construir
        building_type: Tipo de edificio (default: 'hq')

    Returns:
        bool: True si la inserción fue exitosa, False en caso contrario
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
            return True

        log_event(f"Fallo al insertar edificio inicial en sector {sector_id}", player_id, is_error=True)
        return False

    except Exception as e:
        log_event(f"Error crítico en add_initial_building: {e}", player_id, is_error=True)
        return False