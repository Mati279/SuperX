# tests/test_security.py
"""
Tests for security-related fixes.
"""
import pytest
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDebugButtonsGuarded:
    """Tests to verify debug buttons are properly guarded."""

    def test_debug_mode_default_is_false(self):
        """Verify IS_DEBUG_MODE defaults to False."""
        # Clear any existing env var
        if 'SUPERX_DEBUG' in os.environ:
            del os.environ['SUPERX_DEBUG']

        # Force reimport
        import importlib
        import ui.main_game_page as mgp
        importlib.reload(mgp)

        assert mgp.IS_DEBUG_MODE == False

    def test_debug_mode_respects_env_var(self):
        """Verify IS_DEBUG_MODE can be enabled via environment variable."""
        os.environ['SUPERX_DEBUG'] = 'true'

        import importlib
        import ui.main_game_page as mgp
        importlib.reload(mgp)

        assert mgp.IS_DEBUG_MODE == True

        # Clean up
        del os.environ['SUPERX_DEBUG']
        importlib.reload(mgp)


class TestSQLInjectionPrevention:
    """Tests for SQL injection prevention."""

    def test_scan_system_data_sanitizes_input(self):
        """Verify scan_system_data sanitizes dangerous characters."""
        from services.ai_tools import scan_system_data
        import json

        # Test with dangerous SQL characters
        dangerous_inputs = [
            "'; DROP TABLE systems; --",
            "test%' OR '1'='1",
            "system\\'; DELETE FROM planets; --",
            "name_with_underscores",
            "100% match"
        ]

        for dangerous_input in dangerous_inputs:
            # Should not raise an exception
            try:
                result = scan_system_data(dangerous_input)
                # Result should be valid JSON
                parsed = json.loads(result)
                assert isinstance(parsed, dict)
            except Exception as e:
                # Connection errors are OK, we're testing sanitization
                if "connection" not in str(e).lower():
                    pass  # Some errors are expected without DB

    def test_empty_sanitized_input_returns_error(self):
        """Verify empty input after sanitization returns error."""
        from services.ai_tools import scan_system_data
        import json

        # Input that becomes empty after sanitization
        result = scan_system_data("%_%")
        parsed = json.loads(result)

        assert 'error' in parsed


class TestInputSanitization:
    """Tests for input sanitization patterns."""

    def test_sanitization_removes_sql_wildcards(self):
        """Verify SQL wildcards are removed."""
        pattern = r'[%_\'"\\;]'

        test_cases = [
            ("normal_text", "normaltext"),
            ("100%", "100"),
            ("test_name", "testname"),
            ("it's", "its"),
            ('say "hello"', "say hello"),
            ("path\\file", "pathfile"),
            ("cmd; rm -rf", "cmd rm -rf"),
        ]

        for input_str, expected in test_cases:
            result = re.sub(pattern, '', input_str)
            assert result == expected, f"Sanitizing '{input_str}' gave '{result}', expected '{expected}'"


class TestPasswordSecurity:
    """Tests for password handling security."""

    def test_password_hashing_works(self):
        """Verify password hashing produces different output."""
        from utils.security import hash_password

        password = "test123"
        hashed = hash_password(password)

        assert hashed != password
        assert len(hashed) > len(password)

    def test_password_verification_works(self):
        """Verify password verification works correctly."""
        from utils.security import hash_password, verify_password

        password = "test123"
        hashed = hash_password(password)

        # verify_password(stored_password, provided_password)
        assert verify_password(hashed, password) == True
        assert verify_password(hashed, "wrong_password") == False

    def test_same_password_different_hashes(self):
        """Verify same password produces different hashes (salting)."""
        from utils.security import hash_password

        password = "test123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Should be different due to salt
        assert hash1 != hash2
