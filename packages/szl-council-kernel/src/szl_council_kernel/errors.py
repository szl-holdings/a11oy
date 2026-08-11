"""Typed fail-closed errors for the Council Kernel."""

class CouncilKernelError(RuntimeError):
    """Base exception for deterministic kernel failures."""


class ValidationError(CouncilKernelError):
    """Input failed a schema or invariant."""


class AuthorizationError(CouncilKernelError):
    """A capability or policy decision denied an operation."""


class StateTransitionError(CouncilKernelError):
    """A workflow attempted an illegal state transition."""


class IntegrityError(CouncilKernelError):
    """A digest, signature, hash chain, or proof did not verify."""


class IdempotencyConflict(CouncilKernelError):
    """An idempotency key was reused with a different action."""


class PostconditionError(CouncilKernelError):
    """A mutation completed but its required postconditions failed."""


class FoundryError(CouncilKernelError):
    """A research artifact failed quarantine or promotion controls."""
