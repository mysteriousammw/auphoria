"""AUPHORIA error types: user-facing messages with plain-English fixes.

The golden rule: an error raised to the user is **plain English with a
suggested fix**, and the full traceback goes only to the log. These classes
carry a ``hint`` that the CLI prints beneath the message.
"""

from __future__ import annotations


class AuphoriaError(Exception):
    """Base class. Carries a user-friendly message plus an optional fix hint."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def to_user(self) -> str:
        if self.hint:
            return f"{self.message}\n  Fix: {self.hint}"
        return self.message


class DataError(AuphoriaError):
    """The data file is missing, unreadable, or structurally unusable."""


class InputValidationError(AuphoriaError):
    """A user-supplied column, parameter, or analysis id is wrong."""


class AssumptionError(AuphoriaError):
    """The analysis does not fit this data or design; we refuse before running."""


class ConfigError(AuphoriaError):
    """The package's own configuration (a manifest or the catalogue) is broken."""


class EngineError(AuphoriaError):
    """An unexpected internal error during analysis; traceback is logged."""
