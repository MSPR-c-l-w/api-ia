"""Exceptions métier remontées par les use cases (mappées en HTTP par la présentation)."""


class ApplicationError(Exception):
    """Erreur applicative avec code stable pour le client."""

    code: str = "APPLICATION_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class InsufficientUserDataError(ApplicationError):
    code = "INSUFFICIENT_USER_DATA"


class MongoUnavailableError(ApplicationError):
    code = "MONGODB_UNAVAILABLE"


class ProgramNotFoundError(ApplicationError):
    code = "PROGRAM_NOT_FOUND"
