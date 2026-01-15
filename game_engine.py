import os
import json
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client
import google.generativeai as genai
import bcrypt
import base64

# Load environment variables
load_dotenv()

# --- Secrets Helper ---
def get_secret(key):
    value = os.getenv(key)
    if value: return value
    if hasattr(st, 'secrets') and key in st.secrets: return st.secrets[key]
    return None

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("CRITICAL: Supabase credentials are missing.")

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Gemini Initialization ---
ai_client = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        ai_client = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Gemini client connected (Advanced Mode).")
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
else:
    print("WARNING: GEMINI_API_KEY not found.")


# --- Skill System ---
SKILL_MAPPING = {
    # ... (skill mappings remain the same)
}

def calculate_skills(attributes: dict) -> dict:
    """Calculates base skill level (Attr1 + Attr2)."""
    skills = {}
    attrs_safe = {k.lower(): v for k, v in attributes.items()}
    for skill, (a1, a2) in SKILL_MAPPING.items():
        val1 = attrs_safe.get(a1, 0)
        val2 = attrs_safe.get(a2, 0)
        skills[skill] = val1 + val2
    return skills

def log_event(text: str, is_error: bool = False):
    """Saves an event or error to Supabase."""
    prefix = "ERROR: " if is_error else ""
    print(f"LOG: {prefix}{text}")
    try:
        supabase.table("logs").insert({
            "turno": 1, 
            "evento_texto": f"{prefix}{text}",
            "prompt_imagen": ""
        }).execute()
    except Exception as e:
        print(f"Failed to log to DB: {e}")

def get_ai_instruction() -> dict:
    try:
        response = supabase.table("game_config").select("key", "value").execute()
        if response.data:
            return {item['key']: item['value'] for item in response.data}
    except Exception as e:
        log_event(f"Error reading config: {e}", is_error=True)
    return {}

# --- Authentication ---
def hash_password(password: str) -> str:
    """Hashes a password for storing."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(stored_password: str, provided_password: str) -> bool:
    """Verifies a password against a stored hash."""
    return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password.encode('utf-8'))

def encode_image(image_file):
    """Encodes an image file to a base64 string."""
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- Character Generation ---
MODEL_NAME = 'gemini-1.5-flash'

def generate_random_character(player_name: str, password: str, faction_name: str, banner_file) -> dict:
    if not ai_client: return None
    
    game_config = get_ai_instruction()
    world_desc = game_config.get('world_description', 'Sci-fi.')
    
    prompt = f"""
    Generate a sci-fi character.
    World: {world_desc}
    Faction: {faction_name}

    **CRITICAL RULE:** The "sexo" field must ONLY be "Hombre" or "Mujer". No other values are allowed.

    JSON Output (no markdown):
    {{
        "bio": {{"nombre": "{player_name}", "raza": "str", "edad": int, "sexo": "str", "rol": "str"}},
        "atributos": {{"fuerza": int(1-20), "agilidad": int, "intelecto": int, "tecnica": int, "presencia": int, "voluntad": int}},
        "resumen": "str (max 30 words)"
    }}
    """
    
    try:
        response = ai_client.generate_content(prompt)
        text = response.text.strip().replace('```json', '').replace('```', '')
        char_data = json.loads(text)
        
        # Ensure the generated name is the requested player name
        char_data["bio"]["nombre"] = player_name
        char_data["habilidades"] = calculate_skills(char_data["atributos"])
        
        banner_url = f"data:image/png;base64,{encode_image(banner_file)}" if banner_file else None
        
        new_player = {
            "nombre": player_name,
            "password": hash_password(password),
            "faccion_nombre": faction_name,
            "banner_url": banner_url,
            "stats_json": char_data,
            "estado": "Activo",
            "ubicacion": "Base Principal"
        }
        
        res = supabase.table("players").insert(new_player).execute()
        if res.data:
            return res.data[0]
            
    except Exception as e:
        log_event(f"Failed to generate character ({MODEL_NAME}): {e}", is_error=True)
        return None

# --- Action Resolution ---
def resolve_action(action_text: str, player_id: int) -> dict:
    if not ai_client: 
        return {"narrative": "Error: AI not connected.", "updates": []}

    game_config = get_ai_instruction()
    
    try:
        players = supabase.table("players").select("*").execute().data
    except Exception as e:
        return {"narrative": f"Error reading DB: {e}", "updates": []}
    
    game_state = {"players": players}

    prompt = f"""
    GM Sci-Fi.
    World: {game_config.get('world_description','')}
    Rules: {game_config.get('rules','')}
    State: {json.dumps(game_state, default=str)}
    Action (Player ID {player_id}): "{action_text}"
    
    JSON Output (no markdown):
    {{
        "narrative": "str",
        "updates": [ {{"table": "players", "id": int, "data": {{...}} }} ]
    }}
    """

    try:
        response = ai_client.generate_content(prompt)
        text = response.text.strip().replace('```json', '').replace('```', '')
        result = json.loads(text)

        if "updates" in result:
            for update in result["updates"]:
                if update.get("table") == "players" and update.get("id") and update.get("data"):
                    supabase.table(update["table"]).update(update["data"]).eq("id", update["id"]).execute()

        log_event(result.get("narrative", "Action without narrative."))
        return result

    except Exception as e:
        log_event(f"Error resolving action ({MODEL_NAME}): {e}", is_error=True)
        return {"narrative": f"System Error: {e}", "updates": []}
