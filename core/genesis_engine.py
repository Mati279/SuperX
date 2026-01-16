# core/genesis_engine.py
"""
Genesis Engine - Protocolo v1.5 "Infiltración Silenciosa"
Maneja la lógica de inicialización de nuevas facciones bajo reglas estrictas de topología y dotación.
"""

import random
from typing import Dict, Any, List
from data.database import supabase
from data.log_repository import log_event
# CORRECCIÓN: Importamos STAR_TYPES en lugar de STAR_CLASSES
from core.world_constants import STAR_TYPES, STAR_RARITY_WEIGHTS

# --- CONSTANTES DEL PROTOCOLO 19.2 ---
GENESIS_XP = 3265
GENESIS_ATTR_POINTS = 60
GENESIS_SKILL_POINTS = 24

# Recursos iniciales (MMFR)
INITIAL_CREDITS = 1000
INITIAL_INFLUENCE = 10
INITIAL_MATERIALS = 500
INITIAL_COMPONENTS = 200
INITIAL_ENERGY = 100

# Topología de Seguridad
MIN_DIST_PLAYER = 50.0  # Aprox 5 saltos (asumiendo ~10u por salto)
MIN_DIST_FACTION = 20.0 # Aprox 2 saltos

def find_safe_starting_node() -> int:
    """
    19.1. Localización Inicial: Topología de Seguridad.
    Busca un sistema que cumpla con las distancias de seguridad respecto a otros jugadores.
    
    Retorna:
        system_id (int) del nodo seguro encontrado.
    """
    try:
        # 1. Obtener todos los sistemas
        response_sys = supabase.table("systems").select("id, x, y, z").execute()
        all_systems = response_sys.data if response_sys.data else []
        
        if not all_systems:
             log_event("❌ CRÍTICO: No se encontraron sistemas en la galaxia. Ejecuta populate_galaxy_db.py primero.", is_error=True)
             return 1

        # 2. Obtener sistemas ocupados (consultando planet_assets)
        response_assets = supabase.table("planet_assets").select("system_id, player_id").execute()
        occupied_map = {row['system_id']: row['player_id'] for row in response_assets.data} if response_assets.data else {}
        
        # Sistemas candidatos: Aquellos que NO están en el mapa de ocupados
        candidates = [s for s in all_systems if s['id'] not in occupied_map]
        
        # Si no hay nadie en el universo, elegimos uno random
        if not occupied_map:
            if candidates:
                return random.choice(candidates)['id']
            return all_systems[0]['id']

        # 3. Filtrado por distancia (Euclídea como aproximación de saltos)
        occupied_systems_data = [s for s in all_systems if s['id'] in occupied_map]
        safe_candidates = []
        
        for cand in candidates:
            is_safe = True
            c_pos = (cand['x'], cand['y'], cand['z'])
            
            for occ in occupied_systems_data:
                o_pos = (occ['x'], occ['y'], occ['z'])
                # Distancia Euclídea
                dist = ((c_pos[0]-o_pos[0])**2 + (c_pos[1]-o_pos[1])**2 + (c_pos[2]-o_pos[2])**2)**0.5
                
                # Verificamos D_player >= 5 saltos
                if dist < MIN_DIST_PLAYER: 
                    is_safe = False
                    break
            
            if is_safe:
                safe_candidates.append(cand)
                
        # Si encontramos candidatos seguros, elegimos uno. Si no, fallback al azar de los vacíos.
        if safe_candidates:
            return random.choice(safe_candidates)['id']
        elif candidates:
            return random.choice(candidates)['id']
        else:
            # Universo lleno (caso extremo), retornamos random de todos
            return random.choice(all_systems)['id']

    except Exception as e:
        log_event(f"Error calculando nodo seguro: {e}", is_error=True)
        # Fallback de emergencia
        return 1


def generate_genesis_commander_stats(name: str) -> Dict[str, Any]:
    """
    19.2.A Genera las estadísticas de un Comandante Nivel 6 (Operaciones).
    """
    # Distribución de atributos (60 puntos, costo progresivo simulado)
    # Priorizamos Inteligencia y Mando para un líder de célula.
    base_attrs = {
        "fuerza": 5, "destreza": 5, "constitucion": 5,
        "inteligencia": 5, "sabiduria": 5, "carisma": 5
    }
    
    points_left = GENESIS_ATTR_POINTS - 30 # Restamos los base 5*6 (30)
    
    # Repartir puntos restantes ponderados
    weights = ["inteligencia", "carisma", "sabiduria", "destreza", "constitucion", "fuerza"]
    
    # Simple algoritmo de reparto
    while points_left > 0:
        attr = random.choice(weights[:3] if points_left > 15 else weights)
        if base_attrs[attr] < 18: # Soft cap
            base_attrs[attr] += 1
            points_left -= 1

    # Bonus de Nivel 5 (+1 Atributo)
    base_attrs["inteligencia"] += 1

    stats = {
        "nivel": 6,
        "xp": GENESIS_XP,
        "atributos": base_attrs,
        "habilidades": _generate_skills(GENESIS_SKILL_POINTS),
        "feats": ["Liderazgo Táctico", "Logística Avanzada"],
        "clase": "Comandante Operativo"
    }
    return stats

def _generate_skills(points: int) -> Dict[str, int]:
    """Distribuye puntos de habilidad buscando una Maestría."""
    skills = {"pilotaje": 0, "tactica": 0, "diplomacia": 0, "tecnologia": 0, "gestion": 0}
    
    # Regla: Probable habilidad Maestra
    master_skill = random.choice(["tactica", "gestion", "tecnologia"])
    skills[master_skill] = 10 # Inversión fuerte inicial
    points -= 10
    
    keys = list(skills.keys())
    while points > 0:
        k = random.choice(keys)
        # Evitar subir demasiado las secundarias al inicio
        if skills[k] < 8:
            skills[k] += 1
            points -= 1
            
    return skills

def apply_genesis_inventory(player_id: int):
    """
    19.2.B Inventario de Suministros (MMFR).
    """
    # Importación LOCAL para evitar Circular Import con player_repository
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
    """
    19.3. Conocimiento Inicial (Visión Híbrida).
    """
    # 1. Sistema Natal (NR-4: Visibilidad Total)
    _grant_visibility(player_id, start_system_id, level=4)
    
    # 2. Sistemas Conectados (NR-2: Recursos Base)
    try:
        # Buscar conexiones donde A es el inicio
        response_a = supabase.table("starlanes").select("system_b_id").eq("system_a_id", start_system_id).execute()
        neighbors = [row['system_b_id'] for row in response_a.data] if response_a.data else []
        
        # Buscar conexiones donde B es el inicio (bidireccionalidad)
        response_b = supabase.table("starlanes").select("system_a_id").eq("system_b_id", start_system_id).execute()
        neighbors += [row['system_a_id'] for row in response_b.data] if response_b.data else []
        
        for nid in set(neighbors):
            _grant_visibility(player_id, nid, level=2)
            
    except Exception as e:
        log_event(f"Error calculando vecinos FOW: {e}", player_id, is_error=True)

    # 3. Mapa Estelar Antiguo (20% Galaxia, NR-1)
    try:
        response_all = supabase.table("systems").select("id").execute()
        all_sys = response_all.data if response_all.data else []
        
        if not all_sys: return

        total = len(all_sys)
        ancient_map_count = int(total * 0.20)
        
        # Excluir los ya conocidos
        known = {start_system_id} | set(neighbors)
        candidates = [s['id'] for s in all_sys if s['id'] not in known]
        
        if candidates:
            # Seleccionar muestra aleatoria
            selected = random.sample(candidates, k=min(ancient_map_count, len(candidates)))
            
            for sid in selected:
                _grant_visibility(player_id, sid, level=1)
                
    except Exception as e:
        log_event(f"Error generando mapa antiguo: {e}", player_id, is_error=True)

def _grant_visibility(player_id: int, system_id: int, level: int):
    """Inserta o actualiza el registro de exploración."""
    try:
        data = {"player_id": player_id, "system_id": system_id, "scan_level": level}
        # Upsert (insertar o actualizar si existe conflicto en player_id, system_id)
        supabase.table("player_exploration").upsert(data, on_conflict="player_id, system_id").execute()
    except Exception as e:
        print(f"Error granting visibility: {e}")

def grant_genesis_ship(player_id: int, system_id: int, character_id: int):
    """
    19.2.C Activo Aeroespacial: Nave Exploradora Tier II.
    """
    ship_data = {
        "player_id": player_id,
        "nombre": "Génesis-01",
        "clase": "Exploradora Tier II",
        "tipo_casco": "Corbeta Ligera",
        "ubicacion_system_id": system_id,
        "capitan_id": character_id,
        "estado": "Operativa",
        "integridad": 100,
        "modulos": {
            "motor": "Impulso Iónico Mk2 (Starlanes Only)", 
            "sensores": "Matriz Fase II",
            "bodega": "Compacta"
        }
    }
    supabase.table("ships").insert(ship_data).execute()