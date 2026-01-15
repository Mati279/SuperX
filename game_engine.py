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


# --- DATA: RACES & CLASSES (Placeholders) ---
RACES = {
    "Humano": {"desc": "Versátiles y ambiciosos. Dominan la política galáctica.", "bonus": {"voluntad": 1}},
    "Cyborg": {"desc": "Humanos mejorados con implantes. Resistentes y fríos.", "bonus": {"tecnica": 1}},
    "Marciano": {"desc": "Nacidos en la baja gravedad roja. Ágiles pero frágiles.", "bonus": {"agilidad": 1}},
    "Selenita": {"desc": "Habitantes del lado oscuro de la luna. Misteriosos y pálidos.", "bonus": {"intelecto": 1}},
    "Androide": {"desc": "Inteligencia artificial en cuerpo sintético. Incansables.", "bonus": {"fuerza": 1}}
}

CLASSES = {
    "Soldado": {"desc": "Entrenado en armas y tácticas militares.", "bonus_attr": "fuerza"},
    "Piloto": {"desc": "Experto en navegación y combate vehicular.", "bonus_attr": "agilidad"},
    "Ingeniero": {"desc": "Maestro de la reparación y la tecnología.", "bonus_attr": "tecnica"},
    "Diplomático": {"desc": "La palabra es más fuerte que el láser.", "bonus_attr": "presencia"},
    "Espía": {"desc": "El arte del sigilo y el subterfugio.", "bonus_attr": "agilidad"},
    "Hacker": {"desc": "Domina el ciberespacio y los sistemas de seguridad.", "bonus_attr": "intelecto"}
}

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

# --- Authentication ---
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(stored_password: str, provided_password: str) -> bool:
    return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password.encode('utf-8'))

def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# --- New Registration Flow ---

def register_player_account(user_name: str, pin: str, faction_name: str, banner_file) -> dict:
    """Paso 1: Solo crea la cuenta del jugador (Usuario + Facción)."""
    banner_url = f"data:image/png;base64,{encode_image(banner_file)}" if banner_file else None
    
    new_player_data = {
        "nombre": user_name,
        "pin": hash_password(pin),
        "faccion_nombre": faction_name,
        "banner_url": banner_url
    }
    
    try:
        res = supabase.table("players").insert(new_player_data).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        log_event(f"Error registrando cuenta: {e}", is_error=True)
        return None
    return None

def create_commander_manual(player_id: int, name: str, bio_data: dict, attributes: dict) -> bool:
    """Paso 2 y 3: Crea el personaje Comandante con datos manuales."""
    try:
        # Aplicar bonus de raza y clase si es necesario (lógica simple aquí)
        # Por ahora guardamos los atributos tal cual los manda el front, 
        # pero podríamos sumar los bonus aquí si quisiéramos automatizarlo.
        
        # Calcular habilidades derivadas
        habilidades = calculate_skills(attributes)
        
        stats_json = {
            "bio": bio_data,       # {nombre, raza, edad, sexo, rol, clase, historia}
            "atributos": attributes,
            "habilidades": habilidades
        }

        new_char = {
            "player_id": player_id,
            "nombre": name,
            "rango": "Comandante",
            "es_comandante": True,
            "stats_json": stats_json,
            "estado": "Activo",
            "ubicacion": "Puente de Mando"
        }
        
        res = supabase.table("characters").insert(new_char).execute()
        return True if res.data else False
        
    except Exception as e:
        log_event(f"Error creando comandante: {e}", player_id=player_id, is_error=True)
        return False

# --- Action Resolution ---
MODEL_NAME = 'gemini-2.5-flash'

def get_ai_instruction() -> dict:
    try:
        response = supabase.table("game_config").select("key", "value").execute()
        if response.data:
            return {item['key']: item['value'] for item in response.data}
    except Exception as e:
        log_event(f"Error reading config: {e}", is_error=True)
    return {}

def resolve_action(action_text: str, player_id: int) -> dict:
    if not ai_client: return {"narrative": "Error AI.", "updates": []}

    game_config = get_ai_instruction()
    
    try:
        chars = supabase.table("characters").select("*").eq("player_id", player_id).eq("es_comandante", True).execute().data
        if not chars: return {"narrative": "Error: No se encontró al Comandante.", "updates": []}
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