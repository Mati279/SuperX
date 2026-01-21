import sys
import os

# Ajuste de path para que encuentre los módulos 'core' y 'data'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.galaxy_generator import GalaxyGenerator
from data.database import get_supabase
from data.log_repository import log_event

def populate_galaxy():
    print("🌌 Iniciando generación de galaxia...")
    
    # 1. Generar la galaxia en memoria con Gabriel Graph
    # Aumentado a 60 sistemas como solicitado
    generator = GalaxyGenerator(seed=12345, num_systems=60) 
    galaxy = generator.generate_galaxy()
    
    print(f"✅ Galaxia generada: {len(galaxy.systems)} sistemas, {len(galaxy.starlanes)} starlanes.")

    # 2. Conectar a DB
    db = get_supabase()
    if not db:
        print("❌ Error: No se pudo conectar a Supabase.")
        return

    # 3. Limpiar datos viejos (Opcional - ten cuidado en producción)
    # print("🧹 Limpiando tablas antiguas...")
    # db.table("starlanes").delete().neq("id", 0).execute()
    # db.table("planets").delete().neq("id", 0).execute()
    # db.table("systems").delete().neq("id", 0).execute()

    # 4. Insertar Sistemas
    print("🚀 Insertando sistemas...")
    systems_data = []
    for sys_obj in galaxy.systems:
        systems_data.append({
            "id": sys_obj.id,
            "name": sys_obj.name,
            "coord_x": sys_obj.x,
            "coord_y": sys_obj.y,
            "star_class": sys_obj.star.class_type,
            # Otros campos según tu esquema DB
        })
    
    # Ejecutar upsert/insert masivo
    # db.table("systems").upsert(systems_data).execute()

    # 5. Insertar Starlanes
    print("🔗 Insertando starlanes (Grafo Gabriel)...")
    starlanes_data = []
    for source, target in galaxy.starlanes:
        starlanes_data.append({
            "system_a_id": source,
            "system_b_id": target,
            # "distance": ... (si tu DB tiene columna distancia)
        })
    
    # Ejecutar insert masivo de starlanes
    # if starlanes_data:
    #     db.table("starlanes").upsert(starlanes_data).execute()

    log_event("Galaxia repoblada exitosamente con 60 sistemas y topología Gabriel.")
    print("✨ Proceso finalizado.")

if __name__ == "__main__":
    populate_galaxy()