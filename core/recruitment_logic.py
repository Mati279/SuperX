# core/recruitment_logic.py (Completo)
from typing import Dict, Any, Tuple, Optional, List
from config.app_constants import (
    DEFAULT_RECRUIT_RANK,
    DEFAULT_RECRUIT_STATUS
)
# Eliminada importación fallida: DEFAULT_RECRUIT_LOCATION
from core.models import KnowledgeLevel, CharacterStatus

# Importamos el repositorio de personajes para el análisis del roster
# (Usamos import interno en la función para evitar ciclos si la arquitectura crece)
from data.character_repository import get_all_characters_by_player_id

def can_recruit(player_credits: int, candidate_cost: int) -> Tuple[bool, str]:
    """
    Verifica si un jugador tiene suficientes créditos para reclutar a un candidato.
    """
    if player_credits >= candidate_cost:
        return True, "Créditos suficientes."
    else:
        needed = candidate_cost - player_credits
        return False, f"Créditos insuficientes. Se necesitan {needed} más."

def process_recruitment(
    player_id: int, 
    player_credits: int, 
    candidate: Dict[str, Any]
) -> Tuple[int, Dict[str, Any]]:
    """
    Prepara la ACTUALIZACIÓN del personaje para convertirlo de Candidato a Activo.
    
    Args:
        player_id: ID del jugador.
        player_credits: Créditos actuales.
        candidate: El diccionario del personaje (recuperado de characters DB).

    Returns:
        Tuple: (nuevos_creditos, update_data_para_db)
    """
    # 1. Validar fondos (UI debe pre-validar, pero por seguridad)
    # Nota: candidate["costo"] viene inyectado por el repositorio en el refactor
    costo = candidate.get("costo", 100)
    
    can_afford, _ = can_recruit(player_credits, costo)
    if not can_afford:
        raise ValueError("Intento de reclutar sin créditos suficientes.")

    # 2. Calcular balance
    new_credits = player_credits - costo
    
    # 3. Determinar conocimiento inicial (basado en si fue investigado)
    initial_knowledge = KnowledgeLevel.UNKNOWN
    outcome = candidate.get("investigation_outcome")
    if outcome and outcome in ["SUCCESS", "CRIT_SUCCESS"]:
        initial_knowledge = KnowledgeLevel.KNOWN

    # 4. Preparar payload de ACTUALIZACIÓN (no creación)
    # Limpiamos la metadata de reclutamiento del JSON para no ensuciar,
    # o la dejamos como histórico. Preferiblemente limpiar o marcar como reclutado.
    
    stats = candidate.get("stats_json", {}).copy()
    if "recruitment_data" in stats:
        # Opcional: Podríamos borrar stats["recruitment_data"] 
        # o dejarlo como log. Vamos a actualizar ticks_reclutado.
        pass
    
    # IMPORTANTE: La actualización del nivel de conocimiento se debe manejar
    # externamente (repo set_character_knowledge_level) ya que ahora es tabla relacional.
    # Aquí devolvemos los datos para actualizar la entidad Character.

    update_data = {
        "rango": DEFAULT_RECRUIT_RANK,
        "estado": DEFAULT_RECRUIT_STATUS, # "Disponible"
        "ubicacion_local": "Base Principal", # Reemplazo literal de constante eliminada
        # Señal para el controller/repo de que debe actualizar el conocimiento también
        "initial_knowledge_level": initial_knowledge 
    }

    return new_credits, update_data

def analyze_candidates_value(player_id: int, candidates: List[Dict[str, Any]]) -> Dict[int, str]:
    """
    Analiza a los candidatos disponibles y los compara con el roster actual
    para generar recomendaciones estratégicas (Smart Recruitment Advisor).
    
    Returns:
        Dict[candidate_id, recommendation_string]
    """
    recommendations = {}
    if not candidates:
        return recommendations

    # 1. Obtener Roster Actual y sus máximos
    roster = get_all_characters_by_player_id(player_id)
    
    max_attrs = {}
    max_skills = {}
    
    for char in roster:
        # Ignorar personajes retirados o muertos si los hubiera en el fetch general
        # (Aunque el repo suele traer todo, filtremos por seguridad si es necesario)
        stats = char.get("stats_json", {})
        caps = stats.get("capacidades", {})
        
        # Atributos
        for attr, val in caps.get("atributos", {}).items():
            max_attrs[attr] = max(max_attrs.get(attr, 0), val)
            
        # Habilidades
        for skill, val in caps.get("habilidades", {}).items():
            max_skills[skill] = max(max_skills.get(skill, 0), val)

    # 2. Analizar Candidatos
    for cand in candidates:
        cand_id = cand["id"]
        stats = cand.get("stats_json", {})
        caps = stats.get("capacidades", {})
        
        cand_attrs = caps.get("atributos", {})
        cand_skills = caps.get("habilidades", {})
        
        # --- FOG OF WAR LOGIC ---
        # Si NO está investigado (conocido), solo "vemos" el Top 5 de habilidades para la comparación.
        is_known = cand.get("investigation_outcome") in ["SUCCESS", "CRIT_SUCCESS"]
        
        visible_skills = cand_skills
        if not is_known:
            # Simular la visión limitada de la UI: Ordenar y tomar top 5
            sorted_skills = sorted(cand_skills.items(), key=lambda x: -x[1])[:5]
            visible_skills = dict(sorted_skills)
            
        # --- CRITERIOS DE RECOMENDACIÓN ---
        rec_msg = None
        
        # A. Talento Superior (Upgrade) - Atributos (Siempre visibles)
        for attr, val in cand_attrs.items():
            curr_max = max_attrs.get(attr, 0)
            if val >= curr_max + 3:
                rec_msg = f"💡 Consejo Táctico: Potencial físico superior. {attr}: {val} (vs Máx Actual: {curr_max})."
                break # Priorizamos una recomendación por candidato
        
        if not rec_msg:
            # B. Talento Superior (Upgrade) - Habilidades
            for skill, val in visible_skills.items():
                curr_max = max_skills.get(skill, 0)
                if val >= curr_max + 3:
                    rec_msg = f"💡 Consejo Táctico: Mejora significativa en {skill} (Nivel {val} vs tu mejor especialista: {curr_max})."
                    break
        
        if not rec_msg:
            # C. Llenado de Huecos (Gap Filler)
            # El roster tiene < 5 en esta skill y el candidato tiene > 10.
            for skill, val in visible_skills.items():
                curr_max = max_skills.get(skill, 0)
                if curr_max < 5 and val > 10:
                    rec_msg = f"💡 Consejo Táctico: Cubre una debilidad crítica en {skill} ({val})."
                    break

        if rec_msg:
            recommendations[cand_id] = rec_msg
            
    return recommendations