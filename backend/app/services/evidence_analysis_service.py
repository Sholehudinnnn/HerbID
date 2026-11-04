"""EvidenceAnalysisService: Stage 2 RAG synthesis using Google Gemini and deterministic fallback.

Synthesizes:
1. Executive summary of evidence for the reported complaints.
2. Per-document relevance explanations (why each item was retrieved).
3. Unaddressed complaints (complaints mentioned by user without matching FROTI/BPOM recipes).
4. Information limitations (traditional use vs modern clinical trials).
5. Safety and contraindication highlights from retrieved documents.
6. Cited sources list (strictly validated against retrieved items).
7. Diagnosis is strictly null.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from app.config import GEMINI_API_KEY, GEMINI_FALLBACK_MODELS, GEMINI_MODEL_NAME
from app.services.gemini_service import is_gemini_configured

logger = logging.getLogger(__name__)


def _clean_text(s: str) -> str:
    if not s:
        return ""
    return s.replace("\u2014", " - ").replace("\u2013", "-").strip()


class EvidenceAnalysisService:
    def __init__(self):
        pass

    def _build_deterministic_evidence(
        self,
        raw_query: str,
        stage1_analysis: dict[str, Any],
        matched_recipes: list[dict[str, Any]],
        bpom_sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build a deterministic evidence analysis directly from the retrieved documents."""
        reported_symptoms = list(dict.fromkeys(
            [k.get("nama") for k in stage1_analysis.get("keluhan", []) if k.get("nama")]
            + [k for k in stage1_analysis.get("keluhan_teridentifikasi", []) if k]
            + ([stage1_analysis["keluhan_utama"]] if stage1_analysis.get("keluhan_utama") else [])
            + list(stage1_analysis.get("keluhan_tambahan", []))
        ))
        reported_symptoms = [s for s in reported_symptoms if s]

        relevance_explanations: list[dict[str, Any]] = []
        covered_complaints: set[str] = set()
        contraindications: list[str] = []
        valid_codes: list[str] = []

        for rec in matched_recipes[:3]:
            code = str(rec.get("recipe_code") or "")
            nama = str(rec.get("nama_tanaman") or rec.get("nama_ramuan") or "")
            ilmiah = str(rec.get("nama_ilmiah") or "")
            kegunaan = str(rec.get("kegunaan_tradisional") or rec.get("keluhan_terkait") or "")
            larangan = str(rec.get("larangan_kontraindikasi") or "")
            hal = str(rec.get("halaman_rujukan") or "-")
            sumber = str(rec.get("sumber_dokumen") or "FROTI Kemenkes RI")

            if code:
                valid_codes.append(code)

            # Check which user symptoms this recipe addresses
            supported = [
                s for s in reported_symptoms
                if s.lower() in kegunaan.lower() or kegunaan.lower() in s.lower()
            ]
            for s in supported:
                covered_complaints.add(s)

            if not supported and kegunaan:
                supported = [kegunaan]

            if larangan and larangan != "-" and larangan != "Belum dilaporkan kontraindikasi spesifik pada dosis lazim.":
                contraindications.append(f"{nama} ({code}): {larangan}")

            display_name = f"{nama}{f' ({ilmiah})' if ilmiah else ''}"
            relevance_explanations.append(
                {
                    "kode_referensi": code,
                    "nama_ramuan_atau_dokumen": display_name,
                    "mengapa_relevan": (
                        f"Tercatat dalam {sumber} untuk kegunaan tradisional '{kegunaan}', "
                        f"sesuai dengan keluhan yang Anda laporkan."
                    ),
                    "keluhan_yang_didukung": supported,
                    "catatan_sumber": f"{sumber} (hlm. {hal})",
                }
            )

        for src in bpom_sources[:2]:
            sid = str(src.get("source_id") or "")
            judul = str(src.get("judul") or "")
            topik = str(src.get("topik") or "")
            if sid:
                valid_codes.append(sid)
            relevance_explanations.append(
                {
                    "kode_referensi": sid,
                    "nama_ramuan_atau_dokumen": judul,
                    "mengapa_relevan": f"Memberikan rujukan resmi BPOM RI terkait topik {topik}.",
                    "keluhan_yang_didukung": [topik] if topik else [],
                    "catatan_sumber": "Rujukan Resmi BPOM RI",
                }
            )

        # Complaints that have no matching recipe in FROTI
        unaddressed = [s for s in reported_symptoms if s not in covered_complaints]

        if not matched_recipes and not bpom_sources:
            summary = (
                "Belum ditemukan referensi ramuan terverifikasi yang relevan untuk keluhan tersebut "
                "pada basis data FROTI Kemenkes RI maupun rujukan resmi BPOM RI. "
                "Sistem ini bukan diagnosis medis dan bukan pengganti konsultasi dokter."
            )
        else:
            rec_names = [r.get("nama_tanaman", "") for r in matched_recipes[:2] if r.get("nama_tanaman")]
            rec_str = f"ramuan berbasis {', '.join(rec_names)}" if rec_names else "referensi ramuan"
            summary = (
                f"Berdasarkan keluhan yang disampaikan, ditemukan {len(matched_recipes)} ramuan terkurasi "
                f"FROTI Kemenkes RI ({rec_str}) dan {len(bpom_sources)} dokumen rujukan BPOM RI. "
                "Informasi ini bersifat edukatif berdasarkan dokumentasi empiris dan bukan diagnosis medis atau resep pribadi."
            )

        limitations = [
            "Data bersumber dari Formularium Ramuan Obat Tradisional Indonesia (FROTI) Kemenkes RI berdasarkan penggunaan empiris turun-temurun.",
            "Informasi takaran dan ramuan ditujukan untuk edukasi umum dan bukan resep terapi individual.",
            "Bila gejala berlangsung lebih dari 3 hari atau memberat, konsultasi dengan tenaga medis mutlak diperlukan.",
        ]

        return {
            "ai_analysis_title": "Analisis AI HerbID: Sintesis Bukti Ramuan Terkurasi",
            "executive_summary": summary,
            "relevance_explanations": relevance_explanations,
            "unaddressed_complaints": unaddressed,
            "information_limitations": limitations,
            "safety_and_contraindication_highlights": contraindications or [
                "Perhatikan dosis wajar dan hindari penggunaan jangka panjang tanpa pengawasan tenaga kesehatan."
            ],
            "cited_sources": valid_codes,
            "provider": "Deterministic Source Grounding",
            "is_grounded": True,
            "diagnosis_medis": None,
        }

    def _call_gemini_stage2(
        self,
        raw_query: str,
        stage1_analysis: dict[str, Any],
        matched_recipes: list[dict[str, Any]],
        bpom_sources: list[dict[str, Any]],
        timeout_sec: float = 20.0,
    ) -> Optional[dict[str, Any]]:
        """Call Google Gemini to synthesize evidence into structured JSON."""
        if not is_gemini_configured():
            return None

        # Build context strictly from retrieved documents
        context_blocks: list[str] = []
        for r in matched_recipes[:3]:
            context_blocks.append(
                f"- [{r.get('recipe_code', 'FROTI')}] Nama: {r.get('nama_tanaman', '')} "
                f"({r.get('nama_ilmiah', '')})\n"
                f"  Kegunaan tradisional: {r.get('kegunaan_tradisional', '')}\n"
                f"  Bahan & takaran: {r.get('takaran_bahan_sumber', '')}\n"
                f"  Larangan/Kontraindikasi: {r.get('larangan_kontraindikasi', '')}\n"
                f"  Sumber: {r.get('sumber_dokumen', '')} hlm. {r.get('halaman_rujukan', '')}"
            )
        for s in bpom_sources[:2]:
            context_blocks.append(
                f"- [{s.get('source_id', 'BPOM')}] Judul: {s.get('judul', '')}\n"
                f"  Topik: {s.get('topik', '')}\n"
                f"  Ringkasan: {s.get('ringkasan', '')}\n"
                f"  Otoritas: {s.get('otoritas', '')}"
            )

        reported_symptoms = [
            k.get("nama") for k in stage1_analysis.get("keluhan", []) if k.get("nama")
        ]
        symptoms_str = ", ".join(reported_symptoms) if reported_symptoms else raw_query
        temp_str = (
            f"Suhu: {stage1_analysis['suhu_tubuh'].get('tampilan', '')}"
            if stage1_analysis.get("suhu_tubuh")
            else "Suhu tidak disebutkan"
        )
        duration_str = stage1_analysis.get("durasi_terdeteksi") or "Durasi tidak disebutkan"

        docs_text = "\n".join(context_blocks) if context_blocks else "Tidak ada dokumen ramuan yang ditemukan."

        prompt = f"""Kamu adalah modul sintesis bukti ilmiah dan ramuan tradisional sistem HerbID AI.
Tugasmu: Sintesiskan hasil pencarian dokumen terkurasi untuk keluhan pengguna secara objektif dan berbasis bukti (RAG).

Keluhan Pengguna: "{raw_query}"
Analisis Keluhan:
- Keluhan utama: {stage1_analysis.get('keluhan_utama', symptoms_str)}
- Keluhan terdeteksi: {symptoms_str}
- Kondisi suhu: {temp_str}
- Durasi: {duration_str}

Dokumen Terkurasi yang Ditemukan (Gunakan HANYA dokumen ini):
{docs_text}

ATURAN KETAT RAG & KEAMANAN:
1. Sintesiskan HANYA fakta yang tercantum dalam dokumen di atas. DILARANG mengarang ramuan, tanaman, atau khasiat lain.
2. DILARANG membuat diagnosis medis pribadi ('diagnosis_medis' harus selalu null).
3. Jika ada keluhan pengguna yang TIDAK tercakup dalam dokumen yang ditemukan di atas, sebutkan secara jujur di 'unaddressed_complaints'.
4. Cantumkan keterbatasan informasi dokumen tradisional di 'information_limitations'.
5. Cantumkan kontraindikasi atau larangan yang tercatat di dokumen pada 'safety_and_contraindication_highlights'.
6. 'cited_sources' hanya boleh berisi kode dokumen yang BENAR-BENAR ada dalam dokumen di atas (misal 'FROTI-001', 'BPOM-01').

Kembalikan respon HANYA dalam format JSON dengan struktur:
{{
  "ai_analysis_title": "Analisis AI HerbID: Sintesis Bukti Ramuan Terkurasi",
  "executive_summary": "Rangkuman ringkas 2-3 kalimat mengenai temuan referensi untuk keluhan pengguna.",
  "relevance_explanations": [
    {{
      "kode_referensi": "kode dokumen",
      "nama_ramuan_atau_dokumen": "nama ramuan/tanaman",
      "mengapa_relevan": "alasan spesifik kecocokan dengan keluhan pengguna",
      "keluhan_yang_didukung": ["keluhan 1"],
      "catatan_sumber": "sumber rujukan"
    }}
  ],
  "unaddressed_complaints": ["keluhan pengguna yang belum memiliki ramuan dalam dokumen"],
  "information_limitations": ["keterbatasan bukti empiris tradisional"],
  "safety_and_contraindication_highlights": ["larangan atau perhatian khusus dari dokumen"],
  "cited_sources": ["kode dokumen"],
  "provider": "Google Gemini ({GEMINI_MODEL_NAME})",
  "is_grounded": true,
  "diagnosis_medis": null
}}
"""

        models_to_try = [GEMINI_MODEL_NAME] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL_NAME]
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }

        for model in models_to_try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={GEMINI_API_KEY}"
            )
            try:
                r = httpx.post(url, json=payload, timeout=timeout_sec)
                if r.status_code == 200:
                    data = r.json()
                    raw_text = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                    parsed = json.loads(raw_text)
                    if isinstance(parsed, dict):
                        parsed["diagnosis_medis"] = None
                        parsed["provider"] = f"Google Gemini ({model})"
                        parsed["is_grounded"] = True
                        return parsed
                elif r.status_code in (404, 429):
                    logger.warning(f"Gemini Stage 2 with {model} failed (HTTP {r.status_code}), trying fallback...")
                    continue
                else:
                    logger.warning(f"Gemini Stage 2 error {r.status_code}: {r.text[:200]}")
                    return None
            except httpx.TimeoutException:
                logger.warning(f"Gemini Stage 2 timed out on {model}")
                continue
            except Exception as e:
                logger.warning(f"Gemini Stage 2 failed on {model}: {e}")
                continue

        return None


    def synthesize_evidence(
        self,
        raw_query: str,
        stage1_analysis: dict[str, Any],
        matched_recipes: list[dict[str, Any]],
        bpom_sources: list[dict[str, Any]],
        use_gemini: bool = True,
        timeout_sec: float = 20.0,
    ) -> dict[str, Any]:
        """Synthesize evidence using Gemini RAG with transparent deterministic fallback."""
        fallback = self._build_deterministic_evidence(
            raw_query=raw_query,
            stage1_analysis=stage1_analysis,
            matched_recipes=matched_recipes,
            bpom_sources=bpom_sources,
        )

        if not use_gemini or not is_gemini_configured() or (not matched_recipes and not bpom_sources):
            return fallback

        gemini_synth = self._call_gemini_stage2(
            raw_query=raw_query,
            stage1_analysis=stage1_analysis,
            matched_recipes=matched_recipes,
            bpom_sources=bpom_sources,
            timeout_sec=timeout_sec,
        )

        if not gemini_synth:
            return fallback

        # Clean text representations
        gemini_synth["executive_summary"] = _clean_text(gemini_synth.get("executive_summary", ""))
        gemini_synth["diagnosis_medis"] = None
        return gemini_synth
