import os
from dotenv import load_dotenv
from google import genai

# 1. Cargar variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

print("\n--- DIAGNÓSTICO DE GEMINI (Modo Simple) ---")

if not api_key:
    print("❌ ERROR: No hay API Key.")
    exit()

# 2. Conectar
try:
    client = genai.Client(api_key=api_key)
    print("✅ Cliente conectado.")
except Exception as e:
    print(f"❌ Error de conexión: {e}")
    exit()

# 3. Listar Modelos (Sin filtros raros)
print("\n🔍 Buscando modelos disponibles en tu cuenta...")
try:
    # Paginación automática para traer todos
    pager = client.models.list(config={'page_size': 100})
    
    found_any = False
    print("------------------------------------------------")
    for m in pager:
        # Imprimimos el nombre directo (propiedad 'name' suele ser segura)
        # Algunos objetos pueden venir como dict o objeto, probamos ambos
        name = getattr(m, 'name', None) or m.get('name')
        
        if name and 'gemini' in name.lower():
            # Limpiamos el prefijo para que sea fácil de copiar
            clean_name = name.replace('models/', '')
            print(f"🟢 {clean_name}")
            found_any = True
            
    print("------------------------------------------------")

    if not found_any:
        print("⚠️ No se encontraron modelos con la palabra 'gemini'.")
    else:
        print("✅ Copia uno de los nombres verdes (ej: gemini-1.5-flash) para usar en tu juego.")

except Exception as e:
    print(f"❌ ERROR al listar: {e}")
    # Si falla el listado, probamos una generación ciega con el modelo más común
    print("\n⚠️ Intento de emergencia con 'gemini-1.5-flash'...")
    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents="Si lees esto, responde 'OK'."
        )
        print(f"🎉 ¡Funcionó de todos modos! Respuesta: {response.text}")
    except Exception as e2:
        print(f"❌ Falló también la prueba ciega: {e2}")