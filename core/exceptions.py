# core/exceptions.py
"""
Custom exceptions for SuperX application.
Provides structured error handling across the codebase.
"""
from typing import Dict, Any, Optional


class SuperXException(Exception):
    """Base exception for all SuperX errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class DatabaseError(SuperXException):
    """Raised when database operations fail."""
    pass


class ValidationError(SuperXException):
    """Raised when data validation fails."""
    pass


class AuthenticationError(SuperXException):
    """Raised when authentication fails."""
    pass


class GenesisProtocolError(SuperXException):
    """Raised when player initialization (Genesis Protocol) fails."""
    pass


class ResourceInsufficientError(SuperXException):
    """Raised when player lacks required resources for an action."""
    pass


class CharacterGenerationError(SuperXException):
    """Raised when character generation fails."""
    pass


class MissionError(SuperXException):
    """Raised when mission operations fail."""
    pass


class EconomyError(SuperXException):
    """Raised when economy calculations fail."""
    pass


class AIServiceError(SuperXException):
    """Raised when AI service (Gemini) operations fail."""
    pass


class WorldStateError(SuperXException):
    """Raised when world state operations fail."""
    pass
