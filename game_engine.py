import os
import json
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai 
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
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ Gemini client connected.")
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
else:
    print("WARNING: GEMINI_API_KEY not found.")


# --- Skill System ---
SKILL_MAPPING = {
    "Combate Cercano": ("fuerza", "agilidad"),
    "Puntería": ("agilidad", "tecnica"),
    "Hacking": ("intelecto", "tecnica"),
    "Pilotaje": ("agilidad", "intelecto"),
    "Persuasión": ("presencia", "voluntad"),
    "Medicina": ("intelecto", "tecnica"),
    "Sigilo": ("agilidad", "presencia"),
    "Ingeniería": ("tecnica", "intelecto")
}

def calculate_skills(attributes: dict) -> dict:
    skills = {}
    if not attributes: return {}
    attrs_safe = {k.lower(): v for k, v in attributes.items()}
    for skill, (a1, a2) in SKILL_MAPPING.items():
        val1 = attrs_safe.get(a1, 0)
        val2 = attrs_safe.get(a2, 0)
        skills[skill] = val1 + val2
    return skills

def log_event(text: str, player_id: int = None, is_error: bool = False):
    prefix = "ERROR: " if is_error else ""
    print(f"LOG: {prefix}{text}")
    try:
        data = {"evento_texto": f"{prefix}{text}", "turno": 1}
        if player_id:
            data["player_id"] = player_id
        supabase.table("logs").insert(data).execute()
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
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(stored_password: str, provided_password: str) -> bool:
    return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password.encode('utf-8'))

def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- Registration & Character Generation ---
MODEL_NAME = 'gemini-2.5-flash'

def register_faction_and_commander(user_name: str, pin: str, faction_name: str, banner_file) -> dict:
    """
    1. Crea el Jugador (Usuario + Facción).
    2. Genera y crea el Personaje (Comandante).
    """
    if not ai_client: 
        log_event("Intento de registro fallido: Cliente AI no conectado.", is_error=True)
        return None
    
    # 1. Crear Jugador (Dueño de la cuenta) -> Tabla PLAYERS
    # NOTA: Aquí NO va 'estado' ni 'ubicacion'. Solo datos de cuenta.
    banner_url = f"data:image/png;base64,{encode_image(banner_file)}" if banner_file else None
    
    new_player_data = {
        "nombre": user_name,
        "pin": hash_password(pin),
        "faccion_nombre": faction_name,
        "banner_url": banner_url
    }
    
    try:
        # Insert Player
        player_res = supabase.table("players").insert(new_player_data).execute()
        if not player_res.data:
            log_event("Error al insertar jugador en DB.", is_error=True)
            return None
        
        player_id = player_res.data[0]['id']
        
        # 2. Generar Comandante (AI) -> Tabla CHARACTERS
        game_config = get_ai_instruction()
        world_desc = game_config.get('world_description', 'Sci-fi.')
        
        prompt = f"""
        Generate the statistics for a Sci-Fi Commander (RPG Character).
        World: {world_desc}
        Faction: {faction_name}
        Name: {user_name}

        **CRITICAL RULE:** "sexo" must be "Hombre" or "Mujer".

        JSON Output (no markdown):
        {{
            "bio": {{"nombre": "{user_name}", "raza": "str", "edad": int, "sexo": "str", "rol": "Comandante"}},
            "atributos": {{"fuerza": int(1-20), "agilidad": int, "intelecto": int, "tecnica": int, "presencia": int, "voluntad": int}},
            "resumen": "str (max 30 words)"
        }}
        """
        
        response = ai_client.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = response.text.strip().replace('```json', '').replace('```', '')
        char_stats = json.loads(text)
        
        char_stats["habilidades"] = calculate_skills(char_stats["atributos"])
        
        # Aquí SÍ va 'estado' y 'ubicacion' porque es un personaje
        new_character_data = {
            "player_id": player_id,
            "nombre": user_name,
            "rango": "Comandante",
            "es_comandante": True,
            "stats_json": char_stats,
            "estado": "Activo",
            "ubicacion": "Puente de Mando"
        }
        
        # Insert Character
        char_res = supabase.table("characters").insert(new_character_data).execute()
        
        if char_res.data:
            # Retornamos datos combinados para la sesión
            full_data = player_res.data[0]
            full_data['commander_stats'] = char_res.data[0]['stats_json']
            return full_data
            
    except Exception as e:
        log_event(f"Error crítico en registro: {e}", is_error=True)
        # Opcional: Podríamos borrar el player si falla el char, pero por ahora solo logueamos.
        return None
        
    return None

# --- Action Resolution ---
def resolve_action(action_text: str, player_id: int) -> dict:
    if not ai_client: return {"narrative": "Error AI.", "updates": []}

    game_config = get_ai_instruction()
    
    try:
        # Obtener datos del Comandante actual
        chars = supabase.table("characters").select("*").eq("player_id", player_id).eq("es_comandante", True).execute().data
        if not chars:
            return {"narrative": "Error: No se encontró al Comandante.", "updates": []}
        
        commander = chars[0]
    except Exception as e:
        return {"narrative": f"Error reading DB: {e}", "updates": []}
    
    game_state = {"commander": commander}

    prompt = f"""
    GM Sci-Fi.
    World: {game_config.get('world_description','')}
    Rules: {game_config.get('rules','')}
    Current State: {json.dumps(game_state, default=str)}
    
    Player Action: "{action_text}"
    
    JSON Output (no markdown):
    {{
        "narrative": "str",
        "updates": [ {{"table": "characters", "id": int, "data": {{...}} }} ]
    }}
    """

    try:
        response = ai_client.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = response.text.strip().replace('```json', '').replace('```', '')
        result = json.loads(text)

        if "updates" in result:
            for update in result["updates"]:
                if update.get("table") == "characters" and update.get("id"):
                     supabase.table("characters").update(update["data"]).eq("id", update["id"]).execute()

        log_event(result.get("narrative", "..."), player_id=player_id)
        return result

    except Exception as e:
        log_event(f"Error action: {e}", player_id=player_id, is_error=True)
        return {"narrative": f"Error: {e}", "updates": []}