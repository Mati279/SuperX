# utils/helpers.py
import base64
import re
import json
from typing import IO

def encode_image(image_file: IO[bytes]) -> str:
    """
    Codifica un archivo de imagen en formato base64.

    Args:
        image_file: El objeto de archivo de imagen (ej. de st.file_uploader).

    Returns:
        La imagen codificada como un string en base64.
    """
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

def clean_json_string(text: str) -> str:
    """
    Limpia un string para asegurar que sea un JSON válido.
    Extrae el contenido entre las primeras '{' y las últimas '}'.
    Elimina bloques de código markdown y caracteres de control.
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
    # Esto ayuda con caracteres invisibles que rompen json.loads
    cleaned = "".join(ch for ch in cleaned if ord(ch) >= 32 or ch in "\b\f\n\r\t")
    
    return cleaned.strip()