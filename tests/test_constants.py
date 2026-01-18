# tests/test_constants.py
"""
Tests for world constants - especially the newly added constants.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestStarConstants:
    """Tests for star-related constants."""

    def test_star_types_exist(self):
        """Verify STAR_TYPES is defined with all spectral classes."""
        from core.world_constants import STAR_TYPES

        assert STAR_TYPES is not None
        assert len(STAR_TYPES) == 7

        # All spectral classes should be present
        for star_class in ["O", "B", "A", "F", "G", "K", "M"]:
            assert star_class in STAR_TYPES

    def test_star_types_have_required_fields(self):
        """Verify each star type has all required fields for galaxy generation."""
        from core.world_constants import STAR_TYPES

        required_fields = ['color', 'size', 'rarity', 'energy_modifier', 'special_rule', 'class']

        for star_class, data in STAR_TYPES.items():
            for field in required_fields:
                assert field in data, f"STAR_TYPES['{star_class}'] missing '{field}'"

    def test_star_rarity_weights_exist(self):
        """Verify STAR_RARITY_WEIGHTS is defined."""
        from core.world_constants import STAR_RARITY_WEIGHTS

        assert STAR_RARITY_WEIGHTS is not None
        assert len(STAR_RARITY_WEIGHTS) == 7

    def test_star_rarity_weights_sum_approximately_to_one(self):
        """Verify star rarity weights sum to 1.0 (or close)."""
        from core.world_constants import STAR_RARITY_WEIGHTS

        total = sum(STAR_RARITY_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01, f"Star rarity weights sum to {total}, expected ~1.0"


class TestPlanetConstants:
    """Tests for planet-related constants."""

    def test_planet_biomes_exist(self):
        """Verify PLANET_BIOMES is defined."""
        from core.world_constants import PLANET_BIOMES

        assert PLANET_BIOMES is not None
        assert len(PLANET_BIOMES) >= 5  # At least 5 biome types

    def test_planet_biomes_have_required_fields(self):
        """Verify each biome has required fields."""
        from core.world_constants import PLANET_BIOMES

        required_fields = ['bonuses', 'construction_slots', 'maintenance_mod']

        for biome_name, data in PLANET_BIOMES.items():
            for field in required_fields:
                assert field in data, f"PLANET_BIOMES['{biome_name}'] missing '{field}'"

    def test_orbital_zones_exist(self):
        """Verify ORBITAL_ZONES is defined."""
        from core.world_constants import ORBITAL_ZONES

        assert ORBITAL_ZONES is not None
        assert 'inner' in ORBITAL_ZONES
        assert 'habitable' in ORBITAL_ZONES
        assert 'outer' in ORBITAL_ZONES

    def test_orbital_zones_have_rings(self):
        """Verify each orbital zone has ring definitions."""
        from core.world_constants import ORBITAL_ZONES

        for zone_name, data in ORBITAL_ZONES.items():
            assert 'rings' in data, f"ORBITAL_ZONES['{zone_name}'] missing 'rings'"
            assert 'planet_weights' in data, f"ORBITAL_ZONES['{zone_name}'] missing 'planet_weights'"

    def test_asteroid_belt_chance_exists(self):
        """Verify ASTEROID_BELT_CHANCE is defined."""
        from core.world_constants import ASTEROID_BELT_CHANCE

        assert ASTEROID_BELT_CHANCE is not None
        assert 0 <= ASTEROID_BELT_CHANCE <= 1


class TestResourceConstants:
    """Tests for resource-related constants."""

    def test_resource_star_weights_exist(self):
        """Verify RESOURCE_STAR_WEIGHTS is defined."""
        from core.world_constants import RESOURCE_STAR_WEIGHTS

        assert RESOURCE_STAR_WEIGHTS is not None
        # Should have entry for each star class
        assert len(RESOURCE_STAR_WEIGHTS) == 7


class TestBuildingConstants:
    """Tests for building-related constants."""

    def test_building_types_exist(self):
        """Verify BUILDING_TYPES is defined."""
        from core.world_constants import BUILDING_TYPES

        assert BUILDING_TYPES is not None
        assert len(BUILDING_TYPES) >= 4

    def test_building_types_have_production_field(self):
        """Verify each building has the production field (the bug fix)."""
        from core.world_constants import BUILDING_TYPES

        for building_id, data in BUILDING_TYPES.items():
            assert 'production' in data, f"BUILDING_TYPES['{building_id}'] missing 'production' field"
            assert isinstance(data['production'], dict), f"BUILDING_TYPES['{building_id}']['production'] should be dict"

    def test_building_types_have_category(self):
        """Verify each building has a category."""
        from core.world_constants import BUILDING_TYPES

        for building_id, data in BUILDING_TYPES.items():
            assert 'category' in data, f"BUILDING_TYPES['{building_id}'] missing 'category'"

    def test_production_buildings_produce_resources(self):
        """Verify production buildings actually produce something."""
        from core.world_constants import BUILDING_TYPES

        # Mine should produce materials
        assert 'mine_basic' in BUILDING_TYPES
        assert BUILDING_TYPES['mine_basic']['production'].get('materiales', 0) > 0

        # Solar plant should produce energy
        assert 'solar_plant' in BUILDING_TYPES
        assert BUILDING_TYPES['solar_plant']['production'].get('celulas_energia', 0) > 0


class TestGalaxyGeneratorImports:
    """Tests to verify galaxy_generator can import all required constants."""

    def test_galaxy_generator_imports_succeed(self):
        """Verify galaxy_generator.py can import without ImportError."""
        try:
            from core.galaxy_generator import GalaxyGenerator
        except ImportError as e:
            pytest.fail(f"galaxy_generator failed to import: {e}")

    def test_galaxy_generator_can_instantiate(self):
        """Verify GalaxyGenerator can be instantiated."""
        from core.galaxy_generator import GalaxyGenerator

        gen = GalaxyGenerator(seed=42, num_systems=5)
        assert gen.seed == 42
        assert gen.num_systems == 5
