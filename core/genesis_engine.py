# core/genesis_engine.py
"""
Genesis Engine - Protocolo v4.2 "Fair Start"
Maneja la lógica de inicialización de nuevas facciones.
Actualizado: Estandarización de Población Inicial (1.50B - 1.70B).
Actualizado: Generación de Tripulación Inicial (Level 5 + 2x Level 3) con conocimiento KNOWN.
"""

import random
import traceback
from typing import Dict, Any, List
from data.database import get_supabase
from data.log_repository import log_event
from core.world_constants import STAR_TYPES, ECONOMY_RATES
from core.constants import MIN_ATTRIBUTE_VALUE
from core.models import KnowledgeLevel
from services.character_generation_service import recruit_character_with_ai

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
# Rango Estricto V4.2: 1.50B a 1.70B
GENESIS_POP_MIN = 1.50
GENESIS_POP_MAX = 1.70

MIN_DIST_PLAYER = 45.0  
MIN_DIST_FACTION = 30.0 

BASE_NAMES_PREFIX = ["Puesto", "Fuerte", "Colonia", "Base", "Estación", "Nexo", "Avanzada", "Ciudadela"]
BASE_NAMES_SUFFIX = ["Alpha", "Prime", "Zero", "Nova", "Aegis", "Vanguard", "Origin", "Zenith"]

def _get_db():
    """Helper para obtener la instancia de BD de forma segura."""
    return get_supabase()

def genesis_protocol(player_id: int) -> bool:
    try:
        log_event("Iniciando Protocolo Génesis V4.2 (Fair Start)...", player_id)
        db = _get_db()
        
        # 1. Encontrar sistema seguro
        system_id = find_safe_starting_node()
        
        # 2. Seleccionar planeta aleatorio
        response_planets = db.table("planets").select("id, name, biome, system_id").eq("system_id", system_id).execute()
        
        if not response_planets.data:
            log_event(f"⚠ Sistema {system_id} vacío. Buscando respaldo...", player_id, is_error=True)
            # Fallback: buscar cualquier planeta
            fallback = db.table("planets").select("id, name, system_id").limit(1).execute()
            
            if not fallback.data: 
                print("❌ CRITICAL: No existen planetas en la base de datos.")
                return False
                
            target_planet = fallback.data[0]
            system_id = target_planet['system_id'] 
        else:
            target_planet = random.choice(response_planets.data)
        
        base_name = f"{random.choice(BASE_NAMES_PREFIX)} {random.choice(BASE_NAMES_SUFFIX)}"

        # 3. Calcular Población y Seguridad
        # Asignar población inicial decimal (1.5 - 1.7 Billones)
        initial_pop = round(random.uniform(GENESIS_POP_MIN, GENESIS_POP_MAX), 2)
        
        # Calcular Seguridad Inicial Dinámica (MMFR V2)
        # Fórmula: Base (25) + (Pop * 5)
        # Nota: En Genesis ignoramos el anillo orbital ya que no tenemos el dato preciso aquí, se ajustará en el primer tick
        sec_base = ECONOMY_RATES.get("security_base", 25.0)
        sec_pop = ECONOMY_RATES.get("security_per_1b_pop", 5.0)
        initial_security = sec_base + (initial_pop * sec_pop)
        
        # Clamp preventivo
        initial_security = max(1.0, min(initial_security, 100.0))

        asset_data = {
            "player_id": player_id,
            "system_id": system_id,
            "planet_id": target_planet['id'],
            "nombre_asentamiento": base_name,
            "poblacion": initial_pop,
            "pops_activos": initial_pop,
            "pops_desempleados": 0.0,
            "seguridad": initial_security, 
            "infraestructura_defensiva": 0
        }

        db.table("planet_assets").insert(asset_data).execute()
        
        # 4. Inventario y FOW
        apply_genesis_inventory(player_id)
        initialize_fog_of_war(player_id, system_id)

        # 5. Generación de Tripulación Inicial
        # Se comenta para mover la generación al UI manual ("Reunir personal")
        # _deploy_starting_crew(player_id, target_planet['id'])
        
        log_event(f"✅ Protocolo Génesis completado. Base: {base_name}. Pob: {initial_pop}B. Seg: {initial_security:.1f}", player_id)
        return True

    except Exception as e:
        print("\n💥 EXCEPCIÓN EN GENESIS PROTOCOL:")
        traceback.print_exc() 
        log_event(f"❌ Error Crítico en Genesis Protocol: {e}", player_id, is_error=True)
        return False

def find_safe_starting_node() -> int:
    try:
        db = _get_db()
        all_systems_res = db.table("systems").select("id, x, y").execute()
        all_systems = all_systems_res.data if all_systems_res.data else []
        if not all_systems: return 1 
        
        occupied_assets_res = db.table("planet_assets").select("system_id").execute()
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
        db = _get_db()
        response_a = db.table("starlanes").select("system_b_id").eq("system_a_id", start_system_id).execute()
        neighbors = [row['system_b_id'] for row in response_a.data] if response_a.data else []
        response_b = db.table("starlanes").select("system_a_id").eq("system_b_id", start_system_id).execute()
        neighbors += [row['system_a_id'] for row in response_b.data] if response_b.data else []
        
        for nid in set(neighbors):
            _grant_visibility(player_id, nid, level=2)
    except Exception as e:
        log_event(f"Error calculando vecinos FOW: {e}", player_id, is_error=True)

def _grant_visibility(player_id: int, system_id: int, level: int):
    try:
        data = {"player_id": player_id, "system_id": system_id, "scan_level": level}
        _get_db().table("player_exploration").upsert(data, on_conflict="player_id, system_id").execute()
    except Exception as e:
        print(f"Error granting visibility: {e}")

def _deploy_starting_crew(player_id: int, planet_id: int):
    """
    Genera la tripulación inicial (Oficial y Especialistas) con estado KNOWN.
    Esto evita que aparezcan como 'Desconocidos' en la UI.
    """
    try:
        log_event("🚀 Desplegando tripulación inicial de confianza...", player_id)
        
        # 1. Oficial Nivel 5 (Líder de escuadrón/Segundo al mando)
        recruit_character_with_ai(
            player_id=player_id,
            location_planet_id=planet_id,
            min_level=5,
            max_level=5,
            initial_knowledge_level=KnowledgeLevel.KNOWN
        )
        
        # 2. Dos Especialistas Nivel 3
        for _ in range(2):
            recruit_character_with_ai(
                player_id=player_id,
                location_planet_id=planet_id,
                min_level=3,
                max_level=3,
                initial_knowledge_level=KnowledgeLevel.KNOWN
            )
            
    except Exception as e:
        log_event(f"⚠️ Error desplegando tripulación inicial: {e}", player_id, is_error=True)

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