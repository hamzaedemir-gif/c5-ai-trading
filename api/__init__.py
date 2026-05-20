"""FastAPI backend wrapping the existing data / signals / risk modules."""
from .app import create_app

__all__ = ["create_app"]
