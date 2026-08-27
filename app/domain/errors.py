class DomainError(Exception):
    """Base error safe to translate at application boundaries."""


class ValidationError(DomainError):
    pass


class NotFoundError(DomainError):
    pass


class AuthorizationError(DomainError):
    pass


class ConflictError(DomainError):
    pass
