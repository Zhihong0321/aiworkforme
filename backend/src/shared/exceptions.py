"""
Shared Exception hierarchy for the application.
Encourages low-surprise error handling across multiple modules.
"""

class BaseAppError(Exception):
    """Base class for all application-specific errors."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class DomainError(BaseAppError):
    """Errors occurring in the business logic layer."""
    pass

class AuthError(BaseAppError):
    """Errors related to authentication or authorization."""
    pass

class NotFoundError(DomainError):
    """Standard error for missing entities."""
    pass
