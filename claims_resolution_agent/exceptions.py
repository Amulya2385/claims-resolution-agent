class ClaimsResolutionError(Exception):
    """Base exception for expected Claims Resolution Agent failures."""


class ClaimNotFoundError(ClaimsResolutionError):
    """Raised when a requested claim does not exist."""


class PersistenceError(ClaimsResolutionError):
    """Raised when a persistence operation cannot be completed."""


class ApprovalError(ClaimsResolutionError):
    """Raised when an approval workflow cannot proceed safely."""


class AuthorizationError(ClaimsResolutionError):
    """Raised when an operation is not authorized."""


class IdempotencyError(ClaimsResolutionError):
    """Raised when an operation violates an idempotency guarantee."""