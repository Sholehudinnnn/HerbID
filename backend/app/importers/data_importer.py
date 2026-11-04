"""Safe, reproducible importer for JSONL and Colab ZIP datasets."""
import csv
import hashlib
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
from sqlalchemy.orm import Session

from app.config import (
    ALLOW_UNSAFE_JOBLIB,
    BASE_DIR,
    IMPORT_REPORT_PATH,
    INCOMING_DIR,
    PROCESSED_DIR,
)
from app.database import Base, SessionLocal, engine
from app.models.db_models import (
    HerbalRecipe,
    Plant,
    PlantQALink,
    PlantReference,
    QAPair,
    QAReference,
    RecipeIngredient,
    RecipeSource,
    RecipeStep,
    RecipeUsage,
    Source,
)

ALLOWED_ZIP_EXTENSIONS = {".csv", ".joblib", ".npz", ".npy", ".png"}
ALLOWED_ZIP_FILENAMES = {
    "qa_clean_belum_terverifikasi.csv",
    "bpom_sumber_resmi.csv",
    "pencocokan_kandidat_bpom.csv",
    "tfidf_vectorizer.joblib",
    "tfidf_matrix.npz",
    "bpom_semantic_embeddings.npy",
    "template_evaluasi_manual.csv",
    "eda_distribusi_panjang.png",
}
MAX_SINGLE_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_TOTAL_EXTRACT_BYTES = 25 * 1024 * 1024  # 25 MB


class ZipSecurityError(ValueError):
    """Raised when a ZIP archive violates safety constraints."""


def normalize_text(text: Optional[str]) -> str:
    """Normalize text and replace em-dashes with standard spaced hyphens."""
    if not text:
        return ""
    cleaned = text.replace("\u2014", " - ").replace("\u2013", "-")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def slugify(text: str) -> str:
    """Create URL-safe slug from Indonesian plant name."""
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-")


def safe_extract_zip(
    zip_path: Path,
    extract_dir: Path,
    allowed_filenames: Optional[set[str]] = None,
    max_single_bytes: int = MAX_SINGLE_FILE_BYTES,
    max_total_bytes: int = MAX_TOTAL_EXTRACT_BYTES,
) -> list[str]:
    """Safely validate and extract a ZIP archive with path traversal and bomb protection."""
    if not zip_path.exists():
        raise FileNotFoundError(f"File ZIP tidak ditemukan: {zip_path}")

    extract_dir.mkdir(parents=True, exist_ok=True)
    extract_root = extract_dir.resolve()
    extracted_files: list[str] = []
    total_uncompressed = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            raw_name = info.filename
            if info.is_dir():
                continue

            # Reject path traversal, absolute paths, drive letters, or nested directories
            if (
                ".." in raw_name
                or raw_name.startswith("/")
                or raw_name.startswith("\\")
                or ":" in raw_name
            ):
                raise ZipSecurityError(f"Path berbahaya ditolak dalam ZIP: {raw_name}")

            member_name = Path(raw_name).name
            if member_name != raw_name.replace("\\", "/").split("/")[-1]:
                raise ZipSecurityError(f"Nama berkas dalam ZIP tidak valid: {raw_name}")

            ext = Path(member_name).suffix.lower()
            if ext not in ALLOWED_ZIP_EXTENSIONS:
                raise ZipSecurityError(f"Ekstensi berkas tidak diizinkan dalam ZIP: {member_name} ({ext})")

            if allowed_filenames is not None and member_name not in allowed_filenames:
                raise ZipSecurityError(f"Berkas tidak dikenali dalam ZIP: {member_name}")

            if info.file_size > max_single_bytes:
                raise ZipSecurityError(
                    f"Ukuran berkas melebihi batas aman ({info.file_size} > {max_single_bytes} byte): {member_name}"
                )

            total_uncompressed += info.file_size
            if total_uncompressed > max_total_bytes:
                raise ZipSecurityError(
                    f"Total ekstraksi ZIP melebihi batas aman ({total_uncompressed} > {max_total_bytes} byte)"
                )

            target_path = (extract_root / member_name).resolve()
            if not str(target_path).startswith(str(extract_root)):
                raise ZipSecurityError(f"Deteksi path traversal keluar dari folder tujuan: {raw_name}")

            with zf.open(info, "r") as src, open(target_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted_files.append(member_name)

    return sorted(extracted_files)


def classify_qa_topic(qa_id: int, question: str, answer: str) -> str:
    """Assign each of the 52 Q&A records to a structured research topic."""
    q_lower = question.lower()
    if qa_id in {3, 45, 50} or "regulasi" in q_lower or "fitofarmaka" in q_lower or "obat modern" in q_lower:
        return "regulasi"
    if qa_id in {38, 39, 46} or "peringatan" in q_lower or "berbahaya" in q_lower or "bko" in q_lower:
        return "keamanan"
    if qa_id in {1, 31, 32, 34, 35, 40, 42, 52} or any(
        w in q_lower for w in ["akupunktur", "bekam", "sinshe", "usada", "boreh", "mandi rempah", "tapel"]
    ):
        return "praktik tradisional"
    if qa_id in {2, 9, 19, 24, 25, 30, 36, 49} or any(
        w in q_lower for w in ["jamu", "loloh", "wedang", "minyak gosok", "madu"]
    ):
        return "jamu"
    return "tanaman"


# Explicit mapping of primary species Q&A records (derived strictly from the 52 Q&A texts)
PRIMARY_PLANT_SPECS: dict[int, dict[str, Any]] = {
    5: {"nama_umum": "Jahe", "nama_ilmiah": "Zingiber officinale", "nama_lokal": []},
    6: {"nama_umum": "Kunyit", "nama_ilmiah": "Curcuma longa", "nama_lokal": ["Kunir"]},
    7: {"nama_umum": "Temulawak", "nama_ilmiah": "Curcuma xanthorrhiza", "nama_lokal": []},
    8: {"nama_umum": "Kencur", "nama_ilmiah": "Kaempferia galanga", "nama_lokal": []},
    10: {"nama_umum": "Daun Sirih", "nama_ilmiah": "Piper betle", "nama_lokal": ["Sirih"]},
    11: {"nama_umum": "Lidah Buaya", "nama_ilmiah": "Aloe vera", "nama_lokal": []},
    12: {"nama_umum": "Kayu Putih", "nama_ilmiah": "Melaleuca cajuputi", "nama_lokal": ["Pohon Kayu Putih"]},
    14: {"nama_umum": "Sambiloto", "nama_ilmiah": "Andrographis paniculata", "nama_lokal": ["Pahitan", "Raja Pahit"]},
    15: {"nama_umum": "Meniran", "nama_ilmiah": "Phyllanthus niruri", "nama_lokal": []},
    16: {"nama_umum": "Kumis Kucing", "nama_ilmiah": "Orthosiphon aristatus", "nama_lokal": []},
    17: {"nama_umum": "Seledri", "nama_ilmiah": "Apium graveolens", "nama_lokal": []},
    18: {"nama_umum": "Mengkudu", "nama_ilmiah": "Morinda citrifolia", "nama_lokal": ["Pace"]},
    20: {"nama_umum": "Daun Sirsak", "nama_ilmiah": "Annona muricata", "nama_lokal": ["Sirsak"]},
    21: {"nama_umum": "Lengkuas", "nama_ilmiah": "Alpinia galanga", "nama_lokal": ["Laos"]},
    22: {"nama_umum": "Sereh", "nama_ilmiah": "Cymbopogon citratus", "nama_lokal": ["Serai"]},
    23: {"nama_umum": "Daun Pepaya", "nama_ilmiah": "Carica papaya", "nama_lokal": ["Pepaya"]},
    26: {"nama_umum": "Kayu Manis", "nama_ilmiah": "Cinnamomum verum / Cinnamomum burmannii", "nama_lokal": ["Cassia"]},
    27: {"nama_umum": "Cengkeh", "nama_ilmiah": "Syzygium aromaticum", "nama_lokal": []},
    28: {"nama_umum": "Pala", "nama_ilmiah": "Myristica fragrans", "nama_lokal": ["Fuli (Bunga Pala)"]},
    29: {"nama_umum": "Kayu Secang", "nama_ilmiah": "Caesalpinia sappan", "nama_lokal": ["Secang"]},
    33: {"nama_umum": "Daun Jambu Biji", "nama_ilmiah": "Psidium guajava", "nama_lokal": ["Jambu Biji"]},
    37: {"nama_umum": "Kelapa", "nama_ilmiah": "Cocos nucifera", "nama_lokal": ["Nyiur"]},
    41: {"nama_umum": "Pegagan", "nama_ilmiah": "Centella asiatica", "nama_lokal": ["Daun Kaki Kuda", "Gotu Kola"]},
    43: {"nama_umum": "Daun Binahong", "nama_ilmiah": "Anredera cordifolia", "nama_lokal": ["Binahong"]},
    44: {"nama_umum": "Brotowali", "nama_ilmiah": "Tinospora crispa", "nama_lokal": []},
    48: {"nama_umum": "Daun Mint", "nama_ilmiah": "Mentha piperita", "nama_lokal": ["Peppermint"]},
    51: {"nama_umum": "Temu Ireng", "nama_ilmiah": "Curcuma aeruginosa", "nama_lokal": []},
}

# Plants explicitly mentioned in Q&A recipes only by their local Indonesian name (no scientific name in dataset)
LOCAL_ONLY_PLANT_SPECS: list[dict[str, Any]] = [
    {
        "nama_umum": "Asam Jawa",
        "nama_ilmiah": None,
        "nama_lokal": ["Asam", "Sinom (Daun Asam Muda)"],
        "origin_qa_ids": [6, 9, 30, 49],
    },
    {
        "nama_umum": "Temu Giring",
        "nama_ilmiah": None,
        "nama_lokal": [],
        "origin_qa_ids": [52],
    },
    {
        "nama_umum": "Cabe Puyang",
        "nama_ilmiah": None,
        "nama_lokal": ["Puyang"],
        "origin_qa_ids": [49],
    },
]

# Non-plant Q&A rows that mention existing plants as ingredients/examples (merged into existing Plant entities)
SECONDARY_PLANT_MENTIONS: dict[int, list[str]] = {
    3: ["Meniran", "Seledri"],
    9: ["Kencur", "Asam Jawa"],
    13: [
        "Jahe",
        "Kunyit",
        "Temulawak",
        "Kencur",
        "Lengkuas",
        "Sereh",
        "Lidah Buaya",
        "Kumis Kucing",
        "Sambiloto",
        "Daun Sirih",
    ],
    19: ["Kunyit"],
    24: ["Kayu Secang", "Jahe", "Kayu Manis", "Cengkeh", "Pala", "Kelapa"],
    25: ["Kelapa", "Cengkeh", "Sereh"],
    30: ["Kunyit", "Asam Jawa"],
    31: ["Jahe", "Kunyit", "Kencur", "Cengkeh", "Kayu Manis", "Pala", "Kelapa"],
    32: ["Daun Sirih", "Kunyit", "Jahe", "Kencur"],
    39: ["Kunyit", "Jahe"],
    47: [
        "Jahe",
        "Kunyit",
        "Sereh",
        "Lidah Buaya",
        "Daun Sirih",
        "Kumis Kucing",
        "Daun Binahong",
        "Daun Pepaya",
        "Daun Jambu Biji",
        "Kencur",
    ],
    49: ["Kencur", "Kunyit", "Sambiloto", "Cabe Puyang", "Asam Jawa"],
    52: ["Kunyit", "Temu Giring", "Kencur"],
}

# Explicit BPOM topic-level links to specific plants based on bpom_sumber_resmi.csv & pencocokan_kandidat_bpom.csv
PLANT_BPOM_LINKS: dict[str, list[dict[str, str]]] = {
    "Jahe": [
        {
            "source_id": "BPOM-09",
            "tipe_relasi": "Kandidat Topik Bahan Baku OBA",
            "catatan_kurasi": "Terhubung melalui pemetaan topik standar mutu bahan baku obat bahan alam (BPOM-09). Kecocokan tingkat topik, bukan verifikasi klaim klinis.",
        }
    ],
    "Kunyit": [
        {
            "source_id": "BPOM-09",
            "tipe_relasi": "Contoh Bahan Baku pada Sumber BPOM",
            "catatan_kurasi": "Disebutkan secara eksplisit dalam ringkasan BPOM-09 terkait standar mutu bahan baku obat bahan alam (contoh: kunyit, temulawak, minyak kayu putih).",
        }
    ],
    "Temulawak": [
        {
            "source_id": "BPOM-07",
            "tipe_relasi": "Kandidat Topik Registrasi OBA Bentuk Tunggal",
            "catatan_kurasi": "Topik BPOM-07 pada dataset sumber resmi BPOM merujuk pada kategori klaim daftar registrasi obat bahan alam bentuk tunggal (topik: temulawak).",
        },
        {
            "source_id": "BPOM-09",
            "tipe_relasi": "Contoh Bahan Baku pada Sumber BPOM",
            "catatan_kurasi": "Disebutkan secara eksplisit dalam ringkasan BPOM-09 terkait standar mutu bahan baku obat bahan alam.",
        },
    ],
    "Kayu Putih": [
        {
            "source_id": "BPOM-09",
            "tipe_relasi": "Contoh Bahan Baku pada Sumber BPOM",
            "catatan_kurasi": "Minyak kayu putih disebutkan secara eksplisit dalam ringkasan BPOM-09 terkait standar mutu bahan baku obat bahan alam.",
        }
    ],
    "Kencur": [
        {
            "source_id": "BPOM-08",
            "tipe_relasi": "Kandidat Topik Jamu Tradisional (Beras Kencur)",
            "catatan_kurasi": "Terhubung melalui rujukan topik pendampingan pelaku usaha jamu gendong (BPOM-08) pada entri jamu beras kencur. Bukan validasi klaim medis.",
        }
    ],
    "Sambiloto": [
        {
            "source_id": "BPOM-08",
            "tipe_relasi": "Kandidat Topik Jamu Tradisional (Pahitan)",
            "catatan_kurasi": "Terhubung melalui rujukan topik jamu gendong (BPOM-08) yang mencakup varian pahitan/sambiloto. Bukan validasi klaim medis.",
        }
    ],
}

CURATED_PLANT_SUMMARIES: dict[str, str] = {
    "Temulawak": (
        "Tercatat dalam rujukan topik BPOM-07 (Registrasi OBA Bentuk Tunggal) dan BPOM-09 "
        "(Standar Mutu Bahan Baku Obat Bahan Alam). Informasi pada rujukan BPOM bersifat "
        "kategorisasi regulasi dan standar mutu bahan baku, bukan pengesahan klaim terapi "
        "pada jawaban komunitas Kaggle."
    ),
    "Kunyit": (
        "Tercatat sebagai salah satu contoh bahan baku dalam rujukan BPOM-09 (Standar Mutu "
        "Bahan Baku Obat Bahan Alam). Rujukan ini membahas penjagaan mutu bahan baku obat "
        "bahan alam Indonesia dan bukan verifikasi atas seluruh klaim penggunaan empiris."
    ),
    "Kayu Putih": (
        "Minyak kayu putih tercatat sebagai contoh bahan dalam rujukan BPOM-09 (Standar Mutu "
        "Bahan Baku Obat Bahan Alam). Rujukan ini bersifat edukasi standar mutu bahan baku, "
        "bukan rekomendasi dosis klinis."
    ),
    "Jahe": (
        "Dipetakan sebagai kandidat topik pada rujukan BPOM-09 (Standar Mutu Bahan Baku Obat "
        "Bahan Alam). Pemetaan ini berada pada tingkat topik bahan baku dan memerlukan kurasi "
        "lebih lanjut per klaim."
    ),
}


def parse_froti_csv(csv_path: Path) -> list[dict[str, Any]]:
    """Parse dataset_obat_tradisional_FROTI_terkurasi.csv into structured HerbalRecipe dictionaries."""
    records: list[dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            code_val = (row.get("id") or f"FROTI-{idx:03d}").strip()
            keluhan = normalize_text(row.get("keluhan_atau_kegunaan_tradisional", ""))
            nama_tanaman = normalize_text(row.get("nama_tanaman", ""))
            if not nama_tanaman and not keluhan:
                continue
            nama_ilmiah = normalize_text(row.get("nama_ilmiah", ""))
            bagian_tanaman = normalize_text(row.get("bagian_tanaman", ""))
            rute_penggunaan = normalize_text(row.get("rute_penggunaan", ""))
            takaran_bahan = normalize_text(row.get("takaran_bahan_dari_FROTI", ""))
            bahan_tambahan = normalize_text(row.get("bahan_tambahan", ""))
            cara_membuat = normalize_text(row.get("cara_membuat_dari_FROTI", ""))
            aturan_pakai = normalize_text(row.get("aturan_pakai_dalam_FROTI_bukan_resep", ""))

            bayi_0_11 = normalize_text(row.get("bayi_0_11_bulan", ""))
            balita_1_2 = normalize_text(row.get("balita_1_2_tahun", ""))
            balita_3_5 = normalize_text(row.get("balita_3_5_tahun", ""))
            anak_6_8 = normalize_text(row.get("anak_6_8_tahun", ""))
            anak_9_11 = normalize_text(row.get("anak_9_11_tahun", ""))
            remaja_12_17 = normalize_text(row.get("remaja_12_17_tahun", ""))
            dewasa_18_59 = normalize_text(row.get("dewasa_18_59_tahun", ""))

            raw_halaman = (row.get("halaman_pdf") or "").strip()
            raw_peringatan_col = (row.get("peringatan_efek_samping_interaksi") or "").strip()
            if raw_halaman in ("undefined", "") and raw_peringatan_col.isdigit():
                lansia_60_plus = "TIDAK DITETAPKAN dalam rujukan; jangan gunakan sebagai dosis mandiri"
                larangan_kontraindikasi = normalize_text(row.get("lansia_60_plus", ""))
                peringatan_efek_samping = normalize_text(row.get("larangan_kontraindikasi", ""))
                halaman_pdf = raw_peringatan_col
                status_keamanan_dosis = normalize_text(row.get("status_keamanan_dosis", ""))
                sumber_dokumen = normalize_text(row.get("sumber_dokumen", ""))
                tautan_sumber = (row.get("tautan_sumber") or "").strip()
            else:
                lansia_60_plus = normalize_text(row.get("lansia_60_plus", ""))
                larangan_kontraindikasi = normalize_text(row.get("larangan_kontraindikasi", ""))
                peringatan_efek_samping = normalize_text(row.get("peringatan_efek_samping_interaksi", ""))
                status_keamanan_dosis = normalize_text(row.get("status_keamanan_dosis", ""))
                sumber_dokumen = normalize_text(row.get("sumber_dokumen", ""))
                halaman_pdf = normalize_text(raw_halaman)
                tautan_sumber = (row.get("tautan_sumber") or "").strip()

            keluhan_short = keluhan.split("(")[0].strip() if "(" in keluhan else keluhan
            nama_ramuan = f"Ramuan {nama_tanaman} untuk {keluhan_short} ({code_val})"
            slug_val = slugify(f"{code_val}-{nama_tanaman}-{keluhan_short}")
            halaman_label = f"Halaman PDF {halaman_pdf}" if halaman_pdf and halaman_pdf.isdigit() else halaman_pdf

            dosis_usia_map = {
                "bayi_0_11_bulan": bayi_0_11,
                "balita_1_2_tahun": balita_1_2,
                "balita_3_5_tahun": balita_3_5,
                "anak_6_8_tahun": anak_6_8,
                "anak_9_11_tahun": anak_9_11,
                "remaja_12_17_tahun": remaja_12_17,
                "dewasa_18_59_tahun": dewasa_18_59,
                "lansia_60_plus": lansia_60_plus,
            }

            ingredients = [
                {
                    "nama_bahan": f"{nama_tanaman} ({nama_ilmiah}) - {bagian_tanaman}",
                    "jumlah": takaran_bahan,
                    "satuan": "Takaran dalam referensi tradisional, bukan resep medis pribadi",
                    "catatan": f"Bagian tanaman: {bagian_tanaman} | Rute: {rute_penggunaan}",
                }
            ]
            if bahan_tambahan and bahan_tambahan.lower() != "tidak ada":
                ingredients.append(
                    {
                        "nama_bahan": "Campuran Tambahan",
                        "jumlah": bahan_tambahan,
                        "satuan": "Takaran dalam referensi tradisional, bukan resep medis pribadi",
                        "catatan": "Bahan tambahan sesuai rujukan FROTI",
                    }
                )

            raw_step_parts = [p.strip() for p in re.split(r"[;.]", cara_membuat) if p.strip()]
            steps = [
                {
                    "nomor_langkah": s_idx,
                    "deskripsi_langkah": part if part.endswith(".") else f"{part}.",
                }
                for s_idx, part in enumerate(raw_step_parts, start=1)
            ]
            if not steps and cara_membuat:
                steps = [{"nomor_langkah": 1, "deskripsi_langkah": cara_membuat}]

            deskripsi_text = (
                f"Ramuan tradisional berbahan {bagian_tanaman.lower()} {nama_tanaman} ({nama_ilmiah}) "
                f"untuk kegunaan tradisional: {keluhan}. Rute penggunaan: {rute_penggunaan}. "
                f"Sumber rujukan: {sumber_dokumen} ({halaman_label})."
            )

            records.append(
                {
                    "recipe_code": code_val,
                    "slug": slug_val,
                    "nama_ramuan": nama_ramuan,
                    "nama_tanaman": nama_tanaman,
                    "nama_ilmiah": nama_ilmiah,
                    "bagian_tanaman": bagian_tanaman,
                    "rute_penggunaan": rute_penggunaan,
                    "keluhan_terkait": keluhan,
                    "deskripsi": deskripsi_text,
                    "takaran_bahan_sumber": takaran_bahan,
                    "bahan_tambahan": bahan_tambahan or "Tidak ada",
                    "cara_menyiapkan_bahan": f"Siapkan {bagian_tanaman.lower()} {nama_tanaman} ({takaran_bahan}) serta bahan tambahan: {bahan_tambahan or 'Tidak ada'}.",
                    "cara_membuat_sumber": cara_membuat,
                    "aturan_pakai_sumber": aturan_pakai,
                    "dosis_kelompok_usia_map": dosis_usia_map,
                    "kelompok_tidak_dianjurkan": larangan_kontraindikasi,
                    "status_keamanan_dosis": status_keamanan_dosis,
                    "status_verifikasi": "TERKURASI_FROTI_KEMENKES",
                    "sumber_dokumen": sumber_dokumen,
                    "sumber_url": tautan_sumber,
                    "sumber_halaman": halaman_label,
                    "reviewer": "Kurasi Terstruktur FROTI (Kepmenkes HK.01.07/MENKES/187/2017)",
                    "tanggal_review": "2026-10-25",
                    "peringatan": peringatan_efek_samping,
                    "kontraindikasi": larangan_kontraindikasi,
                    "ingredients": ingredients,
                    "steps": steps,
                    "usages": [
                        {
                            "aturan_penggunaan_dari_sumber": f"Rute penggunaan: {rute_penggunaan}. {aturan_pakai}",
                            "status_review_penggunaan": status_keamanan_dosis,
                            "boleh_ditampilkan_publik": True,
                        }
                    ],
                    "sources": [
                        {
                            "nama_referensi": sumber_dokumen,
                            "instansi": "Kementerian Kesehatan Republik Indonesia",
                            "url": tautan_sumber,
                            "halaman": halaman_label,
                            "status_validasi": status_keamanan_dosis,
                        }
                    ],
                }
            )
    return records


def parse_recipes_csv(csv_path: Path) -> list[dict[str, Any]]:
    """Parse a manually curated CSV recipe file (FROTI schema or generic pipe schema) into structured recipe dictionaries."""
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
    if "keluhan_atau_kegunaan_tradisional" in fieldnames and "takaran_bahan_dari_FROTI" in fieldnames:
        return parse_froti_csv(csv_path)

    records: list[dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            nama = normalize_text(row.get("nama_ramuan", ""))
            if not nama:
                continue
            slug_val = slugify(row.get("slug") or nama)
            code_val = (row.get("recipe_code") or f"RAMUAN-CSV-{idx:02d}").strip()
            ingredients: list[dict[str, Any]] = []
            raw_bahan = (row.get("bahan_pipe_list") or "").strip()
            if raw_bahan:
                for b_part in raw_bahan.split("|"):
                    cols = [c.strip() for c in b_part.split(":")]
                    if cols and cols[0]:
                        ingredients.append(
                            {
                                "nama_bahan": normalize_text(cols[0]),
                                "jumlah": normalize_text(cols[1]) if len(cols) > 1 else None,
                                "satuan": normalize_text(cols[2]) if len(cols) > 2 else None,
                                "catatan": normalize_text(cols[3]) if len(cols) > 3 else None,
                            }
                        )
            steps: list[dict[str, Any]] = []
            raw_steps = (row.get("langkah_pipe_list") or "").strip()
            if raw_steps:
                for s_idx, s_part in enumerate(raw_steps.split("|"), start=1):
                    if s_part.strip():
                        steps.append(
                            {
                                "nomor_langkah": s_idx,
                                "deskripsi_langkah": normalize_text(s_part),
                            }
                        )
            boleh_publik = str(row.get("boleh_ditampilkan_publik", "false")).strip().lower() == "true"
            sumber_url = (row.get("sumber_url") or "https://repository.kemkes.go.id/book/352").strip()
            records.append(
                {
                    "recipe_code": code_val,
                    "slug": slug_val,
                    "nama_ramuan": nama,
                    "keluhan_terkait": normalize_text(row.get("keluhan_terkait", "Umum")),
                    "deskripsi": normalize_text(row.get("deskripsi", "")),
                    "cara_menyiapkan_bahan": normalize_text(row.get("cara_menyiapkan_bahan", "")),
                    "kelompok_tidak_dianjurkan": normalize_text(row.get("kelompok_tidak_dianjurkan", "")),
                    "status_verifikasi": normalize_text(row.get("status_verifikasi", "Perlu verifikasi")),
                    "sumber_url": sumber_url,
                    "sumber_halaman": normalize_text(row.get("sumber_halaman", "")),
                    "reviewer": normalize_text(row.get("reviewer", "")),
                    "tanggal_review": normalize_text(row.get("tanggal_review", "")),
                    "peringatan": normalize_text(row.get("peringatan", "")),
                    "kontraindikasi": normalize_text(row.get("kontraindikasi", "")),
                    "ingredients": ingredients,
                    "steps": steps,
                    "usages": [
                        {
                            "aturan_penggunaan_dari_sumber": normalize_text(
                                row.get("aturan_penggunaan_dari_sumber", "")
                            )
                            or None,
                            "status_review_penggunaan": normalize_text(
                                row.get("status_review_penggunaan", "MENUNGGU_VERIFIKASI")
                            ),
                            "boleh_ditampilkan_publik": boleh_publik,
                        }
                    ],
                    "sources": [
                        {
                            "nama_referensi": "Sumber Impor Manual CSV",
                            "instansi": "Kementerian Kesehatan RI / BPOM RI",
                            "url": sumber_url,
                            "halaman": normalize_text(row.get("sumber_halaman", "")),
                            "status_validasi": normalize_text(
                                row.get("status_verifikasi", "PERLU_VERIFIKASI")
                            ),
                        }
                    ],
                }
            )
    return records


def upsert_recipe_records(db_session: Session, raw_recipes: list[dict[str, Any]]) -> list[str]:
    """Insert or update curated recipe records into HerbalRecipe and child tables."""
    inserted_slugs: list[str] = []
    for idx, r_data in enumerate(raw_recipes, start=1):
        if not isinstance(r_data, dict):
            continue
        nama = normalize_text(str(r_data.get("nama_ramuan", "")))
        if not nama:
            continue
        slug_val = slugify(str(r_data.get("slug") or nama))
        code_val = normalize_text(str(r_data.get("recipe_code") or f"RAMUAN-{idx:02d}"))

        existing = db_session.query(HerbalRecipe).filter(
            (HerbalRecipe.slug == slug_val) | (HerbalRecipe.recipe_code == code_val)
        ).first()
        if existing:
            db_session.delete(existing)
            db_session.flush()

        ings_raw = r_data.get("ingredients", []) or []
        steps_raw = r_data.get("steps", []) or []
        usages_raw = r_data.get("usages", []) or []
        sources_raw = r_data.get("sources", []) or []

        # Derive fallback fields if importing from generic JSON recipe format
        nama_tanaman = normalize_text(str(r_data.get("nama_tanaman") or ""))
        nama_ilmiah = normalize_text(str(r_data.get("nama_ilmiah") or ""))
        if not nama_tanaman and ings_raw and isinstance(ings_raw[0], dict):
            first_bahan = str(ings_raw[0].get("nama_bahan", ""))
            if "(" in first_bahan and ")" in first_bahan:
                nama_tanaman = first_bahan.split("(")[0].strip()
                nama_ilmiah = first_bahan.split("(")[1].split(")")[0].strip()
            else:
                nama_tanaman = first_bahan.strip()

        takaran_sumber = normalize_text(str(r_data.get("takaran_bahan_sumber") or ""))
        if not takaran_sumber and ings_raw:
            takaran_sumber = "; ".join(
                f"{i.get('nama_bahan', '')}: {i.get('jumlah', '')} {i.get('satuan', '')}".strip()
                for i in ings_raw
                if isinstance(i, dict)
            )

        bahan_tambahan_val = normalize_text(str(r_data.get("bahan_tambahan") or ""))
        if not bahan_tambahan_val:
            if len(ings_raw) > 1:
                bahan_tambahan_val = "; ".join(
                    f"{i.get('nama_bahan', '')} ({i.get('jumlah', '')} {i.get('satuan', '')})".strip()
                    for i in ings_raw[1:]
                    if isinstance(i, dict)
                )
            else:
                bahan_tambahan_val = "Tidak ada"

        cara_membuat_val = normalize_text(str(r_data.get("cara_membuat_sumber") or ""))
        if not cara_membuat_val and steps_raw:
            cara_membuat_val = " ".join(
                str(s.get("deskripsi_langkah", "")).strip()
                for s in steps_raw
                if isinstance(s, dict)
            )

        aturan_pakai_val = normalize_text(str(r_data.get("aturan_pakai_sumber") or ""))
        if not aturan_pakai_val and usages_raw and isinstance(usages_raw[0], dict):
            aturan_pakai_val = normalize_text(str(usages_raw[0].get("aturan_penggunaan_dari_sumber") or ""))

        sumber_dok_val = normalize_text(str(r_data.get("sumber_dokumen") or ""))
        if not sumber_dok_val and sources_raw and isinstance(sources_raw[0], dict):
            sumber_dok_val = f"{sources_raw[0].get('instansi', '')} - {sources_raw[0].get('nama_referensi', '')}".strip(" -")

        default_age_map = {
            "bayi_0_11_bulan": "TIDAK DITETAPKAN dalam rujukan; jangan gunakan sebagai dosis mandiri",
            "balita_1_2_tahun": "TIDAK DITETAPKAN dalam rujukan; jangan gunakan sebagai dosis mandiri",
            "balita_3_5_tahun": "TIDAK DITETAPKAN dalam rujukan; jangan gunakan sebagai dosis mandiri",
            "anak_6_8_tahun": "TIDAK DITETAPKAN dalam rujukan; jangan gunakan sebagai dosis mandiri",
            "anak_9_11_tahun": "TIDAK DITETAPKAN dalam rujukan; jangan gunakan sebagai dosis mandiri",
            "remaja_12_17_tahun": "TIDAK DITETAPKAN dalam rujukan; jangan gunakan sebagai dosis mandiri",
            "dewasa_18_59_tahun": "Rujukan tidak menetapkan kelompok usia dewasa secara khusus; lihat takaran/aturan umum di kolom sebelumnya dan konsultasi dokter/apoteker.",
            "lansia_60_plus": "TIDAK DITETAPKAN dalam rujukan; jangan gunakan sebagai dosis mandiri",
        }
        age_map = r_data.get("dosis_kelompok_usia_map")
        if not isinstance(age_map, dict) or not age_map:
            age_map = default_age_map

        recipe_obj = HerbalRecipe(
            recipe_code=code_val,
            slug=slug_val,
            nama_ramuan=nama,
            nama_tanaman=nama_tanaman or None,
            nama_ilmiah=nama_ilmiah or None,
            bagian_tanaman=normalize_text(str(r_data.get("bagian_tanaman") or "")) or "Bagian tanaman sesuai rujukan",
            rute_penggunaan=normalize_text(str(r_data.get("rute_penggunaan") or "")) or "Minum",
            deskripsi=normalize_text(str(r_data.get("deskripsi", ""))),
            keluhan_terkait=normalize_text(str(r_data.get("keluhan_terkait", "Umum"))),
            takaran_bahan_sumber=takaran_sumber or None,
            bahan_tambahan=bahan_tambahan_val or "Tidak ada",
            cara_menyiapkan_bahan=normalize_text(str(r_data.get("cara_menyiapkan_bahan") or "")) or None,
            cara_membuat_sumber=cara_membuat_val or None,
            aturan_pakai_sumber=aturan_pakai_val or None,
            dosis_kelompok_usia_json=json.dumps(age_map, ensure_ascii=False),
            kelompok_tidak_dianjurkan=normalize_text(str(r_data.get("kelompok_tidak_dianjurkan") or "")) or None,
            status_keamanan_dosis=normalize_text(
                str(
                    r_data.get("status_keamanan_dosis")
                    or "REFERENSI PENGGUNAAN TRADISIONAL; BUKAN DOSIS AMAN TERBUKTI; BUTUH REVIEW APOTEKER/DOKTER"
                )
            ),
            status_verifikasi=normalize_text(str(r_data.get("status_verifikasi", "Perlu verifikasi"))),
            sumber_dokumen=sumber_dok_val or None,
            sumber_url=str(r_data.get("sumber_url") or "").strip() or None,
            sumber_halaman=normalize_text(str(r_data.get("sumber_halaman") or "")) or None,
            reviewer=normalize_text(str(r_data.get("reviewer") or "")) or None,
            tanggal_review=normalize_text(str(r_data.get("tanggal_review") or "")) or None,
            peringatan=normalize_text(str(r_data.get("peringatan", ""))),
            kontraindikasi=normalize_text(str(r_data.get("kontraindikasi", ""))),
        )
        db_session.add(recipe_obj)
        db_session.flush()

        for ing in r_data.get("ingredients", []) or []:
            if isinstance(ing, dict) and ing.get("nama_bahan"):
                db_session.add(
                    RecipeIngredient(
                        recipe_id=recipe_obj.id,
                        nama_bahan=normalize_text(str(ing["nama_bahan"])),
                        jumlah=normalize_text(str(ing.get("jumlah") or "")) or None,
                        satuan=normalize_text(str(ing.get("satuan") or "")) or None,
                        catatan=normalize_text(str(ing.get("catatan") or "")) or None,
                    )
                )

        for step_idx, st in enumerate(r_data.get("steps", []) or [], start=1):
            if isinstance(st, dict) and st.get("deskripsi_langkah"):
                db_session.add(
                    RecipeStep(
                        recipe_id=recipe_obj.id,
                        nomor_langkah=int(st.get("nomor_langkah") or step_idx),
                        deskripsi_langkah=normalize_text(str(st["deskripsi_langkah"])),
                    )
                )

        for usg in r_data.get("usages", []) or []:
            if isinstance(usg, dict):
                db_session.add(
                    RecipeUsage(
                        recipe_id=recipe_obj.id,
                        aturan_penggunaan_dari_sumber=normalize_text(
                            str(usg.get("aturan_penggunaan_dari_sumber") or "")
                        )
                        or None,
                        status_review_penggunaan=normalize_text(
                            str(usg.get("status_review_penggunaan") or "MENUNGGU_VERIFIKASI")
                        ),
                        boleh_ditampilkan_publik=bool(usg.get("boleh_ditampilkan_publik", False)),
                    )
                )

        for src in r_data.get("sources", []) or []:
            if isinstance(src, dict) and src.get("nama_referensi"):
                db_session.add(
                    RecipeSource(
                        recipe_id=recipe_obj.id,
                        nama_referensi=normalize_text(str(src["nama_referensi"])),
                        instansi=normalize_text(str(src.get("instansi") or "Instansi Resmi")),
                        url=str(src.get("url") or "https://repository.kemkes.go.id/book/352").strip(),
                        halaman=normalize_text(str(src.get("halaman") or "")) or None,
                        status_validasi=normalize_text(
                            str(src.get("status_validasi") or "PERLU_VERIFIKASI")
                        ),
                    )
                )

        inserted_slugs.append(slug_val)

    db_session.flush()
    return inserted_slugs


def run_import(
    incoming_dir: Path = INCOMING_DIR,
    processed_dir: Path = PROCESSED_DIR,
    report_path: Path = IMPORT_REPORT_PATH,
    db_session: Optional[Session] = None,
) -> dict[str, Any]:
    """Execute full data import pipeline from data/incoming into SQLite and data/processed."""
    processed_dir.mkdir(parents=True, exist_ok=True)
    incoming_dir.mkdir(parents=True, exist_ok=True)
    extract_dir = processed_dir / "colab_extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    report: dict[str, Any] = {
        "timestamp": now_iso,
        "incoming_dir": str(incoming_dir),
        "processed_dir": str(processed_dir),
        "files_found": {},
        "zip_security_audit": {},
        "jsonl_import": {"total_lines": 0, "valid_rows": 0, "failed_rows": 0, "errors": []},
        "csv_qa_import": {"total_rows": 0, "strict_review_count": 0},
        "sources_import": {"total_rows": 0, "source_ids": []},
        "candidate_links_import": {
            "total_rows": 0,
            "candidate_topic_rows": 0,
            "unique_questions_with_candidate": 0,
            "questions_needing_reference": 0,
        },
        "plants_import": {
            "total_plants_created": 0,
            "plants_with_scientific_name": 0,
            "plants_local_name_only": 0,
            "merged_duplicate_mentions": [],
            "skipped_non_plant_qa": [],
        },
        "artifacts_audit": {},
    }

    # 1. Locate JSONL (in data/incoming or project root fallback)
    jsonl_path = incoming_dir / "indonesian_traditional_medicine.jsonl"
    if not jsonl_path.exists():
        fallback_jsonl = BASE_DIR / "indonesian_traditional_medicine.jsonl"
        if fallback_jsonl.exists():
            shutil.copy2(fallback_jsonl, jsonl_path)
    report["files_found"]["jsonl_present"] = jsonl_path.exists()

    # 2. Locate and safely extract ZIP (or fallback folder)
    zip_path = incoming_dir / "HERB_INFO_AI_Hasil_Colab.zip"
    fallback_colab_dir = BASE_DIR / "HERB_INFO_AI_Hasil_Colab"
    if not zip_path.exists() and fallback_colab_dir.exists():
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in sorted(fallback_colab_dir.iterdir()):
                if item.is_file():
                    zf.write(item, arcname=item.name)

    report["files_found"]["zip_present"] = zip_path.exists()

    if zip_path.exists():
        extracted_names = safe_extract_zip(
            zip_path=zip_path,
            extract_dir=extract_dir,
            allowed_filenames=ALLOWED_ZIP_FILENAMES,
        )
        report["zip_security_audit"] = {
            "status": "PASSED",
            "extracted_file_count": len(extracted_names),
            "extracted_files": extracted_names,
            "joblib_auto_deserialized": False,
            "joblib_security_note": (
                "tfidf_vectorizer.joblib diarsipkan tanpa deserialisasi otomatis untuk mencegah "
                "eksekusi kode berbahaya (pickle/joblib). Indeks TF-IDF dilatih ulang secara "
                "deterministik dari bpom_sumber_resmi.csv."
            ),
        }
    elif fallback_colab_dir.exists():
        extracted_names = []
        for item in sorted(fallback_colab_dir.iterdir()):
            if item.is_file() and item.name in ALLOWED_ZIP_FILENAMES:
                shutil.copy2(item, extract_dir / item.name)
                extracted_names.append(item.name)
        report["zip_security_audit"] = {
            "status": "FALLBACK_DIR_USED",
            "extracted_file_count": len(extracted_names),
            "extracted_files": extracted_names,
            "joblib_auto_deserialized": False,
        }
    else:
        extracted_names = []
        report["zip_security_audit"] = {"status": "MISSING_ZIP", "extracted_files": []}

    # Archive static artifacts to processed_dir
    for artifact_name in [
        "eda_distribusi_panjang.png",
        "template_evaluasi_manual.csv",
        "bpom_semantic_embeddings.npy",
        "tfidf_matrix.npz",
    ]:
        src_art = extract_dir / artifact_name
        if src_art.exists():
            shutil.copy2(src_art, processed_dir / artifact_name)

    joblib_src = extract_dir / "tfidf_vectorizer.joblib"
    if joblib_src.exists():
        shutil.copy2(joblib_src, processed_dir / "archived_tfidf_vectorizer.joblib")
        if ALLOW_UNSAFE_JOBLIB:
            report["zip_security_audit"]["joblib_opt_in_enabled"] = True

    # Audit embeddings and evaluation template
    emb_path = extract_dir / "bpom_semantic_embeddings.npy"
    if emb_path.exists():
        emb_arr = np.load(emb_path)
        report["artifacts_audit"]["bpom_semantic_embeddings"] = {
            "shape": list(emb_arr.shape),
            "dtype": str(emb_arr.dtype),
        }

    eval_csv_path = extract_dir / "template_evaluasi_manual.csv"
    gold_filled_count = 0
    eval_total_count = 0
    if eval_csv_path.exists():
        with open(eval_csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                eval_total_count += 1
                if (row.get("gold_source_id") or "").strip():
                    gold_filled_count += 1
    report["artifacts_audit"]["template_evaluasi_manual"] = {
        "total_rows": eval_total_count,
        "gold_source_id_filled": gold_filled_count,
        "note": (
            "Semua gold_source_id masih kosong; metrik akurasi tidak diklaim."
            if gold_filled_count == 0
            else f"{gold_filled_count} dari {eval_total_count} baris memiliki gold_source_id."
        ),
    }

    # 3. Parse JSONL line-by-line
    jsonl_records: list[dict[str, str]] = []
    if jsonl_path.exists():
        with open(jsonl_path, "r", encoding="utf-8-sig") as f:
            for line_num, raw_line in enumerate(f, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                report["jsonl_import"]["total_lines"] += 1
                try:
                    obj = json.loads(stripped)
                    if not isinstance(obj, dict) or "instruction" not in obj or "output" not in obj:
                        raise ValueError("Baris JSONL tidak memiliki kunci wajib 'instruction'/'output'")
                    jsonl_records.append(
                        {
                            "instruction": normalize_text(str(obj.get("instruction", ""))),
                            "input": normalize_text(str(obj.get("input", ""))),
                            "output": normalize_text(str(obj.get("output", ""))),
                        }
                    )
                    report["jsonl_import"]["valid_rows"] += 1
                except Exception as exc:
                    report["jsonl_import"]["failed_rows"] += 1
                    report["jsonl_import"]["errors"].append(f"Baris {line_num}: {exc}")

    # 4. Parse qa_clean_belum_terverifikasi.csv
    qa_csv_path = extract_dir / "qa_clean_belum_terverifikasi.csv"
    qa_rows: list[dict[str, Any]] = []
    if qa_csv_path.exists():
        with open(qa_csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                qa_id = int(row["id"])
                pertanyaan = normalize_text(row["pertanyaan"])
                jawaban = normalize_text(row["jawaban_kaggle_asli"])
                strict_flag = str(row.get("indikasi_perlu_review_ketat", "False")).strip().lower() == "true"
                status_val = normalize_text(row.get("status_validasi", "BELUM_TERVERIFIKASI"))
                topik = classify_qa_topic(qa_id, pertanyaan, jawaban)
                qa_rows.append(
                    {
                        "id": qa_id,
                        "pertanyaan": pertanyaan,
                        "jawaban_kaggle_asli": jawaban,
                        "topik": topik,
                        "status_validasi": status_val,
                        "indikasi_perlu_review_ketat": strict_flag,
                        "panjang_pertanyaan": int(row.get("panjang_pertanyaan") or len(pertanyaan)),
                        "panjang_jawaban": int(row.get("panjang_jawaban") or len(jawaban)),
                    }
                )
    else:
        # Transparent fallback from JSONL if CSV is missing
        for idx, rec in enumerate(jsonl_records, start=1):
            pertanyaan = rec["instruction"]
            jawaban = rec["output"]
            topik = classify_qa_topic(idx, pertanyaan, jawaban)
            qa_rows.append(
                {
                    "id": idx,
                    "pertanyaan": pertanyaan,
                    "jawaban_kaggle_asli": jawaban,
                    "topik": topik,
                    "status_validasi": "BELUM_TERVERIFIKASI",
                    "indikasi_perlu_review_ketat": False,
                    "panjang_pertanyaan": len(pertanyaan),
                    "panjang_jawaban": len(jawaban),
                }
            )

    report["csv_qa_import"]["total_rows"] = len(qa_rows)
    report["csv_qa_import"]["strict_review_count"] = sum(
        1 for r in qa_rows if r["indikasi_perlu_review_ketat"]
    )

    # 5. Parse bpom_sumber_resmi.csv
    sources_csv_path = extract_dir / "bpom_sumber_resmi.csv"
    source_rows: list[dict[str, Any]] = []
    if sources_csv_path.exists():
        with open(sources_csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                source_rows.append(
                    {
                        "source_id": row["source_id"].strip(),
                        "judul": normalize_text(row["judul"]),
                        "topik": normalize_text(row["topik"]),
                        "ringkasan_aman": normalize_text(row["ringkasan_aman"]),
                        "source_url": row["source_url"].strip(),
                        "otoritas": "BPOM RI",
                        "status_review": normalize_text(
                            row.get("status_review", "RUJUKAN_BPOM_PERLU_KURASI_PER_KLAIM")
                        ),
                    }
                )

    report["sources_import"]["total_rows"] = len(source_rows)
    report["sources_import"]["source_ids"] = [s["source_id"] for s in source_rows]

    # 6. Parse pencocokan_kandidat_bpom.csv
    cand_csv_path = extract_dir / "pencocokan_kandidat_bpom.csv"
    cand_rows: list[dict[str, Any]] = []
    unique_q_with_cand: set[int] = set()
    q_needing_ref: set[int] = set()
    if cand_csv_path.exists():
        with open(cand_csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                qa_id = int(row["id"])
                src_id = (row.get("source_id") or "").strip() or None
                status_kec = normalize_text(row.get("status_kecocokan", "PERLU_REFERENSI_TAMBAHAN"))
                disetujui = str(row.get("klaim_medis_disetujui", "False")).strip().lower() == "true"
                cand_rows.append(
                    {
                        "qa_id": qa_id,
                        "source_id": src_id,
                        "status_kecocokan": status_kec,
                        "klaim_medis_disetujui": disetujui,
                    }
                )
                if src_id and status_kec == "KANDIDAT_TOPIK_PERLU_VERIFIKASI":
                    unique_q_with_cand.add(qa_id)
                else:
                    q_needing_ref.add(qa_id)

    report["candidate_links_import"] = {
        "total_rows": len(cand_rows),
        "candidate_topic_rows": sum(1 for c in cand_rows if c["source_id"] is not None),
        "unique_questions_with_candidate": len(unique_q_with_cand),
        "questions_needing_reference": len(q_needing_ref),
    }

    # 7. Backup existing database and populate Database Tables (ensure recipe tables reflect latest schema)
    try:
        db_file_str = str(engine.url).replace("sqlite:///", "")
        db_file_path = Path(db_file_str)
        if db_file_path.exists() and db_file_path.is_file():
            backup_file = db_file_path.with_name(f"{db_file_path.name}.bak")
            shutil.copy2(db_file_path, backup_file)
    except Exception:
        pass

    for tbl in [RecipeSource.__table__, RecipeUsage.__table__, RecipeStep.__table__, RecipeIngredient.__table__, HerbalRecipe.__table__]:
        tbl.drop(bind=engine, checkfirst=True)
    Base.metadata.create_all(bind=engine)
    own_session = False
    if db_session is None:
        db_session = SessionLocal()
        own_session = True

    try:
        db_session.query(RecipeSource).delete()
        db_session.query(RecipeUsage).delete()
        db_session.query(RecipeStep).delete()
        db_session.query(RecipeIngredient).delete()
        db_session.query(HerbalRecipe).delete()
        db_session.query(PlantQALink).delete()
        db_session.query(PlantReference).delete()
        db_session.query(QAReference).delete()
        db_session.query(Plant).delete()
        db_session.query(QAPair).delete()
        db_session.query(Source).delete()
        db_session.commit()

        # Insert Sources
        valid_source_ids = set()
        for s_row in source_rows:
            valid_source_ids.add(s_row["source_id"])
            db_session.add(Source(**s_row))
        db_session.flush()

        # Insert QAPairs
        qa_by_id: dict[int, QAPair] = {}
        for q_row in qa_rows:
            qa_obj = QAPair(**q_row)
            db_session.add(qa_obj)
            qa_by_id[q_row["id"]] = qa_obj
        db_session.flush()

        # Insert QAReferences
        for c_row in cand_rows:
            src_id = c_row["source_id"] if c_row["source_id"] in valid_source_ids else None
            if c_row["qa_id"] in qa_by_id:
                db_session.add(
                    QAReference(
                        qa_id=c_row["qa_id"],
                        source_id=src_id,
                        status_kecocokan=c_row["status_kecocokan"],
                        klaim_medis_disetujui=c_row["klaim_medis_disetujui"],
                    )
                )
        db_session.flush()

        # Extract and insert Plants from Q&A
        plants_by_name: dict[str, Plant] = {}
        plant_clean_export: list[dict[str, Any]] = []

        for q_row in qa_rows:
            qid = q_row["id"]
            if qid in PRIMARY_PLANT_SPECS:
                spec = PRIMARY_PLANT_SPECS[qid]
                nama_umum = spec["nama_umum"]
                nama_ilmiah = spec["nama_ilmiah"]
                nama_lokal = spec["nama_lokal"]
                slug = slugify(nama_umum)
                ringkasan_terkurasi = CURATED_PLANT_SUMMARIES.get(nama_umum)
                status_verifikasi = "Perlu verifikasi"

                plant_obj = Plant(
                    slug=slug,
                    nama_umum=nama_umum,
                    nama_ilmiah=nama_ilmiah,
                    famili=None,
                    nama_lokal_json=json.dumps(nama_lokal, ensure_ascii=False),
                    ringkasan_terkurasi=ringkasan_terkurasi,
                    gambar_url=None,
                    gambar_lisensi="Ilustrasi siluet botani generik HERB-INFO AI (tanpa klaim foto spesimen)",
                    status_verifikasi=status_verifikasi,
                    updated_at=now_iso,
                    sumber_data=f"Ekstraksi Entitas Q&A #{qid} (Kaggle) & Pemetaan Topik BPOM",
                )
                db_session.add(plant_obj)
                db_session.flush()
                plants_by_name[nama_umum] = plant_obj

                # Link primary Q&A
                db_session.add(
                    PlantQALink(
                        plant_id=plant_obj.id,
                        qa_id=qid,
                        tipe_kaitan="utama",
                    )
                )
            else:
                # Non-plant Q&A row: record reason in import_report.json
                report["plants_import"]["skipped_non_plant_qa"].append(
                    {
                        "qa_id": qid,
                        "pertanyaan": q_row["pertanyaan"],
                        "topik": q_row["topik"],
                        "alasan": (
                            f"Entri membahas {q_row['topik']} (bukan spesies tanaman tunggal); "
                            "disimpan pada Pengetahuan & Tanya Jawab."
                        ),
                    }
                )

        # Insert local-name-only plants explicitly cited in Q&A recipes
        for local_spec in LOCAL_ONLY_PLANT_SPECS:
            nama_umum = local_spec["nama_umum"]
            slug = slugify(nama_umum)
            plant_obj = Plant(
                slug=slug,
                nama_umum=nama_umum,
                nama_ilmiah=None,
                famili=None,
                nama_lokal_json=json.dumps(local_spec["nama_lokal"], ensure_ascii=False),
                ringkasan_terkurasi=None,
                gambar_url=None,
                gambar_lisensi="Ilustrasi siluet botani generik HERB-INFO AI (tanpa klaim foto spesimen)",
                status_verifikasi="Data terbatas",
                updated_at=now_iso,
                sumber_data=" Disebutkan sebagai bahan tanaman lokal pada Q&A #"
                + ", #".join(str(i) for i in local_spec["origin_qa_ids"]),
            )
            db_session.add(plant_obj)
            db_session.flush()
            plants_by_name[nama_umum] = plant_obj

        # Link secondary/duplicate mentions of plants in multi-herb Q&A entries
        for qid, mentioned_names in SECONDARY_PLANT_MENTIONS.items():
            if qid not in qa_by_id:
                continue
            for p_name in mentioned_names:
                plant_obj = plants_by_name.get(p_name)
                if plant_obj is None:
                    continue
                db_session.add(
                    PlantQALink(
                        plant_id=plant_obj.id,
                        qa_id=qid,
                        tipe_kaitan="disebut_dalam_ramuan",
                    )
                )
                report["plants_import"]["merged_duplicate_mentions"].append(
                    {
                        "qa_id": qid,
                        "nama_tanaman": p_name,
                        "target_slug": plant_obj.slug,
                        "tindakan": "Digabungkan ke entitas tanaman yang sudah ada melalui relasi PlantQALink",
                    }
                )

        # Insert PlantReference links to BPOM sources
        for p_name, ref_list in PLANT_BPOM_LINKS.items():
            plant_obj = plants_by_name.get(p_name)
            if not plant_obj:
                continue
            for ref in ref_list:
                if ref["source_id"] in valid_source_ids:
                    db_session.add(
                        PlantReference(
                            plant_id=plant_obj.id,
                            source_id=ref["source_id"],
                            tipe_relasi=ref["tipe_relasi"],
                            catatan_kurasi=ref["catatan_kurasi"],
                        )
                    )

        # 8. Import ONLY Curated FROTI Kemenkes 2017 Dataset (single active recipe corpus per Requirement D)
        froti_candidates = [
            BASE_DIR / "data" / "dataset_FROTI_HerbID_bersih.csv",
            BASE_DIR / "dataset_FROTI_HerbID_bersih.csv",
            incoming_dir / "dataset_FROTI_HerbID_bersih.csv",
            BASE_DIR / "data" / "dataset_obat_tradisional_FROTI_terkurasi.csv",
            incoming_dir / "dataset_obat_tradisional_FROTI_terkurasi.csv",
            BASE_DIR / "dataset_obat_tradisional_FROTI_terkurasi.csv",
        ]
        froti_csv_path = next((p for p in froti_candidates if p.exists()), None)
        imported_recipe_slugs: list[str] = []
        froti_count = 0

        if froti_csv_path is not None and froti_csv_path.exists():
            try:
                froti_recipes = parse_froti_csv(froti_csv_path)
                froti_slugs = upsert_recipe_records(db_session, froti_recipes)
                imported_recipe_slugs.extend(froti_slugs)
                froti_count = len(froti_slugs)
            except Exception as exc:
                report.setdefault("recipes_import", {})["froti_csv_error"] = str(exc)

        # Note: per Requirement D, BPOM and old Q&A datasets are NOT recipe sources.
        # Only FROTI Kemenkes 2017 is active as the sole herbal recipe corpus.

        db_session.commit()

        report["recipes_import"] = {
            "total_recipes_imported": len(imported_recipe_slugs),
            "froti_curated_count": froti_count,
            "recipe_slugs": imported_recipe_slugs,
            "active_dataset": str(froti_csv_path.name if froti_csv_path else "none"),
            "froti_status": (
                f"Terintegrasi {froti_count} entri resmi Formularium Ramuan Obat Tradisional Indonesia "
                "(FROTI - KMK HK.01.07/MENKES/187/2017) sebagai satu-satunya korpus ramuan aktif."
            ),
        }

        all_plants = db_session.query(Plant).order_by(Plant.nama_umum.asc()).all()
        for p in all_plants:
            plant_clean_export.append(
                {
                    "id": p.id,
                    "slug": p.slug,
                    "nama_umum": p.nama_umum,
                    "nama_ilmiah": p.nama_ilmiah,
                    "famili": p.famili,
                    "nama_lokal": p.nama_lokal,
                    "status_verifikasi": p.status_verifikasi,
                    "sumber_data": p.sumber_data,
                }
            )

        report["plants_import"]["total_plants_created"] = len(all_plants)
        report["plants_import"]["plants_with_scientific_name"] = sum(
            1 for p in all_plants if p.nama_ilmiah
        )
        report["plants_import"]["plants_local_name_only"] = sum(
            1 for p in all_plants if not p.nama_ilmiah
        )

        # Save processed JSON exports
        with open(processed_dir / "plants_clean.json", "w", encoding="utf-8") as f:
            json.dump(plant_clean_export, f, ensure_ascii=False, indent=2)
        with open(processed_dir / "qa_clean.json", "w", encoding="utf-8") as f:
            json.dump(qa_rows, f, ensure_ascii=False, indent=2)
        with open(processed_dir / "sources_clean.json", "w", encoding="utf-8") as f:
            json.dump(source_rows, f, ensure_ascii=False, indent=2)

        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report
    finally:
        if own_session:
            db_session.close()


if __name__ == "__main__":
    result = run_import()
    print(
        f"Impor selesai: {result['plants_import']['total_plants_created']} tanaman, "
        f"{result['csv_qa_import']['total_rows']} Q&A, "
        f"{result['sources_import']['total_rows']} sumber BPOM."
    )
