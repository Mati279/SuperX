#!/usr/bin/env python3
"""
Script de prueba para la herramienta scan_galaxy_data
Ejecutar: python test_galaxy_scan.py
"""

import json
from services.ai_tools import scan_galaxy_data

def print_separator():
    print("\n" + "=" * 80 + "\n")

def test_summary_mode():
    """Test 1: Modo SUMMARY - Vista general de la galaxia"""
    print("🧪 TEST 1: Modo SUMMARY")
    print_separator()

    result = scan_galaxy_data(scan_mode="SUMMARY")
    data = json.loads(result)

    print(f"Status: {data['status']}")
    print(f"Total de sistemas: {data['total_systems']}")
    print(f"\nPrimeros 5 sistemas:")

    for system in data['systems'][:5]:
        print(f"  - {system['name']} ({system['star_type']}) @ {system['position']}")
        print(f"    Planetas: {system['planet_count']}, Asteroides: {system['asteroid_belt_count']}")

    print_separator()
    return data['status'] == 'success'

def test_detailed_search():
    """Test 2: Búsqueda DETAILED de un sistema específico"""
    print("🧪 TEST 2: Búsqueda DETAILED (primer sistema)")
    print_separator()

    # Primero obtener un nombre de sistema real
    summary = json.loads(scan_galaxy_data(scan_mode="SUMMARY"))
    first_system_name = summary['systems'][0]['name']

    print(f"Buscando sistema: {first_system_name}")
    result = scan_galaxy_data(system_name=first_system_name, scan_mode="DETAILED")
    data = json.loads(result)

    if data['status'] == 'success':
        system = data['systems'][0]
        print(f"\n✅ Sistema encontrado: {system['name']}")
        print(f"Estrella: {system['star']['name']} (Clase {system['star']['class_type']})")
        print(f"Rareza: {system['star']['rarity']}")
        print(f"Regla especial: {system['star']['special_rule']}")

        print(f"\nAnillos orbitales:")
        for ring_num, body in system['orbital_rings'].items():
            if body['type'] == 'PLANET':
                resources_str = ', '.join(body['resources']) if body['resources'] else 'Ninguno'
                print(f"  Ring {ring_num}: {body['name']} ({body['biome']})")
                print(f"    Tamaño: {body['size']}, Slots: {body['construction_slots']}")
                print(f"    Recursos: {resources_str}")
                print(f"    Lunas: {len(body['moons'])}")
            elif body['type'] == 'ASTEROID_BELT':
                print(f"  Ring {ring_num}: Cinturón de asteroides (Peligro: {body['hazard_level']:.2f})")
            else:
                print(f"  Ring {ring_num}: Vacío")

        print_separator()
        return True
    else:
        print(f"❌ Error: {data.get('message', 'Unknown')}")
        print_separator()
        return False

def test_partial_search():
    """Test 3: Búsqueda parcial por patrón"""
    print("🧪 TEST 3: Búsqueda parcial (patrón 'Alpha')")
    print_separator()

    result = scan_galaxy_data(system_name="Alpha", scan_mode="DETAILED")
    data = json.loads(result)

    if data['status'] == 'success':
        print(f"✅ Encontrados {data['matches_found']} sistema(s) con 'Alpha':")
        for system in data['systems']:
            print(f"  - {system['name']}")
        print_separator()
        return True
    elif data['status'] == 'error':
        print(f"ℹ️  No se encontraron sistemas con 'Alpha' (esto puede ser normal)")
        print_separator()
        return True
    else:
        print(f"❌ Error inesperado")
        print_separator()
        return False

def test_nonexistent_system():
    """Test 4: Búsqueda de sistema inexistente"""
    print("🧪 TEST 4: Sistema inexistente")
    print_separator()

    result = scan_galaxy_data(system_name="Tatooine-Fake-999", scan_mode="DETAILED")
    data = json.loads(result)

    if data['status'] == 'error':
        print(f"✅ Error esperado: {data['message']}")
        print(f"Hint: {data['hint']}")
        print_separator()
        return True
    else:
        print(f"❌ Debería haber devuelto error")
        print_separator()
        return False

def test_find_resources():
    """Test 5: Buscar planetas con un recurso específico"""
    print("🧪 TEST 5: Buscar planetas con recursos específicos")
    print_separator()

    target_resource = "Hierro"
    print(f"Buscando planetas con '{target_resource}'...")

    # Obtener todos los sistemas
    summary = json.loads(scan_galaxy_data(scan_mode="SUMMARY"))
    planets_found = []

    # Buscar en cada sistema (limitar a 10 para no saturar)
    for system in summary['systems'][:10]:
        details = json.loads(scan_galaxy_data(system_name=system['name'], scan_mode="DETAILED"))
        if details['status'] == 'success':
            for ring_num, body in details['systems'][0]['orbital_rings'].items():
                if body.get('type') == 'PLANET' and target_resource in body.get('resources', []):
                    planets_found.append({
                        'system': system['name'],
                        'planet': body['name'],
                        'ring': ring_num,
                        'resources': body['resources']
                    })

    print(f"\n✅ Encontrados {len(planets_found)} planeta(s) con {target_resource} (en los primeros 10 sistemas):")
    for planet in planets_found[:5]:  # Mostrar solo los primeros 5
        resources_str = ', '.join(planet['resources'])
        print(f"  - {planet['planet']} en {planet['system']} (Ring {planet['ring']})")
        print(f"    Recursos: {resources_str}")

    print_separator()
    return True

def main():
    """Ejecutar todos los tests"""
    print("\n🚀 INICIANDO TESTS DE scan_galaxy_data")
    print("=" * 80)

    tests = [
        ("Summary Mode", test_summary_mode),
        ("Detailed Search", test_detailed_search),
        ("Partial Search", test_partial_search),
        ("Nonexistent System", test_nonexistent_system),
        ("Find Resources", test_find_resources),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ ERROR CRÍTICO en {test_name}: {e}")
            results.append((test_name, False))

    # Resumen final
    print("\n📊 RESUMEN DE TESTS")
    print("=" * 80)
    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nResultado final: {passed}/{total} tests pasados")

    if passed == total:
        print("\n🎉 ¡Todos los tests pasaron exitosamente!")
    else:
        print(f"\n⚠️  {total - passed} test(s) fallaron")

    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
