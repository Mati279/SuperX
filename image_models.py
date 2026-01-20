import os
from dotenv import load_dotenv
from google import genai

# 1. Carga de configuración (Simulando config/settings.py para script standalone)
# Esto asegura que lea tu archivo .env local donde tienes GEMINI_API_KEY
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("❌ Error: No se encontró GEMINI_API_KEY en las variables de entorno.")
    exit(1)

def list_imagen_models():
    """
    Lista todos los modelos disponibles en la API de Gemini
    y filtra aquellos relacionados con la generación de imágenes.
    """
    print(f"📡 Conectando con Google GenAI usando key: ...{API_KEY[-4:]}")
    
    try:
        # Inicializar cliente tal como se hace en services/image_service.py
        client = genai.Client(api_key=API_KEY)
        
        print("\n🔍 Buscando modelos de la familia 'imagen'...\n")
        print(f"{'NOMBRE DEL MODELO':<40} | {'DISPLAY NAME'}")
        print("-" * 60)
        
        found = False
        # Iterar sobre todos los modelos disponibles
        for model in client.models.list():
            # Filtramos por nombre para encontrar los de imagen (ej: imagen-3.0)
            if 'imagen' in model.name.lower():
                found = True
                print(f"{model.name:<40} | {model.display_name}")
        
        if not found:
            print("\n⚠️ No se encontraron modelos específicos con el nombre 'imagen'.")
            print("Listando TODOS los modelos disponibles por si hubo cambio de nomenclatura:\n")
            for model in client.models.list():
                print(f"- {model.name}")

    except Exception as e:
        print(f"\n❌ Error al recuperar los modelos: {e}")

if __name__ == "__main__":
    list_imagen_models()