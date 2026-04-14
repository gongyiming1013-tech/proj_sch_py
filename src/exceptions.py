"""Domain-specific exceptions for the project scheduler."""


class SchedulerError(Exception):
    """Base exception for all scheduler-related errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CyclicDependencyError(SchedulerError):
    """Raised when the dependency graph contains a cycle."""

    def __init__(self, message: str = "Cyclic dependency detected") -> None:
        super().__init__(message)
