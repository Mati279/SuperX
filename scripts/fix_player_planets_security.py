# scripts/fix_player_planets_security.py (Completo)
import sys
import os

# Ajuste de path para encontrar módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.database import get_supabase
from core.rules import calculate_planet_security
# V9.1: Importamos la función para recalcular el sistema
from data.planet_repository import recalculate_system_security

def fix_security():
    print("🛠️ Iniciando reparación de seguridad en planetas de jugadores...")
    
    db = get_supabase()
    if not db:
        print("❌ Error: No se pudo conectar a Supabase.")
        return

    # 1. Obtener planetas de jugadores (surface_owner_id NOT NULL)
    print("🔍 Buscando planetas colonizados...")
    try:
        # Filtro compatible con postgrest: not.is.null
        response = db.table("planets")\
            .select("*")\
            .not_.is_("surface_owner_id", "null")\
            .execute()
    except Exception as e:
        print(f"❌ Error consultando planetas: {e}")
        return

    planets = response.data if response and response.data else []
    print(f"✅ Encontrados {len(planets)} planetas colonizados.")
    
    if not planets:
        return

    updated_count = 0
    error_count = 0
    affected_systems = set() # V9.1: Set para guardar IDs de sistemas únicos

    # 2. Recalcular y actualizar Planetas
    for p in planets:
        try:
            pid = p["id"]
            sid = p.get("system_id") # V9.1: Obtener ID del sistema
            name = p.get("name", "Desconocido")
            base_def = p.get("base_defense", 10) or 10
            pop = p.get("population", 0.0) or 0.0
            ring = p.get("orbital_ring", 3) or 3
            
            # Nota: Asumimos infraestructura 0 para este fix masivo, 
            # o podríamos hacer un join complejo para sumarla. 
            # Para desatascar el '0' crítico, el cálculo base es suficiente.
            infra_def = 0 
            
            # Usar la función central de reglas
            calc_result = calculate_planet_security(
                base_stat=base_def,
                pop_count=pop,
                infrastructure_defense=infra_def,
                orbital_ring=ring,
                is_player_owned=True
            )
            
            # Manejo dual (Dict vs Float) similar al repositorio
            new_security = 0.0
            new_breakdown = {}
            
            if isinstance(calc_result, dict):
                new_security = calc_result.get("total", 20.0)
                new_breakdown = calc_result
            else:
                new_security = float(calc_result)
                new_breakdown = {} # O un dict manual si se desea
            
            # Actualizar DB
            upd_res = db.table("planets").update({
                "security": new_security,
                "security_breakdown": new_breakdown
            }).eq("id", pid).execute()
            
            if upd_res:
                print(f"   -> Reparado {name} (ID {pid}): Seguridad {new_security:.1f}")
                updated_count += 1
                if sid:
                    affected_systems.add(sid) # V9.1: Marcar sistema para recálculo
            else:
                print(f"   ⚠️ Fallo al actualizar {name} (ID {pid})")
                error_count += 1
                
        except Exception as ex:
            print(f"   ❌ Error procesando ID {p.get('id')}: {ex}")
            error_count += 1

    # 3. Fase de Sistemas (V9.1)
    print(f"\n🔄 Recalculando seguridad de {len(affected_systems)} sistemas afectados...")
    systems_updated = 0
    for sys_id in affected_systems:
        try:
            new_val = recalculate_system_security(sys_id)
            print(f"   -> Sistema {sys_id}: Nueva Seguridad Promedio {new_val:.2f}")
            systems_updated += 1
        except Exception as e:
             print(f"   ❌ Error actualizando sistema {sys_id}: {e}")

    print(f"\n✨ Reparación finalizada.")
    print(f"   - Planetas actualizados: {updated_count}")
    print(f"   - Sistemas sincronizados: {systems_updated}")
    print(f"   - Errores: {error_count}")

if __name__ == "__main__":
    fix_security()