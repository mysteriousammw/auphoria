"""AUPHORIA analysis modules package."""

from auphoria.core.registry import list_analyses  # noqa: F401

__all__ = ["list_analyses"]

# Discover + import analyses eagerly is intentionally NOT done here; the
# registry loads modules on demand via auphoria.core.registry.load_analysis.
