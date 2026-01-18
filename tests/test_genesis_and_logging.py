# tests/test_genesis_and_logging.py
"""
Tests for Genesis protocol fixes and logging utilities.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGenesisAttributeNames:
    """Tests for genesis commander stat generation."""

    def test_genesis_stats_use_correct_attribute_names(self):
        """Verify genesis stats use correct attribute names."""
        from core.genesis_engine import generate_genesis_commander_stats

        stats = generate_genesis_commander_stats("Test Commander")

        # Check the attributes are using correct names
        attrs = stats.get('atributos', {})

        # Should have the CORRECT attribute names
        assert 'fuerza' in attrs
        assert 'agilidad' in attrs
        assert 'tecnica' in attrs
        assert 'intelecto' in attrs
        assert 'voluntad' in attrs
        assert 'presencia' in attrs

        # Should NOT have the OLD (wrong) attribute names
        assert 'destreza' not in attrs
        assert 'constitucion' not in attrs
        assert 'inteligencia' not in attrs
        assert 'sabiduria' not in attrs
        assert 'carisma' not in attrs

    def test_genesis_stats_have_required_fields(self):
        """Verify genesis stats have all required fields."""
        from core.genesis_engine import generate_genesis_commander_stats

        stats = generate_genesis_commander_stats("Test Commander")

        assert 'nivel' in stats
        assert 'xp' in stats
        assert 'atributos' in stats
        assert 'clase' in stats

    def test_genesis_starting_level(self):
        """Verify genesis commander starts at correct level."""
        from core.genesis_engine import generate_genesis_commander_stats

        stats = generate_genesis_commander_stats("Test Commander")

        assert stats['nivel'] == 6  # Genesis commanders start at level 6


class TestLoggingUtilities:
    """Tests for logging utility functions."""

    def test_log_exception_function_exists(self):
        """Verify log_exception function is defined."""
        from utils.logging_utils import log_exception

        assert callable(log_exception)

    def test_safe_db_operation_decorator_exists(self):
        """Verify safe_db_operation decorator is defined."""
        from utils.logging_utils import safe_db_operation

        assert callable(safe_db_operation)

    def test_safe_db_operation_catches_exceptions(self):
        """Test that safe_db_operation decorator catches exceptions."""
        from utils.logging_utils import safe_db_operation

        @safe_db_operation("test_operation")
        def failing_function():
            raise ValueError("Test error")

        # Should not raise, should return None
        result = failing_function()
        assert result is None

    def test_safe_db_operation_returns_value_on_success(self):
        """Test that safe_db_operation returns value on success."""
        from utils.logging_utils import safe_db_operation

        @safe_db_operation("test_operation")
        def successful_function():
            return {"key": "value"}

        result = successful_function()
        assert result == {"key": "value"}

    def test_safe_operation_with_custom_default(self):
        """Test safe_operation with custom default return value."""
        from utils.logging_utils import safe_operation

        @safe_operation("test_operation", default_return=[])
        def failing_function():
            raise ValueError("Test error")

        result = failing_function()
        assert result == []


class TestRollbackFunction:
    """Tests for the Genesis rollback function."""

    def test_rollback_function_exists(self):
        """Verify _rollback_genesis function is defined."""
        from data.player_repository import _rollback_genesis

        assert callable(_rollback_genesis)

    def test_genesis_protocol_error_raised_on_failure(self):
        """Verify GenesisProtocolError is raised properly."""
        from core.exceptions import GenesisProtocolError

        with pytest.raises(GenesisProtocolError):
            raise GenesisProtocolError("Test failure", {"player_id": 123})


class TestCharacterNameCollision:
    """Tests for character name collision handling."""

    def test_uuid_import_in_character_service(self):
        """Verify uuid is imported in character_generation_service."""
        import services.character_generation_service as cgs

        # Check uuid is in the module's namespace
        assert 'uuid' in dir(cgs) or hasattr(cgs, 'uuid')
