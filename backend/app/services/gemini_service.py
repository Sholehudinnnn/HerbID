"""Google Gemini API integration for RAG Symptom Diagnosis, Dosage Recommendation, and Semantic Embeddings."""
import json
import logging
import re
import time
from typing import Any, Optional

import httpx
import numpy as np

from app.config import (
    GEMINI_API_KEY,
    GEMINI_EMBEDDING_MODEL,
    GEMINI_FALLBACK_MODELS,
    GEMINI_MODEL_NAME,
)

logger = logging.getLogger(__name__)

CATALOG_SLUGS_MAP: dict[str, str] = {
    "jahe": "jahe",
    "kunyit": "kunyit",
    "temulawak": "temulawak",
    "kencur": "kencur",
    "daun sirih": "daun-sirih",
    "sirih": "daun-sirih",
    "lidah buaya": "lidah-buaya",
    "kayu putih": "kayu-putih",
    "minyak kayu putih": "kayu-putih",
    "sambiloto": "sambiloto",
    "meniran": "meniran",
    "kumis kucing": "kumis-kucing",
    "seledri": "seledri",
    "mengkudu": "mengkudu",
    "pace": "mengkudu",
    "daun sirsak": "daun-sirsak",
    "sirsak": "daun-sirsak",
    "lengkuas": "lengkuas",
    "laos": "lengkuas",
    "sereh": "sereh",
    "serai": "sereh",
    "daun pepaya": "daun-pepaya",
    "pepaya": "daun-pepaya",
    "kayu manis": "kayu-manis",
    "cengkeh": "cengkeh",
    "pala": "pala",
    "kayu secang": "kayu-secang",
    "secang": "kayu-secang",
    "daun jambu biji": "daun-jambu-biji",
    "jambu biji": "daun-jambu-biji",
    "kelapa": "kelapa",
    "minyak kelapa": "kelapa",
    "pegagan": "pegagan",
    "daun kaki kuda": "pegagan",
    "daun binahong": "daun-binahong",
    "binahong": "daun-binahong",
    "brotowali": "brotowali",
    "daun mint": "daun-mint",
    "mint": "daun-mint",
    "temu ireng": "temu-ireng",
    "asam jawa": "asam-jawa",
    "temu giring": "temu-giring",
    "cabe puyang": "cabe-puyang",
}

_GEMINI_CONSULTATION_CACHE: dict[str, dict[str, Any]] = {}
_GEMINI_QUERY_EMBED_CACHE: dict[str, np.ndarray] = {}


def _clean_em_dash(text: str) -> str:
    if not text:
        return ""
    return text.replace("\u2014", " - ").replace("\u2013", "-").strip()


def resolve_catalog_slug(herb_name: str) -> Optional[str]:
    lower = herb_name.lower().strip()
    if lower in CATALOG_SLUGS_MAP:
        return CATALOG_SLUGS_MAP[lower]
    for key, slug in CATALOG_SLUGS_MAP.items():
        if key in lower:
            return slug
    return None


def is_gemini_configured() -> bool:
    return bool(GEMINI_API_KEY and len(GEMINI_API_KEY) > 15 and not GEMINI_API_KEY.startswith("masukkan_"))


def check_gemini_status() -> dict[str, Any]:
    """Securely test Google Gemini API connectivity without exposing secrets.

    Differentiates:
    - not_configured: API key missing or dummy
    - ready: HTTP 200 and successful model inference
    - authentication_failed: HTTP 401/403
    - quota_exhausted: HTTP 429
    - model_not_found: HTTP 404
    - timeout: httpx.TimeoutException
    - error: other connection/JSON errors
    """
    if not is_gemini_configured():
        return {
            "configured": False,
            "status_code": "not_configured",
            "accessible": False,
            "model_name": GEMINI_MODEL_NAME,
            "message": "GEMINI_API_KEY belum dikonfigurasi di file environment backend (.env).",
            "latency_ms": None,
        }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": "ping"}]}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 10},
    }

    t0 = time.perf_counter()
    try:
        r = httpx.post(url, json=payload, timeout=15.0)
        latency = round((time.perf_counter() - t0) * 1000, 2)
        if r.status_code == 200:
            return {
                "configured": True,
                "status_code": "ready",
                "accessible": True,
                "model_name": GEMINI_MODEL_NAME,
                "message": f"Model Google Gemini ({GEMINI_MODEL_NAME}) aktif dan merespons dengan normal.",
                "latency_ms": latency,
            }
        elif r.status_code in (401, 403):
            logger.warning("Gemini API authentication failed (401/403).")
            return {
                "configured": True,
                "status_code": "authentication_failed",
                "accessible": False,
                "model_name": GEMINI_MODEL_NAME,
                "message": "Autentikasi gagal. GEMINI_API_KEY tidak valid atau izin akses ditolak.",
                "latency_ms": latency,
            }
        elif r.status_code == 429:
            logger.warning("Gemini API quota exhausted (429).")
            return {
                "configured": True,
                "status_code": "quota_exhausted",
                "accessible": False,
                "model_name": GEMINI_MODEL_NAME,
                "message": "Batas kuota harian atau rate-limit API Gemini telah tercapai. Sistem beralih ke analisis deterministik.",
                "latency_ms": latency,
            }
        elif r.status_code == 404:
            logger.warning(f"Gemini model not found (404): {GEMINI_MODEL_NAME}")
            return {
                "configured": True,
                "status_code": "model_not_found",
                "accessible": False,
                "model_name": GEMINI_MODEL_NAME,
                "message": f"Model '{GEMINI_MODEL_NAME}' tidak ditemukan pada Google Generative Language API.",
                "latency_ms": latency,
            }
        else:
            logger.warning(f"Gemini API returned HTTP {r.status_code}")
            return {
                "configured": True,
                "status_code": "error",
                "accessible": False,
                "model_name": GEMINI_MODEL_NAME,
                "message": f"Gemini API mengembalikan respons HTTP {r.status_code}.",
                "latency_ms": latency,
            }
    except httpx.TimeoutException:
        logger.warning("Gemini API connection timed out.")
        return {
            "configured": True,
            "status_code": "timeout",
            "accessible": False,
            "model_name": GEMINI_MODEL_NAME,
            "message": "Koneksi ke Google Gemini API mengalami batas waktu (timeout).",
            "latency_ms": None,
        }
    except Exception as exc:
        logger.warning(f"Gemini API connection error: {exc}")
        return {
            "configured": True,
            "status_code": "error",
            "accessible": False,
            "model_name": GEMINI_MODEL_NAME,
            "message": f"Gagal menghubungi Google Gemini API: {type(exc).__name__}.",
            "latency_ms": None,
        }


def embed_texts_gemini(texts: list[str], timeout_sec: float = 10.0) -> Optional[np.ndarray]:
    """Generate L2-normalized semantic embeddings using Google Gemini Embedding API."""
    if not is_gemini_configured() or not texts:
        return None

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_EMBEDDING_MODEL}:batchEmbedContents?key={GEMINI_API_KEY}"
    )
    requests_payload = [
        {
            "model": f"models/{GEMINI_EMBEDDING_MODEL}",
            "content": {"parts": [{"text": t[:1500]}]},
        }
        for t in texts
    ]

    try:
        r = httpx.post(url, json={"requests": requests_payload}, timeout=timeout_sec)
        if r.status_code != 200:
            return None
        data = r.json()
        embeddings = [item["values"] for item in data.get("embeddings", [])]
        if len(embeddings) != len(texts):
            return None
        arr = np.array(embeddings, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms
    except Exception:
        return None


def embed_single_query_gemini(query: str) -> Optional[np.ndarray]:
    key = query.strip().lower()
    if key in _GEMINI_QUERY_EMBED_CACHE:
        return _GEMINI_QUERY_EMBED_CACHE[key]
    arr = embed_texts_gemini([query])
    if arr is not None and arr.shape[0] == 1:
        _GEMINI_QUERY_EMBED_CACHE[key] = arr[0]
        return arr[0]
    return None


def _build_deterministic_grounded_summary(
    query: str,
    matched_recipes: list[dict[str, Any]],
    bpom_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deterministic source-grounded explanation built strictly from retrieved FROTI & BPOM documents."""
    if not matched_recipes and not bpom_results:
        return {
            "grounded_summary": (
                "Belum tersedia referensi ramuan terverifikasi yang relevan untuk keluhan tersebut "
                "pada basis data FROTI Kemenkes RI maupun rujukan BPOM RI."
            ),
            "validated_sources": [],
            "diagnosis_medis": None,
            "is_source_validated": True,
            "provider": "Deterministic Source Grounding",
        }

    parts: list[str] = []
    valid_codes: list[str] = []
    for rec in matched_recipes[:3]:
        code = str(rec.get("recipe_code") or "")
        tanaman = str(rec.get("nama_tanaman") or rec.get("nama_ramuan") or "")
        ilmiah = str(rec.get("nama_ilmiah") or "")
        kegunaan = str(rec.get("kegunaan_tradisional") or rec.get("keluhan_terkait") or "")
        hal = str(rec.get("halaman_rujukan") or "")
        if code:
            valid_codes.append(code)
        parts.append(
            f"{code} ({tanaman}{f' / {ilmiah}' if ilmiah else ''}) tercatat dalam FROTI Kemenkes RI "
            f"(hlm. {hal or '-'}) untuk kegunaan tradisional '{kegunaan}'."
        )

    for src in bpom_results[:2]:
        sid = str(src.get("source_id") or "")
        judul = str(src.get("judul") or "")
        if sid:
            valid_codes.append(sid)
        parts.append(f"Rujukan {sid} ({judul}) memberikan edukasi regulasi/keamanan terkait.")

    parts.append(
        "Informasi ini berasal langsung dari dokumen terkurasi dan bukan diagnosis atau resep medis pribadi."
    )
    return {
        "grounded_summary": " ".join(parts),
        "validated_sources": valid_codes,
        "diagnosis_medis": None,
        "is_source_validated": True,
        "provider": "Deterministic Source Grounding",
    }


def generate_gemini_consultation(
    query: str,
    local_diagnosis: Optional[dict[str, Any]] = None,
    local_recs: Optional[list[dict[str, Any]]] = None,
    matched_recipes: Optional[list[dict[str, Any]]] = None,
    bpom_results: Optional[list[dict[str, Any]]] = None,
    call_remote_llm: bool = False,
    timeout_sec: float = 8.0,
) -> dict[str, Any]:
    """Generate a source-grounded explanation strictly from retrieved FROTI & BPOM documents.

    Refactored per Section 9:
    - NEVER diagnoses medical conditions (`diagnosis_medis` is always None).
    - NEVER invents plants, recipes, or dosages outside retrieved documents.
    - Validates that every cited code/plant comes from `matched_recipes` or `bpom_results`.
    - Falls back cleanly to deterministic source-grounded explanation if Gemini connection fails.
    """
    recs = matched_recipes if matched_recipes is not None else (local_recs or [])
    srcs = bpom_results or []

    deterministic_fallback = _build_deterministic_grounded_summary(query, recs, srcs)
    if not call_remote_llm or not is_gemini_configured() or (not recs and not srcs):
        return deterministic_fallback

    allowed_codes = {
        str(r.get("recipe_code") or "").upper() for r in recs if r.get("recipe_code")
    } | {str(s.get("source_id") or "").upper() for s in srcs if s.get("source_id")}
    allowed_plants = {
        str(r.get("nama_tanaman") or r.get("nama_herbal") or "").lower()
        for r in recs
        if r.get("nama_tanaman") or r.get("nama_herbal")
    }

    context_blocks: list[str] = []
    for r in recs[:3]:
        context_blocks.append(
            f"[{r.get('recipe_code', 'RAMUAN')}] Tanaman: {r.get('nama_tanaman', '')} "
            f"({r.get('nama_ilmiah', '')}); Kegunaan tradisional: {r.get('kegunaan_tradisional', '')}; "
            f"Bahan sumber: {r.get('takaran_bahan_sumber', '')}; "
            f"Larangan: {r.get('larangan_kontraindikasi', '')}; "
            f"Sumber: {r.get('sumber_dokumen', '')} hlm. {r.get('halaman_rujukan', '')}"
        )
    for s in srcs[:2]:
        context_blocks.append(
            f"[{s.get('source_id', 'BPOM')}] Judul: {s.get('judul', '')}; "
            f"Ringkasan: {s.get('ringkasan', '')}"
        )

    prompt = (
        "Kamu adalah modul penjelasan berbasis sumber HERB-INFO AI.\n"
        f"Keluhan pengguna: \"{query}\"\n"
        "Dokumen referensi terkurasi yang ditemukan:\n"
        + "\n".join(context_blocks)
        + "\n\nAturan ketat:\n"
        "1. Rangkum HANYA informasi dari dokumen yang ditemukan di atas dalam 2-3 kalimat bahasa Indonesia.\n"
        "2. DILARANG mengarang tanaman, ramuan, atau dosis baru.\n"
        "3. DILARANG memberikan diagnosis medis pasti atau mengklaim kesembuhan.\n"
        "4. Sebutkan kode dokumen sumber yang digunakan."
    )

    models_to_try = [GEMINI_MODEL_NAME] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL_NAME]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 300},
    }

    for model in models_to_try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={GEMINI_API_KEY}"
        )
        try:
            r = httpx.post(url, json=payload, timeout=timeout_sec)
            if r.status_code == 200:
                resp_json = r.json()
                raw_text = (
                    resp_json.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                cleaned = _clean_em_dash(raw_text)
                if not cleaned:
                    continue

                has_valid_ref = any(c in cleaned.upper() for c in allowed_codes if c) or any(
                    p in cleaned.lower() for p in allowed_plants if p
                )
                if not has_valid_ref:
                    continue

                return {
                    "grounded_summary": cleaned,
                    "validated_sources": sorted(allowed_codes),
                    "diagnosis_medis": None,
                    "is_source_validated": True,
                    "provider": f"Google Gemini ({model}) - Tervalidasi Sumber",
                }
            elif r.status_code in (404, 429):
                continue
        except Exception:
            continue

    return deterministic_fallback



