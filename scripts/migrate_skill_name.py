# scripts/migrate_skill_name.py
"""
SCRIPT DE MIGRACIÓN MANUAL
Uso: Ejecutar una vez para renombrar 'Análisis de datos' a 'Recopilación de Información'
en todos los personajes existentes en la base de datos.
"""

from data.database import get_supabase
from data.log_repository import log_event

def migrate_skill_names():
    print("Iniciando migración de nombres de habilidades...")
    db = get_supabase()
    
    # 1. Obtener todos los personajes
    response = db.table("characters").select("id, nombre, stats_json").execute()
    
    if not response.data:
        print("No se encontraron personajes para migrar.")
        return

    updated_count = 0
    
    for char in response.data:
        char_id = char['id']
        stats = char.get('stats_json', {})
        skills = stats.get('habilidades', {})
        
        # Verificar si tienen la habilidad antigua
        if "Análisis de datos" in skills:
            print(f"Migrando personaje: {char['nombre']} (ID: {char_id})")
            
            # Obtener valor y borrar clave vieja
            val = skills.pop("Análisis de datos")
            
            # Asignar a clave nueva (si no existe ya)
            if "Recopilación de Información" not in skills:
                skills["Recopilación de Información"] = val
            
            # Guardar cambios en el objeto stats
            stats['habilidades'] = skills
            
            # Actualizar DB
            try:
                db.table("characters").update({"stats_json": stats}).eq("id", char_id).execute()
                updated_count += 1
            except Exception as e:
                print(f"Error actualizando ID {char_id}: {e}")
    
    print(f"Migración completada. Personajes actualizados: {updated_count}")
    log_event(f"MIGRACIÓN SISTEMA: {updated_count} personajes actualizados a nueva habilidad 'Recopilación de Información'.")

if __name__ == "__main__":
    migrate_skill_names()