import sys
import os
import math

# --- HACK: Arreglar el path para que encuentre el módulo 'data' ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.database import supabase

SYSTEM_TABLE = 'systems'
STARLANE_TABLE = 'starlanes'

def calculate_distance(s1, s2):
    return math.sqrt((s1['x'] - s2['x'])**2 + (s1['y'] - s2['y'])**2)

def is_gabriel_edge(p1, p2, all_points):
    """
    Regla de Gabriel: Una conexión entre A y B es válida si y solo si
    el círculo que tiene a A-B como diámetro NO contiene ningún otro punto dentro.
    """
    # Centro del círculo entre p1 y p2
    mid_x = (p1['x'] + p2['x']) / 2
    mid_y = (p1['y'] + p2['y']) / 2
    
    # Radio al cuadrado (distancia del centro a p1)
    radius_sq = ((p1['x'] - mid_x)**2 + (p1['y'] - mid_y)**2)
    
    # Verificar si algún OTRO punto cae dentro de este círculo
    for other in all_points:
        if other['id'] == p1['id'] or other['id'] == p2['id']:
            continue
            
        dist_sq = (other['x'] - mid_x)**2 + (other['y'] - mid_y)**2
        
        # Si la distancia es menor (está estrictamente dentro), rompe la regla
        # Usamos un margen de error pequeño (epsilon) por float precision
        if dist_sq < radius_sq - 0.0001:
            return False
            
    return True

def recalibrate_gabriel():
    print("🌌 Iniciando protocolo de cartografía GABRIEL...")

    # 1. Obtener sistemas
    response = supabase.table(SYSTEM_TABLE).select("*").execute()
    systems = response.data

    if not systems or len(systems) < 2:
        print("❌ Error: Se necesitan al menos 2 sistemas.")
        return

    print(f"📍 Analizando geometría de {len(systems)} sistemas...")

    valid_lanes = []
    
    # 2. Fuerza bruta inteligente (Para 50-100 sistemas es instantáneo)
    # Comprobamos cada par posible contra la regla de Gabriel
    for i in range(len(systems)):
        for j in range(i + 1, len(systems)):
            s1 = systems[i]
            s2 = systems[j]
            
            if is_gabriel_edge(s1, s2, systems):
                valid_lanes.append({
                    'system_a_id': s1['id'],
                    'system_b_id': s2['id']
                })

    print(f"✨ Se han calculado {len(valid_lanes)} rutas estables.")
    print("   (El algoritmo de Gabriel garantiza conectividad sin cruces innecesarios)")

    # 3. Aplicar a la DB
    print("🔥 Borrando rutas antiguas...")
    supabase.table(STARLANE_TABLE).delete().neq('id', -1).execute()

    print("💾 Grabando nuevas rutas...")
    batch_size = 50
    for i in range(0, len(valid_lanes), batch_size):
        batch = valid_lanes[i:i + batch_size]
        supabase.table(STARLANE_TABLE).insert(batch).execute()

    print("✅ Red hiperespacial establecida.")

if __name__ == "__main__":
    recalibrate_gabriel()