class InventoryAppError(Exception):
    """Base class for application-level errors."""


class ValidationError(InventoryAppError):
    """Raised when user input fails validation."""


class NotFoundError(InventoryAppError):
    """Raised when an expected record does not exist."""


class ConflictError(InventoryAppError):
    """Raised when a requested operation conflicts with current state."""
