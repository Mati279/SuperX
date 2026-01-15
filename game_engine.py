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

def resolve_action(action_text: str, player_id: int) -> dict:
    """
    Resuelve una acción del jugador usando el LLM y actualiza la base de datos.
    """
    # 1. Recuperar estado actual y reglas
    game_config = get_ai_instruction()
    rules = game_config.get('rules', 'No hay reglas definidas.')
    world_description = game_config.get('world_description', 'No hay descripción del mundo.')

    players_response = supabase.table("players").select("*").execute()
    entities_response = supabase.table("entities").select("*").execute()
    
    game_state = {
        "players": players_response.data,
        "entities": entities_response.data
    }

    # 2. Construir el prompt para Gemini
    prompt = f"""
    Actúa como GM.
    **Descripción del Mundo:**
    {world_description}

    **Reglas del Juego:**
    {rules}

    **Estado Actual del Juego:**
    {json.dumps(game_state, indent=2)}

    **Acción del Jugador:**
    El jugador (ID: {player_id}) realiza la siguiente acción: "{action_text}"

    **Tu Tarea:**
    Resuelve la acción del jugador basándote en las reglas y el estado actual.
    Devuelve SÓLO un objeto JSON válido con dos claves:
    1. "narrative": Un string que describe el resultado de la acción de forma cinemática.
    2. "updates": Una lista de objetos JSON, donde cada objeto representa un cambio en la base de datos. Cada objeto debe tener "table", "id" y "data" para actualizar. Si no hay cambios numéricos, la lista puede estar vacía.

    Ejemplo de formato de respuesta:
    {{
      "narrative": "La flecha silba en el aire y se clava en el hombro del orco, que ruge de dolor.",
      "updates": [
        {{
          "table": "entities",
          "id": 12,
          "data": {{
            "stats_json": {{"hp": 8}}
          }}
        }}
      ]
    }}
    """

    # 3. Llamar a la API de Gemini
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        
        # Limpiar y parsear la respuesta JSON
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '')
        result = json.loads(cleaned_response)

        # 4. Actualizar la base de datos con los cambios
        if "updates" in result:
            for update in result["updates"]:
                table_name = update.get("table")
                record_id = update.get("id")
                update_data = update.get("data")
                
                if table_name and record_id and update_data:
                    supabase.table(table_name).update(update_data).eq("id", record_id).execute()

        # 5. Registrar el evento en los logs
        log_entry = {
            "turno": 1,  # Simplificado, podría ser un contador global
            "evento_texto": result.get("narrative", "No se generó narrativa."),
            "prompt_imagen": "" # Opcional, para futuras implementaciones
        }
        supabase.table("logs").insert(log_entry).execute()

        return result

    except Exception as e:
        print(f"Error al procesar la acción: {e}")
        return {"narrative": "Error del sistema. El Game Master está confundido.", "updates": []}

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
