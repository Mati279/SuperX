import os
import json
import streamlit as st  # Importamos streamlit para acceder a st.secrets
from dotenv import load_dotenv
from supabase import create_client, Client
import google.generativeai as genai

# Cargar variables de entorno (para local)
load_dotenv()

# --- FUNCIÓN HELPER PARA GESTIONAR CLAVES ---
def get_secret(key):
    """Busca la clave primero en variables de entorno, luego en st.secrets."""
    value = os.getenv(key)
    if value:
        return value
    if key in st.secrets:
        return st.secrets[key]
    return None

# Recuperar credenciales
SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")

# Validación temprana para evitar errores cripticos
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("CRITICAL: Faltan las credenciales de SUPABASE_URL o SUPABASE_KEY en .env o Secrets.")

# Inicializar clientes
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    # No lanzamos error aquí para permitir que la UI cargue y avise
    print("WARNING: GEMINI_API_KEY no encontrada.")

def get_ai_instruction() -> dict:
    """Recupera la configuración del juego desde Supabase."""
    try:
        response = supabase.table("game_config").select("key", "value").execute()
        if response.data:
            return {item['key']: item['value'] for item in response.data}
    except Exception as e:
        print(f"Error conectando a DB: {e}")
    return {}

def generate_random_character() -> dict:
    """
    Usa Gemini para generar un personaje aleatorio y lo guarda en la base de datos.
    """
    if not GEMINI_API_KEY:
        st.error("La API Key de Gemini no está configurada. No se puede generar un personaje.")
        return None

    world_description = get_ai_instruction().get('world_description', 'Universo de ciencia ficción genérico.')

    prompt = f"""
    Actúa como un generador de personajes para un juego de rol de ciencia ficción.
    Basado en la siguiente descripción del mundo, crea un único personaje memorable.
    
    **Descripción del Mundo:**
    {world_description}

    **Tu Tarea:**
    Genera un personaje con los siguientes campos y devuelve SÓLO un objeto JSON válido.
    Asegúrate de que los atributos sean coherentes con la biografía del personaje.
    
    **Formato de Salida (JSON estricto):**
    {{
      "biografia": {{
        "nombre": "Nombre del Personaje",
        "raza": "Raza de Ciencia Ficción (ej: Humano, Cyborg, Alienígena)",
        "edad": "Edad del personaje (numérico)",
        "sexo": "Sexo del personaje"
      }},
      "atributos": {{
        "fuerza": "Un valor de 1 a 20",
        "agilidad": "Un valor de 1 a 20",
        "intelecto": "Un valor de 1 a 20",
        "tecnica": "Un valor de 1 a 20",
        "presencia": "Un valor de 1 a 20",
        "voluntad": "Un valor de 1 a 20"
      }}
    }}
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '')
        char_data = json.loads(cleaned_response)

        # Extraer nombre para la tabla principal y guardar el resto en stats_json
        nombre_personaje = char_data.get("biografia", {}).get("nombre", "Sin Nombre")
        
        # Guardar en la base de datos
        db_response = supabase.table("entities").insert({
            "nombre": nombre_personaje,
            "tipo": "Operativo",
            "stats_json": char_data,
            "estado": "Activo"
        }).execute()
        
        if db_response.data:
            st.success(f"¡Operativo '{nombre_personaje}' reclutado y guardado en la base de datos!")
            return db_response.data[0]
        else:
            st.error(f"Error al guardar el personaje en la base de datos: {db_response.error.message if db_response.error else 'Respuesta vacía'}")
            return None

    except Exception as e:
        st.error(f"Error al generar el personaje con Gemini: {e}")
        return None

def resolve_action(action_text: str, player_id: int) -> dict:
    """
    Resuelve una acción del jugador usando el LLM y actualiza la base de datos.
    """
    # 1. Recuperar configuración y reglas
    game_config = get_ai_instruction()
    rules = game_config.get('rules', 'No hay reglas definidas.')
    world_description = game_config.get('world_description', 'No hay descripción del mundo.')

    try:
        # 2. Recuperar la entidad (personaje) del jugador que actúa
        player_entity_response = supabase.table("entities").select("*").eq("id", player_id).single().execute()
        player_character = player_entity_response.data
        
        # 3. Recuperar las demás entidades para el contexto
        other_entities_response = supabase.table("entities").select("*").neq("id", player_id).execute()
        
        game_state = {
            "other_entities": other_entities_response.data
        }

    except Exception as e:
        print(f"Error recuperando datos del personaje: {e}")
        return {"narrative": "Error crítico: No se pudo encontrar al personaje en la base de datos.", "updates": []}

    # 4. Construir el prompt para Gemini con el nuevo formato
    prompt = f"""
    Actúa como un Game Master de ciencia ficción.
    
    **Descripción del Mundo:**
    {world_description}

    **Reglas del Juego:**
    {rules}

    **Personaje que realiza la acción:**
    {json.dumps(player_character, indent=2)}

    **Otros en la escena:**
    {json.dumps(game_state, indent=2)}

    **Acción del Personaje:**
    "{action_text}"

    **Tu Tarea:**
    Resuelve la acción basándote en los atributos del personaje (fuerza, agilidad, intelecto, tecnica, presencia, voluntad) y la situación.
    Describe el resultado de forma cinemática y determina si alguna estadística debe cambiar.
    Devuelve SÓLO un objeto JSON válido con dos claves:
    1. "narrative": Un string que describe el resultado de la acción.
    2. "updates": Una lista de objetos JSON para cambios en la base de datos (puede estar vacía).
       Cada objeto debe tener "table", "id" y "data".

    Ejemplo de respuesta:
    {{
      "narrative": "Zane activa su camuflaje óptico. Sus habilidades técnicas le permiten volverse casi invisible en las sombras del callejón, evadiendo a los guardias.",
      "updates": []
    }}
    """

    # 5. Llamar a la API de Gemini
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '')
        result = json.loads(cleaned_response)

        # 6. Actualizar la base de datos
        if "updates" in result:
            for update in result["updates"]:
                table_name = update.get("table")
                record_id = update.get("id")
                update_data = update.get("data")
                
                if table_name and record_id and update_data:
                    supabase.table(table_name).update(update_data).eq("id", record_id).execute()

        # 7. Registrar el evento en los logs
        log_entry = {
            "turno": 1,  # Simplificado
            "evento_texto": result.get("narrative", "No se generó narrativa."),
            "prompt_imagen": ""
        }
        supabase.table("logs").insert(log_entry).execute()

        return result

    except Exception as e:
        print(f"Error al procesar la acción con Gemini: {e}")
        # Intentar dar una respuesta de error más informativa a la UI
        error_narrative = f"El Game Master está experimentando dificultades técnicas. Detalles: {str(e)}"
        supabase.table("logs").insert({"turno": 1, "evento_texto": error_narrative}).execute()
        return {"narrative": error_narrative, "updates": []}

if __name__ == '__main__':
    # Ejemplo de uso (requiere datos en Supabase)
    # Crear un jugador para probar
    # try:
    #     supabase.table("players").insert({"nombre": "Tester", "faccion_nombre": "Aventureros"}).execute()
    # except:
    #     pass # Ignorar si ya existe

    # player_id = supabase.table("players").select("id").eq("nombre", "Tester").single().execute().data['id']
    
    # test_action = "Intento atacar al goblin que tengo enfrente con mi espada."
    # result = resolve_action(test_action, player_id)
    # print(result)
    pass
