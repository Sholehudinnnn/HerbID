"""Evaluation metrics (Hit@1, Recall@3, MRR@10) and NLP benchmark runner (>= 30 test queries)."""
import csv
from pathlib import Path
from typing import Any, Optional

from app.config import PROCESSED_DIR
from app.services.gemini_service import _GEMINI_QUERY_EMBED_CACHE, embed_texts_gemini, is_gemini_configured
from app.services.search_service import SearchEngineService, preprocess_indonesian_query

DATA_DIR = PROCESSED_DIR.parent
_BENCHMARK_PRED_CACHE: dict[str, dict[str, list[str]]] = {}



# 20 diverse functional test queries covering normal, abbreviations, local names, sensitive clinical,
# irrelevant, empty, XSS, and long input cases. NEVER used as fake gold labels!
FUNCTIONAL_TEST_QUERIES: list[dict[str, Any]] = [
    {
        "id": "FQ-01",
        "category": "regulasi_singkatan",
        "query": "Apa perbedaan jamu, OHT, dan fitofarmaka?",
        "expected_behavior": "Mengembalikan BPOM-01 pada urutan teratas tanpa peringatan klinis",
    },
    {
        "id": "FQ-02",
        "category": "regulasi_umum",
        "query": "perbedaan jamu dan fitofarmaka",
        "expected_behavior": "Mengembalikan BPOM-01 dengan sorotan kata jamu dan fitofarmaka",
    },
    {
        "id": "FQ-03",
        "category": "singkatan_bko",
        "query": "Apa bahaya BKO bahan kimia obat dalam jamu tradisional?",
        "expected_behavior": "Mengembalikan BPOM-05 tentang Bahaya BKO dalam Obat Tradisional",
    },
    {
        "id": "FQ-04",
        "category": "registrasi_klik",
        "query": "Cara cek KLIK kemasan label izin edar kedaluwarsa jamu aman",
        "expected_behavior": "Mengembalikan BPOM-03 dan BPOM-02 terkait edukasi memilih jamu aman & cek produk",
    },
    {
        "id": "FQ-05",
        "category": "registrasi_portal",
        "query": "Bagaimana cara memeriksa status nomor izin edar produk di BPOM?",
        "expected_behavior": "Mengembalikan BPOM-02 (Cek Produk BPOM)",
    },
    {
        "id": "FQ-06",
        "category": "nama_tanaman_spesifik",
        "query": "Standar mutu bahan baku kunyit temulawak dan minyak kayu putih",
        "expected_behavior": "Mengembalikan BPOM-09 dan BPOM-07",
    },
    {
        "id": "FQ-07",
        "category": "registrasi_bahan_tunggal",
        "query": "registrasi obat bahan alam bentuk tunggal temulawak",
        "expected_behavior": "Mengembalikan BPOM-07 pada peringkat atas",
    },
    {
        "id": "FQ-08",
        "category": "tradisi_umkm",
        "query": "pendampingan pelaku usaha UMKM jamu gendong",
        "expected_behavior": "Mengembalikan BPOM-08 tentang Informasi UMKM Jamu Gendong",
    },
    {
        "id": "FQ-09",
        "category": "klaim_regulasi",
        "query": "pedoman klaim khasiat obat bahan alam harus objektif",
        "expected_behavior": "Mengembalikan BPOM-06",
    },
    {
        "id": "FQ-10",
        "category": "sensitif_kehamilan_dosis",
        "query": "Saya hamil, berapa dosis jamu yang aman?",
        "expected_behavior": "Memunculkan peringatan wajib konsultasi apoteker/dokter dan tidak memberikan takaran dosis",
    },
    {
        "id": "FQ-11",
        "category": "sensitif_bayi",
        "query": "Apakah madu dan minyak kayu putih aman diminum bayi 6 bulan?",
        "expected_behavior": "Memunculkan peringatan kelompok rentan (bayi)",
    },
    {
        "id": "FQ-12",
        "category": "sensitif_penyakit_berat",
        "query": "Berapa lembar daun sirsak untuk menyembuhkan kanker dan gagal ginjal?",
        "expected_behavior": "Memunculkan peringatan kondisi medis serius & dosis tanpa memberi instruksi terapi",
    },
    {
        "id": "FQ-13",
        "category": "sensitif_interaksi_obat",
        "query": "Bolehkah minum herbal bersamaan dengan obat pengencer darah warfarin?",
        "expected_behavior": "Memunculkan peringatan interaksi obat & menampilkan edukasi BPOM-04",
    },
    {
        "id": "FQ-14",
        "category": "sensitif_menyusui",
        "query": "Takaran jamu kunyit asam untuk ibu menyusui setiap hari",
        "expected_behavior": "Memunculkan peringatan menyusui dan dosis",
    },
    {
        "id": "FQ-15",
        "category": "typo_ringan",
        "query": "penggolongan jmu oht fitofarmaka obat bahan alam",
        "expected_behavior": "Tetap menemukan BPOM-01 dari token yang valid",
    },
    {
        "id": "FQ-16",
        "category": "kapital_whitespace",
        "query": "   BAHAYA    BKO   DALAM   OBAT   TRADISIONAL   ",
        "expected_behavior": "Menormalisasi spasi/huruf besar dan mengembalikan BPOM-05",
    },
    {
        "id": "FQ-17",
        "category": "query_tidak_relevan",
        "query": "harga tiket pesawat jakarta surabaya besok pagi",
        "expected_behavior": "Skor di bawah ambang batas, mengembalikan hasil kosong dan pesan Sumber tepercaya belum ditemukan",
    },
    {
        "id": "FQ-18",
        "category": "nama_lokal_tanpa_sumber_bpom",
        "query": "resep loloh cemcem dan boreh bali",
        "expected_behavior": "Menjawab jujur Sumber tepercaya belum ditemukan pada rujukan BPOM",
    },
    {
        "id": "FQ-19",
        "category": "query_kosong",
        "query": "    ",
        "expected_behavior": "Tidak crash, mengembalikan daftar kosong dan pesan minta kata kunci",
    },
    {
        "id": "FQ-20",
        "category": "keamanan_xss_html",
        "query": "<script>alert('xss')</script><img src=x onerror=alert(1)> jamu aman",
        "expected_behavior": "Tag HTML/script dibersihkan tanpa dieksekusi dan pencarian kata jamu aman tetap berjalan aman",
    },
]

# 35 Academic NLP Evaluation Benchmark Queries (>= 30 required).
# Note: gold_relevant_ids is EMPTY by default so no fabricated metrics are ever reported prior to manual annotation!
DEFAULT_NLP_BENCHMARK_35: list[dict[str, str]] = [
    {
        "id_uji": "EV-01",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Saya demam, ada informasi ramuan tradisional sambiloto?",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-001",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-02",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Ramuan tradisional kencur untuk sakit kepala sebelah",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-002;FROTI-003",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-03",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Pucuk daun teh untuk mengatasi sakit kepala sebelah",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-003;FROTI-002",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-04",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Rebusan daun sirih untuk berkumur saat sakit tenggorokan",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-004;R-006",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-05",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Herba timi untuk meredakan batuk berdahak",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-005;FROTI-006;FROTI-007",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-06",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Akar manis untuk ramuan batuk berdahak",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-006;FROTI-005;FROTI-007",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-07",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Seduhan buah adas untuk batuk berdahak",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-007;FROTI-005;FROTI-006",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-08",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Ramuan jahe untuk keluhan leher kaku",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-008",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-09",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Olesan rimpang kencur dan beras untuk terkilir",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-009;FROTI-010",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-10",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Parutan rimpang lengkuas untuk terkilir luar",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-010;FROTI-009",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-11",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Rebusan akar alang-alang untuk panas dalam",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-011;FROTI-012",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-12",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Perasan daun cincau untuk meredakan panas dalam",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-012;FROTI-011",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-13",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Rimpang temu hitam untuk nafsu makan berkurang",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-013;FROTI-014",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-14",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Daun pepaya segar untuk mengatasi nafsu makan berkurang pada anak",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-014;FROTI-013",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-15",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Rimpang kunyit untuk keluhan perut kembung",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-015",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-16",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Seduhan jahe untuk gangguan lambung",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-016;FROTI-017",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-17",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Ramuan jahe hangat untuk masuk angin",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-017;R-003",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-18",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Kayu manis untuk meredakan nyeri haid",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-018;R-001",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-19",
        "kategori_uji": "keluhan_froti_eksak",
        "pertanyaan_uji": "Daun andong untuk keluhan haid tidak teratur",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-019",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-20",
        "kategori_uji": "sinonim_keluhan",
        "pertanyaan_uji": "Obat tradisional untuk migrain dan pusing sebelah",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-002;FROTI-003",
        "catatan_anotasi": "Uji ekspansi sinonim migrain -> sakit kepala sebelah",
    },
    {
        "id_uji": "EV-21",
        "kategori_uji": "sinonim_keluhan",
        "pertanyaan_uji": "Ramuan untuk perut begah dan maag asam lambung",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-015;FROTI-016",
        "catatan_anotasi": "Uji ekspansi sinonim begah/maag -> perut kembung & gangguan lambung",
    },
    {
        "id_uji": "EV-22",
        "kategori_uji": "sinonim_keluhan",
        "pertanyaan_uji": "Cara mengobati kaki keseleo dan salah urat",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-009;FROTI-010",
        "catatan_anotasi": "Uji ekspansi sinonim keseleo/salah urat -> terkilir",
    },
    {
        "id_uji": "EV-23",
        "kategori_uji": "sinonim_keluhan",
        "pertanyaan_uji": "Ramuan herbal untuk leher tengeng karena salah bantal",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-008",
        "catatan_anotasi": "Uji ekspansi sinonim tengeng/salah bantal -> leher kaku",
    },
    {
        "id_uji": "EV-24",
        "kategori_uji": "sinonim_keluhan",
        "pertanyaan_uji": "Minuman tradisional untuk dismenore saat datang bulan",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-018;R-001",
        "catatan_anotasi": "Uji ekspansi sinonim dismenore -> nyeri haid",
    },
    {
        "id_uji": "EV-25",
        "kategori_uji": "istilah_tanaman_lokal",
        "pertanyaan_uji": "Manfaat daun ki oray atau pepaitan untuk demam",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-001",
        "catatan_anotasi": "Uji pengenalan istilah lokal ki oray/pepaitan -> sambiloto",
    },
    {
        "id_uji": "EV-26",
        "kategori_uji": "istilah_tanaman_lokal",
        "pertanyaan_uji": "Ramuan cikur dan laja untuk bengkak terkilir",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-009;FROTI-010",
        "catatan_anotasi": "Uji pengenalan istilah lokal Sunda cikur (kencur) & laja (lengkuas)",
    },
    {
        "id_uji": "EV-27",
        "kategori_uji": "istilah_tanaman_lokal",
        "pertanyaan_uji": "Daun suruh untuk kumur radang tenggorokan",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-004;R-006",
        "catatan_anotasi": "Uji pengenalan istilah lokal Jawa suruh -> daun sirih",
    },
    {
        "id_uji": "EV-28",
        "kategori_uji": "istilah_tanaman_lokal",
        "pertanyaan_uji": "Rimpang temu ireng untuk anak susah makan",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-013;FROTI-014",
        "catatan_anotasi": "Uji pengenalan istilah lokal temu ireng -> temu hitam",
    },
    {
        "id_uji": "EV-29",
        "kategori_uji": "istilah_tanaman_lokal",
        "pertanyaan_uji": "Rebusan daun hanjuang untuk siklus menstruasi",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-019",
        "catatan_anotasi": "Uji pengenalan istilah lokal hanjuang -> andong",
    },
    {
        "id_uji": "EV-30",
        "kategori_uji": "typo_salah_ketik_ringan",
        "pertanyaan_uji": "ramuan sambilto untuk demm tinggi",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-001",
        "catatan_anotasi": "Uji koreksi typo sambilto -> sambiloto & demm -> demam",
    },
    {
        "id_uji": "EV-31",
        "kategori_uji": "typo_salah_ketik_ringan",
        "pertanyaan_uji": "rimpang kunyt untuk perut kembng",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-015",
        "catatan_anotasi": "Uji koreksi typo kunyt -> kunyit & kembng -> kembung",
    },
    {
        "id_uji": "EV-32",
        "kategori_uji": "typo_salah_ketik_ringan",
        "pertanyaan_uji": "daun pepya untuk nafsu makan berkurang",
        "target_korpus": "Ramuan FROTI",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "FROTI-014",
        "catatan_anotasi": "Uji koreksi typo pepya -> pepaya",
    },
    {
        "id_uji": "EV-33",
        "kategori_uji": "rujukan_bpom_regulasi",
        "pertanyaan_uji": "Apa perbedaan jamu, OHT, dan fitofarmaka menurut BPOM?",
        "target_korpus": "Sumber BPOM",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "BPOM-01",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-34",
        "kategori_uji": "rujukan_bpom_keamanan",
        "pertanyaan_uji": "Bahaya penambahan BKO bahan kimia obat pada jamu",
        "target_korpus": "Sumber BPOM",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "BPOM-05",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
    {
        "id_uji": "EV-35",
        "kategori_uji": "rujukan_bpom_interaksi",
        "pertanyaan_uji": "Interaksi obat herbal dengan obat medis konvensional",
        "target_korpus": "Sumber BPOM",
        "gold_relevant_ids": "",
        "kandidat_dokumen_petunjuk_anotator": "BPOM-04",
        "catatan_anotasi": "Menunggu verifikasi manual anotator",
    },
]

NLP_BENCHMARK_CSV_PATH = PROCESSED_DIR / "evaluasi_model_nlp_30_pertanyaan.csv"
NLP_BENCHMARK_DATA_COPY_PATH = DATA_DIR / "evaluasi_model_nlp_30_pertanyaan.csv"


def ensure_nlp_benchmark_csv(csv_path: Path = NLP_BENCHMARK_CSV_PATH) -> Path:
    """Create the 35-query NLP evaluation benchmark CSV if it does not exist yet."""
    fieldnames = [
        "id_uji",
        "kategori_uji",
        "pertanyaan_uji",
        "target_korpus",
        "gold_relevant_ids",
        "kandidat_dokumen_petunjuk_anotator",
        "catatan_anotasi",
    ]
    if not csv_path.exists():
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(DEFAULT_NLP_BENCHMARK_35)

    if not NLP_BENCHMARK_DATA_COPY_PATH.exists():
        try:
            NLP_BENCHMARK_DATA_COPY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(NLP_BENCHMARK_DATA_COPY_PATH, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(DEFAULT_NLP_BENCHMARK_35)
        except Exception:
            pass
    return csv_path


def evaluate_nlp_benchmark_30(
    engine_service: SearchEngineService,
    csv_path: Path = NLP_BENCHMARK_CSV_PATH,
    custom_annotations: Optional[dict[str, str]] = None,
    save_to_csv: bool = False,
) -> dict[str, Any]:
    """Evaluate Hit@1, Recall@3, and MRR@10 on the >=30 NLP test queries for TF-IDF and Semantic Search.

    Strictly refuses to fabricate scores: if no manual annotations (`gold_relevant_ids`) are present,
    returns `metrics_available: False` and status `EVALUASI_BELUM_DAPAT_DIHITUNG`.
    """
    ensure_nlp_benchmark_csv(csv_path)

    rows: list[dict[str, str]] = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            row_copy = dict(r)
            if custom_annotations is not None and row_copy["id_uji"] in custom_annotations:
                row_copy["gold_relevant_ids"] = custom_annotations[row_copy["id_uji"]].strip()
            rows.append(row_copy)

    if save_to_csv and custom_annotations is not None and rows:
        fieldnames = list(rows[0].keys())
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    labeled_rows: list[dict[str, str]] = []
    items_with_predictions: list[dict[str, Any]] = []

    # Pre-warm Gemini query embeddings in a single batch call if semantic mode is active and not yet cached
    if engine_service.semantic_available and is_gemini_configured():
        missing_expanded: list[str] = []
        for r in rows:
            q_text = r.get("pertanyaan_uji", "")
            nlp = preprocess_indonesian_query(q_text)
            exp_q = (nlp["expanded_query"] or q_text).strip().lower()
            if exp_q and exp_q not in _GEMINI_QUERY_EMBED_CACHE:
                missing_expanded.append(exp_q)
        if missing_expanded:
            batch_vecs = embed_texts_gemini(missing_expanded)
            if batch_vecs is not None and batch_vecs.shape[0] == len(missing_expanded):
                for idx_q, eq_str in enumerate(missing_expanded):
                    _GEMINI_QUERY_EMBED_CACHE[eq_str] = batch_vecs[idx_q]

    for r in rows:
        q_text = r.get("pertanyaan_uji", "")
        target_korpus = (r.get("target_korpus") or "Ramuan FROTI").strip()
        gold_raw = (r.get("gold_relevant_ids") or "").strip()
        if gold_raw:
            labeled_rows.append(r)

        cache_key = f"{r.get('id_uji', '')}|{q_text}|{target_korpus}|{engine_service.semantic_available}"
        if cache_key in _BENCHMARK_PRED_CACHE:
            tfidf_preds = _BENCHMARK_PRED_CACHE[cache_key]["tfidf"]
            sem_preds = _BENCHMARK_PRED_CACHE[cache_key]["semantic"]
        else:
            tfidf_res = engine_service.search(q_text, mode="tfidf", top_k=10)
            rec_codes_t = [m["recipe_code"] for m in tfidf_res.get("matched_recipes", [])]
            src_ids_t = [s["source_id"] for s in tfidf_res.get("results", [])]
            if "BPOM" in target_korpus.upper():
                tfidf_preds = src_ids_t + rec_codes_t
            else:
                tfidf_preds = rec_codes_t + src_ids_t

            sem_preds = []
            if engine_service.semantic_available:
                sem_res = engine_service.search(q_text, mode="semantic", top_k=10)
                rec_codes_s = [m["recipe_code"] for m in sem_res.get("matched_recipes", [])]
                src_ids_s = [s["source_id"] for s in sem_res.get("results", [])]
                if "BPOM" in target_korpus.upper():
                    sem_preds = src_ids_s + rec_codes_s
                else:
                    sem_preds = rec_codes_s + src_ids_s

            _BENCHMARK_PRED_CACHE[cache_key] = {
                "tfidf": tfidf_preds,
                "semantic": sem_preds,
            }


        items_with_predictions.append(
            {
                "id_uji": r.get("id_uji", ""),
                "kategori_uji": r.get("kategori_uji", ""),
                "pertanyaan_uji": q_text,
                "target_korpus": r.get("target_korpus", ""),
                "gold_relevant_ids": gold_raw,
                "kandidat_dokumen_petunjuk_anotator": r.get("kandidat_dokumen_petunjuk_anotator", ""),
                "catatan_anotasi": r.get("catatan_anotasi", ""),
                "top3_tfidf": tfidf_preds[:3],
                "top3_semantic": sem_preds[:3] if engine_service.semantic_available else [],
                "all_preds_tfidf": tfidf_preds[:10],
                "all_preds_semantic": sem_preds[:10],
            }
        )

    if not labeled_rows:
        return {
            "status": "EVALUASI_BELUM_DAPAT_DIHITUNG",
            "total_queries": len(rows),
            "labeled_queries": 0,
            "metrics_available": False,
            "note": (
                "Evaluasi belum dapat dihitung karena kolom label relevansi manual (gold_relevant_ids) "
                f"pada {len(rows)} pertanyaan uji belum diisi oleh anotator. Sesuai kaidah kejujuran akademik, "
                "sistem tidak membuat angka Hit@1, Recall@3, atau MRR@10 palsu. Anda dapat mengisi anotasi "
                "manual pada berkas evaluasi_model_nlp_30_pertanyaan.csv atau melalui tabel anotasi di halaman ini."
            ),
            "tfidf_metrics": None,
            "semantic_metrics": None,
            "items": items_with_predictions,
        }

    def _compute_metrics_from_preds(pred_key: str) -> dict[str, Any]:
        hits_1 = 0
        recall_3 = 0
        rr_10 = 0.0
        evaluated_n = 0
        for item in items_with_predictions:
            gold_str = (item.get("gold_relevant_ids") or "").strip()
            if not gold_str:
                continue
            gold_set = {g.strip().upper() for g in gold_str.replace(",", ";").split(";") if g.strip()}
            if not gold_set:
                continue
            evaluated_n += 1
            preds = [p.upper() for p in item.get(pred_key, [])]
            if preds and preds[0] in gold_set:
                hits_1 += 1
            if any(p in gold_set for p in preds[:3]):
                recall_3 += 1
            for rank_idx, p in enumerate(preds[:10], start=1):
                if p in gold_set:
                    rr_10 += 1.0 / rank_idx
                    break
        if evaluated_n == 0:
            return {"hit_at_1": 0.0, "recall_at_3": 0.0, "mrr_at_10": 0.0, "labeled_count": 0}
        return {
            "hit_at_1": round(hits_1 / evaluated_n, 4),
            "recall_at_3": round(recall_3 / evaluated_n, 4),
            "mrr_at_10": round(rr_10 / evaluated_n, 4),
            "labeled_count": evaluated_n,
        }

    tfidf_m = _compute_metrics_from_preds("all_preds_tfidf")
    sem_m = (
        _compute_metrics_from_preds("all_preds_semantic")
        if engine_service.semantic_available
        else None
    )

    return {
        "status": "EVALUATED",
        "total_queries": len(rows),
        "labeled_queries": len(labeled_rows),
        "metrics_available": True,
        "note": (
            f"Metrik Hit@1, Recall@3, dan MRR@10 dihitung secara nyata dari {len(labeled_rows)} "
            f"pertanyaan uji yang telah dianotasi manual (dari total {len(rows)} pertanyaan uji)."
        ),
        "tfidf_metrics": tfidf_m,
        "semantic_metrics": sem_m,
        "items": items_with_predictions,
    }


def evaluate_manual_template(
    engine_service: SearchEngineService,
    template_csv_path: Path = PROCESSED_DIR / "template_evaluasi_manual.csv",
) -> dict[str, Any]:
    """Compute Hit@1, Recall@3, and MRR@10 ONLY if gold_source_id annotations exist."""
    if not template_csv_path.exists():
        return {
            "status": "TEMPLATE_NOT_FOUND",
            "total_rows": 0,
            "labeled_rows": 0,
            "metrics_available": False,
            "note": "Berkas template_evaluasi_manual.csv belum tersedia.",
            "tfidf_metrics": None,
            "semantic_metrics": None,
        }

    rows: list[dict[str, str]] = []
    labeled: list[dict[str, str]] = []
    with open(template_csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
            gold = (r.get("gold_source_id") or "").strip()
            if gold:
                labeled.append({"id": r["id"], "pertanyaan": r["pertanyaan"], "gold_source_id": gold})

    if not labeled:
        return {
            "status": "UNLABELED_GOLD_DATA",
            "total_rows": len(rows),
            "labeled_rows": 0,
            "metrics_available": False,
            "note": (
                "Evaluasi relevansi menunggu anotasi manual. "
                f"Seluruh {len(rows)} baris pada template_evaluasi_manual.csv masih memiliki "
                "gold_source_id kosong. Sesuai kaidah integritas ilmiah, skor Hit@1, Recall@3, "
                "dan MRR@10 tidak dihitung atau diklaim sebelum anotasi pakar selesai."
            ),
            "tfidf_metrics": None,
            "semantic_metrics": None,
        }

    def compute_for_mode(mode_name: str) -> dict[str, float]:
        hits_at_1 = 0
        recall_at_3 = 0
        rr_sum = 0.0
        for item in labeled:
            gold_ids = {g.strip() for g in item["gold_source_id"].split(";") if g.strip()}
            res = engine_service.search(item["pertanyaan"], mode=mode_name, top_k=10)
            pred_ids = [r["source_id"] for r in res["results"]]
            if pred_ids and pred_ids[0] in gold_ids:
                hits_at_1 += 1
            if any(pid in gold_ids for pid in pred_ids[:3]):
                recall_at_3 += 1
            for rank_idx, pid in enumerate(pred_ids[:10], start=1):
                if pid in gold_ids:
                    rr_sum += 1.0 / rank_idx
                    break
        n = len(labeled)
        return {
            "hit_at_1": round(hits_at_1 / n, 4),
            "recall_at_3": round(recall_3 / n, 4),
            "mrr_at_10": round(rr_sum / n, 4),
            "labeled_count": n,
        }

    tfidf_m = compute_for_mode("tfidf")
    sem_m = compute_for_mode("semantic") if engine_service.semantic_available else None

    return {
        "status": "EVALUATED",
        "total_rows": len(rows),
        "labeled_rows": len(labeled),
        "metrics_available": True,
        "note": f"Dievaluasi pada {len(labeled)} contoh berlabel manual dari total {len(rows)} pertanyaan.",
        "tfidf_metrics": tfidf_m,
        "semantic_metrics": sem_m,
    }
