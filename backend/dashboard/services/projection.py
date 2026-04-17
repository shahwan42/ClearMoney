"""Re-export ProjectionService from core for backward compatibility."""

from core.projection import ProjectionService  # noqa: F401

__all__ = ["ProjectionService"]
