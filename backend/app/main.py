"""Main FastAPI application entry point for HERB-INFO AI."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import CORS_ORIGINS
from app.database import Base, SessionLocal, engine
from app.importers.data_importer import run_import
from app.models.db_models import HerbalRecipe, Plant, Source
from app.routes.api_routes import router as api_router
from app.services.search_service import search_engine


def initialize_system() -> None:
    """Ensure SQLite database is populated and TF-IDF index is built on startup."""
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    db = SessionLocal()
    try:
        has_sources = db.query(Source).count() > 0
        has_plants = db.query(Plant).count() > 0
        has_froti = (
            db.query(HerbalRecipe).filter(HerbalRecipe.recipe_code == "FROTI-001").first()
            is not None
        )
        if not has_sources or not has_plants or not has_froti:
            try:
                run_import(db_session=db)
            except Exception:
                pass
        try:
            search_engine.build_index(db)
        except Exception:
            pass
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_system()
    yield


app = FastAPI(
    title="HERB-INFO AI API",
    description=(
        "Backend API Ensiklopedia dan Pencarian Informasi Tanaman Obat Tradisional Indonesia "
        "(Baseline TF-IDF & Indeks Semantik dengan Pengaman Klinis)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Parameter permintaan tidak valid (periksa panjang query maksimum 300 karakter dan rentang top_k 1-20).",
            "errors": exc.errors(),
        },
    )


app.include_router(api_router)
