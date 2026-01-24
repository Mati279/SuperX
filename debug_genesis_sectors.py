import sys
import os
import argparse
import json
import traceback
from typing import List, Dict, Any
from unittest.mock import MagicMock, patch

# --- CONFIGURACIÓN DE ENTORNO ---
# Aseguramos que el script pueda importar módulos del proyecto desde la raíz
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from data.database import get_supabase
    from data.planet_repository import initialize_planet_sectors
    from core.world_constants import SECTOR_TYPE_URBAN, SECTOR_TYPE_ORBITAL
except ImportError as e:
    print(f"❌ Error de Importación: No se detectan los módulos del proyecto.\nAsegúrate de ejecutar este script en la raíz del proyecto.\nDetalle: {e}")
    sys.exit(1)

# --- UTILIDADES DE VISUALIZACIÓN ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(msg: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {msg} ==={Colors.ENDC}")

def print_step(msg: str):
    print(f"{Colors.CYAN}➤ {msg}{Colors.ENDC}")

def print_success(msg: str):
    print(f"{Colors.GREEN}✔ {msg}{Colors.ENDC}")

def print_error(msg: str):
    print(f"{Colors.FAIL}✘ {msg}{Colors.ENDC}")

def print_warning(msg: str):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")

def format_json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)

# --- LÓGICA DE NEGOCIO ---

def get_db():
    return get_supabase()

def fetch_planet_details(planet_id: int) -> Dict[str, Any]:
    """Obtiene datos base del planeta necesarios para la inicialización."""
    db = get_db()
    res = db.table("planets").select("id, name, biome, mass_class").eq("id", planet_id).single().execute()
    if not res.data:
        raise ValueError(f"El planeta ID {planet_id} no existe.")
    return res.data

def fetch_current_sectors(planet_id: int) -> List[Dict[str, Any]]:
    """Obtiene los sectores actuales de la base de datos."""
    db = get_db()
    res = db.table("sectors").select("*").eq("planet_id", planet_id).order("id").execute()
    return res.data if res.data else []

def clean_planet_sectors(planet_id: int):
    """BORRADO FÍSICO de sectores para testing limpio."""
    print_warning(f"EJECUTANDO LIMPIEZA: Borrando sectores del planeta {planet_id}...")
    db = get_db()
    # Primero borramos edificios dependientes para evitar errores de FK si existen
    # (Asumiendo cascada, pero por seguridad en testing)
    sector_ids_res = db.table("sectors").select("id").eq("planet_id", planet_id).execute()
    if sector_ids_res.data:
        s_ids = [s['id'] for s in sector_ids_res.data]
        db.table("planet_buildings").delete().in_("sector_id", s_ids).execute()
        
    db.table("sectors").delete().eq("planet_id", planet_id).execute()
    print_success("Sectores eliminados correctamente.")

def verify_sector_integrity(sectors: List[Dict[str, Any]], planet_id: int) -> bool:
    """Verifica reglas de negocio y consistencia de IDs."""
    has_error = False
    urban_found = False
    orbital_found = False
    
    print_step("Analizando integridad de sectores...")
    
    for s in sectors:
        sid = s.get('id')
        stype = s.get('sector_type')
        name = s.get('name')
        
        # 1. Validación de ID Manual
        # El ID debe ser mayor a planet_id * 1000 y menor a (planet_id + 1) * 1000
        min_id = planet_id * 1000
        max_id = (planet_id + 1) * 1000
        
        if not (min_id < sid < max_id):
            print_error(f"ID Inválido para sector {name}: {sid}. Debería estar entre {min_id} y {max_id}.")
            has_error = True
        
        # 2. Tipos Requeridos
        if stype == SECTOR_TYPE_URBAN:
            urban_found = True
            expected_id = min_id + 1
            # Nota: Si hubo transformación, el ID puede no ser ...001, eso es aceptable en legacy,
            # pero en limpieza total debería ser ...001.
            print(f"   - Urbano encontrado: ID {sid} ({name})")
            
        if stype == SECTOR_TYPE_ORBITAL:
            orbital_found = True
            expected_orbital_id = min_id + 99
            if sid != expected_orbital_id:
                print_warning(f"Sector Orbital tiene ID no estándar: {sid}. Esperado: {expected_orbital_id}")
            else:
                print(f"   - Orbital encontrado: ID {sid} (Correcto)")

    if not urban_found:
        print_error("Falta el Sector Urbano (Distrito Central).")
        has_error = True
    
    if not orbital_found:
        print_error("Falta el Sector Orbital.")
        has_error = True

    return not has_error

# --- MOCKING PARA DRY RUN ---
def dry_run_simulation(planet_id: int, biome: str, mass_class: str):
    """
    Simula la ejecución interceptando las llamadas a la DB dentro de planet_repository.
    """
    print_header("MODO SIMULACIÓN (DRY-RUN)")
    print("Interceptando escrituras a base de datos...")

    # Mock del cliente de Supabase
    mock_supabase = MagicMock()
    
    # Configurar el mock para lecturas (debe devolver datos reales o vacíos para simular)
    # Para simular correctamente initialize_planet_sectors, necesitamos que el 'select' devuelva
    # el estado actual.
    
    real_sectors = fetch_current_sectors(planet_id)
    
    # Configurar retorno de select().eq().execute()
    # Esto es complejo de mockear perfectamente dada la cadena fluida de Supabase.
    # En su lugar, usaremos un enfoque híbrido: 
    # Mockear solo .insert() y .update() en data.planet_repository._get_db
    
    original_get_db = sys.modules['data.planet_repository']._get_db
    
    def side_effect_insert(data):
        print(f"{Colors.BLUE}[DRY-RUN] INSERT detectado en tabla 'sectors':{Colors.ENDC}")
        print(format_json(data))
        return MagicMock(data=[data] if isinstance(data, dict) else data)

    def side_effect_update(data):
        print(f"{Colors.BLUE}[DRY-RUN] UPDATE detectado en tabla 'sectors':{Colors.ENDC}")
        print(format_json(data))
        return MagicMock(data=[data])

    # Creamos un proxy que usa la DB real para lecturas pero mockea escrituras
    class SafeDbProxy:
        def __init__(self, real_client):
            self.real = real_client
            
        def table(self, name):
            table_mock = MagicMock()
            real_table = self.real.table(name)
            
            # Pasamos las lecturas al real
            def select(*args, **kwargs):
                return real_table.select(*args, **kwargs)
            
            table_mock.select = select
            
            # Interceptamos escrituras
            if name == "sectors":
                table_mock.insert = MagicMock(side_effect=lambda d: MagicMock(execute=lambda: side_effect_insert(d)))
                table_mock.update = MagicMock(side_effect=lambda d: MagicMock(eq=lambda k,v: MagicMock(execute=lambda: side_effect_update(d))))
            else:
                # Para otras tablas, comportamiento por defecto (o error safe)
                table_mock = real_table
                
            return table_mock

    # Patching
    proxy = SafeDbProxy(get_db())
    
    with patch('data.planet_repository._get_db', return_value=proxy):
        print_step(f"Ejecutando initialize_planet_sectors({planet_id}, {biome}, {mass_class})...")
        initialize_planet_sectors(planet_id, biome, mass_class)
        print_success("Simulación finalizada. No se realizaron cambios en la DB.")

# --- MAIN ---

def main():
    parser = argparse.ArgumentParser(description="Debug y Fix de Inicialización de Sectores (Genesis Protocol)")
    parser.add_argument("planet_id", type=int, help="ID del planeta a diagnosticar")
    parser.add_argument("--clean", action="store_true", help="BORRA los sectores existentes del planeta antes de iniciar (Reset)")
    parser.add_argument("--dry-run", action="store_true", help="Simula las operaciones de inserción/actualización sin escribir en la DB")
    
    args = parser.parse_args()
    planet_id = args.planet_id
    
    print_header(f"DIAGNÓSTICO GENESIS SECTORS - PLANETA {planet_id}")
    
    try:
        # 0. Obtener Info Planeta
        p_info = fetch_planet_details(planet_id)
        biome = p_info.get('biome', 'Desconocido')
        mass = p_info.get('mass_class', 'Estándar') or 'Estándar' # Fallback como en el código
        
        print(f"Datos Planeta: {p_info['name']} | Bioma: {biome} | Masa: {mass}")
        
        # 1. Limpieza (Opcional)
        if args.clean:
            if args.dry_run:
                print_warning("Flag --clean ignorado en modo --dry-run para protección.")
            else:
                clean_planet_sectors(planet_id)

        # 2. Estado Previo
        print_header("FASE 1: ESTADO ACTUAL")
        sectors_before = fetch_current_sectors(planet_id)
        if not sectors_before:
            print_warning("No hay sectores registrados.")
        else:
            print(f"Encontrados {len(sectors_before)} sectores.")
            for s in sectors_before:
                print(f" - [{s['id']}] {s['name']} ({s['sector_type']})")

        # 3. Ejecución
        print_header("FASE 2: EJECUCIÓN")
        
        if args.dry_run:
            dry_run_simulation(planet_id, biome, mass)
            return # Salimos en dry-run porque la fase 3 fallaría (no se escribieron datos)
        
        print_step(f"Llamando a initialize_planet_sectors({planet_id}, {biome}, {mass})...")
        sectors_result = initialize_planet_sectors(planet_id, biome, mass)
        
        if sectors_result:
            print_success(f"Función retornó {len(sectors_result)} sectores.")
        else:
            print_error("Función retornó lista vacía (posible fallo crítico capturado internamente).")

        # 4. Verificación
        print_header("FASE 3: VERIFICACIÓN POST-EJECUCIÓN")
        sectors_after = fetch_current_sectors(planet_id)
        
        print(f"Sectores en DB: {len(sectors_after)}")
        for s in sectors_after:
            print(f" - [{s['id']}] {s['name']} ({s['sector_type']}) - Slots: {s.get('max_slots')}")
            
        is_valid = verify_sector_integrity(sectors_after, planet_id)
        
        if is_valid:
            print_header("RESULTADO FINAL: ✅ ÉXITO")
            print(f"El planeta {planet_id} tiene una estructura de sectores válida para el Protocolo Génesis.")
        else:
            print_header("RESULTADO FINAL: ❌ FALLO")
            print("Se detectaron inconsistencias en la generación de sectores.")
            
    except Exception as e:
        print_header("EXCEPCIÓN NO CONTROLADA")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()