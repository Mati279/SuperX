# core/genesis_engine.py
"""
Genesis Engine - Protocolo v1.5 "Infiltración Silenciosa"
Maneja la lógica de inicialización de nuevas facciones bajo reglas estrictas de topología y dotación.
"""

import random
from typing import Dict, Any, Tuple, List
from data.database import supabase
from data.log_repository import log_event
from core.world_constants import STAR_CLASSES

# --- CONSTANTES DEL PROTOCOLO 19.2 ---
GENESIS_XP = 3265
GENESIS_ATTR_POINTS = 60
GENESIS_SKILL_POINTS = 24
GENESIS_FEATS_COUNT = 2

INITIAL_CREDITS = 1000
INITIAL_INFLUENCE = 10
INITIAL_MATERIALS = 500
INITIAL_COMPONENTS = 200
INITIAL_ENERGY = 100

MIN_DIST_FACTION = 2
MIN_DIST_PLAYER = 5

def find_safe_starting_node() -> int:
    """
    19.1. Localización Inicial: Topología de Seguridad.
    Busca un sistema que cumpla D_faction >= 2 y D_player >= 5.
    
    Retorna:
        system_id (int) del nodo seguro encontrado.
    """
    # 1. Obtener todos los sistemas y sus ocupantes
    # (Asumimos que 'systems' tiene una columna 'owner_faction_id' o similar)
    response = supabase.table("systems").select("id, x, y, z, ocupado_por_faction_id").execute()
    all_systems = response.data
    
    # Filtrar sistemas vacíos y sin recursos de lujo (Regla 19.1 - Limitación Estratégica)
    # Nota: Si la regla de lujo es compleja, aquí simplificamos buscando sistemas "estándar".
    candidates = [s for s in all_systems if s['ocupado_por_faction_id'] is None]
    
    occupied_systems = [s for s in all_systems if s['ocupado_por_faction_id'] is not None]
    
    # Si no hay nadie, cualquier random sirve (primer jugador)
    if not occupied_systems:
        chosen = random.choice(candidates)
        return chosen['id']

    # 2. Filtrado por distancia (Algoritmo ingenuo de distancia Euclídea por ahora)
    # TODO: Para precisión exacta de "saltos", necesitaríamos BFS sobre la tabla 'starlanes'.
    # Usamos distancia euclídea como aproximación rápida: 1 salto ~ 10-15 unidades de mapa.
    
    safe_candidates = []
    
    for cand in candidates:
        is_safe = True
        c_pos = (cand['x'], cand['y'], cand['z'])
        
        for occ in occupied_systems:
            o_pos = (occ['x'], occ['y'], occ['z'])
            dist = ((c_pos[0]-o_pos[0])**2 + (c_pos[1]-o_pos[1])**2 + (c_pos[2]-o_pos[2])**2)**0.5
            
            # Aproximación: Si un salto es aprox 10u.
            # D_player >= 5 saltos -> dist >= 50u
            # D_faction >= 2 saltos -> dist >= 20u
            # Aquí asumimos que todos los ocupados son jugadores por simplicidad inicial.
            if dist < 50: 
                is_safe = False
                break
        
        if is_safe:
            safe_candidates.append(cand)
            
    if not safe_candidates:
        # Fallback: Si no hay sitio perfecto, el más lejano posible
        return random.choice(candidates)['id']
    
    return random.choice(safe_candidates)['id']


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
    
    points_left = GENESIS_ATTR_POINTS - 30 # Restamos los base 5*6
    
    # Repartir puntos restantes ponderados
    weights = ["inteligencia", "carisma", "sabiduria", "destreza", "constitucion", "fuerza"]
    while points_left > 0:
        attr = random.choice(weights[:3] if points_left > 20 else weights)
        if base_attrs[attr] < 18: # Cap suave
            base_attrs[attr] += 1
            points_left -= 1

    # Bonus de Nivel 5 (+1 Atributo)
    base_attrs["inteligencia"] += 1

    stats = {
        "nivel": 6,
        "xp": GENESIS_XP,
        "atributos": base_attrs,
        "habilidades": _generate_skills(GENESIS_SKILL_POINTS),
        "feats": ["Liderazgo Táctico", "Logística Avanzada"], # 2 Feats fijos o random
        "clase": "Comandante Operativo"
    }
    return stats

def _generate_skills(points: int) -> Dict[str, int]:
    """Distribuye puntos de habilidad buscando una Maestría."""
    skills = {"pilotaje": 0, "tactica": 0, "diplomacia": 0, "tecnologia": 0, "gestion": 0}
    
    # Regla 19.2.A: Probable habilidad Maestra (51-75 en escala d100, aquí usamos puntos directos)
    # Asumimos que 1 punto = 5% skill rating aprox para simplificar el modelo de datos.
    
    # Invertir fuerte en una principal
    master_skill = random.choice(["tactica", "gestion", "tecnologia"])
    skills[master_skill] = 10 # Rango alto
    points -= 10
    
    keys = list(skills.keys())
    while points > 0:
        k = random.choice(keys)
        if skills[k] < 10:
            skills[k] += 1
            points -= 1
            
    return skills

def apply_genesis_inventory(player_id: int):
    """
    19.2.B Inventario de Suministros (MMFR).
    """
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
    # Obtener conexiones desde starlanes
    try:
        response = supabase.table("starlanes").select("system_b_id").eq("system_a_id", start_system_id).execute()
        neighbors = [row['system_b_id'] for row in response.data]
        # Bideccionalidad
        response2 = supabase.table("starlanes").select("system_a_id").eq("system_b_id", start_system_id).execute()
        neighbors += [row['system_a_id'] for row in response2.data]
        
        for nid in set(neighbors):
            _grant_visibility(player_id, nid, level=2)
            
    except Exception as e:
        log_event(f"Error calculando vecinos FOW: {e}", player_id, is_error=True)

    # 3. Mapa Estelar Antiguo (20% Galaxia, NR-1)
    try:
        all_sys = supabase.table("systems").select("id").execute().data
        total = len(all_sys)
        ancient_map_count = int(total * 0.20)
        
        # Seleccionar random excluyendo los ya conocidos
        known = {start_system_id} | set(neighbors)
        candidates = [s['id'] for s in all_sys if s['id'] not in known]
        
        if candidates:
            selected = random.sample(candidates, k=min(ancient_map_count, len(candidates)))
            for sid in selected:
                _grant_visibility(player_id, sid, level=1)
                
    except Exception as e:
        log_event(f"Error generando mapa antiguo: {e}", player_id, is_error=True)

def _grant_visibility(player_id: int, system_id: int, level: int):
    """Inserta o actualiza el registro de exploración."""
    # Upsert en tabla de exploracion (asumida 'player_exploration')
    data = {"player_id": player_id, "system_id": system_id, "scan_level": level}
    supabase.table("player_exploration").upsert(data).execute()

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
            "motor": "Impulso Iónico Mk2 (Starlanes Only)", # Regla 19.4
            "sensores": "Matriz Fase II",
            "bodega": "Compacta"
        }
    }
    supabase.table("ships").insert(ship_data).execute()