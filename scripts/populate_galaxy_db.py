# scripts/populate_galaxy_db.py
import random
import time
from data.database import supabase
from core.galaxy_generator import GalaxyGenerator
from data.player_repository import register_player_account

def populate_database():
    print("🚀 Iniciando población de la galaxia...")
    
    # 1. Generar Sistemas y Planetas (Lógica existente)
    print("✨ Generando sistemas estelares...")
    generator = GalaxyGenerator(seed=1234, num_systems=50)
    galaxy = generator.generate_galaxy()
    
    # ... (Aquí iría tu lógica de inserción de sistemas/planetas si la tienes separada
    # o si usas el generador para insertarlos directamente)
    # Asumiendo que ya tienes sistemas cargados o que este script los carga:
    
    # 2. Crear Jugadores de Prueba (Bots)
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
            player = register_player_account(username, pin, faction_name, None)
            if player:
                print(f"   ✅ Facción creada: {faction_name} (ID: {player['id']})")
                print(f"      📍 Base establecida correctamente.")
        except Exception as e:
            print(f"   ⚠️ Error creando {faction_name}: {e}")
            
    print("✅ Población completada.")

if __name__ == "__main__":
    populate_database()