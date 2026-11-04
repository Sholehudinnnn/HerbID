"""ASGI entrypoint for Vercel and production runners."""
import sys
from pathlib import Path

# Ensure backend directory is in sys.path so 'app.*' imports always succeed
_CURRENT_DIR = Path(__file__).resolve().parent
if str(_CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(_CURRENT_DIR))

_PARENT_DIR = _CURRENT_DIR.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

from app.main import app  # noqa: E402

__all__ = ["app"]
