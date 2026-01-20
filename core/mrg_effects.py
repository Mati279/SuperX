# core/mrg_effects.py
"""
DEPRECATED: Este módulo ha sido marcado como obsoleto en la v2.1.
La lógica de efectos (Beneficios/Malus) se ha movido fuera del motor MRG
para ser manejada directamente por los sistemas invocadores (Game Loop / Scenes).

Este archivo se mantiene temporalmente para evitar errores de importación
durante la transición, pero no contiene lógica ejecutable.
"""

# No-op
def apply_benefit(*args, **kwargs):
    pass

def apply_malus(*args, **kwargs):
    pass