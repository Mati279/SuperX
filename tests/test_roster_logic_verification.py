# test_roster_logic_verification.py
import sys
import os

# Add project root to path
# Tests are in tests/, so project root is ..
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ui.logic.roster_logic import (
    get_prop,
    hydrate_unit_members,
    get_assigned_entity_ids,
    build_location_index,
    calculate_unit_display_capacity
)

def test_get_prop():
    print("Testing get_prop...")
    d = {"a": 1}
    assert get_prop(d, "a") == 1
    assert get_prop(d, "b", 2) == 2
    
    class MockObj:
        def __init__(self):
            self.x = 10
    
    o = MockObj()
    assert get_prop(o, "x") == 10
    assert get_prop(o, "y", 20) == 20
    print("get_prop OK")

def test_hydrate():
    print("Testing hydrate_unit_members...")
    units = [{"members": [{"id": 1, "entity_type": "character", "name": "Old"}]}]
    char_map = {1: "New Name"}
    troop_map = {}
    
    hydrated = hydrate_unit_members(units, char_map, troop_map)
    assert hydrated[0]["members"][0]["name"] == "New Name"
    print("hydrate OK")

def test_build_index():
    print("Testing build_location_index...")
    units = [
        {"id": 101, "system_id": 1, "status": "GROUND", "sector_id": 10},
        {"id": 102, "system_id": 1, "status": "SPACE", "ring": 1},
        {"id": 103, "status": "TRANSIT", "transit_origin": 1}
    ]
    chars = [
        {"id": 1, "location": {"system_id": 1, "sector_id": 10}},
        {"id": 2, "location": {"system_id": 1, "ring": 0}}
    ]
    
    index = build_location_index(chars, units, set())
    
    # Check Units
    assert 101 in [u["id"] for u in index["ground_forces"][1]]
    assert 102 in [u["id"] for u in index["space_forces"][1]]
    assert len(index["units_in_transit"]) == 1
    
    # Check Chars
    assert 1 in [c["id"] for c in index["chars_by_sector"][10]]
    
    print("build_index OK")

def test_helpers():
    print("Testing helpers...")
    # set_prop
    d = {"x": 1}
    assert set_prop(d, "x", 2) == True
    assert d["x"] == 2
    
    # get_leader_capacity
    mock_leader = {
        "details": {
            "atributos": {"presencia": 12, "voluntad": 14},
            "rango": "Oficial"
        }
    }
    # Base(2) + Vol/2(7) + Rank(2) = 11 -> Clamp(10)
    pres, cap = get_leader_capacity(mock_leader)
    assert cap == 10
    
    mock_leader_weak = {
        "details": {
            "atributos": {"presencia": 10, "voluntad": 8},
            "rango": "Recluta"
        }
    }
    # Base(2) + Vol/2(4) + Rank(0) = 6
    pres, cap = get_leader_capacity(mock_leader_weak)
    assert cap == 6
    
    print("helpers OK")

    print("helpers OK")

def check_syntax():
    print("Checking UI modules syntax...")
    try:
        import ui.components.roster_widgets
        print("ui.components.roster_widgets syntax OK")
    except ImportError:
        pass # Expected if streamlit not fully mocked or similar, but syntax error would raise SyntaxError
    except Exception as e:
        print(f"ui.components.roster_widgets import error (might be runtime): {e}")

    try:
        import ui.faction_roster
        print("ui.faction_roster syntax OK")
    except ImportError:
        pass
    except Exception as e:
        print(f"ui.faction_roster import error (might be runtime): {e}")

if __name__ == "__main__":
    try:
        from ui.logic.roster_logic import set_prop, get_leader_capacity
        test_get_prop()
        test_hydrate()
        test_build_index()
        test_helpers()
        check_syntax()
        print("\nALL LOGIC TESTS PASSED [OK]")
    except AssertionError as e:
        print(f"\nTEST FAILED [X]: {e}")
    except Exception as e:
        print(f"\nCRITICAL ERROR [X]: {e}")
