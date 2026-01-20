# tests/test_mrg_engine.py
"""
Tests for the MRG (Mission Resolution Generator) engine.
Updated for SuperX v2.1 specifications.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMRGEngine:
    """Tests for the MRG resolution engine."""

    def test_resolve_action_returns_result(self):
        """Test that resolve_action returns a valid MRGResult with mathematical data."""
        from core.mrg_engine import resolve_action, MRGResult

        # Usamos dificultad estándar (50)
        result = resolve_action(merit_points=50, difficulty=50)

        assert isinstance(result, MRGResult)
        assert hasattr(result, 'roll')
        assert hasattr(result, 'result_type')
        assert hasattr(result, 'margin')
        assert hasattr(result, 'bonus_applied')
        
        # Verificamos que sea un objeto de valor sin lógica de efectos pendientes
        assert isinstance(result.margin, int)

    def test_result_types_exist(self):
        """Verify all result types are defined."""
        from core.mrg_engine import ResultType

        assert hasattr(ResultType, 'CRITICAL_SUCCESS')
        assert hasattr(ResultType, 'TOTAL_SUCCESS')
        assert hasattr(ResultType, 'PARTIAL_SUCCESS')
        assert hasattr(ResultType, 'PARTIAL_FAILURE')
        assert hasattr(ResultType, 'TOTAL_FAILURE')
        assert hasattr(ResultType, 'CRITICAL_FAILURE')

    def test_high_merit_improves_chances(self):
        """Test that higher merit points improve success chances."""
        from core.mrg_engine import resolve_action, ResultType

        # Run many trials and count successes
        high_merit_successes = 0
        low_merit_successes = 0
        trials = 100
        
        # Max bonus is now 50 (v2.1), so the gap is smaller but should still be statistically significant
        for _ in range(trials):
            high_result = resolve_action(merit_points=100, difficulty=50)
            low_result = resolve_action(merit_points=10, difficulty=50)

            if high_result.result_type in [ResultType.CRITICAL_SUCCESS, ResultType.TOTAL_SUCCESS, ResultType.PARTIAL_SUCCESS]:
                high_merit_successes += 1
            if low_result.result_type in [ResultType.CRITICAL_SUCCESS, ResultType.TOTAL_SUCCESS, ResultType.PARTIAL_SUCCESS]:
                low_merit_successes += 1

        # High merit should have more successes on average
        assert high_merit_successes >= low_merit_successes

    def test_roll_is_within_bounds(self):
        """Test that dice roll is within expected bounds (2-100 for 2d50)."""
        from core.mrg_engine import resolve_action

        for _ in range(50):
            result = resolve_action(merit_points=50, difficulty=50)
            assert 2 <= result.roll.total <= 100


class TestMRGConstants:
    """Tests for MRG constants (Updated v2.1)."""

    def test_difficulty_constants_exist(self):
        """Verify new v2.1 difficulty constants are defined and ordered."""
        from core.mrg_constants import (
            DIFFICULTY_ROUTINE,
            DIFFICULTY_STANDARD,
            DIFFICULTY_CHALLENGING,
            DIFFICULTY_HEROIC
        )

        # Difficulties should be in ascending order
        assert DIFFICULTY_ROUTINE < DIFFICULTY_STANDARD
        assert DIFFICULTY_STANDARD < DIFFICULTY_CHALLENGING
        assert DIFFICULTY_CHALLENGING < DIFFICULTY_HEROIC
        
        # Specific values check
        assert DIFFICULTY_ROUTINE == 25
        assert DIFFICULTY_STANDARD == 50


class TestRulesEngine:
    """Tests for the rules calculation engine (Legacy preserved)."""

    def test_calculate_skills_returns_dict(self):
        """Test that calculate_skills returns a dictionary."""
        from core.rules import calculate_skills

        attributes = {
            "fuerza": 10,
            "agilidad": 12,
            "tecnica": 8,
            "intelecto": 15,
            "voluntad": 7,
            "presencia": 14
        }

        skills = calculate_skills(attributes)

        assert isinstance(skills, dict)
        assert len(skills) > 0

    def test_calculate_skills_with_correct_attribute_names(self):
        """Test calculate_skills works with correct attribute names."""
        from core.rules import calculate_skills

        # Using the CORRECT attribute names
        attributes = {
            "fuerza": 10,
            "agilidad": 10,
            "tecnica": 10,
            "intelecto": 10,
            "voluntad": 10,
            "presencia": 10
        }

        try:
            skills = calculate_skills(attributes)
            assert isinstance(skills, dict)
        except KeyError as e:
            pytest.fail(f"calculate_skills failed with KeyError: {e}")

    def test_attribute_cost_calculation(self):
        """Test attribute point cost calculation."""
        from core.rules import calculate_attribute_cost

        # Cost from 9 to 10 (below soft cap) should cost 1
        cost_9_to_10 = calculate_attribute_cost(9, 10)
        # Cost from 15 to 16 (above soft cap of 15) should cost 2
        cost_15_to_16 = calculate_attribute_cost(15, 16)

        assert cost_9_to_10 == 1
        assert cost_15_to_16 == 2