# scripts/migrate_planet_names.py (Completo)
import sys
import os
import time

# Configuración del path para incluir el directorio raíz del proyecto
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(project_root)

from data.database import get_supabase

def migrate_planet_names():
    """
    Script de migración para renombrar planetas según la convención:
    [Nombre del Sistema]-R[Anillo Orbital]
    Ejemplo: System-001-R3
    
    CORRECCIÓN: Incluye campos NOT NULL (system_id, biome, orbital_ring) 
    para satisfacer la validación de integridad de UPSERT.
    """
    print("🚀 Iniciando migración de nombres de planetas (Corregido)...")

    # 1. Conexión a Base de Datos
    db = get_supabase()
    if not db:
        print("❌ Error: No se pudo conectar a Supabase. Verifique sus credenciales.")
        return

    try:
        # 2. Obtener Sistemas (Diccionario {id: name} para búsqueda rápida)
        print("📥 Obteniendo datos de sistemas...")
        systems_response = db.table("systems").select("id, name").execute()
        systems = {sys['id']: sys['name'] for sys in systems_response.data}
        print(f"   - {len(systems)} sistemas cargados.")

        # 3. Obtener Planetas
        # Solicitamos todos los campos NOT NULL para evitar error 23502 durante el upsert
        print("📥 Obteniendo datos de planetas...")
        planets_response = db.table("planets").select("id, system_id, orbital_ring, name, biome").execute()
        planets = planets_response.data
        print(f"   - {len(planets)} planetas encontrados.")

        # 4. Calcular actualizaciones
        print("⚙️ Generando nuevos nombres...")
        updates = []
        unchanged_count = 0
        
        for p in planets:
            sys_id = p.get('system_id')
            sys_name = systems.get(sys_id)
            
            if not sys_name:
                print(f"⚠️ Advertencia: Planeta ID {p['id']} tiene system_id {sys_id} que no existe.")
                continue

            ring = p.get('orbital_ring')
            old_name = p.get('name')
            biome = p.get('biome') # Necesario para satisfacer NOT NULL
            
            # Nueva convención
            new_name = f"{sys_name}-R{ring}"
            
            if old_name != new_name:
                updates.append({
                    "id": p['id'],
                    "name": new_name,
                    # IMPORTANTE: Pasamos los campos NOT NULL originales para que el upsert sea válido
                    "system_id": sys_id,
                    "orbital_ring": ring,
                    "biome": biome
                })
            else:
                unchanged_count += 1

        print(f"   - {len(updates)} planetas requieren cambio de nombre.")
        print(f"   - {unchanged_count} planetas ya tienen el nombre correcto.")

        # 5. Ejecutar actualizaciones en lotes (Batch Update)
        if updates:
            print("💾 Aplicando cambios en la base de datos...")
            batch_size = 100
            total_updated = 0

            for i in range(0, len(updates), batch_size):
                batch = updates[i:i+batch_size]
                
                # Upsert ahora incluye system_id, orbital_ring y biome, evitando el error de constraint
                try:
                    db.table("planets").upsert(batch).execute()
                    total_updated += len(batch)
                    print(f"   ... Lote {i // batch_size + 1}: {len(batch)} actualizados (Total: {total_updated})")
                except Exception as batch_error:
                    print(f"❌ Error en lote {i // batch_size + 1}: {batch_error}")
                    # Opcional: Intentar continuar o romper según preferencia
                    # break 
                
                time.sleep(0.1)

            print("✅ Migración completada exitosamente.")
        else:
            print("✨ No se requieren cambios en la base de datos.")

    except Exception as e:
        print(f"❌ Error crítico durante la migración: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_planet_names()