"""Compatibility layer for existing imports.

Prefer importing from assistants.bucherim.bucherim_service.
"""

from .bucherim_service import BucherimService, BucherimSmsRequest

__all__ = ["BucherimService", "BucherimSmsRequest"]
