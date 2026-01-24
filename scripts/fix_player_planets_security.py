# scripts/fix_player_planets_security.py (Completo)
import sys
import os

# Ajuste de path para encontrar módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.database import get_supabase
# V9.1: Usamos calculate_and_update_system_security para obtener breakdown completo
from core.rules import calculate_planet_security, calculate_and_update_system_security

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
    
    # Aunque no haya planetas colonizados, queremos ejecutar la Fase 3 (Limpieza de Sistemas)
    # Así que no retornamos si planets está vacío, solo saltamos el bucle.

    updated_count = 0
    error_count = 0

    # 2. Recalcular y actualizar Planetas (Solo colonizados)
    if planets:
        print("🔄 Fase 1: Recalculando seguridad de colonias...")
        for p in planets:
            try:
                pid = p["id"]
                name = p.get("name", "Desconocido")
                base_def = p.get("base_defense", 10) or 10
                pop = p.get("population", 0.0) or 0.0
                ring = p.get("orbital_ring", 3) or 3
                
                # Asumimos infraestructura 0 para este fix masivo
                infra_def = 0 
                
                # Usar la función central de reglas
                calc_result = calculate_planet_security(
                    base_stat=base_def,
                    pop_count=pop,
                    infrastructure_defense=infra_def,
                    orbital_ring=ring,
                    is_player_owned=True
                )
                
                # Manejo dual (Dict vs Float)
                new_security = 0.0
                new_breakdown = {}
                
                if isinstance(calc_result, dict):
                    new_security = calc_result.get("total", 20.0)
                    new_breakdown = calc_result
                else:
                    new_security = float(calc_result)
                    new_breakdown = {}
                
                # Actualizar DB
                upd_res = db.table("planets").update({
                    "security": new_security,
                    "security_breakdown": new_breakdown
                }).eq("id", pid).execute()
                
                if upd_res:
                    print(f"   -> Reparado {name} (ID {pid}): Seguridad {new_security:.1f}")
                    updated_count += 1
                else:
                    print(f"   ⚠️ Fallo al actualizar {name} (ID {pid})")
                    error_count += 1
                    
            except Exception as ex:
                print(f"   ❌ Error procesando ID {p.get('id')}: {ex}")
                error_count += 1
    else:
        print("   (Sin colonias para reparar, saltando Fase 1)")

    # 3. Fase de Sistemas Global (Limpieza de valores estáticos)
    print(f"\n🌍 Fase 2: Sincronización Global de Sistemas (Limpieza de valores estáticos)...")
    
    try:
        # Obtener TODOS los sistemas
        sys_res = db.table("systems").select("id").execute()
        all_systems = sys_res.data if sys_res and sys_res.data else []
    except Exception as e:
        print(f"❌ Error obteniendo sistemas: {e}")
        all_systems = []
        
    print(f"   -> Procesando {len(all_systems)} sistemas...")
    
    systems_updated = 0
    for s in all_systems:
        try:
            sys_id = s["id"]
            # Usamos calculate_and_update_system_security que genera el breakdown y actualiza la DB
            # Esta función maneja internamente el promedio de los planetas del sistema
            calculate_and_update_system_security(sys_id)
            
            if systems_updated % 5 == 0:
                print(f"      Sincronizado sistema {sys_id}...", end="\r")
            systems_updated += 1
        except Exception as e:
             print(f"   ❌ Error actualizando sistema {s.get('id')}: {e}")

    print(f"\n\n✨ Reparación finalizada.")
    print(f"   - Planetas (Colonias) actualizados: {updated_count}")
    print(f"   - Sistemas (Global) sincronizados: {systems_updated}")
    print(f"   - Errores en planetas: {error_count}")

if __name__ == "__main__":
    fix_security()