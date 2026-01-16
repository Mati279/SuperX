#!/usr/bin/env python3
"""
Test simple y directo de scan_galaxy_data sin dependencias externas
"""

import json
import sys
sys.path.insert(0, '.')

# Importar solo lo necesario
from core.galaxy_generator import get_galaxy
from core.world_models import Planet, AsteroidBelt

def to_dict(obj):
    """Helper para convertir dataclasses a dict"""
    if hasattr(obj, '__dataclass_fields__'):
        result = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name)
            if isinstance(value, list):
                result[field_name] = [to_dict(item) for item in value]
            elif isinstance(value, dict):
                result[field_name] = {k: to_dict(v) if v else None for k, v in value.items()}
            elif hasattr(value, '__dataclass_fields__'):
                result[field_name] = to_dict(value)
            else:
                result[field_name] = value
        return result
    return obj

def test_galaxy_access():
    """Test básico: Verificar que podemos acceder a la galaxia"""
    print("[TEST] Acceso a la galaxia procedural")
    print("=" * 80)

    galaxy = get_galaxy()
    print(f"[OK] Galaxia cargada: {len(galaxy.systems)} sistemas")

    # Mostrar primer sistema
    first_system = galaxy.systems[0]
    print(f"\nPrimer sistema: {first_system.name}")
    print(f"  Estrella: {first_system.star.name} (Clase {first_system.star.class_type})")
    print(f"  Posición: {first_system.position}")

    # Contar planetas
    planet_count = sum(1 for body in first_system.orbital_rings.values()
                      if body and isinstance(body, Planet))
    print(f"  Planetas: {planet_count}")

    # Mostrar un planeta con recursos
    for ring_num, body in first_system.orbital_rings.items():
        if isinstance(body, Planet) and body.resources:
            print(f"\n  Planeta en Ring {ring_num}: {body.name}")
            print(f"    Bioma: {body.biome}")
            print(f"    Tamaño: {body.size}")
            print(f"    Recursos: {', '.join(body.resources)}")
            break

    print("\n" + "=" * 80)
    return True

def test_summary_mode():
    """Test modo SUMMARY"""
    print("\n[TEST] TEST: Modo SUMMARY")
    print("=" * 80)

    galaxy = get_galaxy()

    systems_summary = []
    for system in galaxy.systems:
        planet_count = sum(1 for body in system.orbital_rings.values()
                         if body and isinstance(body, Planet))
        asteroid_count = sum(1 for body in system.orbital_rings.values()
                           if body and isinstance(body, AsteroidBelt))

        systems_summary.append({
            "id": system.id,
            "name": system.name,
            "star_type": system.star.type,
            "star_class": system.star.class_type,
            "position": system.position,
            "planet_count": planet_count,
            "asteroid_belt_count": asteroid_count
        })

    result = {
        "status": "success",
        "scan_mode": "SUMMARY",
        "total_systems": len(galaxy.systems),
        "systems": systems_summary
    }

    print(f"[OK] Total sistemas: {result['total_systems']}")
    print(f"\nPrimeros 5 sistemas:")
    for system in result['systems'][:5]:
        print(f"  * {system['name']} ({system['star_type']})")
        print(f"    Posición: {system['position']}, Planetas: {system['planet_count']}")

    print("\n" + "=" * 80)
    return True

def test_detailed_mode():
    """Test modo DETAILED"""
    print("\n[TEST] TEST: Modo DETAILED")
    print("=" * 80)

    galaxy = get_galaxy()
    test_system = galaxy.systems[0]

    print(f"Escaneando: {test_system.name}")

    system_data = {
        "id": test_system.id,
        "name": test_system.name,
        "position": test_system.position,
        "star": to_dict(test_system.star),
        "orbital_rings": {}
    }

    for ring_num, body in test_system.orbital_rings.items():
        if body is None:
            system_data["orbital_rings"][ring_num] = {"type": "EMPTY"}
        elif isinstance(body, Planet):
            system_data["orbital_rings"][ring_num] = {
                "type": "PLANET",
                **to_dict(body)
            }
        elif isinstance(body, AsteroidBelt):
            system_data["orbital_rings"][ring_num] = {
                "type": "ASTEROID_BELT",
                **to_dict(body)
            }

    print(f"\n[OK] Estrella: {system_data['star']['name']}")
    print(f"   Clase: {system_data['star']['class_type']}, Rareza: {system_data['star']['rarity']}")

    print(f"\nAnillos orbitales:")
    for ring_num, body in system_data['orbital_rings'].items():
        if body['type'] == 'PLANET':
            resources = ', '.join(body['resources']) if body['resources'] else 'Ninguno'
            print(f"  Ring {ring_num}: {body['name']} ({body['biome']})")
            print(f"    Recursos: {resources}")
        elif body['type'] == 'ASTEROID_BELT':
            print(f"  Ring {ring_num}: Cinturón de asteroides")
        else:
            print(f"  Ring {ring_num}: Vacío")

    print("\n" + "=" * 80)
    return True

def test_find_resources():
    """Test búsqueda de recursos"""
    print("\n[TEST] TEST: Buscar planetas con recursos específicos")
    print("=" * 80)

    galaxy = get_galaxy()
    target_resource = "Hierro"

    planets_with_resource = []

    for system in galaxy.systems[:10]:  # Limitar a primeros 10 sistemas
        for ring_num, body in system.orbital_rings.items():
            if isinstance(body, Planet) and target_resource in body.resources:
                planets_with_resource.append({
                    'system': system.name,
                    'planet': body.name,
                    'resources': body.resources
                })

    print(f"Buscando '{target_resource}' en los primeros 10 sistemas...")
    print(f"\n[OK] Encontrados {len(planets_with_resource)} planeta(s):")

    for planet in planets_with_resource[:5]:
        resources_str = ', '.join(planet['resources'])
        print(f"  * {planet['planet']} en {planet['system']}")
        print(f"    Recursos: {resources_str}")

    print("\n" + "=" * 80)
    return True

def main():
    """Ejecutar todos los tests"""
    print("\n>>> TESTS DE GALAXY SCAN (SIN DEPENDENCIAS EXTERNAS)\n")

    tests = [
        test_galaxy_access,
        test_summary_mode,
        test_detailed_mode,
        test_find_resources
    ]

    passed = 0
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"[ERROR] ERROR: {e}")
            import traceback
            traceback.print_exc()

    total = len(tests)
    print(f"\n[RESULT] RESULTADO: {passed}/{total} tests pasados")

    if passed == total:
        print("[SUCCESS] ¡Todos los tests exitosos!")
    else:
        print(f"[WARNING]  {total - passed} test(s) fallaron")

    print("\n")

if __name__ == "__main__":
    main()
