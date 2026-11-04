"""Configuration settings for HERB-INFO AI Backend (automatically loads .env)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

if ENV_FILE.exists():
    with open(ENV_FILE, "r", encoding="utf-8") as _ef:
        for _line in _ef:
            _stripped = _line.strip()
            if not _stripped or _stripped.startswith("#") or "=" not in _stripped:
                continue
            _k, _v = _stripped.split("=", 1)
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            if _k:
                os.environ[_k] = _v

# Dynamic DATA_DIR detection (supports root, backend subfolder, or environment override)
_possible_data_dirs = [
    Path(os.getenv("HERB_DATA_DIR", "")),
    BASE_DIR / "data",
    Path(__file__).resolve().parent.parent / "data",
    Path.cwd() / "data",
]
DATA_DIR = next((d for d in _possible_data_dirs if d and d.is_dir()), BASE_DIR / "data")

INCOMING_DIR = Path(os.getenv("HERB_INCOMING_DIR", str(DATA_DIR / "incoming")))
PROCESSED_DIR = Path(os.getenv("HERB_PROCESSED_DIR", str(DATA_DIR / "processed")))
DB_PATH = Path(os.getenv("HERB_DB_PATH", str(PROCESSED_DIR / "herb_info.db")))
IMPORT_REPORT_PATH = DATA_DIR / "import_report.json"
INDEX_META_PATH = PROCESSED_DIR / "index_metadata.json"

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "HERB_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
    ).split(",")
    if origin.strip()
]

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash").strip()
GEMINI_FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash"]
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001").strip()
ENABLE_SEMANTIC_MODEL = os.getenv("HERB_ENABLE_SEMANTIC_MODEL", "true").lower() in ("1", "true", "yes")
ALLOW_UNSAFE_JOBLIB = os.getenv("HERB_ALLOW_UNSAFE_JOBLIB", "false").lower() in ("1", "true", "yes")
