# scripts/populate_galaxy_db.py
import random
import time
from typing import List, Dict, Any
from data.database import supabase
from core.galaxy_generator import GalaxyGenerator
from data.player_repository import register_player_account

# Constantes demográficas locales para la generación
MIN_POPULATION_PLANET = 500_000
MAX_POPULATION_PLANET = 10_000_000_000 # 10 Billones

def apply_demographic_distribution():
    """
    Recorre todos los sistemas y aplica la lógica de población a los planetas.
    Regla:
    - 1 Planeta garantizado con población por sistema.
    - Resto: 30% probabilidad de tener población.
    - Rango: 500k a 10B.
    """
    print("👥 Aplicando distribución demográfica (Post-Generation)...")
    
    # 1. Obtener todos los sistemas
    systems_res = supabase.table("systems").select("id").execute()
    systems = systems_res.data if systems_res.data else []
    
    updates_count = 0
    
    for system in systems:
        sys_id = system['id']
        
        # Obtener planetas del sistema
        planets_res = supabase.table("planets").select("id, name").eq("system_id", sys_id).execute()
        planets = planets_res.data if planets_res.data else []
        
        if not planets:
            continue
            
        # Elegir el garantizado
        guaranteed_planet = random.choice(planets)
        
        for planet in planets:
            should_have_pop = (planet['id'] == guaranteed_planet['id']) or (random.random() < 0.30)
            
            if should_have_pop:
                # Generar población
                pop_amount = random.randint(MIN_POPULATION_PLANET, MAX_POPULATION_PLANET)
                
                # Actualizar DB
                # Nota: Hacemos update individual para simplicidad del script admin.
                # Si son 1000 sistemas tomará un momento, pero es seguro.
                supabase.table("planets").update({"poblacion": pop_amount}).eq("id", planet['id']).execute()
                updates_count += 1
                
    print(f"✅ Demografía aplicada. {updates_count} planetas habitados actualizados.")

def populate_database():
    print("🚀 Iniciando población de la galaxia...")
    
    # 1. Generar Sistemas y Planetas (Lógica existente)
    print("✨ Generando sistemas estelares...")
    generator = GalaxyGenerator(seed=1234, num_systems=50)
    # Esto inserta los planetas con population = 0 (default)
    #python -m scripts.populate_galaxy_dbgalaxy = generator.generate_galaxy()
    
    # 2. Aplicar Demografía (Nueva Lógica)
    # Como GalaxyGenerator no tiene la lógica de población, la aplicamos ahora sobre los datos insertados.
    apply_demographic_distribution()
    
    # 3. Crear Jugadores de Prueba (Bots)
    print("🤖 Creando facciones de prueba...")
    test_factions = [
        ("Imperio Solari", "Solari"),
        ("Republica Nova", "Nova"),
        ("Sindicato Q", "Q-Syn"),
        ("Alianza Estelar", "Starlance")
    ]
    
    for faction_name, user_prefix in test_factions:
        username = f"{user_prefix}_Cmd"
        pin = "1234"
        
        try:
            # Crear cuenta (register_player_account ya ejecuta génesis completo)
            # Genesis Engine sobreescribirá la población del asset del jugador con el valor "Fair Start" (1.5B+)
            player = register_player_account(username, pin, faction_name, None)
            if player:
                print(f"   ✅ Facción creada: {faction_name} (ID: {player['id']})")
                print(f"      📍 Base establecida correctamente.")
        except Exception as e:
            print(f"   ⚠️ Error creando {faction_name}: {e}")
            
    print("✅ Población completada.")

if __name__ == "__main__":
    populate_database()