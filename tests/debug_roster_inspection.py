
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.character_repository import get_all_player_characters
from ui.logic.roster_logic import build_location_index, get_assigned_entity_ids, get_prop
from data.unit_repository import get_units_by_player

from data.database import get_supabase

def  get_active_player_id():
    db = get_supabase()
    # Get player with most characters
    res = db.table("characters").select("player_id", count="exact").execute()
    # This just counts total, we need a player ID.
    
    # Get all players - select only ID to avoid schema errors
    players = db.table("players").select("id").execute().data
    print(f"Players found: {len(players)}")
    
    for p in players:
        pid = p['id']
        count = db.table("characters").select("id", count="exact").eq("player_id", pid).execute().count
        print(f"Player {pid}: {count} characters")
        if count > 0:
            return pid
    return 1

PLAYER_ID = get_active_player_id()
print(f"Selected Player ID: {PLAYER_ID}")

def debug_roster():
    print(f"--- Debugging Roster for Player {PLAYER_ID} ---")
    
    chars = get_all_player_characters(PLAYER_ID)
    print(f"Total Characters: {len(chars)}")
    
    units = get_units_by_player(PLAYER_ID)
    print(f"Total Units: {len(units)}")
    
    assigned_chars, assigned_troops = get_assigned_entity_ids(units)
    print(f"Assigned Chars: {len(assigned_chars)} IDs: {assigned_chars}")
    
    active_chars = [c for c in chars if get_prop(c, "status_id") != "CANDIDATE"] # Assuming status_id checks
    print(f"Active Characters (Not Candidate): {len(active_chars)}")

    print("\n--- Inspecting Characters ---")
    for c in active_chars:
        cid = get_prop(c, "id")
        name = get_prop(c, "nombre")
        loc = get_prop(c, "location")
        stats_loc = get_prop(c, "stats_json", {}).get("estado", {}).get("ubicacion")
        
        print(f"ID: {cid} | Name: {name}")
        print(f"  > Location Prop: {loc} (Type: {type(loc)})")
        print(f"  > Stats JSON Location: {stats_loc}")
        print(f"  > Assigned? {cid in assigned_chars}")
        
    print("\n--- Building Index ---")
    index = build_location_index(active_chars, units, assigned_chars)
    
    print(f"Unlocated in Index: {len(index.get('unlocated', []))}")
    print(f"Systems Presence: {index.get('systems_presence')}")
    print(f"Space Forces keys: {index.get('space_forces', {}).keys()}")
    
    for u in index.get("unlocated", []):
        print(f"  -> Unlocated Item: {get_prop(u, 'nombre')} (Type: {get_prop(u, 'entity_type')})")

if __name__ == "__main__":
    try:
        debug_roster()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
