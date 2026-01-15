# utils/helpers.py
import base64
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
