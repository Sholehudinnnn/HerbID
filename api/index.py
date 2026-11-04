"""Vercel Serverless Function entrypoint."""
import sys
from pathlib import Path

# Add backend directory to sys.path so 'app.*' imports resolve cleanly
_ROOT_DIR = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _ROOT_DIR / "backend"

for p in [str(_BACKEND_DIR), str(_ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from app.main import app  # noqa: E402

__all__ = ["app"]
