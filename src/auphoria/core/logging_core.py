"""Logging setup for AUPHORIA runs.

Every run gets a ``log.txt`` that records every decision (level INFO with a
``DECISION:`` prefix) plus any debug/traceback detail. The console shows
INFO lines in beginner mode and only WARNING+ in expert mode; tracebacks are
never shown on the console.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOGGER_NAME = "auphoria"
_FORMAT = "%(asctime)s %(levelname)s %(message)s"
_DATE = "%Y-%m-%d %H:%M:%S"


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def _reset(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False


def setup_logging(log_file: Path | None = None, expert: bool = False) -> logging.Logger:
    """Configure the AUPHORIA logger, optionally writing to ``log_file``."""
    logger = get_logger()
    _reset(logger)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE)

    if log_file is not None:
        # The file handler receives everything, including tracebacks (DEBUG).
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    # Beginner mode explains (INFO); expert mode stops the chatter (WARNING).
    console.setLevel(logging.WARNING if expert else logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger


def log_decision(logger: logging.Logger, message: str) -> None:
    """Record a decision the engine or an analysis made, so nothing is silent."""
    logger.info("DECISION: %s", message)


def log_traceback(logger: logging.Logger, exc: BaseException) -> None:
    """Write a full traceback to the log only (never to the console)."""
    logger.debug("Full traceback:", exc_info=(type(exc), exc, exc.__traceback__))
