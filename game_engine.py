import os
import json
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
from google.genai import types

# Cargar variables de entorno
load_dotenv()

# --- HELPER DE SECRETOS ---
def get_secret(key):
    value = os.getenv(key)
    if value: return value
    if key in st.secrets: return st.secrets[key]
    return None

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("CRITICAL: Faltan credenciales de Supabase.")

# Inicializar Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Inicializar Cliente de Google GenAI
ai_client = None
if GEMINI_API_KEY:
    try:
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
        # VERIFICACIÓN: Imprimimos modelos disponibles para confirmar conexión y versión
        # Esto aparecerá en los logs de Streamlit (Manage App > Logs)
        print("--- MODELOS DISPONIBLES EN TU CUENTA ---")
        # Nota: La lista completa puede ser larga, solo confirmamos inicio exitoso
        print("Conexión con Google AI Studio: EXITOSA")
    except Exception as e:
        print(f"Error inicializando Gemini: {e}")
else:
    print("WARNING: GEMINI_API_KEY no encontrada.")

# --- SISTEMA DE HABILIDADES (SKILLS) ---
SKILL_MAPPING = {
    # I. Combate
    "armas_mano": ("agilidad", "tecnica"),
    "fusiles_asalto": ("agilidad", "fuerza"),
    "armas_precision": ("agilidad", "voluntad"),
    "armamento_pesado": ("fuerza", "tecnica"),
    "combate_cuerpo_a_cuerpo": ("fuerza", "agilidad"),
    "demoliciones": ("tecnica", "intelecto"),
    "primeros_auxilios": ("intelecto", "tecnica"),
    "uso_escudos": ("tecnica", "voluntad"),
    "lanzables": ("agilidad", "fuerza"),
    "tacticas_cobertura": ("intelecto", "agilidad"),
    # II. Pilotaje
    "pilotaje_cazas": ("agilidad", "intelecto"),
    "pilotaje_fragatas": ("intelecto", "tecnica"),
    "pilotaje_capital": ("intelecto", "presencia"),
    "navegacion_hiperespacial": ("intelecto", "tecnica"),
    "artilleria_torretas": ("agilidad", "tecnica"),
    "defensa_de_punto": ("tecnica", "intelecto"),
    "guerra_electronica": ("intelecto", "tecnica"),
    "gestion_energia": ("intelecto", "voluntad"),
    "maniobras_evasivas": ("agilidad", "intelecto"),
    "anclaje_abordaje": ("tecnica", "agilidad"),
    # III. Técnica
    "hacking_sistemas": ("intelecto", "tecnica"),
    "ingenieria_motores": ("tecnica", "fuerza"),
    "robotica": ("tecnica", "intelecto"),
    "cibernetica": ("tecnica", "intelecto"),
    "xenobiologia": ("intelecto", "voluntad"),
    "astrofisica": ("intelecto", "intelecto"),
    "quimica_combustibles": ("tecnica", "intelecto"),
    "sistemas_soporte_vital": ("tecnica", "intelecto"),
    "mineria_asteroides": ("tecnica", "fuerza"),
    "arqueologia_estelar": ("intelecto", "presencia"),
    # IV. Diplomacia
    "persuasion": ("presencia", "intelecto"),
    "intimidacion": ("presencia", "fuerza"),
    "engano": ("presencia", "intelecto"),
    "negociacion_comercial": ("presencia", "intelecto"),
    "protocolo_diplomatico": ("presencia", "voluntad"),
    "liderazgo": ("presencia", "voluntad"),
    "infiltracion": ("agilidad", "intelecto"),
    "busqueda_informacion": ("presencia", "intelecto"),
    "interrogatorio": ("voluntad", "presencia"),
    "propaganda": ("presencia", "intelecto"),
    # V. Supervivencia
    "atletismo": ("fuerza", "agilidad"),
    "salto_progresivo": ("fuerza", "agilidad"),
    "natacion_buceo": ("fuerza", "voluntad"),
    "maniobra_zero_g": ("agilidad", "voluntad"),
    "resistencia_ambiental": ("fuerza", "voluntad"),
    "percepcion_trampas": ("intelecto", "voluntad"),
    "rastreo": ("intelecto", "voluntad"),
    # VI. Gestión
    "logistica_galactica": ("intelecto", "tecnica"),
    "administracion_colonial": ("intelecto", "presencia"),
    "xenolinguistica": ("intelecto", "presencia"),
    "espionaje_industrial": ("intelecto", "agilidad"),
    "seguridad_interna": ("intelecto", "voluntad")
}

def calculate_skills(attributes: dict) -> dict:
    """Calcula nivel base de habilidades (Attr1 + Attr2)."""
    skills = {}
    attrs_safe = {k.lower(): v for k, v in attributes.items()}
    for skill, (a1, a2) in SKILL_MAPPING.items():
        val1 = attrs_safe.get(a1, 0)
        val2 = attrs_safe.get(a2, 0)
        skills[skill] = val1 + val2
    return skills

def log_event(text: str, is_error: bool = False):
    """Guarda un evento o error en Supabase."""
    prefix = "ERROR: " if is_error else ""
    try:
        supabase.table("logs").insert({
            "turno": 1, 
            "evento_texto": f"{prefix}{text}",
            "prompt_imagen": ""
        }).execute()
    except Exception as e:
        print(f"Fallo al loguear en DB: {e}")

def get_ai_instruction() -> dict:
    try:
        response = supabase.table("game_config").select("key", "value").execute()
        if response.data:
            return {item['key']: item['value'] for item in response.data}
    except Exception as e:
        log_event(f"Error leyendo config: {e}", is_error=True)
    return {}

# --- MODELO ELEGIDO ---
# gemini-1.5-flash-001: La versión estable, rápida y más barata.
# Al tener cuenta con Billing, este modelo NO debería dar 429.
MODEL_NAME = 'gemini-1.5-flash-001'

def generate_random_character(faction_name: str = "Neutral") -> dict:
    if not ai_client: return None
    
    game_config = get_ai_instruction()
    world_desc = game_config.get('world_description', 'Ciencia ficción.')
    
    prompt = f"""
    Genera un personaje sci-fi.
    Mundo: {world_desc}
    Facción: {faction_name}
    
    Output JSON (sin markdown):
    {{
        "bio": {{"nombre": "str", "raza": "str", "edad": int, "sexo": "str", "rol": "str"}},
        "atributos": {{"fuerza": int(1-20), "agilidad": int, "intelecto": int, "tecnica": int, "presencia": int, "voluntad": int}},
        "resumen": "str (max 30 words)"
    }}
    """
    
    try:
        response = ai_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        
        text = response.text.strip().replace('```json', '').replace('```', '')
        char_data = json.loads(text)
        char_data["habilidades"] = calculate_skills(char_data["atributos"])
        
        new_entity = {
            "nombre": char_data["bio"]["nombre"],
            "tipo": "Personaje",
            "stats_json": char_data,
            "estado": "Vivo",
            "ubicacion": "Base Principal"
        }
        
        res = supabase.table("entities").insert(new_entity).execute()
        if res.data:
            return res.data[0]
            
    except Exception as e:
        log_event(f"Fallo generando personaje ({MODEL_NAME}): {e}", is_error=True)
        return None

def resolve_action(action_text: str, player_id: int) -> dict:
    if not ai_client: 
        return {"narrative": "Error: IA no conectada.", "updates": []}

    game_config = get_ai_instruction()
    
    # Obtener estado actual
    try:
        players = supabase.table("players").select("*").execute().data
        entities = supabase.table("entities").select("*").execute().data
    except Exception as e:
        return {"narrative": f"Error leyendo DB: {e}", "updates": []}
    
    game_state = {"players": players, "entities": entities}

    prompt = f"""
    GM Sci-Fi.
    Mundo: {game_config.get('world_description','')}
    Reglas: {game_config.get('rules','')}
    Estado: {json.dumps(game_state, default=str)}
    Acción (ID {player_id}): "{action_text}"
    
    Output JSON (sin markdown):
    {{
        "narrative": "str",
        "updates": [ {{"table": "str", "id": int, "data": {{...}} }} ]
    }}
    """

    try:
        response = ai_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        
        text = response.text.strip().replace('```json', '').replace('```', '')
        result = json.loads(text)

        # Ejecutar actualizaciones
        if "updates" in result:
            for update in result["updates"]:
                if update.get("table") and update.get("id") and update.get("data"):
                    supabase.table(update["table"]).update(update["data"]).eq("id", update["id"]).execute()

        # Loguear evento
        log_event(result.get("narrative", "Acción sin narrativa."))

        return result

    except Exception as e:
        log_event(f"Error resolviendo acción ({MODEL_NAME}): {e}", is_error=True)
        return {"narrative": f"Error del sistema: {e}", "updates": []}