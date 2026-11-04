"""ComplaintAnalysisService: Two-stage NLP & LLM complaint understanding for HERB-INFO AI.

Stage 1:
- Uses Google Gemini (gemini-2.5-flash) with structured JSON generation to analyze:
  * Primary and secondary complaints
  * Characteristic/subtype (e.g. dry cough vs wet cough)
  * Negation polarity (e.g. 'tidak pilek', 'batuk tidak berdahak')
  * Stated duration and body temperature with units
  * Danger signs / emergency flags
  * Missing information and clarification questions
  * Information sufficiency ('cukup', 'kurang', 'perlu_klarifikasi')
  * Safety status ('aman_edukatif', 'perlu_perhatian', 'darurat_medis')
  * Diagnosis is STRICTLY null (never formulated)
- Robust deterministic fallback when Gemini is offline or unavailable.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

import httpx

from app.config import GEMINI_API_KEY, GEMINI_FALLBACK_MODELS, GEMINI_MODEL_NAME
from app.services.complaint_extractor import (
    SYMPTOM_BY_KEY,
    SYMPTOM_LEXICON,
    extract_structured_complaints,
    extract_temperatures,
    is_negated,
)
from app.services.gemini_service import is_gemini_configured

logger = logging.getLogger(__name__)

CANONICAL_FROTI_SYMPTOM_MAP: dict[str, str] = {
    # Batuk
    "batuk kering": "batuk_kering",
    "batuk tidak berdahak": "batuk_kering",
    "batuk non produktif": "batuk_kering",
    "batuk tanpa dahak": "batuk_kering",
    "batuk berdahak": "batuk_berdahak",
    "batuk berlendir": "batuk_berdahak",
    "batuk produktif": "batuk_berdahak",
    "batuk": "batuk",
    # Demam
    "demam": "demam",
    "meriang": "demam",
    "panas badan": "demam",
    "badan panas": "demam",
    "suhu tinggi": "demam",
    # Sakit kepala
    "sakit kepala sebelah": "sakit_kepala_sebelah",
    "nyeri kepala sebelah": "sakit_kepala_sebelah",
    "migrain": "sakit_kepala_sebelah",
    "migren": "sakit_kepala_sebelah",
    "sakit kepala": "sakit_kepala",
    "pusing": "sakit_kepala",
    "pening": "sakit_kepala",
    # Tenggorokan
    "sakit tenggorokan": "sakit_tenggorokan",
    "radang tenggorokan": "sakit_tenggorokan",
    "nyeri telan": "sakit_tenggorokan",
    "tenggorokan perih": "sakit_tenggorokan",
    "tenggorokan gatal": "sakit_tenggorokan",
    # Leher
    "leher kaku": "leher_kaku",
    "kaku leher": "leher_kaku",
    "tengeng": "leher_kaku",
    "pegal leher": "leher_kaku",
    # Terkilir
    "terkilir": "terkilir",
    "keseleo": "terkilir",
    "salah urat": "terkilir",
    # Panas dalam
    "panas dalam": "panas_dalam",
    "sariawan": "panas_dalam",
    "bibir pecah": "panas_dalam",
    # Nafsu makan
    "nafsu makan berkurang": "nafsu_makan_berkurang",
    "kurang nafsu makan": "nafsu_makan_berkurang",
    "tidak nafsu makan": "nafsu_makan_berkurang",
    "susah makan": "nafsu_makan_berkurang",
    # Perut & Pencernaan
    "perut kembung": "perut_kembung",
    "kembung": "perut_kembung",
    "begah": "perut_kembung",
    "sebah": "perut_kembung",
    "gangguan lambung": "gangguan_lambung",
    "asam lambung": "gangguan_lambung",
    "maag": "gangguan_lambung",
    "perih lambung": "gangguan_lambung",
    "masuk angin": "masuk_angin",
    # Menstruasi
    "nyeri haid": "nyeri_haid",
    "sakit haid": "nyeri_haid",
    "sakit saat haid": "nyeri_haid",
    "kram haid": "nyeri_haid",
    "dismenore": "nyeri_haid",
    "senggugut": "nyeri_haid",
    "haid tidak teratur": "haid_tidak_teratur",
    "menstruasi tidak teratur": "haid_tidak_teratur",
    "telat haid": "haid_tidak_teratur",
    "haid terlambat": "haid_tidak_teratur",
    "haid": "haid_ambigu",
    "menstruasi": "haid_ambigu",
    "datang bulan": "haid_ambigu",
    # Gejala umum lainnya
    "pilek": "pilek",
    "flu": "pilek",
    "diare": "diare",
    "mencret": "diare",
    "lemas": "lemas",
    "menggigil": "menggigil",
}

FROTI_SUPPORTED_KEYS: set[str] = {
    "demam",
    "sakit_kepala_sebelah",
    "sakit_tenggorokan",
    "batuk_berdahak",
    "leher_kaku",
    "terkilir",
    "panas_dalam",
    "nafsu_makan_berkurang",
    "perut_kembung",
    "gangguan_lambung",
    "masuk_angin",
    "nyeri_haid",
    "haid_tidak_teratur",
}


def resolve_symptom_key(text: str) -> Optional[str]:
    """Map natural language complaint string to canonical symptom key."""
    low = (text or "").lower().strip()
    if not low:
        return None
    if low in CANONICAL_FROTI_SYMPTOM_MAP:
        return CANONICAL_FROTI_SYMPTOM_MAP[low]
    for phrase in sorted(CANONICAL_FROTI_SYMPTOM_MAP.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(phrase)}\b", low):
            return CANONICAL_FROTI_SYMPTOM_MAP[phrase]
    return None



class ComplaintAnalysisService:
    def __init__(self, emergency_keywords: Optional[list[str]] = None):
        self.emergency_keywords = emergency_keywords or [
            "sulit bernapas",
            "sesak napas",
            "nyeri dada",
            "batuk berdarah",
            "penurunan kesadaran",
            "pingsan",
            "tidak sadarkan diri",
            "perdarahan",
            "pendarahan",
            "muntah darah",
            "dehidrasi berat",
            "demam berat",
            "demam berkepanjangan",
            "kejang",
            "serangan jantung",
            "stroke",
            "overdosis",
            "keracunan",
        ]

    def _call_gemini_stage1(
        self,
        raw_query: str,
        durasi_input: str = "",
        timeout_sec: float = 18.0,
    ) -> Optional[dict[str, Any]]:
        """Call Google Gemini to extract structured complaint information."""
        if not is_gemini_configured():
            return None

        prompt = f"""Kamu adalah modul pemahaman keluhan dan NLP cerdas sistem HerbID AI.
Analisis teks keluhan pengguna berikut ini secara akurat dan objektif:

Input Keluhan: "{raw_query}"
Input Durasi (jika ada): "{durasi_input}"

ATURAN WAJIB:
1. Identifikasi keluhan utama dan keluhan tambahan.
2. Identifikasi karakteristik/subtipe keluhan dengan cermat:
   - Bedakan tegas 'batuk kering' (tanpa dahak / tidak berdahak) vs 'batuk berdahak' (berlendir / mengeluarkan dahak).
   - Jika pengguna hanya menyebut 'haid' atau 'menstruasi' tanpa menyebutkan apakah terasa nyeri/kram atau siklusnya tidak teratur, tandai kecukupan_informasi = 'perlu_klarifikasi', informasi_belum_jelas = ['Karakteristik keluhan haid belum spesifik'], dan pertanyaan_klarifikasi = ['Apakah keluhan menstruasi yang Anda alami berupa nyeri haid (kram/dismenore) atau siklus haid yang tidak teratur / terlambat?'].
3. Perhatikan negasi kata:
   - Misal 'tidak demam' -> demam memiliki negasi = true, status_disebutkan = 'dinegasikan'. JANGAN masukkan keluhan yang dinegasikan ke keluhan_utama.
   - Misal 'batuk tidak berdahak' -> batuk kering (negasi = false).
4. Ekstrak durasi keluhan bila disebutkan.
5. Ekstrak suhu tubuh bila ada (misal: "33 derajat", "38,3°C", "suhu 38.3"). Jika suhu < 35°C (misal 33 derajat), nilai status_keselamatan = 'darurat_medis' dan masukkan tanda bahaya hipotermia/suhu tubuh rendah abnormal.
6. Identifikasi informasi yang belum jelas dan susun pertanyaan klarifikasi edukatif.
7. Deteksi tanda bahaya medis jika ada (misal sesak napas, penurunan kesadaran, muntah darah, dll).
8. DILARANG KERAS membuat diagnosis medis pasti atau resep obat ("diagnosis" harus selalu null).
9. Nilai kecukupan informasi: "cukup", "kurang", atau "perlu_klarifikasi".
10. Nilai status keselamatan awal: "aman_edukatif", "perlu_perhatian", atau "darurat_medis".

Kembalikan respon HANYA dalam format JSON dengan struktur:
{{
  "query_asli": "{raw_query}",
  "keluhan_utama": "keluhan utama yang dirasakan atau null jika tidak ada/dinegasikan",
  "keluhan_tambahan": ["keluhan tambahan 1", "keluhan tambahan 2"],
  "rincian_keluhan": [
    {{
      "nama_keluhan": "nama singkat keluhan",
      "jenis_karakteristik": "deskripsi detail jenis keluhan",
      "status_disebutkan": "dilaporkan / dinegasikan",
      "negasi": false
    }}
  ],
  "durasi": "durasi jika ada atau null",
  "suhu_tubuh": {{
    "disebutkan": true,
    "nilai": 38.3,
    "satuan": "°C",
    "interpretasi_awal": "demam / normal / rendah / tinggi"
  }},
  "tanda_bahaya": {{
    "terdeteksi": false,
    "daftar_tanda_bahaya": []
  }},
  "informasi_belum_jelas": ["hal yang belum disebutkan jelas"],
  "pertanyaan_klarifikasi": ["pertanyaan ramah untuk memperjelas kondisi"],
  "kecukupan_informasi": "cukup",
  "status_keselamatan": "aman_edukatif",
  "diagnosis": null
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
                        parsed["diagnosis"] = None
                        parsed["used_model"] = model
                        return parsed
                elif r.status_code in (404, 429):
                    logger.warning(f"Gemini Stage 1 with {model} failed (HTTP {r.status_code}), trying fallback...")
                    continue
                else:
                    logger.warning(f"Gemini Stage 1 error {r.status_code}: {r.text[:200]}")
                    return None
            except httpx.TimeoutException:
                logger.warning(f"Gemini Stage 1 timed out on {model}")
                continue
            except Exception as e:
                logger.warning(f"Gemini Stage 1 failed on {model}: {e}")
                continue

        return None

    def analyze_complaint(
        self,
        raw_query: str,
        durasi_input: str = "",
        use_gemini: bool = True,
        timeout_sec: float = 18.0,
    ) -> dict[str, Any]:
        """Analyze user complaint with Gemini Stage 1 or deterministic fallback.

        Always produces a data structure fully compatible with downstream retrieval
        and safety checks.
        """
        # Always run deterministic extraction as baseline / grounding
        fallback = extract_structured_complaints(raw_query, self.emergency_keywords)
        fallback["provider"] = "Deterministic Rule-Based Fallback"
        fallback["diagnosis_medis"] = None
        fallback["rincian_keluhan"] = [
            {
                "nama_keluhan": k["nama"],
                "jenis_karakteristik": k.get("jenis", k["nama"]),
                "status_disebutkan": k.get("status", "dilaporkan"),
                "negasi": False,
            }
            for k in fallback.get("keluhan", [])
        ] + [
            {
                "nama_keluhan": k["nama"],
                "jenis_karakteristik": f"dinyatakan tidak dirasakan ({k.get('teks_asli', '')})",
                "status_disebutkan": "dinegasikan",
                "negasi": True,
            }
            for k in fallback.get("keluhan_dinegasikan", [])
        ]
        fallback["kecukupan_informasi"] = (
            "perlu_klarifikasi"
            if fallback.get("perlu_klarifikasi")
            else ("kurang" if not fallback.get("keluhan") else "cukup")
        )

        if not use_gemini or not is_gemini_configured():
            return fallback

        gemini_result = self._call_gemini_stage1(
            raw_query=raw_query,
            durasi_input=durasi_input,
            timeout_sec=timeout_sec,
        )

        if not gemini_result:
            return fallback

        # Merge Gemini's analytical insights into the structured dictionary
        merged = dict(fallback)
        used_model = gemini_result.get("used_model") or GEMINI_MODEL_NAME
        merged["provider"] = f"Google Gemini ({used_model})"

        # 1. Primary & Secondary complaints metadata
        if gemini_result.get("keluhan_utama"):
            merged["keluhan_utama"] = str(gemini_result["keluhan_utama"])
        if isinstance(gemini_result.get("keluhan_tambahan"), list):
            merged["keluhan_tambahan"] = [
                str(k) for k in gemini_result["keluhan_tambahan"] if k
            ]

        # 2. Detailed symptom breakdowns
        if isinstance(gemini_result.get("rincian_keluhan"), list):
            merged["rincian_keluhan"] = gemini_result["rincian_keluhan"]

        # 3. Information sufficiency & clarification
        if gemini_result.get("kecukupan_informasi"):
            merged["kecukupan_informasi"] = str(gemini_result["kecukupan_informasi"])

        if isinstance(gemini_result.get("informasi_belum_jelas"), list) and gemini_result["informasi_belum_jelas"]:
            current_info = list(merged.get("informasi_belum_jelas", []))
            for item in gemini_result["informasi_belum_jelas"]:
                if item and item not in current_info:
                    current_info.append(item)
            merged["informasi_belum_jelas"] = current_info

        if isinstance(gemini_result.get("pertanyaan_klarifikasi"), list) and gemini_result["pertanyaan_klarifikasi"]:
            current_q = list(merged.get("pertanyaan_klarifikasi", []))
            for q in gemini_result["pertanyaan_klarifikasi"]:
                if q and q not in current_q:
                    current_q.append(q)
            merged["pertanyaan_klarifikasi"] = current_q
            merged["perlu_klarifikasi"] = bool(current_q)

        # 4. Danger signs from Gemini (cross-checked)
        g_danger = gemini_result.get("tanda_bahaya", {})
        if isinstance(g_danger, dict) and g_danger.get("terdeteksi") and isinstance(g_danger.get("daftar_tanda_bahaya"), list):
            curr_danger = list(merged.get("tanda_bahaya_terdeteksi", []))
            for d in g_danger["daftar_tanda_bahaya"]:
                if d and d not in curr_danger:
                    curr_danger.append(str(d))
            merged["tanda_bahaya_terdeteksi"] = curr_danger

        # 5. Stated duration
        if gemini_result.get("durasi") and not merged.get("durasi_terdeteksi"):
            merged["durasi_terdeteksi"] = str(gemini_result["durasi"])

        # 6. Active synchronization: update keluhan, symptom_keys, symptom_labels from Gemini analysis
        positive_keys_ordered: list[str] = []
        negated_keys: list[str] = [k["key"] for k in merged.get("keluhan_dinegasikan", [])]

        # Extract from Gemini rincian_keluhan
        for r_item in (gemini_result.get("rincian_keluhan") or []):
            name_raw = str(r_item.get("nama_keluhan", ""))
            char_raw = str(r_item.get("jenis_karakteristik", ""))
            is_neg = bool(r_item.get("negasi")) or str(r_item.get("status_disebutkan", "")).lower() == "dinegasikan"
            key = resolve_symptom_key(f"{name_raw} {char_raw}") or resolve_symptom_key(name_raw)

            if key:
                if is_neg:
                    if key not in negated_keys:
                        negated_keys.append(key)
                else:
                    if key not in positive_keys_ordered:
                        positive_keys_ordered.append(key)

        # Extract from Gemini keluhan_utama & keluhan_tambahan
        g_utama = gemini_result.get("keluhan_utama")
        if g_utama and isinstance(g_utama, str) and g_utama.lower() not in ("null", "none", "tidak ada"):
            k_utama = resolve_symptom_key(g_utama)
            if k_utama and k_utama not in negated_keys and k_utama not in positive_keys_ordered:
                positive_keys_ordered.insert(0, k_utama)

        for g_tam in (gemini_result.get("keluhan_tambahan") or []):
            if isinstance(g_tam, str):
                k_tam = resolve_symptom_key(g_tam)
                if k_tam and k_tam not in negated_keys and k_tam not in positive_keys_ordered:
                    positive_keys_ordered.append(k_tam)

        # Merge with deterministic fallback keys (ensures zero omissions)
        for fb_k in fallback.get("symptom_keys", []):
            if fb_k not in negated_keys and fb_k not in positive_keys_ordered:
                positive_keys_ordered.append(fb_k)

        # Clean positive keys: purge any negated keys
        positive_keys_ordered = [k for k in positive_keys_ordered if k not in negated_keys]

        # Cough resolution: specific cough type supersedes generic "batuk"
        if {"batuk_kering", "batuk_berdahak"} & set(positive_keys_ordered) and "batuk" in positive_keys_ordered:
            positive_keys_ordered = [k for k in positive_keys_ordered if k != "batuk"]

        # Menstruation resolution: specific haid complaint supersedes generic "haid_ambigu"
        if {"nyeri_haid", "haid_tidak_teratur"} & set(positive_keys_ordered) and "haid_ambigu" in positive_keys_ordered:
            positive_keys_ordered = [k for k in positive_keys_ordered if k != "haid_ambigu"]

        # Ambiguous haid handling
        if "haid_ambigu" in positive_keys_ordered:
            merged["perlu_klarifikasi"] = True
            merged["is_haid_ambigu"] = True
            merged["kecukupan_informasi"] = "perlu_klarifikasi"
            haid_q = "Apakah keluhan menstruasi yang Anda alami berupa nyeri haid (kram/dismenore) atau siklus haid yang tidak teratur / terlambat?"
            if haid_q not in merged.get("pertanyaan_klarifikasi", []):
                merged.setdefault("pertanyaan_klarifikasi", []).insert(0, haid_q)
            haid_info = "Anda menyebutkan kondisi haid/menstruasi, tetapi belum merinci keluhan spesifik yang dirasakan."
            if haid_info not in merged.get("informasi_belum_jelas", []):
                merged.setdefault("informasi_belum_jelas", []).append(haid_info)

        # Build reconstructed keluhan list for retrieval
        reconstructed_keluhan: list[dict[str, Any]] = []
        for idx, k in enumerate(positive_keys_ordered):
            sd = SYMPTOM_BY_KEY.get(k)
            label = sd.label if sd else k
            jenis = sd.jenis if sd else k
            reconstructed_keluhan.append({
                "key": k,
                "nama": label,
                "jenis": jenis,
                "status": "dilaporkan",
                "teks_asli": label,
                "peran": "utama" if idx == 0 else "tambahan",
            })

        reconstructed_negated: list[dict[str, Any]] = []
        for k in negated_keys:
            sd = SYMPTOM_BY_KEY.get(k)
            label = sd.label if sd else k
            reconstructed_negated.append({
                "key": k,
                "nama": label,
                "teks_asli": label,
            })

        merged["keluhan"] = reconstructed_keluhan
        merged["keluhan_dinegasikan"] = reconstructed_negated
        merged["symptom_keys"] = positive_keys_ordered
        merged["symptom_labels"] = [k["nama"] for k in reconstructed_keluhan]
        merged["keluhan_utama"] = reconstructed_keluhan[0]["nama"] if reconstructed_keluhan else None
        merged["keluhan_tambahan"] = [k["nama"] for k in reconstructed_keluhan[1:]]

        # Check unsupported FROTI symptoms and annotate clearly
        catatan_cakupan: list[str] = list(merged.get("catatan_cakupan_referensi", []))
        for k in positive_keys_ordered:
            if k == "batuk_kering":
                c_note = (
                    "FROTI Kemenkes RI 2017 tidak memiliki referensi ramuan khusus untuk batuk kering (tanpa dahak). "
                    "Ramuan batuk berdahak sengaja tidak ditampilkan karena ditujukan untuk jenis keluhan yang berbeda."
                )
                if c_note not in catatan_cakupan:
                    catatan_cakupan.append(c_note)
            elif k not in FROTI_SUPPORTED_KEYS and k != "haid_ambigu":
                sd = SYMPTOM_BY_KEY.get(k)
                lbl = sd.label if sd else k
                c_note = f"Belum ditemukan referensi ramuan yang sesuai untuk '{lbl}' pada dataset formularium resmi FROTI Kemenkes 2017."
                if c_note not in catatan_cakupan:
                    catatan_cakupan.append(c_note)

        merged["catatan_cakupan_referensi"] = catatan_cakupan

        # Strictly ensure diagnosis is null
        merged["diagnosis_medis"] = None
        return merged

