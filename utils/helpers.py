# utils/helpers.py
import base64
import re
import json
from typing import IO, Optional, Dict, Any

def encode_image(image_file: IO[bytes]) -> str:
    """
    Codifica un archivo de imagen en formato base64.
    """
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

def clean_json_string(text: str) -> str:
    """
    Limpia un string para asegurar que sea un JSON válido.
    Extrae el contenido entre las primeras '{' y las últimas '}'.
    """
    if not text:
        return ""
    
    # 1. Eliminar bloques de código markdown si existen
    cleaned = re.sub(r'```json\s*?', '', text)
    cleaned = re.sub(r'```\s*?', '', cleaned)
    
    # 2. Intentar encontrar el bloque principal {}
    match = re.search(r'(\{.*\})', cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1)
    
    # 3. Eliminar caracteres de control (excepto tab, newline, carriage return)
    cleaned = "".join(ch for ch in cleaned if ord(ch) >= 32 or ch in "\b\f\n\r\t")
    
    return cleaned.strip()

def try_repair_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Intenta extraer y reparar un bloque JSON de un string sucio o truncado.
    Útil para respuestas de IA que no cierran correctamente sus estructuras.
    """
    if not text:
        return None

    try:
        # 1. Limpieza inicial y extracción por llaves
        # Buscamos desde la primera { hasta la última }
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if not match:
            # Si no hay llaves cerradas, intentamos desde la primera { hasta el final
            match = re.search(r'(\{.*)', text, re.DOTALL)
            if not match: return None
        
        clean_text = match.group(0)
        
        # 2. Sanitización de caracteres problemáticos para el parser
        # Reemplazamos saltos de línea literales dentro de strings por espacios
        # Nota: Esto es agresivo, pero previene fallos por Unterminated String
        clean_text = clean_text.replace('\n', ' ').replace('\r', '')
        
        # 3. Primer intento de parseo
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            # 4. Intento de reparación de truncado: cerrar comillas y llaves
            # Si termina abruptamente, cerramos el campo de texto y el objeto.
            repaired = clean_text.strip()
            if not repaired.endswith('}'):
                # Si parece que se cortó dentro de un string de valor
                if repaired.count('"') % 2 != 0:
                    repaired += '"'
                repaired += '}'
            
            try:
                return json.loads(repaired)
            except:
                return None
    except Exception:
        return None