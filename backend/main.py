"""ASGI entrypoint for Vercel and production runners."""
from app.main import app

__all__ = ["app"]
