import os
import json
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client
import google.generativeai as genai

# Cargar variables
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

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- SISTEMA DE HABILIDADES (SKILLS) ---
# Mapeo: Habilidad -> (Atributo 1, Atributo 2)
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

def get_ai_instruction() -> dict:
    try:
        response = supabase.table("game_config").select("key", "value").execute()
        if response.data:
            return {item['key']: item['value'] for item in response.data}
    except Exception:
        pass
    return {}

def generate_random_character(faction_name: str = "Neutral") -> dict:
    """Genera un personaje completo con Gemini y calcula sus skills."""
    game_config = get_ai_instruction()
    world_desc = game_config.get('world_description', 'Ciencia ficción futurista.')
    
    prompt = f"""
    Genera un personaje para un juego de rol:
    Mundo: {world_desc}
    Facción: {faction_name}
    
    Devuelve SOLO un JSON con esta estructura exacta:
    {{
        "bio": {{"nombre": "String", "raza": "String", "edad": Int, "sexo": "String", "rol": "String"}},
        "atributos": {{"fuerza": Int(1-20), "agilidad": Int(1-20), "intelecto": Int(1-20), "tecnica": Int(1-20), "presencia": Int(1-20), "voluntad": Int(1-20)}},
        "resumen": "Breve descripción narrativa del personaje."
    }}
    Sé creativo con la raza y el rol.
    """
    
    try:
        # CORRECCIÓN DEL MODELO AQUI
        model = genai.GenerativeModel('gemini-1.5-flash-001') 
        response = model.generate_content(prompt)
        text = response.text.strip().replace('```json', '').replace('```', '')
        char_data = json.loads(text)
        
        # Calcular habilidades derivadas
        char_data["habilidades"] = calculate_skills(char_data["atributos"])
        
        # Guardar en DB
        new_entity = {
            "nombre": char_data["bio"]["nombre"],
            "tipo": "Personaje",
            "stats_json": char_data,
            "estado": "Vivo",
            "ubicacion": "Base Principal"
        }
        
        # Insertar y devolver
        res = supabase.table("entities").insert(new_entity).execute()
        if res.data:
            return res.data[0]
            
    except Exception as e:
        print(f"Error generando personaje: {e}")
        return None

def resolve_action(action_text: str, player_id: int) -> dict:
    # ... (Tu lógica existente, actualizada con el modelo correcto) ...
    game_config = get_ai_instruction()
    rules = game_config.get('rules', '')
    world_description = game_config.get('world_description', '')

    # Fetch simple del estado
    players_response = supabase.table("players").select("*").execute()
    entities_response = supabase.table("entities").select("*").execute()
    
    game_state = {
        "players": players_response.data,
        "entities": entities_response.data
    }

    prompt = f"""
    Actúa como GM.
    Mundo: {world_description}
    Reglas: {rules}
    Estado: {json.dumps(game_state)}
    Acción Jugador {player_id}: "{action_text}"
    
    Resuelve la acción. Devuelve JSON con "narrative" y "updates" (lista de objetos con table, id, data).
    """

    try:
        # CORRECCIÓN DEL MODELO AQUI TAMBIÉN
        model = genai.GenerativeModel('gemini-1.5-flash-001')
        response = model.generate_content(prompt)
        cleaned = response.text.strip().replace('```json', '').replace('```', '')
        result = json.loads(cleaned)

        if "updates" in result:
            for update in result["updates"]:
                if update.get("table") and update.get("id") and update.get("data"):
                    supabase.table(update["table"]).update(update["data"]).eq("id", update["id"]).execute()

        log_entry = {
            "turno": 1,
            "evento_texto": result.get("narrative", "Error narrativo"),
            "prompt_imagen": ""
        }
        supabase.table("logs").insert(log_entry).execute()

        return result
    except Exception as e:
        return {"narrative": f"Error del sistema: {e}", "updates": []}