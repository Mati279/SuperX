# core/genesis_engine.py (Completo)
"""
Genesis Engine - Protocolo v4.2 "Fair Start"
Maneja la lógica de inicialización de nuevas facciones.
Actualizado: Estandarización de Población Inicial (1.50B - 1.70B).
Corrección V4.4: Escritura de seguridad en tabla 'planets' usando fórmula centralizada.
Corrección V4.5: Persistencia de 'population' en tabla global 'planets'.
Corrección V5.9: Fix crítico de nomenclatura 'poblacion' a 'population' en planet_assets.
Corrección V6.0: Fix de persistencia de seguridad (Race Condition con Triggers DB).
Corrección V6.1: Filtro estricto de Biomas Habitables en selección de planeta inicial.
Actualizado V7.2: Soporte para Niebla de Superficie (Descubrimiento automático de sector base).
Actualizado V7.3: Garantía de Inicialización de Sectores y Asignación de Distrito Central.
Actualizado V7.4: Construcción automática de Comando Central (HQ) en sector urbano inicial.
                  Fix claim_genesis_sector: Eliminadas columnas inexistentes (owner_id, has_outpost).
                  Recuperación de planet_asset_id para vinculación correcta de edificios.
Actualizado V7.5: Fix Soberanía Inicial (Sincronización Orbital en Creación).
Actualizado V7.6: Estandarización de Planeta Inicial (Mass Class: Estándar).
Actualizado V7.7: Refactor integral para uso de create_planet_asset (Seguridad y Fail-safes).
Refactor V8.0: Eliminación de tripulación automática (Solo Start).
Refactor V11.0: Integración de initialize_player_base para creación de Base Militar en lugar de 'hq' genérico.
"""

import random
import traceback
from typing import Dict, Any, List
from data.database import get_supabase
from data.log_repository import log_event
# Importación actualizada para V7.4 y V7.7
from data.planet_repository import (
    create_planet_asset, # V7.7 Importante
    grant_sector_knowledge,
    initialize_planet_sectors,
    claim_genesis_sector,
    add_initial_building,
    initialize_player_base, # V11.0: Nueva función para bases
    update_planet_sovereignty
)
from core.world_constants import STAR_TYPES, ECONOMY_RATES, HABITABLE_BIRTH_BIOMES, SECTOR_TYPE_URBAN
from core.constants import MIN_ATTRIBUTE_VALUE
from core.rules import calculate_planet_security, SECURITY_POP_MULT, RING_PENALTY

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
        
        target_planet = None
        system_id = None
        
        # 1. Búsqueda de Sistema y Planeta Habitable (Retry Logic)
        # Intentamos hasta 3 veces encontrar un sistema seguro que contenga planetas con biomas habitables.
        max_retries = 3
        for attempt in range(max_retries):
            # A. Encontrar sistema seguro
            candidate_system_id = find_safe_starting_node()
            
            # B. Obtener planetas del sistema (Updated V7.3: Include mass_class)
            response_planets = db.table("planets").select("id, name, biome, system_id, orbital_ring, base_defense, mass_class").eq("system_id", candidate_system_id).execute()
            
            # C. Filtrar candidatos por Bioma Habitable y Masa Estándar (Updated V7.6)
            candidates = []
            if response_planets.data:
                candidates = [
                    p for p in response_planets.data 
                    if p.get('biome') in HABITABLE_BIRTH_BIOMES and p.get('mass_class') == 'Estándar'
                ]
            
            if candidates:
                # Éxito: Seleccionamos uno de los planetas válidos
                target_planet = random.choice(candidates)
                system_id = candidate_system_id
                break 
            else:
                log_event(f"⚠ Sistema {candidate_system_id} descartado: Sin planetas habitables Estándar (Intento {attempt + 1}/{max_retries}).", player_id)

        # 2. Fallback Global si falla la búsqueda segura
        if not target_planet:
            log_event(f"⚠ No se encontró sistema seguro con biomas válidos. Ejecutando Fallback Global...", player_id, is_error=True)
            
            # Fallback: buscar explícitamente cualquier planeta con bioma habitable y masa Estándar en la BD
            # Updated V7.3: Include mass_class
            # Updated V7.6: Added .eq("mass_class", "Estándar")
            fallback = db.table("planets").select("id, name, biome, system_id, orbital_ring, base_defense, mass_class")\
                .in_("biome", HABITABLE_BIRTH_BIOMES)\
                .eq("mass_class", "Estándar")\
                .limit(10).execute()
            
            if not fallback.data: 
                error_msg = "❌ CRITICAL: No existen planetas habitables de clase 'Estándar' en la base de datos."
                print(error_msg)
                log_event(error_msg, player_id, is_error=True)
                return False
                
            target_planet = random.choice(fallback.data)
            system_id = target_planet['system_id']
        
        # Generar nombre de base
        base_name = f"{random.choice(BASE_NAMES_PREFIX)} {random.choice(BASE_NAMES_SUFFIX)}"

        # 3. Calcular Población y Creación de Asset
        # Asignar población inicial decimal (1.5 - 1.7 Billones)
        initial_pop = round(random.uniform(GENESIS_POP_MIN, GENESIS_POP_MAX), 2)
        
        # --- REFACTOR V7.7: Usar repositorio centralizado ---
        # Delegamos la creación, cálculo de seguridad y actualizaciones de planetas al repositorio
        # Esto activa los fail-safes de sectores y triggers de base de datos correctamente.
        
        created_asset = create_planet_asset(
            planet_id=target_planet['id'],
            system_id=system_id,
            player_id=player_id,
            settlement_name=base_name,
            initial_population=initial_pop
        )

        if not created_asset:
            log_event("❌ Error crítico: No se pudo crear el asset planetario mediante create_planet_asset.", player_id, is_error=True)
            return False

        planet_asset_id = created_asset['id']
        
        # Recuperar seguridad calculada por el repositorio para logging (opcional)
        # La función create_planet_asset ya maneja el update de soberanía y seguridad en tabla 'planets'.
        log_event(f"Asset planetario creado con ID: {planet_asset_id}. Población: {initial_pop}B", player_id)
        
        # 4. Inventario y FOW
        apply_genesis_inventory(player_id)
        initialize_fog_of_war(player_id, system_id)

        # --- V7.4 / V11.0: Descubrimiento, Asignación de Sector y Base Inicial ---
        try:
            # A. Garantizar existencia de sectores (Inicialización Lazy)
            # Usamos mass_class del select anterior, default a 'Estándar' si falta
            p_mass = target_planet.get('mass_class') or 'Estándar'
            sectors = initialize_planet_sectors(target_planet['id'], target_planet.get('biome', 'Templado'), p_mass)

            # B. Identificar Sector Urbano (Distrito Central)
            landing_sector = next((s for s in sectors if s.get('sector_type') == SECTOR_TYPE_URBAN), None)

            if landing_sector:
                landing_sector_id = landing_sector['id']

                # C. Reclamar Sector (Marca is_known=True)
                claim_result = claim_genesis_sector(landing_sector_id, player_id)

                # D. Descubrir Sector (Niebla - player_sector_knowledge)
                grant_sector_knowledge(player_id, landing_sector_id)

                # E. Construir BASE MILITAR Inicial (V11.0)
                # Reemplazamos 'add_initial_building(..., 'hq')' por la nueva función
                base_result = initialize_player_base(
                    player_id=player_id,
                    planet_id=target_planet['id'],
                    sector_id=landing_sector_id
                )

                if claim_result and base_result:
                    log_event(
                        f"✅ Sector Urbano {landing_sector_id} asignado con Base Militar "
                        f"para jugador {player_id} (Asset: {planet_asset_id})",
                        player_id
                    )
                else:
                    log_event(
                        f"⚠ Advertencia: Sector {landing_sector_id} parcialmente configurado "
                        f"(claim={claim_result}, base={base_result})",
                        player_id,
                        is_error=True
                    )
            else:
                # Error Crítico: initialize_planet_sectors debería haber creado uno
                log_event("❌ CRITICAL: No se encontró Sector Urbano tras inicialización.", player_id, is_error=True)

        except Exception as e:
            log_event(f"Error inicializando sectores/base inicial: {e}", player_id, is_error=True)
            traceback.print_exc()

        # Finalización del protocolo
        log_event(f"✅ Protocolo Génesis completado. Base: {base_name}. Pob: {initial_pop}B. (Bioma: {target_planet.get('biome', 'Unknown')})", player_id)
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