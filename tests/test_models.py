# tests/test_models.py
"""
Tests for core models - especially the fixed get_merit_points() method.
"""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCharacterAttributes:
    """Tests for CharacterAttributes model."""

    def test_default_attributes_exist(self):
        """Verify all six attributes exist with correct names."""
        from core.models import CharacterAttributes

        attrs = CharacterAttributes()

        # These are the CORRECT attribute names
        assert hasattr(attrs, 'fuerza')
        assert hasattr(attrs, 'agilidad')
        assert hasattr(attrs, 'tecnica')
        assert hasattr(attrs, 'intelecto')
        assert hasattr(attrs, 'voluntad')
        assert hasattr(attrs, 'presencia')

        # These OLD names should NOT exist
        assert not hasattr(attrs, 'destreza')
        assert not hasattr(attrs, 'constitucion')
        assert not hasattr(attrs, 'inteligencia')
        assert not hasattr(attrs, 'sabiduria')
        assert not hasattr(attrs, 'carisma')

    def test_default_values(self):
        """Verify default attribute values are 5."""
        from core.models import CharacterAttributes

        attrs = CharacterAttributes()

        assert attrs.fuerza == 5
        assert attrs.agilidad == 5
        assert attrs.tecnica == 5
        assert attrs.intelecto == 5
        assert attrs.voluntad == 5
        assert attrs.presencia == 5

    def test_custom_values(self):
        """Test creating attributes with custom values."""
        from core.models import CharacterAttributes

        attrs = CharacterAttributes(
            fuerza=10,
            agilidad=12,
            tecnica=8,
            intelecto=15,
            voluntad=7,
            presencia=14
        )

        assert attrs.fuerza == 10
        assert attrs.agilidad == 12
        assert attrs.tecnica == 8
        assert attrs.intelecto == 15
        assert attrs.voluntad == 7
        assert attrs.presencia == 14


class TestCommanderData:
    """Tests for CommanderData model and get_merit_points()."""

    def test_get_merit_points_with_v2_structure(self):
        """Test get_merit_points() with V2 character structure."""
        from core.models import CommanderData

        stats_json = {
            "capacidades": {
                "atributos": {
                    "fuerza": 10,
                    "agilidad": 12,
                    "tecnica": 8,
                    "intelecto": 15,
                    "voluntad": 7,
                    "presencia": 14
                }
            }
        }

        commander = CommanderData(
            id=1,
            player_id=1,
            nombre="Test Commander",
            stats_json=stats_json
        )

        # Merit points should be sum of all 6 attributes
        expected = 10 + 12 + 8 + 15 + 7 + 14  # = 66
        assert commander.get_merit_points() == expected

    def test_get_merit_points_with_defaults(self):
        """Test get_merit_points() falls back to defaults."""
        from core.models import CommanderData

        commander = CommanderData(
            id=1,
            player_id=1,
            nombre="Test Commander",
            stats_json={}
        )

        # Should use default values (5 each * 6 = 30)
        assert commander.get_merit_points() == 30

    def test_get_merit_points_does_not_crash(self):
        """Regression test: get_merit_points() should not crash with AttributeError."""
        from core.models import CommanderData

        # This was the bug - using wrong attribute names caused AttributeError
        commander = CommanderData(
            id=1,
            player_id=1,
            nombre="Test",
            stats_json={"capacidades": {"atributos": {}}}
        )

        # Should not raise AttributeError
        try:
            result = commander.get_merit_points()
            assert isinstance(result, int)
        except AttributeError as e:
            pytest.fail(f"get_merit_points() raised AttributeError: {e}")


class TestExceptions:
    """Tests for custom exception classes."""

    def test_superx_exception_base(self):
        """Test base SuperXException."""
        from core.exceptions import SuperXException

        exc = SuperXException("Test error", {"key": "value"})

        assert exc.message == "Test error"
        assert exc.details == {"key": "value"}
        assert "Test error" in str(exc)

    def test_genesis_protocol_error(self):
        """Test GenesisProtocolError exception."""
        from core.exceptions import GenesisProtocolError

        exc = GenesisProtocolError("Registration failed", {"player_id": 123})

        assert exc.message == "Registration failed"
        assert exc.details["player_id"] == 123

    def test_all_exception_types_exist(self):
        """Verify all custom exception types are defined."""
        from core.exceptions import (
            SuperXException,
            DatabaseError,
            ValidationError,
            AuthenticationError,
            GenesisProtocolError,
            ResourceInsufficientError,
            CharacterGenerationError,
            MissionError,
            EconomyError,
            AIServiceError,
            WorldStateError
        )

        # All should be subclasses of SuperXException
        assert issubclass(DatabaseError, SuperXException)
        assert issubclass(ValidationError, SuperXException)
        assert issubclass(GenesisProtocolError, SuperXException)
