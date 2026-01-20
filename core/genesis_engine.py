# core/genesis_engine.py
"""
Genesis Engine - Protocolo v2.0 "Asentamiento Seguro"
Maneja la lógica de inicialización de nuevas facciones.
Actualizado: Soporte para Población Decimal (1.0 = 1B).
"""

import random
from typing import Dict, Any, List
from data.database import supabase
from data.log_repository import log_event
from core.world_constants import STAR_TYPES
from core.constants import MIN_ATTRIBUTE_VALUE

# --- CONSTANTES DEL PROTOCOLO ---
GENESIS_XP = 3265
GENESIS_ATTR_POINTS = 60
GENESIS_SKILL_POINTS = 24

INITIAL_CREDITS = 1000
INITIAL_INFLUENCE = 10
INITIAL_MATERIALS = 500
INITIAL_COMPONENTS = 200
INITIAL_ENERGY = 100

# Población Inicial Jugador (Decimal: Billones)
# Rango: 1.50B a 1.70B
GENESIS_POP_MIN = 1.50
GENESIS_POP_MAX = 1.70

MIN_DIST_PLAYER = 45.0  
MIN_DIST_FACTION = 30.0 

BASE_NAMES_PREFIX = ["Puesto", "Fuerte", "Colonia", "Base", "Estación", "Nexo", "Avanzada", "Ciudadela"]
BASE_NAMES_SUFFIX = ["Alpha", "Prime", "Zero", "Nova", "Aegis", "Vanguard", "Origin", "Zenith"]

def genesis_protocol(player_id: int) -> bool:
    try:
        log_event("Iniciando Protocolo Génesis...", player_id)
        system_id = find_safe_starting_node()
        
        response_planets = supabase.table("planets").select("id, name, biome").eq("system_id", system_id).execute()
        
        if not response_planets.data:
            log_event(f"⚠ Sistema {system_id} vacío. Buscando respaldo...", player_id, is_error=True)
            fallback = supabase.table("planets").select("id, name, system_id").limit(1).single().execute()
            if not fallback.data: return False
            target_planet = fallback.data
            system_id = target_planet['system_id'] 
        else:
            target_planet = random.choice(response_planets.data)
        
        base_name = f"{random.choice(BASE_NAMES_PREFIX)} {random.choice(BASE_NAMES_SUFFIX)}"

        # Asignar población inicial decimal
        initial_pop = round(random.uniform(GENESIS_POP_MIN, GENESIS_POP_MAX), 2)

        asset_data = {
            "player_id": player_id,
            "system_id": system_id,
            "planet_id": target_planet['id'],
            "nombre_asentamiento": base_name,
            "poblacion": initial_pop,
            "pops_activos": initial_pop,
            "pops_desempleados": 0.0,
            "seguridad": 1.0,
            "infraestructura_defensiva": 0,
            "felicidad": 1.0
        }

        supabase.table("planet_assets").insert(asset_data).execute()
        apply_genesis_inventory(player_id)
        initialize_fog_of_war(player_id, system_id)
        
        log_event(f"✅ Protocolo Génesis completado. Base: {base_name}. Pob: {initial_pop}B", player_id)
        return True

    except Exception as e:
        log_event(f"❌ Error Crítico en Genesis Protocol: {e}", player_id, is_error=True)
        return False

def find_safe_starting_node() -> int:
    try:
        all_systems_res = supabase.table("systems").select("id, x, y").execute()
        all_systems = all_systems_res.data if all_systems_res.data else []
        if not all_systems: return 1 
        
        occupied_assets_res = supabase.table("planet_assets").select("system_id").execute()
        occupied_ids = {row['system_id'] for row in occupied_assets_res.data} if occupied_assets_res.data else set()
        
        if not occupied_ids:
            return random.choice(all_systems)['id']

        occupied_systems_data = [s for s in all_systems if s['id'] in occupied_ids]
        thresholds = [45.0, 35.0, 25.0, 15.0, 5.0]
        
        for current_threshold in thresholds:
            candidates = []
            for sys in all_systems:
                if sys['id'] in occupied_ids: continue 
                
                is_safe = True
                sys_pos = (sys['x'], sys['y'])
                for occ in occupied_systems_data:
                    occ_pos = (occ['x'], occ['y'])
                    dist = ((sys_pos[0]-occ_pos[0])**2 + (sys_pos[1]-occ_pos[1])**2)**0.5
                    if dist < current_threshold:
                        is_safe = False
                        break
                
                if is_safe: candidates.append(sys)
            
            if candidates:
                return random.choice(candidates)['id']

        available = [s for s in all_systems if s['id'] not in occupied_ids]
        if available: return random.choice(available)['id']
        return random.choice(all_systems)['id']

    except Exception as e:
        print(f"Error calculando nodo seguro: {e}")
        return 1

def apply_genesis_inventory(player_id: int):
    from data.player_repository import update_player_resources
    resources = {
        "creditos": INITIAL_CREDITS,
        "influencia": INITIAL_INFLUENCE,
        "materiales": INITIAL_MATERIALS,
        "componentes": INITIAL_COMPONENTS,
        "celulas_energia": INITIAL_ENERGY
    }
    update_player_resources(player_id, resources)

def initialize_fog_of_war(player_id: int, start_system_id: int):
    _grant_visibility(player_id, start_system_id, level=4)
    try:
        response_a = supabase.table("starlanes").select("system_b_id").eq("system_a_id", start_system_id).execute()
        neighbors = [row['system_b_id'] for row in response_a.data] if response_a.data else []
        response_b = supabase.table("starlanes").select("system_a_id").eq("system_b_id", start_system_id).execute()
        neighbors += [row['system_a_id'] for row in response_b.data] if response_b.data else []
        
        for nid in set(neighbors):
            _grant_visibility(player_id, nid, level=2)
    except Exception as e:
        log_event(f"Error calculando vecinos FOW: {e}", player_id, is_error=True)

def _grant_visibility(player_id: int, system_id: int, level: int):
    try:
        data = {"player_id": player_id, "system_id": system_id, "scan_level": level}
        supabase.table("player_exploration").upsert(data, on_conflict="player_id, system_id").execute()
    except Exception as e:
        print(f"Error granting visibility: {e}")

def generate_genesis_commander_stats(name: str) -> Dict[str, Any]:
    v = MIN_ATTRIBUTE_VALUE
    stats = {
        "nivel": 6,
        "xp": GENESIS_XP,
        "atributos": {"fuerza": v, "agilidad": v, "tecnica": v, "intelecto": v, "voluntad": v, "presencia": v},
        "habilidades": {"tactica": 10},
        "clase": "Comandante"
    }
    return stats