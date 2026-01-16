# scripts/populate_galaxy_db.py
import sys
import os

# Ajustar path para que encuentre los módulos 'core' y 'data'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.galaxy_generator import get_galaxy
from core.world_models import Planet, AsteroidBelt
from data.database import supabase
import math

def populate_galaxy():
    print("🌌 Iniciando materialización de la galaxia en Supabase...")
    
    # 1. Obtener la galaxia generada por Python
    galaxy = get_galaxy()
    systems = galaxy.systems
    
    print(f"🔭 Procesando {len(systems)} sistemas estelares...")

    for sys_obj in systems:
        # --- A. Insertar SISTEMA ---
        system_data = {
            "name": sys_obj.name,
            "x": sys_obj.position[0],
            "y": sys_obj.position[1],
            "z": 0, # El generador actual es 2D (x,y), z=0 por defecto
            "star_class": sys_obj.star.class_type,
            "ocupado_por_faction_id": None
        }
        
        # Insertar y recuperar el ID generado por la DB
        try:
            res = supabase.table("systems").insert(system_data).execute()
            if not res.data:
                print(f"❌ Error insertando sistema {sys_obj.name}")
                continue
            
            db_system_id = res.data[0]['id']
            print(f"   ⭐ Sistema {sys_obj.name} creado (ID: {db_system_id})")

            # --- B. Insertar CONTENIDO ORBITAL (Planetas) ---
            for ring, body in sys_obj.orbital_rings.items():
                if body is None:
                    continue

                if isinstance(body, Planet):
                    planet_data = {
                        "system_id": db_system_id,
                        "name": body.name,
                        "biome": body.biome,
                        "planet_size": body.size,
                        "orbital_ring": ring,
                        "construction_slots": body.construction_slots,
                        "resources": body.resources, # Supabase guarda JSON arrays automáticamente
                        "bonuses": {"desc": body.bonuses, "maintenance": body.maintenance_mod}
                    }
                    supabase.table("planets").insert(planet_data).execute()
                
                # (Opcional) Si quieres guardar cinturones de asteroides, 
                # necesitarías una tabla 'asteroid_belts' o usar la de planets con otro tipo.
                # Por ahora el SQL schema solo tenía 'planets'.

        except Exception as e:
            print(f"🔥 Error crítico en sistema {sys_obj.name}: {e}")

    # --- C. Generar RUTAS ESTELARES (Starlanes) ---
    print("🔗 Generando Rutas de Hiperespacio (Starlanes)...")
    # Recuperamos todos los sistemas con sus IDs reales de la DB
    all_systems_db = supabase.table("systems").select("id, x, y").execute().data
    
    connections_created = 0
    MAX_DISTANCE = 150.0 # Distancia máxima para conectar dos sistemas

    for i, sys_a in enumerate(all_systems_db):
        for sys_b in all_systems_db[i+1:]: # Evitar duplicados y auto-conexiones
            # Calcular distancia Euclídea
            dist = math.sqrt((sys_a['x'] - sys_b['x'])**2 + (sys_a['y'] - sys_b['y'])**2)
            
            if dist <= MAX_DISTANCE:
                # Crear conexión bidireccional lógica (guardada una vez)
                lane_data = {
                    "system_a_id": sys_a['id'],
                    "system_b_id": sys_b['id'],
                    "distance": round(dist, 2),
                    "estado": "Estable"
                }
                supabase.table("starlanes").insert(lane_data).execute()
                connections_created += 1

    print(f"✅ Galaxia Materializada: {len(systems)} Sistemas, {connections_created} Rutas Estelares.")

if __name__ == "__main__":
    populate_galaxy()