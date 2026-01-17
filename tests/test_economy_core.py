# tests/test_economy_core.py
"""
Tests unitarios para el Motor Económico (economy_engine.py).
Prueba la lógica de cálculo económico SIN conexión a base de datos real.

Ejecutar con: pytest tests/test_economy_core.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

# Importar funciones puras a testear
from core.economy_engine import (
    calculate_security_multiplier,
    calculate_income,
    calculate_building_maintenance,
    calculate_planet_production,
    calculate_cascade_shutdown,
    calculate_luxury_extraction,
    merge_luxury_resources,
    process_planet_tick,
    CascadeResult
)
from core.models import ProductionSummary


# --- FIXTURES ---

@pytest.fixture
def sample_buildings() -> List[Dict[str, Any]]:
    """Edificios de ejemplo para tests."""
    return [
        {
            "id": 1,
            "planet_asset_id": 100,
            "player_id": 1,
            "building_type": "mina_basica",
            "is_active": True,
            "pops_required": 100,
            "energy_consumption": 5
        },
        {
            "id": 2,
            "planet_asset_id": 100,
            "player_id": 1,
            "building_type": "fabrica_componentes",
            "is_active": True,
            "pops_required": 200,
            "energy_consumption": 10
        },
        {
            "id": 3,
            "planet_asset_id": 100,
            "player_id": 1,
            "building_type": "generador_energia",
            "is_active": False,
            "pops_required": 50,
            "energy_consumption": 0
        }
    ]


@pytest.fixture
def sample_planet() -> Dict[str, Any]:
    """Planeta de ejemplo para tests."""
    return {
        "id": 100,
        "planet_id": 1,
        "system_id": 1,
        "player_id": 1,
        "nombre_asentamiento": "Colonia Alfa",
        "poblacion": 1000,
        "pops_activos": 800,
        "pops_desempleados": 200,
        "seguridad": 1.0,
        "infraestructura_defensiva": 10,
        "felicidad": 1.2,
        "buildings": []
    }


@pytest.fixture
def sample_luxury_sites() -> List[Dict[str, Any]]:
    """Sitios de extracción de lujo para tests."""
    return [
        {
            "id": 1,
            "player_id": 1,
            "resource_key": "cristales_raros",
            "resource_category": "minerales",
            "extraction_rate": 5,
            "is_active": True
        },
        {
            "id": 2,
            "player_id": 1,
            "resource_key": "gas_noble",
            "resource_category": "gases",
            "extraction_rate": 3,
            "is_active": True
        },
        {
            "id": 3,
            "player_id": 1,
            "resource_key": "cristales_raros",
            "resource_category": "minerales",
            "extraction_rate": 2,
            "is_active": False  # Inactivo
        }
    ]


# --- TESTS: CALCULATE_SECURITY_MULTIPLIER ---

class TestCalculateSecurityMultiplier:
    """Tests para calculate_security_multiplier."""

    def test_zero_infrastructure(self):
        """Sin infraestructura defensiva, retorna seguridad mínima."""
        with patch.dict('core.economy_engine.ECONOMY_RATES', {
            'infrastructure_security_rate': 0.01,
            'security_min': 0.5,
            'security_max': 1.2
        }):
            result = calculate_security_multiplier(0)
            assert result == 0.5

    def test_max_infrastructure(self):
        """Con mucha infraestructura, no excede el máximo."""
        with patch.dict('core.economy_engine.ECONOMY_RATES', {
            'infrastructure_security_rate': 0.01,
            'security_min': 0.5,
            'security_max': 1.2
        }):
            result = calculate_security_multiplier(100)
            assert result == 1.2  # Capped at max

    def test_medium_infrastructure(self):
        """Infraestructura media da seguridad proporcional."""
        with patch.dict('core.economy_engine.ECONOMY_RATES', {
            'infrastructure_security_rate': 0.01,
            'security_min': 0.5,
            'security_max': 1.2
        }):
            result = calculate_security_multiplier(50)
            assert result == 1.0  # 0.5 + (50 * 0.01) = 1.0


# --- TESTS: CALCULATE_INCOME ---

class TestCalculateIncome:
    """Tests para calculate_income."""

    def test_basic_income(self):
        """Ingresos básicos sin modificadores."""
        with patch.dict('core.economy_engine.ECONOMY_RATES', {
            'income_per_pop': 1.0,
            'happiness_bonus_max': 0.5
        }):
            result = calculate_income(
                population=1000,
                security=1.0,
                happiness=1.0
            )
            assert result == 1000

    def test_income_with_low_security(self):
        """Seguridad baja reduce ingresos."""
        with patch.dict('core.economy_engine.ECONOMY_RATES', {
            'income_per_pop': 1.0,
            'happiness_bonus_max': 0.5
        }):
            result = calculate_income(
                population=1000,
                security=0.5,
                happiness=1.0
            )
            assert result == 500

    def test_income_with_high_happiness(self):
        """Felicidad alta aumenta ingresos."""
        with patch.dict('core.economy_engine.ECONOMY_RATES', {
            'income_per_pop': 1.0,
            'happiness_bonus_max': 0.5
        }):
            result = calculate_income(
                population=1000,
                security=1.0,
                happiness=1.5
            )
            # Con happiness 1.5, bonus = 50%
            assert result == 1500

    def test_income_zero_population(self):
        """Sin población, sin ingresos."""
        with patch.dict('core.economy_engine.ECONOMY_RATES', {
            'income_per_pop': 1.0,
            'happiness_bonus_max': 0.5
        }):
            result = calculate_income(
                population=0,
                security=1.0,
                happiness=1.0
            )
            assert result == 0


# --- TESTS: CALCULATE_BUILDING_MAINTENANCE ---

class TestCalculateBuildingMaintenance:
    """Tests para calculate_building_maintenance."""

    def test_active_buildings_only(self, sample_buildings):
        """Solo cuenta edificios activos."""
        with patch.dict('core.economy_engine.BUILDING_TYPES', {
            'mina_basica': {'energy_cost': 5},
            'fabrica_componentes': {'energy_cost': 10},
            'generador_energia': {'energy_cost': 0}
        }):
            result = calculate_building_maintenance(sample_buildings)
            # Solo edificios 1 y 2 están activos (5 + 10 = 15)
            assert result['celulas_energia'] == 15

    def test_no_buildings(self):
        """Sin edificios, sin mantenimiento."""
        result = calculate_building_maintenance([])
        assert result['celulas_energia'] == 0

    def test_all_inactive(self, sample_buildings):
        """Todos inactivos, sin mantenimiento."""
        inactive_buildings = [
            {**b, 'is_active': False} for b in sample_buildings
        ]
        result = calculate_building_maintenance(inactive_buildings)
        assert result['celulas_energia'] == 0


# --- TESTS: CALCULATE_CASCADE_SHUTDOWN ---

class TestCalculateCascadeShutdown:
    """Tests para calculate_cascade_shutdown."""

    def test_sufficient_pops_no_shutdown(self):
        """Con suficientes POPs, no se desactiva nada."""
        buildings = [
            {"id": 1, "building_type": "mina", "is_active": True, "pops_required": 100},
            {"id": 2, "building_type": "fab", "is_active": True, "pops_required": 100}
        ]

        with patch.dict('core.economy_engine.BUILDING_TYPES', {
            'mina': {'category': 'extraccion'},
            'fab': {'category': 'industria'}
        }):
            with patch.dict('core.economy_engine.BUILDING_SHUTDOWN_PRIORITY', {
                'extraccion': 4,
                'industria': 2
            }):
                result = calculate_cascade_shutdown(500, buildings)

        assert len(result.buildings_to_disable) == 0
        assert result.remaining_pops == 300

    def test_insufficient_pops_triggers_shutdown(self):
        """Sin suficientes POPs, se desactivan edificios."""
        buildings = [
            {"id": 1, "building_type": "mina", "is_active": True, "pops_required": 100},
            {"id": 2, "building_type": "fab", "is_active": True, "pops_required": 200}
        ]

        with patch.dict('core.economy_engine.BUILDING_TYPES', {
            'mina': {'category': 'extraccion', 'name': 'Mina'},
            'fab': {'category': 'industria', 'name': 'Fábrica'}
        }):
            with patch.dict('core.economy_engine.BUILDING_SHUTDOWN_PRIORITY', {
                'extraccion': 4,  # Menor prioridad = se desactiva primero
                'industria': 2
            }):
                result = calculate_cascade_shutdown(100, buildings)

        # Debería desactivar fábrica (prioridad 2) antes que mina (prioridad 4)
        assert len(result.buildings_to_disable) >= 1

    def test_reactivation_when_pops_available(self):
        """Reactiva edificios cuando hay POPs disponibles."""
        buildings = [
            {"id": 1, "building_type": "mina", "is_active": True, "pops_required": 100},
            {"id": 2, "building_type": "fab", "is_active": False, "pops_required": 50}
        ]

        with patch.dict('core.economy_engine.BUILDING_TYPES', {
            'mina': {'category': 'extraccion', 'name': 'Mina'},
            'fab': {'category': 'industria', 'name': 'Fábrica'}
        }):
            with patch.dict('core.economy_engine.BUILDING_SHUTDOWN_PRIORITY', {
                'extraccion': 4,
                'industria': 2
            }):
                result = calculate_cascade_shutdown(200, buildings)

        # Con 200 POPs y solo 100 requeridos, debería reactivar el inactivo
        assert len(result.buildings_to_enable) == 1
        assert result.buildings_to_enable[0][0] == 2


# --- TESTS: CALCULATE_LUXURY_EXTRACTION ---

class TestCalculateLuxuryExtraction:
    """Tests para calculate_luxury_extraction."""

    def test_active_sites_only(self, sample_luxury_sites):
        """Solo procesa sitios activos."""
        result = calculate_luxury_extraction(sample_luxury_sites)

        assert "minerales.cristales_raros" in result
        assert result["minerales.cristales_raros"] == 5  # Solo el activo
        assert "gases.gas_noble" in result
        assert result["gases.gas_noble"] == 3

    def test_no_sites(self):
        """Sin sitios, sin extracción."""
        result = calculate_luxury_extraction([])
        assert len(result) == 0

    def test_aggregation(self):
        """Agrega múltiples sitios del mismo recurso."""
        sites = [
            {"resource_key": "x", "resource_category": "cat", "extraction_rate": 5, "is_active": True},
            {"resource_key": "x", "resource_category": "cat", "extraction_rate": 3, "is_active": True}
        ]
        result = calculate_luxury_extraction(sites)
        assert result["cat.x"] == 8


# --- TESTS: MERGE_LUXURY_RESOURCES ---

class TestMergeLuxuryResources:
    """Tests para merge_luxury_resources."""

    def test_merge_new_resources(self):
        """Añade nuevos recursos a diccionario vacío."""
        current = {}
        extracted = {"minerales.oro": 10}

        result = merge_luxury_resources(current, extracted)

        assert "minerales" in result
        assert result["minerales"]["oro"] == 10

    def test_merge_existing_resources(self):
        """Suma a recursos existentes."""
        current = {"minerales": {"oro": 5}}
        extracted = {"minerales.oro": 10}

        result = merge_luxury_resources(current, extracted)

        assert result["minerales"]["oro"] == 15

    def test_merge_mixed(self):
        """Maneja combinación de nuevos y existentes."""
        current = {"minerales": {"oro": 5}}
        extracted = {
            "minerales.oro": 10,
            "gases.helio": 3
        }

        result = merge_luxury_resources(current, extracted)

        assert result["minerales"]["oro"] == 15
        assert result["gases"]["helio"] == 3


# --- TESTS: PROCESS_PLANET_TICK ---

class TestProcessPlanetTick:
    """Tests para process_planet_tick."""

    def test_basic_planet_processing(self, sample_planet):
        """Procesa un planeta básico correctamente."""
        with patch.dict('core.economy_engine.ECONOMY_RATES', {
            'infrastructure_security_rate': 0.01,
            'security_min': 0.5,
            'security_max': 1.2,
            'income_per_pop': 1.0,
            'happiness_bonus_max': 0.5
        }):
            result = process_planet_tick(sample_planet, player_energy=100)

        assert result.planet_id == 100
        assert result.income > 0
        assert result.maintenance_paid is True

    def test_planet_with_buildings(self, sample_planet, sample_buildings):
        """Procesa planeta con edificios."""
        sample_planet["buildings"] = sample_buildings

        with patch.dict('core.economy_engine.ECONOMY_RATES', {
            'infrastructure_security_rate': 0.01,
            'security_min': 0.5,
            'security_max': 1.2,
            'income_per_pop': 1.0,
            'happiness_bonus_max': 0.5
        }):
            with patch.dict('core.economy_engine.BUILDING_TYPES', {
                'mina_basica': {'energy_cost': 5, 'production': {'materiales': 10}, 'category': 'extraccion'},
                'fabrica_componentes': {'energy_cost': 10, 'production': {'componentes': 5}, 'category': 'industria'},
                'generador_energia': {'energy_cost': 0, 'production': {'celulas_energia': 20}, 'category': 'energia'}
            }):
                with patch.dict('core.economy_engine.BUILDING_SHUTDOWN_PRIORITY', {
                    'extraccion': 4,
                    'industria': 2,
                    'energia': 3
                }):
                    result = process_planet_tick(sample_planet, player_energy=100)

        assert result.planet_id == 100
        assert isinstance(result.production, ProductionSummary)


# --- TESTS DE INTEGRACIÓN CON MOCKS ---

class TestEconomyTickWithMocks:
    """Tests de integración usando mocks para repositorios."""

    @patch('core.economy_engine.get_all_player_planets_with_buildings')
    @patch('core.economy_engine.get_player_finances')
    @patch('core.economy_engine.get_luxury_extraction_sites_for_player')
    @patch('core.economy_engine.batch_update_planet_security')
    @patch('core.economy_engine.batch_update_building_status')
    @patch('core.economy_engine.update_player_resources')
    @patch('core.economy_engine.log_event')
    def test_run_economy_tick_for_player(
        self,
        mock_log,
        mock_update_resources,
        mock_batch_buildings,
        mock_batch_security,
        mock_luxury_sites,
        mock_finances,
        mock_planets
    ):
        """Test completo del tick económico con mocks."""
        from core.economy_engine import run_economy_tick_for_player

        # Configurar mocks
        mock_planets.return_value = [{
            "id": 1,
            "poblacion": 1000,
            "pops_activos": 800,
            "pops_desempleados": 200,
            "seguridad": 1.0,
            "infraestructura_defensiva": 10,
            "felicidad": 1.0,
            "buildings": []
        }]

        mock_finances.return_value = {
            "creditos": 1000,
            "materiales": 500,
            "componentes": 100,
            "celulas_energia": 50,
            "influencia": 10
        }

        mock_luxury_sites.return_value = []

        with patch.dict('core.economy_engine.ECONOMY_RATES', {
            'infrastructure_security_rate': 0.01,
            'security_min': 0.5,
            'security_max': 1.2,
            'income_per_pop': 1.0,
            'happiness_bonus_max': 0.5
        }):
            result = run_economy_tick_for_player(player_id=1)

        # Verificar resultado
        assert result.success is True
        assert result.player_id == 1
        assert result.total_income > 0

        # Verificar que se llamaron los repositorios
        mock_planets.assert_called_once_with(1)
        mock_finances.assert_called_once_with(1)
        mock_update_resources.assert_called_once()


# --- CONFIGURACIÓN DE PYTEST ---

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
