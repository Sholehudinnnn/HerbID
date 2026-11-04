"""SafetyAssessmentService: Deterministic safety guardrails and clinical safety checks for HERB-INFO AI.

Ensures:
1. Temperature safety: < 35°C (urgent hypothermia) or >= 40°C (hyperpyrexia) halts recipe instructions.
2. Emergency sign detection: Unnegated red flags immediately trigger emergency warnings and halt consumption.
3. Medication normalization: 'tidak ada' / 'belum minum obat' is never treated as a pharmaceutical drug name.
4. Vulnerable & Child populations: Dose personalization is blocked and replaced with professional advice.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from app.services.complaint_extractor import (
    TEMP_FEVER_C,
    TEMP_LOW_URGENT_C,
    normalize_medication_input,
    strip_medication_none_statements,
)

AGE_GROUP_LABELS: dict[str, str] = {
    "dewasa_18_59_tahun": "Dewasa (18-59 tahun)",
    "anak_6_8_tahun": "Anak (6-8 tahun)",
    "anak_9_11_tahun": "Anak (9-11 tahun)",
    "lansia_60_keatas": "Lansia (60 tahun ke atas)",
    "ibu_hamil": "Ibu Hamil",
    "ibu_menyusui": "Ibu Menyusui",
    "riwayat_alergi_kronis": "Riwayat Alergi / Penyakit Kronis",
}

VULNERABLE_AGE_OR_CONDITIONS: frozenset[str] = frozenset(
    {"lansia_60_keatas", "ibu_hamil", "ibu_menyusui", "riwayat_alergi_kronis"}
)

SAFETY_WARNING_TEXT = (
    "Informasi ini bersifat edukatif. Kondisi yang Anda sebutkan memerlukan pertimbangan "
    "tenaga kesehatan. Sistem tidak memberikan diagnosis, resep, atau dosis pengobatan personal. "
    "Sistem tidak memberikan diagnosis/dosis/rekomendasi terapi. Konsultasikan dengan apoteker/dokter."
)

VULNERABLE_CONSUMPTION_WARNING = (
    "PERINGATAN KEAMANAN KHUSUS KELOMPOK RENTAN: Informasi takaran dalam referensi tradisional "
    "hanya untuk tujuan edukasi umum bagi orang dewasa sehat. Untuk kelompok rentan (ibu hamil, ibu menyusui, "
    "anak di bawah 12 tahun, lansia, atau pasien penyakit kronis), JANGAN mengonsumsi ramuan herbal tanpa "
    "rekomendasi dan pengawasan langsung dari dokter atau apoteker."
)

CHILD_AGE_WARNING_TEXT = (
    "PERINGATAN KHUSUS USIA ANAK (6-11 TAHUN): Takaran herbal untuk anak tidak dapat disimpulkan "
    "dari dosis dewasa. Penggunaan ramuan herbal pada anak memerlukan konsultasi langsung dengan dokter "
    "spesialis anak atau apoteker untuk memastikan keamanan organ hati dan ginjal yang masih berkembang."
)

VULNERABLE_REGEX = re.compile(
    r"\b(hamil|menyusui|bayi|balita|anak(?:\s+kecil)?|lansia|geriatri|penyakit\s+kronis|gagal\s+ginjal|gangguan\s+hati|jantung)\b",
    re.IGNORECASE,
)


class SafetyAssessmentService:
    @staticmethod
    def is_query_for_vulnerable(text: str) -> bool:
        return bool(VULNERABLE_REGEX.search(text))

    def assess_safety(
        self,
        extraction: dict[str, Any],
        raw_query: str,
        age_group: str = "dewasa_18_59_tahun",
        obat_rutin: str = "",
        vulnerable_flags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Perform comprehensive deterministic safety evaluation."""
        clean_age = age_group if age_group in AGE_GROUP_LABELS else "dewasa_18_59_tahun"
        age_label = AGE_GROUP_LABELS.get(clean_age, "Dewasa (18-59 tahun)")

        # 1. Routine Medication Normalization
        raw_obat_clean = obat_rutin.strip()
        _, med_none_in_query = strip_medication_none_statements(raw_query)
        norm_med = normalize_medication_input(raw_obat_clean)
        clean_obat_rutin = norm_med if norm_med else None
        obat_tidak_dilaporkan = med_none_in_query or (bool(raw_obat_clean) and not clean_obat_rutin)

        # 2. Vulnerable flags & population gates
        v_flags = [f for f in (vulnerable_flags or []) if f]
        if clean_obat_rutin and "obat_rutin" not in v_flags:
            v_flags.append(f"obat_rutin:{clean_obat_rutin}")

        query_is_vuln = self.is_query_for_vulnerable(raw_query)
        is_child_group = clean_age in {"anak_6_8_tahun", "anak_9_11_tahun"}
        is_vulnerable = (
            clean_age in VULNERABLE_AGE_OR_CONDITIONS
            or len(v_flags) > 0
            or query_is_vuln
            or bool(clean_obat_rutin)
        )

        # 3. Emergency Signs & Temperature Guardrail
        kw_hits: list[str] = list(extraction.get("tanda_bahaya_kata_kunci", []))
        temp_urgent: Optional[str] = extraction.get("peringatan_mendesak")
        stop_instructions = bool(extraction.get("instruksi_ramuan_dihentikan", False))

        emergency_parts: list[str] = []
        if kw_hits:
            emergency_parts.append(
                f"TANDA BAHAYA TERDETEKSI ({', '.join(kw_hits)}). Kondisi ini berpotensi darurat medis. "
                "SEGERA cari pertolongan medis di IGD atau fasilitas kesehatan terdekat. Jangan mengandalkan ramuan tradisional."
            )
        if temp_urgent:
            emergency_parts.append(temp_urgent)

        emergency_warning = " ".join(emergency_parts) if emergency_parts else None
        if emergency_warning:
            stop_instructions = True

        # 4. Safety Triggers
        safety_triggers: list[str] = []
        if clean_obat_rutin:
            safety_triggers.append("interaksi obat medis & suplemen")
        if is_vulnerable:
            safety_triggers.append("kelompok rentan (bayi/balita/hamil/menyusui/lansia/penyakit kronis)")
        if is_child_group:
            safety_triggers.append("kelompok usia anak (6-11 tahun)")

        requires_advice = (
            len(safety_triggers) > 0
            or emergency_warning is not None
            or is_vulnerable
            or is_child_group
        )

        safety_banner = SAFETY_WARNING_TEXT if requires_advice else None
        if is_vulnerable:
            vulnerable_warning = VULNERABLE_CONSUMPTION_WARNING
        elif is_child_group:
            vulnerable_warning = CHILD_AGE_WARNING_TEXT
        else:
            vulnerable_warning = None

        # 5. Determine overall safety status
        if emergency_warning or stop_instructions:
            safety_status = "darurat_medis"
        elif requires_advice:
            safety_status = "perlu_perhatian"
        else:
            safety_status = "aman_edukatif"

        # 6. Safety Info Section schema object
        kondisi_wajib: list[str] = [
            "Gejala memburuk atau tidak membaik dalam 3 hari",
            "Timbul tanda bahaya (sesak napas, nyeri dada, batuk berdarah, penurunan kesadaran)",
            "Memiliki riwayat penyakit ginjal, hati, atau kardiovaskular",
        ]
        if is_vulnerable:
            kondisi_wajib.append("Sedang hamil, menyusui, atau berusia lanjut (>60 tahun)")
        if clean_obat_rutin:
            kondisi_wajib.append(f"Sedang mengonsumsi obat medis rutin: {clean_obat_rutin}")

        batasan_info: list[str] = [
            "Data takaran berasal dari referensi tradisional/FROTI Kemenkes RI, bukan resep medis pribadi.",
            "Sistem tidak menegakkan diagnosis penyakit dan tidak menggantikan pemeriksaan fisik langsung oleh dokter.",
            "Penggunaan herbal harus dihentikan jika muncul reaksi alergi seperti ruam kulit, gatal, atau mual hebat.",
        ]

        safety_info_section = {
            "informasi_usia": f"Kategori pengguna: {age_label}.",
            "kondisi_wajib_konsultasi": kondisi_wajib,
            "batasan_informasi": batasan_info,
            "peringatan_obat_rutin": (
                f"Perhatian: Anda melaporkan penggunaan obat '{clean_obat_rutin}'. Beberapa herbal berinteraksi dengan obat medis; konsultasikan jeda waktu konsumsi dengan apoteker."
                if clean_obat_rutin
                else None
            ),
            "status_obat_rutin": (
                f"Obat rutin dilaporkan: {clean_obat_rutin}"
                if clean_obat_rutin
                else ("Tidak ada obat rutin yang dilaporkan." if obat_tidak_dilaporkan else "Belum disebutkan.")
            ),
        }

        return {
            "clean_age": clean_age,
            "age_label": age_label,
            "clean_obat_rutin": clean_obat_rutin,
            "obat_tidak_dilaporkan": obat_tidak_dilaporkan,
            "v_flags": v_flags,
            "query_is_vuln": query_is_vuln,
            "is_vulnerable": is_vulnerable,
            "is_child_group": is_child_group,
            "emergency_warning": emergency_warning,
            "stop_instructions": stop_instructions,
            "safety_triggers": safety_triggers,
            "safety_banner": safety_banner,
            "vulnerable_warning": vulnerable_warning,
            "requires_advice": requires_advice,
            "safety_status": safety_status,
            "safety_info_section": safety_info_section,
        }
