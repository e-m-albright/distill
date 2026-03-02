"""Custom exceptions."""


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, code: str) -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(AppError):
    """Resource not found."""

    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found", "NOT_FOUND")


class ValidationError(AppError):
    """Validation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "VALIDATION_ERROR")
