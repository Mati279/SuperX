# scripts/fix_galaxy_population.py (Completo)
import random
from data.database import get_supabase

# --- CONFIGURACIÓN DEMOGRÁFICA (DECIMAL) ---
# Unidad: Billones (1.0 = 1,000,000,000)
MIN_POP = 1.00 
MAX_POP = 10.00
CHANCE_NON_GUARANTEED = 0.30

def fix_population():
    db = get_supabase()
    print("☢️  INICIANDO PROTOCOLO DE RE-POBLACIÓN (Escala Decimal)")
    print("======================================================")
    print(f"📊 Rango: {MIN_POP}B - {MAX_POP}B | Formato: Float con 2 decimales")
    
    # 1. Resetear TODA la población a 0.0
    # Refactor V5.7: Estandarización a 'population'
    print("🧹 PASO 1: Reset global a 0.0...")
    try:
        db.table("planets").update({"population": 0.0}).gt("id", 0).execute()
    except Exception as e:
        print(f"   ⚠️ Error en el reset masivo: {e}")

    # 2. Asignar nueva población
    print("\n🌱 PASO 2: Asignando valores aleatorios...")
    
    systems = db.table("systems").select("id").execute().data or []
    count_populated = 0
    
    for i, system in enumerate(systems):
        sys_id = system['id']
        planets = db.table("planets").select("id").eq("system_id", sys_id).execute().data or []
        
        if not planets: continue

        guaranteed_planet = random.choice(planets)
        
        for planet in planets:
            p_id = planet['id']
            is_guaranteed = (p_id == guaranteed_planet['id'])
            lucky_roll = (random.random() < CHANCE_NON_GUARANTEED)
            
            if is_guaranteed or lucky_roll:
                # Generar float aleatorio entre 1.00 y 10.00
                raw_val = random.uniform(MIN_POP, MAX_POP)
                # Redondear a 2 decimales (Ej: 3.45)
                pop_val = round(raw_val, 2)
                
                try:
                    # Refactor V5.7: Estandarización a 'population'
                    db.table("planets").update({"population": pop_val}).eq("id", p_id).execute()
                    count_populated += 1
                except Exception as e:
                    print(f"   ⚠️ Error update planeta {p_id}: {e}")

        if (i + 1) % 10 == 0:
            print(f"   ... Procesados {i + 1}/{len(systems)} sistemas", end="\r")

    print("\n" + "="*50)
    print("✅ RE-POBLACIÓN DECIMAL COMPLETADA")
    print(f"🪐 Planetas Habitados: {count_populated}")
    print("======================================================")

if __name__ == "__main__":
    fix_population()