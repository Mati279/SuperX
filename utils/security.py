# utils/security.py
import bcrypt

def hash_password(password: str) -> str:
    """
    Genera un hash de una contraseña usando bcrypt.

    Args:
        password: La contraseña en texto plano.

    Returns:
        El hash de la contraseña como string.
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(stored_password: str, provided_password: str) -> bool:
    """
    Verifica si una contraseña proporcionada coincide con un hash almacenado.

    Args:
        stored_password: El hash de la contraseña almacenada.
        provided_password: La contraseña en texto plano a verificar.

    Returns:
        True si la contraseña es correcta, False en caso contrario.
    """
    return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password.encode('utf-8'))
