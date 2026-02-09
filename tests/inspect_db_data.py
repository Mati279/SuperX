
from data.database import get_supabase
import json

def inspect_db():
    db = get_supabase()
    
    # 1. Get Active Player
    players = db.table("players").select("id").execute().data
    player_id = None
    for p in players:
        count = db.table("characters").select("id", count="exact").eq("player_id", p['id']).execute().count
        if count > 0:
            player_id = p['id']
            break
            
    if not player_id:
        print("No active player found.")
        return

    print(f"--- Inspecting Player {player_id} ---")

    # 2. Check Assets (Base)
    assets = db.table("planet_assets").select("*").eq("player_id", player_id).execute().data
    print(f"\n[Planet Assets] Found: {len(assets)}")
    for a in assets:
        print(f"  > ID: {a.get('id')} | Planet: {a.get('planet_id')} | System: {a.get('system_id')} | Name: {a.get('nombre_asentamiento')}")

    # 3. Check Characters details
    chars = db.table("characters").select("id, nombre, location, location_id, system_id, planet_id, sector_id").eq("player_id", player_id).execute().data
    print(f"\n[Characters] Found: {len(chars)}")
    for c in chars:
        print(f"  > ID: {c.get('id')} | Name: {c.get('nombre')}")
        print(f"    - location (json): {c.get('location')}")
        print(f"    - system_id (col): {c.get('system_id')}")
        print(f"    - planet_id (col): {c.get('planet_id')}")
        print(f"    - sector_id (col): {c.get('sector_id')}")

if __name__ == "__main__":
    try:
        inspect_db()
    except Exception as e:
        print(e)
