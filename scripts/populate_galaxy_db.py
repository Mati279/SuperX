# data/scripts/populate_galaxy_db.py (Completo)
import sys
import os

# Ajuste de path para encontrar módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.galaxy_generator import GalaxyGenerator
from data.database import get_supabase
from data.log_repository import log_event

def populate_galaxy():
    print("🌌 Iniciando generación completa de galaxia...")
    
    # 1. Generar en memoria
    generator = GalaxyGenerator(seed=12345, num_systems=60) 
    galaxy = generator.generate_galaxy()
    
    print(f"✅ Galaxia generada en memoria: {len(galaxy.systems)} sistemas, {len(galaxy.starlanes)} starlanes.")

    # 2. Conectar a DB
    db = get_supabase()
    if not db:
        print("❌ Error: No se pudo conectar a Supabase.")
        return

    # 3. Limpieza (Opcional, descomentar si se quiere resetear todo)
    print("🧹 Limpiando tablas antiguas (Sistemas, Planetas, Sectores)...")
    try:
        # Borramos starlanes primero por FKs
        db.table("starlanes").delete().neq("id", 0).execute()
        # Borramos sectores (si existe tabla) y planetas
        # Nota: Si la tabla sectors no existe, esto fallará, pero es necesario para limpieza completa
        try:
            db.table("sectors").delete().neq("id", 0).execute()
        except:
            pass # Ignorar si tabla no existe aún
        db.table("planets").delete().neq("id", 0).execute()
        db.table("systems").delete().neq("id", 0).execute()
    except Exception as e:
        print(f"⚠️ Advertencia durante limpieza: {e}")

    # 4. Insertar Sistemas
    print("🚀 Insertando sistemas...")
    systems_data = []
    for sys_obj in galaxy.systems:
        systems_data.append({
            "id": sys_obj.id,
            "name": sys_obj.name,
            "x": sys_obj.x,
            "y": sys_obj.y,
            "star_type": sys_obj.star.class_type,
            "description": sys_obj.description or "Sistema inexplorado",
            "controlling_faction_id": sys_obj.controlling_faction_id
        })
    
    if systems_data:
        db.table("systems").upsert(systems_data).execute()

    # 5. Insertar Planetas y Recolectar Sectores
    print("🪐 Insertando planetas y sectores...")
    planets_data = []
    sectors_data = []

    for sys_obj in galaxy.systems:
        for p in sys_obj.planets:
            # Mapeo del objeto Planet a la tabla planets corregida
            planets_data.append({
                "id": p.id,
                "system_id": p.system_id,
                "name": p.name,
                "orbital_ring": p.orbital_ring,
                "biome": p.biome,
                "mass_class": p.mass_class,
                "population": p.population,
                "base_defense": p.base_defense,
                "security": p.security,
                "is_habitable": p.is_habitable,
                "is_known": False,
                "max_sectors": p.max_sectors,
                "slots": 0 # Legacy field
            })
            
            # Recolectar sectores de este planeta
            for s in p.sectors:
                sectors_data.append({
                    "id": s.id,
                    "planet_id": p.id,
                    "name": s.name,
                    "sector_type": s.type,
                    "max_slots": s.max_slots,
                    "resource_category": s.resource_category,
                    "luxury_resource": s.luxury_resource,
                    "is_known": s.is_known
                })

    # Insertar Planetas por lotes para evitar timeouts
    batch_size = 100
    for i in range(0, len(planets_data), batch_size):
        batch = planets_data[i:i+batch_size]
        db.table("planets").upsert(batch).execute()
        print(f"   ... Insertados planetas {i} a {i+len(batch)}")

    # 6. Insertar Sectores
    print(f"🏗️ Insertando {len(sectors_data)} sectores...")
    for i in range(0, len(sectors_data), batch_size):
        batch = sectors_data[i:i+batch_size]
        db.table("sectors").upsert(batch).execute()
        print(f"   ... Insertados sectores {i} a {i+len(batch)}")

    # 7. Insertar Starlanes
    print("🔗 Insertando starlanes...")
    starlanes_db = []
    for source, target in galaxy.starlanes:
        # Ordenar IDs para evitar duplicados A-B vs B-A si la tabla tiene unique constraint
        id_a, id_b = sorted((source, target))
        starlanes_db.append({
            "system_a_id": id_a,
            "system_b_id": id_b
        })
    
    if starlanes_db:
        # Usamos on_conflict ignore o upsert según configuración de tabla
        try:
            db.table("starlanes").upsert(starlanes_db).execute()
        except Exception as e:
            print(f"⚠️ Error insertando starlanes (posibles duplicados): {e}")

    log_event(f"Generación completa: {len(systems_data)} Sis, {len(planets_data)} Plan, {len(sectors_data)} Sec.")
    print("✨ Proceso finalizado exitosamente.")

if __name__ == "__main__":
    populate_galaxy()