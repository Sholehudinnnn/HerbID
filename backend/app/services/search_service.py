"""TF-IDF baseline, Symptom-to-Herb Recommender, and optional Semantic search engine."""
import difflib
import hashlib
import importlib.util
import json
import re
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.config import ENABLE_SEMANTIC_MODEL, GEMINI_EMBEDDING_MODEL, GEMINI_MODEL_NAME, INDEX_META_PATH, PROCESSED_DIR
from app.models.db_models import HerbalRecipe, Source
from app.services.complaint_analysis_service import ComplaintAnalysisService
from app.services.safety_assessment_service import SafetyAssessmentService
from app.services.herbal_retrieval_service import HerbalRetrievalService
from app.services.evidence_analysis_service import EvidenceAnalysisService
from app.services.source_validation_service import SourceValidationService
from app.services.complaint_extractor import (
    SYMPTOM_BY_KEY,
    extract_duration,
    extract_structured_complaints,
    find_unnegated_keywords,
    format_celsius,
    normalize_medication_input,
    recipe_symptom_compatibility,
    strip_medication_none_statements,
)
from app.services.gemini_service import (
    embed_single_query_gemini,
    embed_texts_gemini,
    generate_gemini_consultation,
    is_gemini_configured,
)

MIN_SIMILARITY_THRESHOLD = 0.12
SEMANTIC_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

INDONESIAN_STOPWORDS = [
    "ada", "adalah", "agak", "agar", "akan", "aku", "amat", "anda", "antar", "antara",
    "apa", "apabila", "apakah", "apalagi", "atas", "atau", "bagaimana", "bagi", "bahkan",
    "bahwa", "banyak", "baru", "bawah", "beberapa", "begini", "begitu", "belum", "berapa",
    "berbagai", "berikut", "bisa", "boleh", "bolehkah", "buat", "bukan", "cara", "cukup",
    "dalam", "dan", "dapat", "dari", "daripada", "dekat", "demi", "demikian", "dengan",
    "depan", "di", "dia", "diri", "doang", "dong", "dulu", "enggak", "gak", "guna", "hal",
    "hampir", "hanya", "harus", "hingga", "ia", "ialah", "ibarat", "ingin", "ini", "itu",
    "jadi", "jangan", "jauh", "jika", "jikalau", "juga", "jumlah", "justru", "kalau",
    "kali", "kami", "kamu", "kan", "kapan", "karena", "kata", "ke", "kecil", "kemudian",
    "kenapa", "kepada", "ketika", "khusus", "kini", "kita", "kok", "kurang", "lagi",
    "lalu", "lama", "langsung", "lebih", "lewat", "luar", "macam", "maka", "makin",
    "malah", "mana", "masih", "masing", "mau", "melainkan", "melalui", "memang", "mempunyai",
    "menjadi", "menurut", "mereka", "meski", "meskipun", "misal", "misalnya", "mungkin",
    "nah", "namun", "nanti", "nya", "oleh", "orang", "pada", "padahal", "paling", "para",
    "pasti", "per", "pernah", "pula", "pun", "punya", "saat", "saja", "saling", "sama",
    "sampai", "samping", "sana", "sangat", "satu", "saya", "sebab", "sebagai", "sebagaimana",
    "sebagian", "sebelum", "sebenarnya", "sebuah", "secara", "sedang", "sedangkan", "sedikit",
    "segala", "segera", "sehingga", "sejak", "sekali", "sekarang", "sekitar", "selain",
    "selalu", "selama", "seluruh", "semakin", "sementara", "semua", "sendiri", "seorang",
    "seperti", "sering", "serta", "sesuatu", "sesudah", "setelah", "setiap", "siapa",
    "sini", "situ", "suatu", "sudah", "supaya", "tadi", "tahu", "tak", "tanpa", "tapi",
    "telah", "tempat", "tentang", "tentu", "terhadap", "terlalu", "termasuk", "ternyata",
    "tersebut", "terus", "tetap", "tetapi", "tiap", "tidak", "tidakkah", "toh", "turut",
    "untuk", "usah", "waktu", "walau", "walaupun", "ya", "yaitu", "yakni", "yang",
    "bagusnya", "minum", "cocok", "gitu", "dosisnya", "obatnya", "saran", "informasi",
    "ramuan", "tradisional", "berkaitan", "membuat", "bahan", "manfaat",
]

SAFETY_WARNING_TEXT = (
    "Informasi ini bersifat edukatif. Kondisi yang Anda sebutkan memerlukan pertimbangan "
    "tenaga kesehatan. Sistem tidak memberikan diagnosis, resep, atau dosis pengobatan personal. "
    "Sistem tidak memberikan diagnosis/dosis/rekomendasi terapi. Konsultasikan dengan apoteker/dokter."
)

EMERGENCY_KEYWORDS = [
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

SENSITIVE_PATTERNS: list[tuple[str, list[str]]] = [
    (
        "dosis & aturan konsumsi personal",
        [
            "dosis",
            "takaran",
            "berapa kali",
            "berapa gelas",
            "berapa lembar",
            "berapa sendok",
            "berapa mg",
            "berapa ml",
            "berapa gram",
            "aturan pakai",
            "resep obat",
            "cara mengobati",
            "menyembuhkan",
            "berat badan",
        ],
    ),
    (
        "kehamilan, menyusui & bayi/anak kecil",
        [
            "hamil",
            "kehamilan",
            "bumil",
            "janin",
            "kandungan",
            "menyusui",
            "busui",
            "ibu melahirkan",
            "bayi",
            "balita",
            "anak kecil",
        ],
    ),
    (
        "kondisi medis serius / darurat",
        [
            "kanker",
            "tumor",
            "gagal ginjal",
            "penyakit ginjal",
            "cuci darah",
            "penyakit hati",
            "gangguan hati",
            "serangan jantung",
            "stroke",
            "darurat",
            "overdosis",
            "keracunan",
            "pendarahan",
            "perdarahan",
            "botulisme",
            "hepatitis",
            "sulit bernapas",
            "sesak napas",
            "penurunan kesadaran",
            "pingsan",
            "dehidrasi berat",
            "demam berat",
            "demam berkepanjangan",
            "kejang",
        ],
    ),
    (
        "interaksi & kombinasi obat rutin",
        [
            "interaksi obat",
            "kombinasi obat",
            "campur obat",
            "bersamaan dengan obat",
            "obat medis",
            "obat dokter",
            "obat resep",
            "obat rutin",
            "warfarin",
            "aspirin",
            "antidepresan",
            "insulin",
        ],
    ),
]

# Structured Symptom-to-Herb Knowledge Base derived strictly from the 52 Q&A dataset records
SYMPTOM_CLUSTERS: list[dict[str, Any]] = [
    {
        "id": "demam",
        "keywords": ["demam", "panas", "meriang", "antipiretik", "suhu badan", "turun panas", "malaria"],
        "detected_condition": "Indikasi Keluhan: Demam & Panas Tubuh (Antipiretik)",
        "clinical_summary": (
            "Berdasarkan analisis gejala, keluhan mengarah pada kondisi peningkatan suhu tubuh (demam). "
            "Dalam pengobatan tradisional Indonesia (dataset Q&A #14, #19, #22, #44), keluhan ini "
            "ditangani dengan tanaman yang memiliki sifat antipiretik (penurun demam), anti-inflamasi, "
            "dan imunostimulan (peningkat daya tahan tubuh)."
        ),
        "when_to_see_doctor": (
            "Segera periksakan ke dokter apabila suhu tubuh melebihi 39°C, demam berlangsung lebih "
            "dari 3 hari, disertai bintik merah/mimisan (kecurigaan DBD), kejang, atau dialami oleh "
            "bayi dan ibu hamil."
        ),
        "recommendations": [
            {
                "qa_id": 44,
                "nama_herbal": "Brotowali",
                "nama_ilmiah": "Tinospora crispa",
                "slug": "brotowali",
                "senyawa_aktif": "Berberin dan tinokrisposid",
                "khasiat_relevan": (
                    "Antipiretik (menurunkan demam, penggunaan tradisional paling terkenal), "
                    "antimalaria, antidiabetes, dan meningkatkan nafsu makan."
                ),
                "dosis_dan_cara_pakai": (
                    "Takaran Rebusan Tradisional (Q&A #44): Ambil batang brotowali, potong-potong, "
                    "lalu rebus dengan 3 gelas air hingga menyusut tersisa 1 gelas. Saring dan "
                    "diminum 2 kali sehari (pagi dan sore)."
                ),
                "peringatan": (
                    "Air rebusan brotowali memiliki rasa yang sangat pahit. Hentikan pemakaian jika "
                    "muncul gangguan lambung dan jangan gunakan pada ibu hamil tanpa izin dokter."
                ),
                "sumber_dataset": "Dataset Q&A #44 (Brotowali)",
                "relevance_score": 0.96,
            },
            {
                "qa_id": 14,
                "nama_herbal": "Sambiloto",
                "nama_ilmiah": "Andrographis paniculata",
                "slug": "sambiloto",
                "senyawa_aktif": "Andrographolide",
                "khasiat_relevan": (
                    "Antipiretik (penurun demam), imunostimulan (meningkatkan sistem kekebalan tubuh "
                    "melawan infeksi bakteri/virus), dan anti-inflamasi."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian & Dosis (Q&A #14 & #49): Dikonsumsi sebagai seduhan jamu pahitan "
                    "(daun kering diseduh air panas) 1-2 kali sehari, atau menggunakan kapsul ekstrak "
                    "sambiloto terstandar (Fitofarmaka/OHT berizin BPOM) sesuai aturan pakai kemasan."
                ),
                "peringatan": (
                    "Dijuluki 'raja pahit'. Hindari konsumsi dosis tinggi jangka panjang dan tidak "
                    "dianjurkan untuk ibu hamil/menyusui."
                ),
                "sumber_dataset": "Dataset Q&A #14 (Sambiloto)",
                "relevance_score": 0.93,
            },
            {
                "qa_id": 22,
                "nama_herbal": "Sereh (Serai)",
                "nama_ilmiah": "Cymbopogon citratus",
                "slug": "sereh",
                "senyawa_aktif": "Sitral, geraniol, dan mircena",
                "khasiat_relevan": (
                    "Antipiretik tradisional (membantu menurunkan demam melalui peluruhan keringat), "
                    "meredakan sakit kepala dan nyeri otot saat meriang."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian & Dosis (Q&A #22): Geprek 1-2 batang sereh segar, rebus dalam "
                    "1-2 gelas air selama 10 menit, dan diminum hangat sebagai teh sereh 1-2 kali sehari."
                ),
                "peringatan": "Aman sebagai minuman hangat harian; tambahkan madu bila tidak ada pantangan gula.",
                "sumber_dataset": "Dataset Q&A #22 (Sereh)",
                "relevance_score": 0.87,
            },
        ],
    },
    {
        "id": "dbd_trombosit",
        "keywords": ["dbd", "demam berdarah", "trombosit", "nyamuk aedes"],
        "detected_condition": "Indikasi Keluhan: Demam Berdarah (DBD) & Penurunan Trombosit",
        "clinical_summary": (
            "Keluhan berkaitan dengan pemulihan kadar trombosit pada demam berdarah (DBD). Dalam "
            "dataset (Q&A #23 & #33), ekstrak daun pepaya dan rebusan daun jambu biji digunakan "
            "secara luas sebagai terapi pendamping (komplementer) perawatan medis rumah sakit."
        ),
        "when_to_see_doctor": (
            "PERINGATAN DARURAT: Demam berdarah (DBD) wajib mendapatkan pemantauan cairan infus dan "
            "pemeriksaan darah rutin di rumah sakit/dokter. Herbal hanya berfungsi sebagai pendamping."
        ),
        "recommendations": [
            {
                "qa_id": 33,
                "nama_herbal": "Daun Jambu Biji",
                "nama_ilmiah": "Psidium guajava",
                "slug": "daun-jambu-biji",
                "senyawa_aktif": "Tanin, flavonoid, dan quercetin",
                "khasiat_relevan": (
                    "Membantu meningkatkan jumlah trombosit sebagai pendamping pengobatan DBD serta "
                    "kaya antioksidan quercetin."
                ),
                "dosis_dan_cara_pakai": (
                    "Takaran Rebusan Tradisional (Q&A #33): Ambil 5-7 lembar daun jambu biji muda, "
                    "cuci bersih, rebus dengan 2 gelas air hingga tersisa 1 gelas. Diminum 2 kali sehari."
                ),
                "peringatan": "Jangan menghentikan terapi cairan/obat dari dokter selama masa perawatan DBD.",
                "sumber_dataset": "Dataset Q&A #33 (Daun Jambu Biji)",
                "relevance_score": 0.96,
            },
            {
                "qa_id": 23,
                "nama_herbal": "Daun Pepaya",
                "nama_ilmiah": "Carica papaya",
                "slug": "daun-pepaya",
                "senyawa_aktif": "Enzim papain, alkaloid karpain, dan flavonoid",
                "khasiat_relevan": (
                    "Pendamping pengobatan demam berdarah (DBD) untuk membantu menaikkan trombosit "
                    "dan meningkatkan nafsu makan."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian (Q&A #23): Daun pepaya segar dicuci bersih, ditumbuk/diblender "
                    "dengan sedikit air matang lalu diperas untuk diambil sarinya (atau dikonsumsi "
                    "sebagai ekstrak kapsul daun pepaya berizin BPOM)."
                ),
                "peringatan": "Rasanya sangat pahit; tidak dianjurkan untuk ibu hamil karena kandungan enzim papain.",
                "sumber_dataset": "Dataset Q&A #23 (Daun Pepaya)",
                "relevance_score": 0.94,
            },
        ],
    },
    {
        "id": "batuk_pernapasan",
        "keywords": [
            "batuk", "dahak", "berdahak", "tenggorokan", "radang tenggorokan",
            "pilek", "flu", "hidung tersumbat", "sesak", "ekspektoran",
        ],
        "detected_condition": "Indikasi Keluhan: Batuk, Radang Tenggorokan & Hidung Tersumbat",
        "clinical_summary": (
            "Keluhan mengarah pada iritasi saluran pernapasan atas (batuk/radang tenggorokan/hidung "
            "tersumbat). Dataset mencatat penggunaan ekspektoran alami (peluruh dahak), antiseptik "
            "tenggorokan, dan dekongestan uap herbal (Q&A #8, #9, #12, #36, #48)."
        ),
        "when_to_see_doctor": (
            "Konsultasikan ke dokter jika batuk berlangsung lebih dari 2 minggu, disertai sesak "
            "napas, dahak berdarah, atau demam tinggi."
        ),
        "recommendations": [
            {
                "qa_id": 8,
                "nama_herbal": "Kencur (Jamu Beras Kencur)",
                "nama_ilmiah": "Kaempferia galanga",
                "slug": "kencur",
                "senyawa_aktif": "Etil p-metoksisinamat dan etil sinamat",
                "khasiat_relevan": (
                    "Mengobati batuk sebagai ekspektoran alami (pengencer dahak), meredakan radang "
                    "tenggorokan, dan menghangatkan tubuh."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian & Takaran (Q&A #8 & #9): Parut/blender rimpang kencur segar "
                    "bersama beras yang telah direndam, saring sarinya, tambahkan gula merah dan "
                    "sedikit asam jawa dengan air hangat. Diminum 1-2 gelas sehari."
                ),
                "peringatan": "Aman untuk dewasa dan anak-anak dalam takaran minuman jamu wajar.",
                "sumber_dataset": "Dataset Q&A #8 & #9 (Kencur & Beras Kencur)",
                "relevance_score": 0.95,
            },
            {
                "qa_id": 36,
                "nama_herbal": "Madu Alami",
                "nama_ilmiah": None,
                "slug": None,
                "senyawa_aktif": "Fruktosa, glukosa, enzim, vitamin, mineral, antioksidan",
                "khasiat_relevan": (
                    "Meredakan batuk (efektif sebagai pereda batuk malam hari pada dewasa dan anak "
                    "di atas usia 1 tahun) serta bersifat antibakteri."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian & Takaran (Q&A #36): Diminum 1-2 sendok teh langsung atau "
                    "dicampurkan ke dalam seduhan air hangat / wedang jahe / perasan jeruk."
                ),
                "peringatan": (
                    "PERINGATAN KERAS (Q&A #36): Madu TIDAK BOLEH diberikan kepada bayi di bawah "
                    "usia 1 tahun karena risiko keracunan botulisme."
                ),
                "sumber_dataset": "Dataset Q&A #36 (Madu)",
                "relevance_score": 0.91,
            },
            {
                "qa_id": 12,
                "nama_herbal": "Kayu Putih & Daun Mint",
                "nama_ilmiah": "Melaleuca cajuputi / Mentha piperita",
                "slug": "kayu-putih",
                "senyawa_aktif": "Cajuput oil (Sineol) dan Menthol",
                "khasiat_relevan": (
                    "Dekongestan alami untuk melegakan hidung tersumbat dan melapangkan saluran napas."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Pemakaian (Q&A #12 & #48): Hirup uap air hangat yang ditetesi minyak kayu "
                    "putih atau seduhan daun mint; oleskan minyak kayu putih pada dada, leher, dan punggung."
                ),
                "peringatan": "Minyak kayu putih hanya untuk pemakaian luar/inhalasi uap, jangan diminum.",
                "sumber_dataset": "Dataset Q&A #12 & #48",
                "relevance_score": 0.86,
            },
        ],
    },
    {
        "id": "diare_pencernaan",
        "keywords": ["diare", "mencret", "buang air besar", "bab cair", "sakit perut", "antidiare", "sembelit"],
        "detected_condition": "Indikasi Keluhan: Diare & Gangguan Saluran Pencernaan",
        "clinical_summary": (
            "Keluhan mengarah pada gangguan motilitas usus dan diare. Berdasarkan dataset (Q&A #33, "
            "#8, #28), daun jambu biji merupakan herbal antidiare utama yang telah didukung "
            "penelitian ilmiah berkat kandungan tanin dan antibakterinya."
        ),
        "when_to_see_doctor": (
            "Waspadai tanda dehidrasi (lemas, bibir kering, jarang buang air kecil). Segera ke "
            "dokter bila diare disertai lendir/darah, demam tinggi, atau terjadi pada bayi/balita."
        ),
        "recommendations": [
            {
                "qa_id": 33,
                "nama_herbal": "Daun Jambu Biji",
                "nama_ilmiah": "Psidium guajava",
                "slug": "daun-jambu-biji",
                "senyawa_aktif": "Tanin, flavonoid, dan quercetin",
                "khasiat_relevan": (
                    "Antidiare alami yang efektif memadatkan tinja dan menghambat pertumbuhan "
                    "bakteri penyebab diare."
                ),
                "dosis_dan_cara_pakai": (
                    "Takaran Rebusan Tradisional (Q&A #33): Ambil 5-7 lembar daun jambu biji muda, "
                    "rebus dengan 2 gelas air hingga tersisa 1 gelas, saring, dan diminum 2 kali sehari. "
                    "Tetap konsumsi cairan elektrolit/oralit untuk mencegah dehidrasi."
                ),
                "peringatan": "Jika diare tidak membaik dalam 2 hari, segera periksakan ke fasilitas kesehatan.",
                "sumber_dataset": "Dataset Q&A #33 (Daun Jambu Biji)",
                "relevance_score": 0.98,
            },
            {
                "qa_id": 8,
                "nama_herbal": "Kencur",
                "nama_ilmiah": "Kaempferia galanga",
                "slug": "kencur",
                "senyawa_aktif": "Etil p-metoksisinamat dan etil sinamat",
                "khasiat_relevan": "Memiliki efek antidiare ringan serta meredakan perut kembung dan mulas.",
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian (Q&A #8): Rimpang kencur segar diparut, diseduh dengan air "
                    "matang hangat dan disaring, diminum 1-2 kali sehari."
                ),
                "peringatan": "Pastikan rimpang dicuci bersih dan dikupas sebelum diolah.",
                "sumber_dataset": "Dataset Q&A #8 (Kencur)",
                "relevance_score": 0.85,
            },
        ],
    },
    {
        "id": "masuk_angin_mual",
        "keywords": [
            "masuk angin", "mual", "muntah", "kembung", "mabuk perjalanan",
            "perut begah", "sendawa", "morning sickness",
        ],
        "detected_condition": "Indikasi Keluhan: Masuk Angin, Perut Kembung & Mual",
        "clinical_summary": (
            "Keluhan mengarah pada dispepsia fungsional ringan (kembung/mual/masuk angin). Dataset "
            "(Q&A #5, #12, #24, #48) merekomendasikan rimpang penghangat karminatif (peluruh gas) "
            "dan antispasmodik saluran cerna."
        ),
        "when_to_see_doctor": (
            "Periksakan ke dokter apabila mual/muntah menyebabkan tidak bisa makan/minum sama "
            "sekali, disertai nyeri ulu hati hebat, atau terjadi muntah berdarah."
        ),
        "recommendations": [
            {
                "qa_id": 5,
                "nama_herbal": "Jahe",
                "nama_ilmiah": "Zingiber officinale",
                "slug": "jahe",
                "senyawa_aktif": "Gingerol dan shogaol",
                "khasiat_relevan": (
                    "Anti-mual (efektif untuk mabuk perjalanan dan mual), menghangatkan tubuh, "
                    "meningkatkan sirkulasi darah, serta meredakan perut kembung dan masuk angin."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian & Takaran (Q&A #5): Bakar atau geprek 1 ruas rimpang jahe (sekitar "
                    "2-3 cm), seduh/rebus dalam 1 gelas air hangat (wedang jahe), diminum 1-2 kali sehari."
                ),
                "peringatan": (
                    "Peringatan Interaksi (Q&A #39): Jahe dosis tinggi berinteraksi dengan obat "
                    "pengencer darah (warfarin). Ibu hamil wajib berkonsultasi dengan dokter sebelum konsumsi."
                ),
                "sumber_dataset": "Dataset Q&A #5 & #39 (Jahe)",
                "relevance_score": 0.97,
            },
            {
                "qa_id": 48,
                "nama_herbal": "Daun Mint",
                "nama_ilmiah": "Mentha piperita",
                "slug": "daun-mint",
                "senyawa_aktif": "Menthol",
                "khasiat_relevan": (
                    "Merelaksasi otot saluran cerna, mengatasi perut kembung, mual perjalanan, "
                    "dan sindrom iritasi usus (IBS)."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian (Q&A #48): Seduh 5-10 lembar daun mint segar dengan 1 cangkir "
                    "air panas selama 5-10 menit, diminum hangat setelah makan."
                ),
                "peringatan": "Gunakan secukupnya pada penderita asam lambung (GERD) karena menthol merelaksasi sfingter esofagus.",
                "sumber_dataset": "Dataset Q&A #48 (Daun Mint)",
                "relevance_score": 0.90,
            },
            {
                "qa_id": 12,
                "nama_herbal": "Minyak Kayu Putih",
                "nama_ilmiah": "Melaleuca cajuputi",
                "slug": "kayu-putih",
                "senyawa_aktif": "Cajuput oil (Sineol)",
                "khasiat_relevan": "Menghangatkan tubuh serta meredakan perut kembung dan masuk angin dari luar.",
                "dosis_dan_cara_pakai": (
                    "Aturan Pakai Luar (Q&A #12): Oleskan minyak kayu putih secukupnya pada area "
                    "perut, dada, dan punggung."
                ),
                "peringatan": "Hanya untuk pemakaian luar pada kulit yang tidak luka.",
                "sumber_dataset": "Dataset Q&A #12 (Minyak Kayu Putih)",
                "relevance_score": 0.86,
            },
        ],
    },
    {
        "id": "hipertensi_kolesterol",
        "keywords": [
            "darah tinggi", "hipertensi", "tekanan darah", "tensi", "tensi tinggi",
            "kolesterol", "ldl", "pembuluh darah",
        ],
        "detected_condition": "Indikasi Keluhan: Tekanan Darah Tinggi (Hipertensi) & Kolesterol",
        "clinical_summary": (
            "Keluhan berkaitan dengan pengendalian tekanan darah dan profil lipid/kolesterol. "
            "Dataset (Q&A #3, #16, #17, #18) mencatat tanaman dengan efek vasodilator dan diuretik "
            "alami, termasuk seledri yang telah mencapai tingkat Fitofarmaka di Indonesia."
        ),
        "when_to_see_doctor": (
            "Jangan menghentikan obat antihipertensi dokter secara sepihak. Segera ke IGD bila "
            "tekanan darah >= 180/120 mmHg atau disertai nyeri dada, pandangan kabur, dan sakit kepala hebat."
        ),
        "recommendations": [
            {
                "qa_id": 17,
                "nama_herbal": "Seledri (Ekstrak / Fitofarmaka)",
                "nama_ilmiah": "Apium graveolens",
                "slug": "seledri",
                "senyawa_aktif": "Apigenin, phthalide, dan flavonoid",
                "khasiat_relevan": (
                    "Antihipertensi (membantu menurunkan tekanan darah), diuretik pelancar urin, "
                    "dan membantu menurunkan kadar kolesterol darah."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian & Dosis (Q&A #3 & #17): Dikonsumsi sebagai jus seledri segar "
                    "atau lalapan harian; untuk dosis terukur, gunakan sediaan Fitofarmaka ekstrak "
                    "seledri terstandar (contoh: Tensigard) sesuai dosis pada kemasan berizin BPOM."
                ),
                "peringatan": "Pantau tekanan darah secara berkala agar tidak terjadi hipotensi (tekanan darah terlalu rendah).",
                "sumber_dataset": "Dataset Q&A #3 & #17 (Seledri)",
                "relevance_score": 0.97,
            },
            {
                "qa_id": 16,
                "nama_herbal": "Kumis Kucing",
                "nama_ilmiah": "Orthosiphon aristatus",
                "slug": "kumis-kucing",
                "senyawa_aktif": "Sinensetin dan rosmarinic acid",
                "khasiat_relevan": (
                    "Diuretik alami dan antihipertensi yang membantu menurunkan tekanan darah melalui "
                    "peningkatan ekskresi cairan urin."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian (Q&A #16): Seduh 1 genggam kecil daun kumis kucing kering "
                    "dengan 1 gelas air mendidih sebagai teh herbal, diminum 1-2 kali sehari."
                ),
                "peringatan": "Pastikan asupan air putih cukup; hati-hati pada penderita gagal ginjal atau pembengkakan jantung.",
                "sumber_dataset": "Dataset Q&A #16 (Kumis Kucing)",
                "relevance_score": 0.91,
            },
            {
                "qa_id": 18,
                "nama_herbal": "Mengkudu (Pace)",
                "nama_ilmiah": "Morinda citrifolia",
                "slug": "mengkudu",
                "senyawa_aktif": "Scopoletin, xeronine, dan damnacanthal",
                "khasiat_relevan": "Senyawa scopoletin membantu melebarkan pembuluh darah dan menurunkan tekanan darah.",
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian (Q&A #18): Dikonsumsi sebagai jus buah mengkudu matang yang "
                    "disaring atau dalam bentuk kapsul ekstrak mengkudu berizin BPOM."
                ),
                "peringatan": "Buah mengkudu tinggi kalium; penderita gangguan ginjal wajib berkonsultasi ke dokter.",
                "sumber_dataset": "Dataset Q&A #18 (Mengkudu)",
                "relevance_score": 0.88,
            },
        ],
    },
    {
        "id": "diabetes_gula_darah",
        "keywords": ["diabetes", "gula darah", "kencing manis", "insulin", "antidiabetes"],
        "detected_condition": "Indikasi Keluhan: Gula Darah Tinggi / Diabetes Melitus",
        "clinical_summary": (
            "Keluhan berkaitan dengan regulasi glukosa darah dan sensitivitas insulin. Dataset "
            "(Q&A #26, #44, #20) mencatat kayu manis, brotowali, dan daun sirsak sebagai herbal "
            "pendukung pengontrol gula darah."
        ),
        "when_to_see_doctor": (
            "Peringatan Interaksi (Q&A #39): Menggabungkan herbal penurun gula darah dosis tinggi "
            "dengan obat diabetes dokter/insulin dapat memicu hipoglikemia (gula darah anjlok). "
            "Konsultasikan dengan dokter."
        ),
        "recommendations": [
            {
                "qa_id": 26,
                "nama_herbal": "Kayu Manis",
                "nama_ilmiah": "Cinnamomum verum / Cinnamomum burmannii",
                "slug": "kayu-manis",
                "senyawa_aktif": "Sinamaldehid, asam sinamat, dan polifenol",
                "khasiat_relevan": (
                    "Membantu mengontrol kadar gula darah dengan meningkatkan sensitivitas insulin "
                    "(bermanfaat untuk diabetes tipe 2) serta menurunkan kolesterol LDL."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian (Q&A #26): Rebus 1-2 batang kecil kulit kayu manis dalam 1 "
                    "gelas air selama 10 menit sebagai teh kayu manis tanpa tambahan gula pasir, "
                    "diminum 1 kali sehari."
                ),
                "peringatan": "Gunakan dalam takaran wajar; konsumsi cassia dosis berlebihan jangka panjang berisiko bagi fungsi hati.",
                "sumber_dataset": "Dataset Q&A #26 (Kayu Manis)",
                "relevance_score": 0.96,
            },
            {
                "qa_id": 44,
                "nama_herbal": "Brotowali",
                "nama_ilmiah": "Tinospora crispa",
                "slug": "brotowali",
                "senyawa_aktif": "Berberin dan tinokrisposid",
                "khasiat_relevan": "Antidiabetes tradisional untuk membantu menurunkan kadar gula darah.",
                "dosis_dan_cara_pakai": (
                    "Takaran Rebusan Tradisional (Q&A #44): Batang brotowali dipotong, direbus "
                    "dengan 3 gelas air hingga tersisa 1 gelas, diminum 2 kali sehari."
                ),
                "peringatan": "Pantau kadar gula darah secara rutin bila sedang menggunakan obat antidiabetes resep.",
                "sumber_dataset": "Dataset Q&A #44 (Brotowali)",
                "relevance_score": 0.92,
            },
            {
                "qa_id": 20,
                "nama_herbal": "Daun Sirsak",
                "nama_ilmiah": "Annona muricata",
                "slug": "daun-sirsak",
                "senyawa_aktif": "Acetogenins dan antioksidan",
                "khasiat_relevan": "Membantu menurunkan kadar gula darah dan tekanan darah.",
                "dosis_dan_cara_pakai": (
                    "Takaran Rebusan Tradisional (Q&A #20): Rebus 10-15 lembar daun sirsak kering "
                    "dengan air hingga mendidih sebagai teh herbal."
                ),
                "peringatan": "Jangan menggantikan pengobatan medis konvensional dengan rebusan daun sirsak semata.",
                "sumber_dataset": "Dataset Q&A #20 (Daun Sirsak)",
                "relevance_score": 0.86,
            },
        ],
    },
    {
        "id": "nyeri_haid_wanita",
        "keywords": ["nyeri haid", "haid", "menstruasi", "datang bulan", "kunyit asam", "kunir asam", "kewanitaan"],
        "detected_condition": "Indikasi Keluhan: Nyeri Haid (Dismenore) & Siklus Menstruasi",
        "clinical_summary": (
            "Keluhan berkaitan dengan kram/nyeri menstruasi dan kesehatan kewanitaan. Dataset "
            "(Q&A #6, #30, #51) mencatat resep lengkap Jamu Kunyit Asam yang memiliki efek "
            "anti-inflamasi dan analgesik ringan alami."
        ),
        "when_to_see_doctor": (
            "Periksakan ke dokter kandungan bila nyeri haid sangat hebat hingga pingsan, atau "
            "disertai perdarahan berlebih di luar siklus normal."
        ),
        "recommendations": [
            {
                "qa_id": 30,
                "nama_herbal": "Kunyit & Asam Jawa (Jamu Kunyit Asam)",
                "nama_ilmiah": "Curcuma longa",
                "slug": "kunyit",
                "senyawa_aktif": "Kurkuminoid (kurkumin) dan ekstrak asam jawa",
                "khasiat_relevan": (
                    "Mengurangi nyeri haid (anti-inflamasi kuat), membantu melancarkan haid, "
                    "antioksidan, dan menjaga daya tahan tubuh."
                ),
                "dosis_dan_cara_pakai": (
                    "Takaran Resep & Dosis Tradisional (Q&A #30): Parut/blender 200g kunyit segar "
                    "dan peras sarinya. Rebus 1 liter air bersama sari kunyit, 100g asam jawa, "
                    "150g gula merah/aren, dan sedikit garam hingga mendidih lalu saring. "
                    "Dosis konsumsi: Diminum 1 gelas per hari."
                ),
                "peringatan": "Kunyit dosis pekat sebaiknya dihindari oleh ibu hamil dan penderita batu empedu.",
                "sumber_dataset": "Dataset Q&A #6 & #30 (Kunyit & Jamu Kunyit Asam)",
                "relevance_score": 0.98,
            },
        ],
    },
    {
        "id": "sakit_gigi_mulut_mimisan",
        "keywords": ["sakit gigi", "gigi berlubang", "bau mulut", "gusi", "sariawan", "mimisan"],
        "detected_condition": "Indikasi Keluhan: Sakit Gigi, Kebersihan Mulut & Mimisan",
        "clinical_summary": (
            "Keluhan berkaitan dengan nyeri gigi/infeksi bakteri rongga mulut atau mimisan. "
            "Dataset (Q&A #10 & #27) mencatat eugenol pada cengkeh sebagai analgesik gigi yang "
            "terbukti ilmiah, serta chavicol pada daun sirih sebagai antiseptik kuat."
        ),
        "when_to_see_doctor": (
            "Periksakan ke dokter gigi bila terdapat bengkak gusi/abses bernanah atau demam."
        ),
        "recommendations": [
            {
                "qa_id": 27,
                "nama_herbal": "Cengkeh (Minyak Cengkeh)",
                "nama_ilmiah": "Syzygium aromaticum",
                "slug": "cengkeh",
                "senyawa_aktif": "Eugenol",
                "khasiat_relevan": (
                    "Analgesik lokal (meredakan nyeri sakit gigi yang telah terbukti ilmiah) dan "
                    "antiseptik pembunuh bakteri rongga mulut."
                ),
                "dosis_dan_cara_pakai": (
                    "Aturan Pakai (Q&A #27): Teteskan 1-2 tetes minyak cengkeh pada bulatan kapas "
                    "kecil yang bersih, lalu tempelkan langsung pada bagian gigi yang sakit/berlubang."
                ),
                "peringatan": "Jangan menelan minyak cengkeh murni dan hindari mengenai jaringan gusi sehat secara berlebihan.",
                "sumber_dataset": "Dataset Q&A #27 (Cengkeh)",
                "relevance_score": 0.97,
            },
            {
                "qa_id": 10,
                "nama_herbal": "Daun Sirih",
                "nama_ilmiah": "Piper betle",
                "slug": "daun-sirih",
                "senyawa_aktif": "Chavicol, eugenol, dan kavikol",
                "khasiat_relevan": (
                    "Antiseptik kuat penghambat bakteri penyebab bau mulut dan gigi berlubang, "
                    "serta membantu menghentikan mimisan."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Pemakaian (Q&A #10): Rebus 3-5 lembar daun sirih bersih dengan 1-2 gelas "
                    "air, gunakan air rebusan hangat untuk berkumur (jangan ditelan). Untuk mimisan: "
                    "cuci bersih 1 lembar daun sirih, gulung, dan masukkan perlahan ke lubang hidung."
                ),
                "peringatan": "Gunakan daun yang telah dicuci bersih dengan air mengalir.",
                "sumber_dataset": "Dataset Q&A #10 (Daun Sirih)",
                "relevance_score": 0.93,
            },
        ],
    },
    {
        "id": "luka_kulit_jamur",
        "keywords": ["luka", "luka bakar", "panu", "kurap", "jamur kulit", "gatal", "kulit", "pasca operasi"],
        "detected_condition": "Indikasi Keluhan: Luka Kulit, Luka Bakar Ringan & Infeksi Jamur (Panu/Kurap)",
        "clinical_summary": (
            "Keluhan berkaitan dengan regenerasi jaringan kulit atau infeksi jamur permukaan. "
            "Dataset (Q&A #11, #21, #41, #43) mencatat daun binahong dan pegagan untuk pemulihan "
            "luka, lidah buaya untuk luka bakar ringan, serta lengkuas untuk jamur kulit (panu/kurap)."
        ),
        "when_to_see_doctor": (
            "Luka dalam, luka bakar luas/melepuh berat, atau luka pada penderita diabetes wajib "
            "ditangani secara medis steril oleh tenaga kesehatan."
        ),
        "recommendations": [
            {
                "qa_id": 43,
                "nama_herbal": "Daun Binahong",
                "nama_ilmiah": "Anredera cordifolia",
                "slug": "daun-binahong",
                "senyawa_aktif": "Saponin, flavonoid, dan polifenol",
                "khasiat_relevan": (
                    "Mempercepat penyembuhan luka dan regenerasi jaringan pasca operasi, anti-inflamasi, "
                    "serta menghambat bakteri pada luka."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Pemakaian (Q&A #43): Untuk luka luar ringan, tumbuk halus beberapa lembar "
                    "daun binahong yang telah dicuci bersih lalu tempelkan pada area luka; atau "
                    "rebus 5-7 lembar daun binahong dalam 2 gelas air hingga tersisa 1 gelas untuk diminum."
                ),
                "peringatan": "Jangan menempelkan tumbukan daun mentah pada luka terbuka yang dalam/pasca jahitan operasi karena risiko infeksi.",
                "sumber_dataset": "Dataset Q&A #43 (Daun Binahong)",
                "relevance_score": 0.95,
            },
            {
                "qa_id": 11,
                "nama_herbal": "Lidah Buaya",
                "nama_ilmiah": "Aloe vera",
                "slug": "lidah-buaya",
                "senyawa_aktif": "Polisakarida gel, vitamin, mineral, dan enzim",
                "khasiat_relevan": "Mempercepat regenerasi kulit pada luka bakar ringan dan mengurangi iritasi kulit.",
                "dosis_dan_cara_pakai": (
                    "Aturan Pakai (Q&A #11): Belah daun lidah buaya segar, cuci getah kuningnya, "
                    "ambil gel bening bagian dalam, dan oleskan perlahan pada luka bakar derajat ringan."
                ),
                "peringatan": "Bilas bersih getah kuning (aloin) pada kulit daun karena dapat memicu gatal/iritasi.",
                "sumber_dataset": "Dataset Q&A #11 (Lidah Buaya)",
                "relevance_score": 0.92,
            },
            {
                "qa_id": 21,
                "nama_herbal": "Lengkuas (Laos)",
                "nama_ilmiah": "Alpinia galanga",
                "slug": "lengkuas",
                "senyawa_aktif": "Asetoksikavikol asetat (ACA) dan galangin",
                "khasiat_relevan": "Antijamur alami yang efektif melawan jamur kulit seperti panu dan kurap.",
                "dosis_dan_cara_pakai": (
                    "Aturan Pakai Luar (Q&A #21): Ambil rimpang lengkuas segar, belah menjadi dua, "
                    "lalu gosokkan/oleskan langsung bagian dalamnya pada area kulit yang terkena panu/kurap."
                ),
                "peringatan": "Hentikan pemakaian bila kulit mengalami iritasi atau kemerahan berlebih.",
                "sumber_dataset": "Dataset Q&A #21 (Lengkuas)",
                "relevance_score": 0.90,
            },
        ],
    },
    {
        "id": "nyeri_sendi_asam_urat_ginjal",
        "keywords": [
            "asam urat", "nyeri sendi", "pegal linu", "nyeri otot", "rematik",
            "batu ginjal", "anyang-anyangan", "buang air kecil", "diuretik",
        ],
        "detected_condition": "Indikasi Keluhan: Nyeri Sendi, Pegal Linu, Asam Urat & Batu Ginjal",
        "clinical_summary": (
            "Keluhan berkaitan dengan peradangan sendi/otot atau penumpukan kristal asam urat dan "
            "batu saluran kemih. Dataset (Q&A #5, #6, #16, #25, #31) merekomendasikan herbal "
            "diuretik peluruh urin serta anti-inflamasi."
        ),
        "when_to_see_doctor": (
            "Segera ke dokter bila nyeri pinggang sangat tajam disertai kencing berdarah, demam, "
            "atau tidak bisa buang air kecil."
        ),
        "recommendations": [
            {
                "qa_id": 16,
                "nama_herbal": "Kumis Kucing",
                "nama_ilmiah": "Orthosiphon aristatus",
                "slug": "kumis-kucing",
                "senyawa_aktif": "Sinensetin dan rosmarinic acid",
                "khasiat_relevan": (
                    "Diuretik alami untuk melancarkan buang air kecil, membantu mengeluarkan batu "
                    "ginjal ukuran kecil, serta membantu pembuangan asam urat melalui urin."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian (Q&A #16): Seduh daun kumis kucing kering dengan 1 gelas air "
                    "panas sebagai teh herbal, diminum 1-2 kali sehari disertai minum air putih yang cukup."
                ),
                "peringatan": "Hindari penggunaan berlebih pada penderita gangguan fungsi ginjal berat atau gagal jantung.",
                "sumber_dataset": "Dataset Q&A #16 (Kumis Kucing)",
                "relevance_score": 0.96,
            },
            {
                "qa_id": 6,
                "nama_herbal": "Kunyit & Jahe",
                "nama_ilmiah": "Curcuma longa / Zingiber officinale",
                "slug": "kunyit",
                "senyawa_aktif": "Kurkumin, gingerol, dan shogaol",
                "khasiat_relevan": "Anti-inflamasi kuat untuk mengurangi pembengkakan dan nyeri sendi serta otot.",
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian (Q&A #5 & #6): Rebus irisan rimpang kunyit dan jahe segar dalam "
                    "1-2 gelas air hingga mendidih, diminum hangat 1 kali sehari."
                ),
                "peringatan": "Waspadai produk jamu pegal linu ilegal tanpa nomor BPOM yang sering dicampur BKO fenilbutazon/deksametason (Q&A #46).",
                "sumber_dataset": "Dataset Q&A #5, #6 & #46",
                "relevance_score": 0.91,
            },
        ],
    },
    {
        "id": "imunitas_nafsu_makan_hati",
        "keywords": [
            "daya tahan tubuh", "imun", "imunitas", "nafsu makan", "susah makan",
            "hati", "liver", "hepatitis", "stamina", "lemas", "cacingan",
        ],
        "detected_condition": "Indikasi Keluhan: Penurunan Daya Tahan Tubuh, Nafsu Makan & Fungsi Hati",
        "clinical_summary": (
            "Keluhan berkaitan dengan pemeliharaan sistem imun (imunomodulator), nafsu makan, dan "
            "perlindungan organ hati (hepatoprotektor). Dataset (Q&A #7, #9, #15, #51) mencatat "
            "temulawak dan meniran sebagai herbal unggulan Indonesia."
        ),
        "when_to_see_doctor": (
            "Periksakan ke dokter apabila penurunan berat badan terjadi drastis atau disertai mata "
            "dan kulit menguning (ikterus/gangguan hati)."
        ),
        "recommendations": [
            {
                "qa_id": 7,
                "nama_herbal": "Temulawak",
                "nama_ilmiah": "Curcuma xanthorrhiza",
                "slug": "temulawak",
                "senyawa_aktif": "Xanthorrhizol dan kurkuminoid",
                "khasiat_relevan": (
                    "Hepatoprotektor (melindungi dan memelihara fungsi hati), meningkatkan nafsu "
                    "makan (terutama pada anak), anti-inflamasi, dan mengurangi perut kembung."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian & Takaran (Q&A #7): Iris tipis 1 rimpang temulawak segar, "
                    "rebus dengan 2 gelas air hingga tersisa 1 gelas (dapat ditambah sedikit gula "
                    "aren/madu), diminum 1 kali sehari; atau gunakan suplemen ekstrak temulawak berizin BPOM."
                ),
                "peringatan": "Tercatat dalam rujukan BPOM-07 (Registrasi OBA Bentuk Tunggal) dan BPOM-09.",
                "sumber_dataset": "Dataset Q&A #7 (Temulawak) & BPOM-07",
                "relevance_score": 0.97,
            },
            {
                "qa_id": 15,
                "nama_herbal": "Meniran (Fitofarmaka Imunomodulator)",
                "nama_ilmiah": "Phyllanthus niruri",
                "slug": "meniran",
                "senyawa_aktif": "Filantin dan hipofilantin",
                "khasiat_relevan": (
                    "Imunomodulator (mengatur dan meningkatkan sistem imun tubuh yang telah melalui "
                    "uji klinis lengkap), hepatoprotektif, dan antivirus."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Dosis (Q&A #3 & #15): Gunakan produk Fitofarmaka ekstrak meniran "
                    "terstandar (contoh: Stimuno) sesuai dosis pada kemasan resmi berizin BPOM."
                ),
                "peringatan": "Penggunaan imunostimulan pada penderita penyakit autoimun harus dikonsultasikan dengan dokter.",
                "sumber_dataset": "Dataset Q&A #3 & #15 (Meniran)",
                "relevance_score": 0.94,
            },
        ],
    },
    {
        "id": "tidur_stres_kognitif",
        "keywords": ["susah tidur", "insomnia", "stres", "cemas", "gelisah", "daya ingat", "konsentrasi"],
        "detected_condition": "Indikasi Keluhan: Gangguan Tidur (Insomnia), Stres & Konsentrasi",
        "clinical_summary": (
            "Keluhan berkaitan dengan ketegangan saraf, sulit tidur, atau penurunan fokus. Dataset "
            "(Q&A #22, #28, #41) mencatat pegagan untuk fungsi kognitif & anti-kecemasan, sereh "
            "untuk relaksasi, dan pala sebagai sedatif ringan."
        ),
        "when_to_see_doctor": (
            "Konsultasikan ke tenaga profesional bila gangguan tidur berlangsung kronis dan "
            "mengganggu aktivitas harian."
        ),
        "recommendations": [
            {
                "qa_id": 41,
                "nama_herbal": "Pegagan (Daun Kaki Kuda)",
                "nama_ilmiah": "Centella asiatica",
                "slug": "pegagan",
                "senyawa_aktif": "Triterpenoid saponin (asiatikosida dan madekassosida)",
                "khasiat_relevan": (
                    "Meningkatkan fungsi kognitif (daya ingat dan konsentrasi), memberikan efek "
                    "anti-kecemasan yang menenangkan tanpa menyebabkan kantuk berlebih, dan "
                    "melancarkan peredaran darah."
                ),
                "dosis_dan_cara_pakai": (
                    "Saran Penyajian (Q&A #41): Dikonsumsi segar sebagai lalapan bersih atau "
                    "diseduh hangat dari daun pegagan kering 1 kali sehari."
                ),
                "peringatan": "Hindari penggunaan berlebihan dalam jangka panjang tanpa jeda.",
                "sumber_dataset": "Dataset Q&A #41 (Pegagan)",
                "relevance_score": 0.94,
            },
            {
                "qa_id": 28,
                "nama_herbal": "Pala",
                "nama_ilmiah": "Myristica fragrans",
                "slug": "pala",
                "senyawa_aktif": "Miristisin dan elemicin",
                "khasiat_relevan": "Memberikan efek sedatif ringan untuk membantu tidur dan menghangatkan tubuh.",
                "dosis_dan_cara_pakai": (
                    "Takaran Aman (Q&A #28): Tambahkan sejumput kecil (ujung sendok teh) bubuk biji "
                    "pala ke dalam segelas air hangat atau susu hangat sebelum tidur."
                ),
                "peringatan": (
                    "PERINGATAN DOSIS (Q&A #28): Konsumsi pala dalam jumlah besar (lebih dari 1-2 "
                    "sendok teh bubuk) dapat menyebabkan efek halusinogenik dan toksik."
                ),
                "sumber_dataset": "Dataset Q&A #28 (Pala)",
                "relevance_score": 0.91,
            },
        ],
    },
]


def sanitize_query_text(raw_query: str) -> str:
    """Strip HTML tags, control characters, and excessive whitespace from user query."""
    if not raw_query:
        return ""
    no_tags = re.sub(r"<[^>]*>", " ", raw_query)
    no_proto = re.sub(r"(?i)(javascript|vbscript|data)\s*:", " ", no_tags)
    cleaned = re.sub(r"\s+", " ", no_proto).strip()
    return cleaned


def detect_safety_triggers(query_text: str) -> list[str]:
    """Check if the query touches clinical dosage, vulnerable groups, severe illness, or drug interactions."""
    q_lower = query_text.lower()
    triggered: list[str] = []
    for category, keywords in SENSITIVE_PATTERNS:
        for kw in keywords:
            if kw in q_lower:
                triggered.append(category)
                break
    return triggered


def build_emergency_message(matched_keywords: list[str]) -> Optional[str]:
    """Compose the standard emergency warning text for detected danger-sign keywords."""
    if not matched_keywords:
        return None
    return (
        "PERINGATAN GEJALA DARURAT: Kondisi yang Anda sebutkan ("
        + ", ".join(matched_keywords)
        + ") memerlukan penanganan medis segera. Segera cari pertolongan di Instalasi Gawat "
        "Darurat (IGD) atau fasilitas kesehatan terdekat."
    )


def detect_emergency_warning(query_text: str) -> Optional[str]:
    """Check if the query mentions emergency clinical symptoms requiring urgent medical care.

    Negation aware: "tidak sesak napas" does not trigger the warning.
    """
    return build_emergency_message(find_unnegated_keywords(query_text, EMERGENCY_KEYWORDS))


def tokenize_indonesian(text: str) -> list[str]:
    """Extract lowercase alphanumeric content tokens of length >= 2 excluding stopwords."""
    stop_set = set(INDONESIAN_STOPWORDS)
    return [
        tok
        for tok in re.findall(r"[a-z0-9]{2,}", text.lower())
        if tok not in stop_set
    ]


def analyze_symptoms_and_recommend(query_text: str) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    """Disabled per Requirement D: Q&A hardcoded groups are retired in favor of official FROTI Kemenkes 2017."""
    return None, []


MANDATORY_TAKARAN_LABEL = "Takaran dalam referensi tradisional, bukan resep medis pribadi"
MISSING_AGE_DOSAGE_TEXT = "Dosis belum ditetapkan dalam sumber. Dosis belum ditetapkan—konsultasikan dengan dokter atau apoteker"
VULNERABLE_CONSUMPTION_WARNING = (

    "PERINGATAN KELOMPOK RENTAN: Untuk balita, bayi, ibu hamil/menyusui, lansia, serta pengguna "
    "dengan penyakit kronis atau obat rutin, instruksi konsumsi tidak ditampilkan sebagai "
    "rekomendasi otomatis. Dosis belum ditetapkan—konsultasikan dengan dokter atau apoteker untuk "
    "pemeriksaan profesional."
)

AGE_GROUP_LABELS: dict[str, str] = {
    "bayi_0_11_bulan": "Bayi (0-11 bulan)",
    "balita_1_2_tahun": "Balita (1-2 tahun)",
    "balita_3_5_tahun": "Balita (3-5 tahun)",
    "anak_6_8_tahun": "Anak (6-8 tahun)",
    "anak_9_11_tahun": "Anak (9-11 tahun)",
    "remaja_12_17_tahun": "Remaja (12-17 tahun)",
    "dewasa_18_59_tahun": "Dewasa (18-59 tahun)",
    "lansia_60_plus": "Lansia (60+ tahun)",
    "ibu_hamil_menyusui": "Ibu Hamil / Menyusui",
    "penyakit_kronis_obat_rutin": "Penyakit Kronis / Obat Rutin",
}

AVAILABLE_AGE_GROUPS: list[dict[str, str]] = [
    {"id": k, "label": v, "vulnerable": "true" if k in {
        "bayi_0_11_bulan",
        "balita_1_2_tahun",
        "balita_3_5_tahun",
        "lansia_60_plus",
        "ibu_hamil_menyusui",
        "penyakit_kronis_obat_rutin",
    } else "false"}
    for k, v in AGE_GROUP_LABELS.items()
]

VULNERABLE_AGE_OR_CONDITIONS: set[str] = {
    "bayi_0_11_bulan",
    "balita_1_2_tahun",
    "balita_3_5_tahun",
    "lansia_60_plus",
    "ibu_hamil_menyusui",
    "penyakit_kronis_obat_rutin",
}

VULNERABLE_QUERY_KEYWORDS: list[str] = [
    "bayi",
    "balita",
    "batita",
    "anak kecil",
    "ibu hamil",
    "hamil",
    "kehamilan",
    "bumil",
    "menyusui",
    "busui",
    "lansia",
    "lanjut usia",
    "manula",
    "penyakit kronis",
    "obat rutin",
    "obat dokter",
    "obat medis",
    "pengencer darah",
    "warfarin",
    "gagal ginjal",
    "gagal jantung",
]

# Synonym expansion for user complaints & traditional uses (complaint terms ONLY).
# Rules: never map a generic "batuk" to "batuk berdahak"; never insert herb/plant names as complaint synonyms;
# cough type is preserved ("batuk kering" stays "batuk kering", "batuk berlendir" = "batuk berdahak").
FROTI_QUERY_SYNONYMS: dict[str, list[str]] = {
    "batuk kering": ["batuk kering"],
    "batuk tidak berdahak": ["batuk kering"],
    "batuk gak berdahak": ["batuk kering"],
    "batuk nggak berdahak": ["batuk kering"],
    "batuk tanpa dahak": ["batuk kering"],
    "batuk berdahak": ["batuk berdahak"],
    "batuk berlendir": ["batuk berdahak"],
    "batuk dengan dahak": ["batuk berdahak"],
    "migrain": ["sakit kepala sebelah"],
    "migren": ["sakit kepala sebelah"],
    "pusing": ["sakit kepala"],
    "nyeri kepala": ["sakit kepala"],
    "radang tenggorokan": ["sakit tenggorokan"],
    "tenggorokan sakit": ["sakit tenggorokan"],
    "nyeri telan": ["sakit tenggorokan"],
    "keseleo": ["terkilir"],
    "salah urat": ["terkilir"],
    "kaku leher": ["leher kaku"],
    "pegal leher": ["leher kaku"],
    "tengeng": ["leher kaku"],
    "salah bantal": ["leher kaku"],
    "sariawan": ["panas dalam"],
    "bibir pecah": ["panas dalam"],
    "susah makan": ["nafsu makan berkurang"],
    "kurang nafsu makan": ["nafsu makan berkurang"],
    "tidak nafsu makan": ["nafsu makan berkurang"],
    "begah": ["perut kembung"],
    "sebah": ["perut kembung"],
    "maag": ["gangguan lambung"],
    "asam lambung": ["gangguan lambung"],
    "perih lambung": ["gangguan lambung"],
    "dispepsia": ["gangguan lambung"],
    "meriang": ["demam"],
    "panas badan": ["demam"],
    "badan panas": ["demam"],
    "dismenore": ["nyeri haid"],
    "senggugut": ["nyeri haid"],
    "nyeri haid": ["nyeri haid"],
    "sakit saat haid": ["nyeri haid"],
    "kram haid": ["nyeri haid"],
    "haid tidak teratur": ["haid tidak teratur"],
    "menstruasi tidak teratur": ["haid tidak teratur"],
    "telat haid": ["haid tidak teratur"],
    "haid terlambat": ["haid tidak teratur"],
    "mencret": ["diare"],
    "bab cair": ["diare"],
}

# Local / regional Indonesian plant name dictionary mapped to canonical plant names
LOCAL_PLANT_TERMS_MAP: dict[str, str] = {
    "koneng gede": "temulawak",
    "temu lawak": "temulawak",
    "kunir": "kunyit",
    "koneng": "kunyit",
    "cikur": "kencur",
    "cekuh": "kencur",
    "ki oray": "sambiloto",
    "sambilata": "sambiloto",
    "pepaitan": "sambiloto",
    "bidara sadina": "sambiloto",
    "suruh": "daun sirih",
    "seureuh": "daun sirih",
    "laos": "lengkuas",
    "laja": "lengkuas",
    "sere": "sereh",
    "serei": "sereh",
    "kates": "pepaya",
    "gedang": "pepaya",
    "temu ireng": "temu hitam",
    "temu erang": "temu hitam",
    "hanjuang": "andong",
    "kayu urip": "andong",
    "camcao": "daun cincau",
    "juju": "daun cincau",
    "ilalang": "alang-alang",
    "alalang": "alang-alang",
    "kayu legi": "akar manis",
    "antanan": "pegagan",
    "daun kaki kuda": "pegagan",
    "bratawali": "brotowali",
    "antawali": "brotowali",
    "remujung": "kumis kucing",
    "songot koceng": "kumis kucing",
    "memeniran": "meniran",
    "pace": "mengkudu",
    "cangkudu": "mengkudu",
    "ilat boyo": "lidah buaya",
    "keningar": "kayu manis",
    "sepang": "kayu secang",
    "jambu klutuk": "daun jambu biji",
    "jambu batu": "daun jambu biji",
    "halia": "jahe",
}

# Common lightweight typo corrections for Indonesian herbal & complaint queries
TYPO_CORRECTION_MAP: dict[str, str] = {
    "jmu": "jamu",
    "fitofarmka": "fitofarmaka",
    "fitofarmak": "fitofarmaka",
    "sambilto": "sambiloto",
    "smbiloto": "sambiloto",
    "sambilloto": "sambiloto",
    "temulwak": "temulawak",
    "tmulawak": "temulawak",
    "kunyt": "kunyit",
    "knyit": "kunyit",
    "kencr": "kencur",
    "kncur": "kencur",
    "jahee": "jahe",
    "jhe": "jahe",
    "sledri": "seledri",
    "seledr": "seledri",
    "lengkas": "lengkuas",
    "lngkuas": "lengkuas",
    "pepya": "pepaya",
    "ppaya": "pepaya",
    "sirh": "sirih",
    "cincu": "cincau",
    "andng": "andong",
    "brotowli": "brotowali",
    "mengkdu": "mengkudu",
    "demm": "demam",
    "dmm": "demam",
    "batk": "batuk",
    "btuk": "batuk",
    "btk": "batuk",
    "skt": "sakit",
    "berdahk": "berdahak",
    "kembng": "kembung",
    "kmbung": "kembung",
    "lambng": "lambung",
    "lmbung": "lambung",
    "terklir": "terkilir",
    "trkilir": "terkilir",
    "tenggorokn": "tenggorokan",
    "migrn": "migrain",
    "diaree": "diare",
    "kolestrol": "kolesterol",
    "hipertnsi": "hipertensi",
}

DOMAIN_VOCAB_TERMS: list[str] = [
    "sambiloto", "kencur", "sirih", "timi", "adas", "jahe", "lengkuas", "pepaya",
    "kunyit", "andong", "temulawak", "seledri", "mengkudu", "sirsak", "sereh",
    "cengkeh", "pala", "secang", "pegagan", "binahong", "brotowali", "meniran",
    "cincau", "demam", "batuk", "berdahak", "terkilir", "kembung", "lambung",
    "tenggorokan", "kepala", "migrain", "diare", "kolesterol", "hipertensi",
    "fitofarmaka", "jamu", "herbal", "ramuan", "tradisional", "bpom", "froti",
]

SCORE_DISCLAIMER_TEXT = (
    "Skor relevansi mengukur kemiripan teks/makna terhadap dokumen sumber, bukan ukuran khasiat medis."
)

CHILD_AGE_WARNING_TEXT = (
    "PERINGATAN USIA ANAK: Penggunaan ramuan tradisional pada anak memerlukan pengawasan dokter "
    "atau apoteker. Jangan menghitung dosis anak dari dosis dewasa. Informasi takaran sumber "
    "ditampilkan hanya sebagai dokumentasi referensi tradisional, bukan resep pribadi."
)


def preprocess_indonesian_query(raw_query: str) -> dict[str, Any]:
    """Perform NLP preprocessing: case/space normalization, local plant recognition, typo correction, and synonym expansion."""
    normalized = sanitize_query_text(raw_query).lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if not normalized:
        return {
            "raw_query": raw_query,
            "normalized_query": "",
            "corrected_query": "",
            "expanded_query": "",
            "typo_corrections": [],
            "matched_synonyms": [],
            "recognized_local_plants": [],
            "is_irrelevant_query": False,
            "irrelevant_reason": None,
        }

    # 1. Local plant term recognition (phrase & token level)
    recognized_local_plants: list[dict[str, str]] = []
    local_additions: list[str] = []
    for local_term, canonical_plant in LOCAL_PLANT_TERMS_MAP.items():
        if re.search(rf"\b{re.escape(local_term)}\b", normalized):
            recognized_local_plants.append(
                {"istilah_lokal": local_term, "nama_tanaman_standar": canonical_plant}
            )
            local_additions.append(canonical_plant)

    # 2. Lightweight typo handling (exact map + SequenceMatcher >= 0.86 on words >= 6 chars)
    tokens = normalized.split()
    corrected_tokens: list[str] = []
    typo_corrections: list[dict[str, str]] = []

    for tok in tokens:
        clean_tok = re.sub(r"[^a-z0-9-]", "", tok)
        if clean_tok in TYPO_CORRECTION_MAP:
            fixed = TYPO_CORRECTION_MAP[clean_tok]
            corrected_tokens.append(fixed)
            typo_corrections.append({"asli": clean_tok, "koreksi": fixed})
        elif (
            len(clean_tok) >= 6
            and clean_tok not in DOMAIN_VOCAB_TERMS
            and clean_tok not in INDONESIAN_STOPWORDS
        ):
            best_match = difflib.get_close_matches(clean_tok, DOMAIN_VOCAB_TERMS, n=1, cutoff=0.86)
            if best_match:
                fixed = best_match[0]
                corrected_tokens.append(fixed)
                typo_corrections.append({"asli": clean_tok, "koreksi": fixed})
            else:
                corrected_tokens.append(tok)
        else:
            corrected_tokens.append(tok)

    corrected_query = " ".join(corrected_tokens)

    # 3. Complaint synonym expansion
    # Longest phrase first, consuming matched spans so a short key never fires inside a longer phrase
    # (e.g. "batuk tidak berdahak" must not also trigger a "berdahak" expansion).
    matched_synonyms: list[dict[str, str]] = []
    synonym_additions: list[str] = []
    consumed_spans: list[tuple[int, int]] = []
    for syn_key in sorted(FROTI_QUERY_SYNONYMS, key=len, reverse=True):
        syn_targets = FROTI_QUERY_SYNONYMS[syn_key]
        for m_syn in re.finditer(rf"\b{re.escape(syn_key)}\b", corrected_query):
            span = m_syn.span()
            if any(not (span[1] <= cs or span[0] >= ce) for cs, ce in consumed_spans):
                continue
            consumed_spans.append(span)
            if not any(ms["istilah_pengguna"] == syn_key for ms in matched_synonyms):
                matched_synonyms.append(
                    {"istilah_pengguna": syn_key, "sinonim_standar": ", ".join(syn_targets)}
                )
            synonym_additions.extend(syn_targets)

    expanded_parts = [corrected_query] + local_additions + synonym_additions
    expanded_query = " ".join(dict.fromkeys(p for p in expanded_parts if p)).strip()

    return {
        "raw_query": raw_query,
        "normalized_query": normalized,
        "corrected_query": corrected_query,
        "expanded_query": expanded_query,
        "typo_corrections": typo_corrections,
        "matched_synonyms": matched_synonyms,
        "recognized_local_plants": recognized_local_plants,
        "is_irrelevant_query": False,
        "irrelevant_reason": None,
    }


def generate_recipe_explainability(
    query_text: str,
    rec: dict[str, Any],
    matched_terms: list[str],
    mode_used: str,
) -> str:
    """Create a human-readable Indonesian explanation for why a recipe document was retrieved."""
    keluhan = rec.get("keluhan_terkait") or "keluhan tradisional"
    tanaman = rec.get("nama_tanaman") or rec.get("nama_ramuan") or "tanaman obat"
    kode = rec.get("recipe_code") or "RAMUAN"
    terms_str = ", ".join(matched_terms[:5]) if matched_terms else query_text.strip()
    model_str = "Semantic Embedding Similarity" if mode_used == "semantic" else "TF-IDF + Cosine Similarity"
    return (
        f"Hasil ini ditemukan karena pertanyaan Anda berkaitan dengan '{terms_str}' "
        f"dan dokumen {kode} ({tanaman}) memiliki kegunaan tradisional yang sesuai "
        f"yaitu '{keluhan}' (dihitung menggunakan {model_str}). "
        f"{SCORE_DISCLAIMER_TEXT}"
    )


def generate_bpom_explainability(
    query_text: str,
    src: dict[str, str],
    matched_terms: list[str],
    mode_used: str,
) -> str:
    """Create a human-readable Indonesian explanation for why a BPOM reference was retrieved."""
    terms_str = ", ".join(matched_terms[:5]) if matched_terms else src.get("topik", "regulasi")
    model_str = "Semantic Embedding Similarity" if mode_used == "semantic" else "TF-IDF + Cosine Similarity"
    return (
        f"Hasil ini ditemukan karena pertanyaan Anda memiliki kecocokan istilah/makna ({terms_str}) "
        f"dengan dokumen resmi {src['source_id']} bertopik '{src['topik']}' ({model_str}). "
        f"{SCORE_DISCLAIMER_TEXT}"
    )


def is_query_for_vulnerable_group(query_text: str) -> bool:
    """Return True if the user query mentions toddlers, infants, pregnancy/lactation, elderly, or chronic meds."""
    q_low = (query_text or "").lower()
    return any(kw in q_low for kw in VULNERABLE_QUERY_KEYWORDS)


def resolve_age_group_dosage(
    dosis_map: dict[str, str],
    age_group: str,
    is_vulnerable: bool = False,
) -> tuple[str, dict[str, str]]:
    """Resolve age-group dosage strictly from source without calculating or fabricating numbers."""
    normalized_map: dict[str, str] = {}
    for k, label in AGE_GROUP_LABELS.items():
        raw_val = (dosis_map.get(k) or "").strip()
        raw_low = raw_val.lower()
        if (
            not raw_val
            or "tidak ditetapkan" in raw_low
            or "tidak menetapkan" in raw_low
            or k in {"ibu_hamil_menyusui", "penyakit_kronis_obat_rutin"}
        ):
            if raw_val and "tidak" in raw_low:
                normalized_map[k] = f"{MISSING_AGE_DOSAGE_TEXT} ({raw_val})"
            else:
                normalized_map[k] = MISSING_AGE_DOSAGE_TEXT
        else:
            normalized_map[k] = f"{raw_val} ({MANDATORY_TAKARAN_LABEL})"

    selected_raw = (dosis_map.get(age_group) or "").strip()
    selected_low = selected_raw.lower()
    is_unestablished = (
        not selected_raw
        or "tidak ditetapkan" in selected_low
        or "tidak menetapkan" in selected_low
        or age_group in {"ibu_hamil_menyusui", "penyakit_kronis_obat_rutin"}
    )

    if is_unestablished:
        if selected_raw and "tidak" in selected_low:
            resolved_selected = f"{MISSING_AGE_DOSAGE_TEXT} ({selected_raw})"
        else:
            resolved_selected = MISSING_AGE_DOSAGE_TEXT
    elif is_vulnerable:
        resolved_selected = (
            f"{MISSING_AGE_DOSAGE_TEXT} — Instruksi konsumsi tidak ditampilkan sebagai rekomendasi "
            f"otomatis untuk kelompok rentan. (Catatan sumber: {selected_raw})"
        )
    else:
        resolved_selected = f"{selected_raw} ({MANDATORY_TAKARAN_LABEL})"

    return resolved_selected, normalized_map


def split_side_effects_and_interactions(peringatan_text: str) -> tuple[str, str]:
    """Split FROTI warning text into distinct side-effects and drug-interaction strings."""
    raw = (peringatan_text or "").strip()
    if not raw:
        return ("Tidak ada data efek samping spesifik dalam sumber.", "Tidak ada data interaksi obat spesifik dalam sumber.")

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw) if s.strip()]
    side_effects: list[str] = []
    interactions: list[str] = []
    for sent in sentences:
        low = sent.lower()
        if any(
            kw in low
            for kw in [
                "interaksi",
                "berinteraksi",
                "antikoagulan",
                "antiplatelet",
                "warfarin",
                "isoniazid",
                "barbiturat",
                "imunosupresan",
                "obat",
                "antihipertensi",
                "antidiabetes",
            ]
        ):
            interactions.append(sent)
        else:
            side_effects.append(sent)

    efek_str = " ".join(side_effects) if side_effects else raw
    interaksi_str = (
        " ".join(interactions)
        if interactions
        else "Belum tercatat interaksi obat spesifik pada entri ini; beri jeda minimal 2 jam bila menggunakan obat dokter."
    )
    return (efek_str, interaksi_str)


def extract_complaint_duration(raw_query: str, explicit_duration: str = "") -> Optional[str]:
    """Extract complaint duration from explicit form input or natural language query."""
    if explicit_duration and explicit_duration.strip():
        return sanitize_query_text(explicit_duration.strip())
    return extract_duration(sanitize_query_text(raw_query))


def build_complaint_understanding(
    raw_query: str,
    sanitized_query: str,
    keluhan_terdeteksi: list[str],
    age_group: str,
    age_label: str,
    durasi_keluhan: Optional[str],
    vulnerable_flags: list[str],
    obat_rutin: str,
    emergency_warning: Optional[str],
    requires_advice: bool,
    is_irrelevant: bool,
    grounded_summary: Optional[str] = None,
    extraction: Optional[dict[str, Any]] = None,
    plant_query: bool = False,
    catatan_cakupan: Optional[list[str]] = None,
    obat_tidak_dilaporkan: bool = False,
) -> dict[str, Any]:
    """Build structured complaint understanding (multi-symptom, negation, temperature, clarification)."""
    ex = extraction or {}
    informasi_belum_jelas: list[str] = list(ex.get("informasi_belum_jelas", []))
    pertanyaan_klarifikasi: list[str] = list(ex.get("pertanyaan_klarifikasi", []))

    if extraction is not None:
        symptoms = list(ex.get("symptom_labels", []))
    else:
        symptoms = list(dict.fromkeys(k.strip().lower() for k in keluhan_terdeteksi if k and k.strip()))

    if not sanitized_query:
        informasi_belum_jelas.append("Keluhan utama belum diisi.")
        pertanyaan_klarifikasi.append("Keluhan kesehatan apa yang sedang Anda alami saat ini?")
    elif is_irrelevant:
        informasi_belum_jelas.append("Kalimat yang dimasukkan tidak menyebutkan keluhan kesehatan atau tanaman obat.")
        pertanyaan_klarifikasi.append(
            "Apakah ada keluhan kesehatan tertentu (seperti batuk berdahak, perut kembung, demam, atau nyeri haid) yang ingin Anda cari referensinya?"
        )
    else:
        if not symptoms and not plant_query:
            informasi_belum_jelas.append("Topik keluhan spesifik belum teridentifikasi secara jelas.")
            pertanyaan_klarifikasi.append(
                "Bisa dijelaskan lebih spesifik keluhan utama yang Anda rasakan (misalnya batuk berdahak, sakit tenggorokan, perut kembung, atau terkilir)?"
            )
        if not durasi_keluhan and symptoms:
            informasi_belum_jelas.append("Durasi berlangsungnya keluhan belum disebutkan.")
            pertanyaan_klarifikasi.append(
                "Sudah berapa lama keluhan ini berlangsung, dan apakah disertai gejala lain seperti demam tinggi?"
            )

    tanda_bahaya: list[str] = list(ex.get("tanda_bahaya", []))
    konflik: list[str] = list(ex.get("konflik", []))
    peringatan_durasi: Optional[str] = None
    if durasi_keluhan and any(w in durasi_keluhan.lower() for w in ["minggu", "bulan", "lama"]):
        peringatan_durasi = (
            f"Keluhan berlangsung cukup lama ({durasi_keluhan}). Keluhan yang berkepanjangan sebaiknya "
            "diperiksakan ke tenaga kesehatan."
        )

    if emergency_warning or tanda_bahaya:
        status_keselamatan = "TANDA BAHAYA MEDIS ? darurat medis, dahulukan pemeriksaan tenaga medis"
    elif konflik:
        status_keselamatan = "perlu klarifikasi informasi (data yang dilaporkan tidak konsisten)"
    elif requires_advice:
        status_keselamatan = "perlu pemeriksaan aturan keselamatan"
    else:
        status_keselamatan = "informasi edukatif referensi tradisional"

    keluhan_terstruktur = list(ex.get("keluhan", []))
    keluhan_utama = ex.get("keluhan_utama") or (symptoms[0] if symptoms else None)
    keluhan_tambahan = ex.get("keluhan_tambahan") or (symptoms[1:] if len(symptoms) > 1 else [])

    if obat_rutin and obat_rutin.strip():
        status_obat = f"Obat rutin dilaporkan: {obat_rutin.strip()}"
    elif obat_tidak_dilaporkan:
        status_obat = "Pengguna menyatakan tidak ada obat rutin yang digunakan"
    else:
        status_obat = "Obat rutin tidak dilaporkan"

    return {
        "input_keluhan": raw_query,
        "keluhan_teridentifikasi": symptoms,
        "symptoms": symptoms,
        "keluhan_utama": keluhan_utama,
        "keluhan_tambahan": keluhan_tambahan,
        "keluhan_terstruktur": keluhan_terstruktur,
        "keluhan_dinegasikan": list(ex.get("keluhan_dinegasikan", [])),
        "rincian_keluhan": list(ex.get("rincian_keluhan", [])),
        "kecukupan_informasi": ex.get("kecukupan_informasi", "cukup"),
        "provider": ex.get("provider", "Deterministic Rule-Based Fallback"),
        "suhu_tubuh": ex.get("suhu_tubuh"),
        "peringatan_suhu": list(ex.get("peringatan_suhu", [])),
        "konflik_informasi": konflik,
        "peringatan_durasi": peringatan_durasi,
        "durasi_keluhan": durasi_keluhan,
        "kelompok_usia": age_group,
        "label_kelompok_usia": age_label,
        "kondisi_khusus": vulnerable_flags,
        "obat_rutin": obat_rutin.strip() if obat_rutin and obat_rutin.strip() else None,
        "status_obat_rutin": status_obat,
        "informasi_belum_jelas": informasi_belum_jelas,
        "pertanyaan_klarifikasi": pertanyaan_klarifikasi[:3],
        "perlu_klarifikasi": bool(
            ex.get("perlu_klarifikasi")
            or ex.get("is_haid_ambigu")
            or (len(pertanyaan_klarifikasi) > 0 and (len(symptoms) == 0 or "haid" in symptoms or "batuk" in symptoms))
        ),
        "tanda_bahaya_terdeteksi": tanda_bahaya,
        "instruksi_ramuan_dihentikan": bool(emergency_warning or tanda_bahaya),
        "status_keselamatan": status_keselamatan,
        "catatan_cakupan_referensi": list(catatan_cakupan or []),
        "diagnosis_medis": None,
        "ringkasan_sumber_terkurasi": grounded_summary,
    }


def build_safety_info_section(
    age_group: str,
    age_label: str,
    is_vulnerable: bool,
    obat_rutin: str,
    obat_tidak_dilaporkan: bool = False,
) -> dict[str, Any]:
    """Build structured Section 8.C Safety Information block."""
    if is_vulnerable:
        info_usia = (
            f"Kelompok terpilih: {age_label}. Instruksi takaran konsumsi TIDAK ditampilkan sebagai "
            "rekomendasi otomatis. Dosis belum ditetapkan dalam sumber untuk rekomendasi mandiri pada kelompok ini."
        )
    elif age_group in {"anak_6_8_tahun", "anak_9_11_tahun"}:
        info_usia = (
            f"Kelompok terpilih: {age_label}. Jangan menghitung dosis anak dari dosis orang dewasa. "
            "Hanya gunakan bila tercantum eksplisit pada sumber FROTI dan di bawah pengawasan dokter/apoteker."
        )
    else:
        info_usia = (
            f"Kelompok terpilih: {age_label}. Takaran yang tercantum merupakan dokumentasi referensi "
            "tradisional FROTI Kemenkes RI, bukan resep pengobatan pribadi."
        )

    kondisi_konsultasi = [
        "Bayi (0-11 bulan), balita (1-5 tahun), dan anak-anak.",
        "Ibu hamil dan ibu menyusui (banyak herba bersifat emenagog/teratogenik atau belum memiliki data keamanan laktasi).",
        "Lansia (60+ tahun) serta pasien dengan gangguan fungsi hati, ginjal, atau penyakit kronis.",
        "Pengguna obat medis rutin (seperti obat pengencer darah/warfarin, obat diabetes, antihipertensi, isoniazid, atau imunosupresan).",
        "Keluhan yang tidak membaik dalam 3 hari, demam tinggi, sesak napas, atau disertai perdarahan.",
    ]
    peringatan_obat: Optional[str] = None
    if obat_rutin and obat_rutin.strip():
        peringatan_obat = (
            f"PERHATIAN OBAT RUTIN: Anda mencantumkan penggunaan '{sanitize_query_text(obat_rutin)}'. "
            "Konsultasikan potensi interaksi herba-obat dengan dokter atau apoteker sebelum menggunakan ramuan tradisional."
        )
        kondisi_konsultasi.insert(0, peringatan_obat)

    if obat_rutin and obat_rutin.strip():
        status_obat_rutin: Optional[str] = f"Obat rutin dilaporkan: {sanitize_query_text(obat_rutin)}."
    else:
        status_obat_rutin = (
            "Tidak ada obat rutin yang dilaporkan. Tetap perhatikan peringatan umum: ramuan tradisional dapat "
            "berinteraksi dengan obat medis, sehingga bila Anda sedang atau akan menggunakan obat apa pun "
            "(termasuk obat bebas atau suplemen), konsultasikan dahulu dengan dokter atau apoteker."
        )

    batasan = [
        "Sistem ini bersifat edukatif dan bukan alat diagnosis medis maupun pemberi resep pengobatan pribadi.",
        "Skor relevansi (TF-IDF / Semantic Similarity) hanya mengukur kecocokan teks/makna terhadap dokumen sumber, bukan tingkat keberhasilan pengobatan.",
        "Data ramuan diambil dari Formularium Ramuan Obat Tradisional Indonesia (FROTI) Kemenkes RI dan rujukan resmi BPOM RI tanpa menggabungkan tanaman baru di luar sumber.",
    ]

    return {
        "informasi_usia": info_usia,
        "kondisi_wajib_konsultasi": kondisi_konsultasi,
        "batasan_informasi": batasan,
        "peringatan_obat_rutin": peringatan_obat,
        "status_obat_rutin": status_obat_rutin,
    }


def format_recipe_card_dict(
    rec: dict[str, Any],
    age_group: str = "dewasa_18_59_tahun",
    vulnerable_flags: Optional[list[str]] = None,
    query_is_vulnerable: bool = False,
    obat_rutin: str = "",
    stop_instructions: bool = False,
    stop_instructions_reason: Optional[str] = None,
) -> dict[str, Any]:
    """Format a recipe dictionary with all 8 required FROTI fields and age/vulnerable safety gating."""
    clean_age = age_group if age_group in AGE_GROUP_LABELS else "dewasa_18_59_tahun"
    age_label = AGE_GROUP_LABELS.get(clean_age, "Dewasa (18-59 tahun)")
    v_flags = [f for f in (vulnerable_flags or []) if f]
    has_routine_meds = bool(obat_rutin and obat_rutin.strip())
    is_vulnerable = (
        clean_age in VULNERABLE_AGE_OR_CONDITIONS
        or len(v_flags) > 0
        or query_is_vulnerable
        or has_routine_meds
        or stop_instructions
    )
    is_child_group = clean_age in {"anak_6_8_tahun", "anak_9_11_tahun"}

    dosis_map = rec.get("dosis_kelompok_usia_map") or {}
    dosis_terpilih, normalized_age_map = resolve_age_group_dosage(
        dosis_map=dosis_map,
        age_group=clean_age,
        is_vulnerable=is_vulnerable,
    )

    rute = rec.get("rute_penggunaan") or "Minum"
    aturan_asli = rec.get("aturan_pakai_sumber") or ""
    if stop_instructions:
        cara_pakai_display = stop_instructions_reason or (
            "PERINGATAN KONDISI MEDIS: Instruksi konsumsi tidak ditampilkan karena terdeteksi tanda bahaya atau "
            "suhu tubuh abnormal. Segera periksakan diri ke fasilitas kesehatan terdekat."
        )
        peringatan_rentan = cara_pakai_display
        dosis_terpilih = "Instruksi konsumsi tidak diberikan karena terdeteksi kondisi medis darurat atau suhu abnormal."
    elif is_vulnerable:
        cara_pakai_display = VULNERABLE_CONSUMPTION_WARNING
        peringatan_rentan = VULNERABLE_CONSUMPTION_WARNING
    elif aturan_asli:
        cara_pakai_display = f"Rute penggunaan: {rute}. {aturan_asli} ({MANDATORY_TAKARAN_LABEL})"
        peringatan_rentan = CHILD_AGE_WARNING_TEXT if is_child_group else None
    else:
        cara_pakai_display = "Informasi takaran atau cara penggunaan belum tersedia dalam sumber yang telah diverifikasi."
        peringatan_rentan = CHILD_AGE_WARNING_TEXT if is_child_group else None

    takaran_raw = rec.get("takaran_bahan_sumber") or "Belum tersedia di sumber"
    if MANDATORY_TAKARAN_LABEL.lower() not in takaran_raw.lower():
        takaran_display = f"{takaran_raw} — {MANDATORY_TAKARAN_LABEL}"
    else:
        takaran_display = takaran_raw

    kontra_raw = rec.get("kontraindikasi") or ""
    peringatan_raw = rec.get("peringatan") or ""
    efek_samping_str, interaksi_obat_str = split_side_effects_and_interactions(peringatan_raw)

    # Check contraindication & interaction warnings against user profile
    kontra_alerts: list[str] = []
    if clean_age == "ibu_hamil_menyusui" or any("hamil" in f or "menyusui" in f for f in v_flags):
        if any(k in kontra_raw.lower() for k in ["hamil", "kehamilan", "menyusui", "laktasi"]):
            kontra_alerts.append("Tercantum larangan kehamilan/menyusui pada sumber")
    if has_routine_meds:
        med_low = obat_rutin.strip().lower()
        if med_low in peringatan_raw.lower() or "interaksi" in peringatan_raw.lower():
            kontra_alerts.append(f"Perhatian potensi interaksi obat dengan '{sanitize_query_text(obat_rutin)}'")

    status_kontra = (
        "; ".join(kontra_alerts)
        if kontra_alerts
        else "Lolos pemeriksaan awal — wajib perhatikan larangan & interaksi obat pada sumber"
    )

    return {
        "id": rec["id"],
        "recipe_code": rec["recipe_code"],
        "slug": rec["slug"],
        "nama_ramuan": rec["nama_ramuan"],
        "nama_tanaman": rec.get("nama_tanaman") or rec["nama_ramuan"],
        "nama_ilmiah": rec.get("nama_ilmiah"),
        "bagian_tanaman": rec.get("bagian_tanaman"),
        "kegunaan_tradisional": rec["keluhan_terkait"],
        "keluhan_terkait": rec["keluhan_terkait"],
        "deskripsi": rec["deskripsi"],
        "takaran_bahan_sumber": takaran_display,
        "label_takaran": MANDATORY_TAKARAN_LABEL,
        "campuran_tambahan": rec.get("bahan_tambahan") or "Tidak ada",
        "langkah_pembuatan": rec.get("cara_membuat_sumber") or "",
        "langkah_pembuatan_list": rec.get("langkah_list") or [],
        "rute_penggunaan": rute,
        "cara_penggunaan": cara_pakai_display,
        "aturan_pakai_sumber_asli": None if (is_vulnerable or stop_instructions) else aturan_asli,
        "kelompok_usia_terpilih": clean_age,
        "label_kelompok_usia": age_label,
        "dosis_kelompok_usia": dosis_terpilih,
        "dosis_per_kelompok_usia": normalized_age_map,
        "instruksi_konsumsi_disembunyikan": is_vulnerable or stop_instructions,
        "peringatan_kelompok_rentan": peringatan_rentan,
        "larangan_kontraindikasi": kontra_raw,
        "efek_samping": efek_samping_str,
        "interaksi_obat": interaksi_obat_str,
        "efek_samping_dan_interaksi": peringatan_raw,
        "status_pemeriksaan_kontraindikasi": status_kontra,
        "status_keamanan_dosis": rec.get("status_keamanan_dosis") or "",
        "sumber_dokumen": rec.get("sumber_dokumen") or rec.get("nama_sumber") or "",
        "halaman_rujukan": rec.get("sumber_halaman") or "",
        "tautan_sumber": rec.get("sumber_url"),
        "nama_sumber": rec["nama_sumber"],
        "status_verifikasi": rec["status_verifikasi"],
        "tanggal_review": rec.get("tanggal_review"),
        "jumlah_bahan": rec["jumlah_bahan"],
        "jumlah_langkah": rec["jumlah_langkah"],
        "aturan_penggunaan_tersedia": rec["aturan_penggunaan_tersedia"] and not is_vulnerable and not stop_instructions,
        "similarity_score": rec.get("similarity_score"),
        "score_label": rec.get("score_label"),
        "matched_terms": rec.get("matched_terms") or [],
        "alasan_relevansi": rec.get("alasan_relevansi"),
        "peringatan_skor": rec.get("peringatan_skor") or SCORE_DISCLAIMER_TEXT,
    }



class SearchEngineService:
    """Manages deterministic TF-IDF index, curated FROTI recipe retrieval, symptom recommender, and semantic embeddings."""

    def __init__(self) -> None:
        self.sources: list[dict[str, str]] = []
        self.recipes: list[dict[str, Any]] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix: Any = None
        self.recipe_vectorizer: Optional[TfidfVectorizer] = None
        self.recipe_tfidf_matrix: Any = None
        self.recipe_char_vectorizer: Optional[TfidfVectorizer] = None
        self.recipe_char_matrix: Any = None
        self.corpus_hash: str = ""
        self.semantic_embeddings: Optional[np.ndarray] = None
        self.gemini_source_embeddings: Optional[np.ndarray] = None
        self.recipe_semantic_embeddings: Optional[np.ndarray] = None
        self.gemini_recipe_embeddings: Optional[np.ndarray] = None
        self.semantic_model: Any = None
        self.semantic_available: bool = False
        self.semantic_status: str = "Mode semantik belum tersedia"
        self.semantic_reason: str = "Indeks belum dimuat."
        self.complaint_service = ComplaintAnalysisService(EMERGENCY_KEYWORDS)
        self.safety_service = SafetyAssessmentService()
        self.retrieval_service = HerbalRetrievalService(self)
        self.evidence_service = EvidenceAnalysisService()
        self.validation_service = SourceValidationService()
        try:
            from app.database import SessionLocal
            with SessionLocal() as db_init:
                if db_init.query(HerbalRecipe).first():
                    self.build_index(db_init)
        except Exception:
            pass

    def build_index(self, db: Session, processed_dir: Path = PROCESSED_DIR) -> dict[str, Any]:
        """Rebuild deterministic TF-IDF index from SQLite Source & HerbalRecipe rows and verify semantic embeddings."""
        source_objs = db.query(Source).order_by(Source.source_id.asc()).all()
        self.sources = [
            {
                "source_id": s.source_id,
                "judul": s.judul,
                "topik": s.topik,
                "ringkasan_aman": s.ringkasan_aman,
                "source_url": s.source_url,
                "otoritas": s.otoritas,
                "status_review": s.status_review,
            }
            for s in source_objs
        ]

        # Load curated HerbalRecipe rows (including all 19 FROTI records) from SQLite
        recipe_objs = db.query(HerbalRecipe).order_by(HerbalRecipe.id.asc()).all()
        self.recipes = []
        for r in recipe_objs:
            bahan_names = " ".join(ing.nama_bahan for ing in r.ingredients)
            langkah_list = [st.deskripsi_langkah for st in r.steps]
            primary_source_name = (
                r.sumber_dokumen
                or (f"{r.sources[0].instansi} - {r.sources[0].nama_referensi}" if r.sources else "Kemenkes RI, FROTI")
            )
            has_public_usage = any(
                u.boleh_ditampilkan_publik and bool(u.aturan_penggunaan_dari_sumber)
                for u in r.usages
            )
            search_text = (
                f"{r.recipe_code} {r.nama_ramuan} {r.nama_tanaman or ''} {r.nama_ilmiah or ''} "
                f"{r.bagian_tanaman or ''} {r.rute_penggunaan or ''} {r.keluhan_terkait} "
                f"{r.takaran_bahan_sumber or ''} {r.bahan_tambahan or ''} {r.cara_membuat_sumber or ''} "
                f"{r.deskripsi} {bahan_names}"
            )
            self.recipes.append(
                {
                    "id": r.id,
                    "recipe_code": r.recipe_code,
                    "slug": r.slug,
                    "nama_ramuan": r.nama_ramuan,
                    "nama_tanaman": r.nama_tanaman or r.nama_ramuan,
                    "nama_ilmiah": r.nama_ilmiah,
                    "bagian_tanaman": r.bagian_tanaman,
                    "rute_penggunaan": r.rute_penggunaan or "Minum",
                    "keluhan_terkait": r.keluhan_terkait,
                    "deskripsi": r.deskripsi,
                    "takaran_bahan_sumber": r.takaran_bahan_sumber or "",
                    "bahan_tambahan": r.bahan_tambahan or "Tidak ada",
                    "cara_membuat_sumber": r.cara_membuat_sumber or " ".join(langkah_list),
                    "langkah_list": langkah_list,
                    "aturan_pakai_sumber": r.aturan_pakai_sumber or "",
                    "dosis_kelompok_usia_map": r.dosis_kelompok_usia_map,
                    "peringatan": r.peringatan,
                    "kontraindikasi": r.kontraindikasi,
                    "status_keamanan_dosis": r.status_keamanan_dosis or "",
                    "sumber_dokumen": r.sumber_dokumen or primary_source_name,
                    "sumber_url": r.sumber_url,
                    "sumber_halaman": r.sumber_halaman or "",
                    "nama_sumber": primary_source_name,
                    "status_verifikasi": r.status_verifikasi,
                    "tanggal_review": r.tanggal_review,
                    "jumlah_bahan": len(r.ingredients),
                    "jumlah_langkah": len(r.steps),
                    "aturan_penggunaan_tersedia": has_public_usage,
                    "search_text": search_text,
                }
            )

        if self.recipes:
            recipe_corpus = [r["search_text"] for r in self.recipes]
            self.recipe_vectorizer = TfidfVectorizer(
                lowercase=True,
                ngram_range=(1, 2),
                token_pattern=r"(?u)\b[a-zA-Z0-9]{2,}\b",
                stop_words=INDONESIAN_STOPWORDS,
                sublinear_tf=True,
            )
            self.recipe_tfidf_matrix = self.recipe_vectorizer.fit_transform(recipe_corpus)

            # Subword character n-gram vectorizer for morphological & fuzzy semantic resilience on FROTI recipes
            self.recipe_char_vectorizer = TfidfVectorizer(
                lowercase=True,
                analyzer="char_wb",
                ngram_range=(3, 5),
                sublinear_tf=True,
            )
            self.recipe_char_matrix = self.recipe_char_vectorizer.fit_transform(recipe_corpus)
        else:
            self.recipe_vectorizer = None
            self.recipe_tfidf_matrix = None
            self.recipe_char_vectorizer = None
            self.recipe_char_matrix = None

        if not self.sources:
            self.vectorizer = None
            self.tfidf_matrix = None
            self.corpus_hash = ""
            self.semantic_available = False
            self.semantic_status = "Mode semantik belum tersedia"
            self.semantic_reason = "Data sumber BPOM kosong; silakan jalankan importer terlebih dahulu."
            return self.get_metadata()

        corpus_texts = [
            f"{s['judul']} {s['topik']} {s['ringkasan_aman']}" for s in self.sources
        ]
        canonical_joined = "\n".join(
            f"{s['source_id']}|{s['judul']}|{s['topik']}|{s['ringkasan_aman']}"
            for s in self.sources
        )
        self.corpus_hash = hashlib.sha256(canonical_joined.encode("utf-8")).hexdigest()

        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            token_pattern=r"(?u)\b[a-zA-Z0-9]{2,}\b",
            stop_words=INDONESIAN_STOPWORDS,
            sublinear_tf=True,
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus_texts)

        # Verify semantic embeddings files for BOTH BPOM sources and FROTI recipes
        emb_path = processed_dir / "bpom_semantic_embeddings.npy"
        gemini_emb_path = processed_dir / "gemini_bpom_embeddings.npy"
        recipe_emb_path = processed_dir / "recipe_semantic_embeddings.npy"
        gemini_recipe_emb_path = processed_dir / "gemini_recipe_embeddings.npy"
        has_st_pkg = importlib.util.find_spec("sentence_transformers") is not None

        if emb_path.exists():
            try:
                emb = np.load(emb_path)
                if emb.ndim == 2 and emb.shape[0] == len(self.sources):
                    self.semantic_embeddings = emb.astype(np.float32)
            except Exception:
                self.semantic_embeddings = None

        if recipe_emb_path.exists() and self.recipes:
            try:
                r_emb = np.load(recipe_emb_path)
                if r_emb.ndim == 2 and r_emb.shape[0] == len(self.recipes):
                    self.recipe_semantic_embeddings = r_emb.astype(np.float32)
            except Exception:
                self.recipe_semantic_embeddings = None

        # Check or build Gemini semantic embeddings for BOTH BPOM sources AND FROTI recipes
        if is_gemini_configured():
            loaded_gemini_src = False
            if gemini_emb_path.exists():
                try:
                    g_emb = np.load(gemini_emb_path)
                    if g_emb.ndim == 2 and g_emb.shape[0] == len(self.sources):
                        self.gemini_source_embeddings = g_emb.astype(np.float32)
                        loaded_gemini_src = True
                except Exception:
                    loaded_gemini_src = False
            if not loaded_gemini_src:
                computed = embed_texts_gemini(corpus_texts)
                if computed is not None and computed.shape[0] == len(self.sources):
                    self.gemini_source_embeddings = computed
                    try:
                        processed_dir.mkdir(parents=True, exist_ok=True)
                        np.save(gemini_emb_path, computed)
                    except Exception:
                        pass

            if self.recipes:
                loaded_gemini_rec = False
                if gemini_recipe_emb_path.exists():
                    try:
                        gr_emb = np.load(gemini_recipe_emb_path)
                        if gr_emb.ndim == 2 and gr_emb.shape[0] == len(self.recipes):
                            self.gemini_recipe_embeddings = gr_emb.astype(np.float32)
                            loaded_gemini_rec = True
                    except Exception:
                        loaded_gemini_rec = False
                if not loaded_gemini_rec:
                    recipe_texts_for_embed = [
                        (
                            f"Tanaman: {r['nama_tanaman']} ({r.get('nama_ilmiah') or ''}). "
                            f"Kegunaan tradisional / keluhan: {r['keluhan_terkait']}. "
                            f"Bagian tanaman: {r.get('bagian_tanaman') or ''}. "
                            f"Deskripsi & pembuatan: {r['deskripsi']} {r['cara_membuat_sumber']}"
                        )
                        for r in self.recipes
                    ]
                    computed_rec = embed_texts_gemini(recipe_texts_for_embed)
                    if computed_rec is not None and computed_rec.shape[0] == len(self.recipes):
                        self.gemini_recipe_embeddings = computed_rec
                        try:
                            processed_dir.mkdir(parents=True, exist_ok=True)
                            np.save(gemini_recipe_emb_path, computed_rec)
                        except Exception:
                            pass

        if self.semantic_embeddings is not None and has_st_pkg and ENABLE_SEMANTIC_MODEL:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                self.semantic_model = SentenceTransformer(SEMANTIC_MODEL_NAME)
                if self.recipes and self.recipe_semantic_embeddings is None:
                    rec_texts = [r["search_text"] for r in self.recipes]
                    r_vecs = self.semantic_model.encode(rec_texts, normalize_embeddings=True)
                    self.recipe_semantic_embeddings = np.asarray(r_vecs, dtype=np.float32)
                    try:
                        np.save(recipe_emb_path, self.recipe_semantic_embeddings)
                    except Exception:
                        pass
                self.semantic_available = True
                self.semantic_status = "Mode semantik aktif"
                self.semantic_reason = (
                    f"Menggunakan model {SEMANTIC_MODEL_NAME} untuk ramuan FROTI "
                    f"({len(self.recipes)} entri) dan sumber BPOM ({list(self.semantic_embeddings.shape)})."
                )
            except Exception as exc:
                self.semantic_available = False
                self.semantic_status = "Mode semantik belum tersedia"
                self.semantic_reason = f"Gagal memuat model sentence-transformers: {exc}"
        elif self.gemini_source_embeddings is not None and is_gemini_configured():
            self.semantic_available = True
            self.semantic_status = f"Mode semantik aktif (Gemini {GEMINI_EMBEDDING_MODEL} untuk FROTI & BPOM)"
            rec_shape = (
                list(self.gemini_recipe_embeddings.shape)
                if self.gemini_recipe_embeddings is not None
                else [len(self.recipes), self.gemini_source_embeddings.shape[1]]
            )
            self.semantic_reason = (
                f"Mode semantik aktif menggunakan Google Gemini Embedding ({GEMINI_EMBEDDING_MODEL}) "
                f"pada {len(self.recipes)} ramuan FROTI/terkurasi (dimensi {rec_shape}) "
                f"dan {len(self.sources)} sumber BPOM (dimensi {list(self.gemini_source_embeddings.shape)}), "
                "serta tervalidasi dengan matriks Colab bpom_semantic_embeddings.npy (9x384)."
            )
        elif self.semantic_embeddings is not None:
            self.semantic_available = False
            self.semantic_status = "Mode semantik belum tersedia"
            self.semantic_reason = (
                f"Matriks dokumen bpom_semantic_embeddings.npy ({self.semantic_embeddings.shape[0]}x"
                f"{self.semantic_embeddings.shape[1]}) telah tervalidasi sesuai 9 sumber BPOM, namun "
                "encoder query belum aktif. Sistem menjalankan Baseline TF-IDF secara deterministik."
            )
        else:
            self.semantic_available = False
            self.semantic_status = "Mode semantik belum tersedia"
            self.semantic_reason = "Berkas bpom_semantic_embeddings.npy tidak ditemukan di folder data."

        meta = self.get_metadata()
        INDEX_META_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(INDEX_META_PATH, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return meta

    def get_metadata(self) -> dict[str, Any]:
        active_recipe_emb = (
            self.gemini_recipe_embeddings
            if self.gemini_recipe_embeddings is not None
            else self.recipe_semantic_embeddings
        )
        return {
            "source_count": len(self.sources),
            "recipe_count": len(self.recipes),
            "froti_recipe_count": sum(
                1 for r in self.recipes if str(r.get("recipe_code", "")).startswith("FROTI-")
            ),
            "source_ids": [s["source_id"] for s in self.sources],
            "recipe_codes": [r["recipe_code"] for r in self.recipes],
            "corpus_sha256": self.corpus_hash,
            "sklearn_version": sklearn.__version__,
            "tfidf_ready": self.vectorizer is not None and self.tfidf_matrix is not None,
            "recipe_tfidf_ready": self.recipe_vectorizer is not None and self.recipe_tfidf_matrix is not None,
            "semantic_model_name": (
                f"Google Gemini Embedding ({GEMINI_EMBEDDING_MODEL})"
                if self.gemini_source_embeddings is not None
                else SEMANTIC_MODEL_NAME
            ),
            "semantic_embeddings_present": self.semantic_embeddings is not None,
            "semantic_embeddings_shape": (
                list(self.semantic_embeddings.shape) if self.semantic_embeddings is not None else None
            ),
            "recipe_semantic_embeddings_present": active_recipe_emb is not None,
            "recipe_semantic_embeddings_shape": (
                list(active_recipe_emb.shape) if active_recipe_emb is not None else None
            ),
            "gemini_configured": is_gemini_configured(),
            "semantic_available": self.semantic_available,
            "semantic_status": self.semantic_status,
            "semantic_reason": self.semantic_reason,
        }

    def search_recipes_by_query(
        self,
        sanitized_query: str,
        mode_used: str = "tfidf",
        top_k: int = 5,
        age_group: str = "dewasa_18_59_tahun",
        vulnerable_flags: Optional[list[str]] = None,
        nlp_info: Optional[dict[str, Any]] = None,
        obat_rutin: str = "",
        stop_instructions: bool = False,
        stop_instructions_reason: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Rank curated HerbalRecipe (FROTI & documented) records using TF-IDF or Semantic Embeddings."""
        if not sanitized_query or not self.recipes or self.recipe_vectorizer is None or self.recipe_tfidf_matrix is None:
            return []

        nlp = nlp_info or preprocess_indonesian_query(sanitized_query)
        expanded_query = nlp["expanded_query"] or sanitized_query
        q_lower = nlp["corrected_query"].lower() if nlp.get("corrected_query") else sanitized_query.lower()

        # 1. Baseline TF-IDF Cosine Similarity on FROTI & curated recipes
        q_vec = self.recipe_vectorizer.transform([expanded_query])
        tfidf_sims = cosine_similarity(q_vec, self.recipe_tfidf_matrix).flatten()

        # Character n-gram similarity for light typo resilience
        char_sims = np.zeros(len(self.recipes), dtype=np.float32)
        if self.recipe_char_vectorizer is not None and self.recipe_char_matrix is not None:
            q_char = self.recipe_char_vectorizer.transform([q_lower])
            char_sims = cosine_similarity(q_char, self.recipe_char_matrix).flatten()

        # 2. Advanced Semantic Embedding Similarity on FROTI & curated recipes when mode_used == 'semantic'
        sem_sims: Optional[np.ndarray] = None
        if mode_used == "semantic":
            if self.semantic_model is not None and self.recipe_semantic_embeddings is not None:
                q_emb = self.semantic_model.encode([expanded_query], normalize_embeddings=True)
                doc_norms = np.linalg.norm(self.recipe_semantic_embeddings, axis=1, keepdims=True)
                doc_norms[doc_norms == 0] = 1.0
                normed_docs = self.recipe_semantic_embeddings / doc_norms
                sem_sims = np.dot(normed_docs, q_emb[0])
            elif self.gemini_recipe_embeddings is not None and is_gemini_configured():
                q_vec_gem = embed_single_query_gemini(expanded_query)
                if q_vec_gem is not None and q_vec_gem.shape[0] == self.gemini_recipe_embeddings.shape[1]:
                    raw_gem = np.dot(self.gemini_recipe_embeddings, q_vec_gem)
                    # Calibrate Gemini embedding cosine similarity (typical baseline ~0.52 for unrelated text)
                    sem_sims = np.where(
                        (tfidf_sims > 0.0) | (raw_gem >= 0.65),
                        0.65 * np.clip((raw_gem - 0.50) * 2.0, 0.0, 1.0) + 0.35 * tfidf_sims,
                        0.0,
                    )

        query_tokens = set(tokenize_indonesian(expanded_query))
        query_is_vuln = is_query_for_vulnerable_group(sanitized_query)

        scored_items: list[tuple[float, dict[str, Any]]] = []
        for idx, rec in enumerate(self.recipes):
            base_tfidf = float(tfidf_sims[idx])
            if sem_sims is not None:
                score_val = float(sem_sims[idx])
            else:
                # Include a small char-ngram contribution only when lexical tokens or high char overlap exist
                score_val = base_tfidf + (0.15 * float(char_sims[idx]) if char_sims[idx] >= 0.22 else 0.0)

            doc_tokens = set(tokenize_indonesian(rec["search_text"]))
            matched = sorted(query_tokens.intersection(doc_tokens))

            plant_low = (rec.get("nama_tanaman") or "").lower()
            sci_low = (rec.get("nama_ilmiah") or "").lower()
            keluhan_low = rec["keluhan_terkait"].lower()
            ramuan_low = rec["nama_ramuan"].lower()

            # Boost direct matches on plant name, scientific name, or traditional complaint/use
            if plant_low and plant_low in expanded_query.lower():
                score_val = max(score_val, 0.42) + 0.20
                if plant_low not in matched:
                    matched.append(plant_low)
            if sci_low and any(tok in sci_low for tok in query_tokens if len(tok) >= 4):
                score_val = max(score_val, 0.40) + 0.18
            if any(tok in keluhan_low or tok in ramuan_low for tok in query_tokens if len(tok) >= 3):
                score_val = max(score_val, 0.28) + 0.15
            elif q_lower in rec["search_text"].lower():
                score_val = max(score_val, 0.24)

            # Give official FROTI entries priority when relevant
            if score_val >= 0.12 and str(rec.get("recipe_code", "")).startswith("FROTI-"):
                score_val += 0.05

            if score_val < 0.12:
                continue

            alasan_rel = generate_recipe_explainability(
                query_text=sanitized_query,
                rec=rec,
                matched_terms=matched,
                mode_used=mode_used,
            )

            enriched_rec = {
                **rec,
                "similarity_score": round(min(score_val, 0.99), 4),
                "score_label": (
                    "Relevansi semantik (bukan ukuran khasiat medis)"
                    if mode_used == "semantic"
                    else "Relevansi teks/topik TF-IDF (bukan ukuran khasiat medis)"
                ),
                "matched_terms": matched,
                "alasan_relevansi": alasan_rel,
                "peringatan_skor": SCORE_DISCLAIMER_TEXT,
            }
            card = format_recipe_card_dict(
                rec=enriched_rec,
                age_group=age_group,
                vulnerable_flags=vulnerable_flags,
                query_is_vulnerable=query_is_vuln,
                obat_rutin=obat_rutin,
                stop_instructions=stop_instructions,
                stop_instructions_reason=stop_instructions_reason,
            )
            scored_items.append((score_val, card))

        scored_items.sort(key=lambda x: (-x[0], x[1]["id"]))
        return [item[1] for item in scored_items[:top_k]]

    def _phrase_similarity(self, phrase: str, mode_used: str) -> tuple[np.ndarray, str]:
        """Similarity of one complaint phrase against ALL curated recipes.

        Both models run on the same recipe corpus (`self.recipes`):
        - Baseline: TF-IDF + cosine similarity.
        - Advanced: sentence/Gemini embedding cosine similarity (calibrated), falling back to TF-IDF
          if no embedding backend is reachable. Returns (similarities, model actually used).
        """
        q_vec = self.recipe_vectorizer.transform([phrase])
        tfidf_sims = cosine_similarity(q_vec, self.recipe_tfidf_matrix).flatten()
        if mode_used != "semantic":
            return tfidf_sims, "tfidf"

        if self.semantic_model is not None and self.recipe_semantic_embeddings is not None:
            q_emb = self.semantic_model.encode([phrase], normalize_embeddings=True)
            doc_norms = np.linalg.norm(self.recipe_semantic_embeddings, axis=1, keepdims=True)
            doc_norms[doc_norms == 0] = 1.0
            normed_docs = self.recipe_semantic_embeddings / doc_norms
            return np.dot(normed_docs, q_emb[0]), "semantic"

        if self.gemini_recipe_embeddings is not None and is_gemini_configured():
            q_vec_gem = embed_single_query_gemini(phrase)
            if q_vec_gem is not None and q_vec_gem.shape[0] == self.gemini_recipe_embeddings.shape[1]:
                raw_gem = np.dot(self.gemini_recipe_embeddings, q_vec_gem)
                calibrated = np.where(
                    (tfidf_sims > 0.0) | (raw_gem >= 0.65),
                    0.65 * np.clip((raw_gem - 0.50) * 2.0, 0.0, 1.0) + 0.35 * tfidf_sims,
                    0.0,
                )
                return calibrated, "semantic"
        return tfidf_sims, "tfidf"

    def search_recipes_structured(
        self,
        extraction: dict[str, Any],
        nlp_info: dict[str, Any],
        mode_used: str = "tfidf",
        top_k: int = 3,
        age_group: str = "dewasa_18_59_tahun",
        vulnerable_flags: Optional[list[str]] = None,
        obat_rutin: str = "",
        query_is_vuln: bool = False,
        stop_instructions: bool = False,
        stop_instructions_reason: Optional[str] = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Rank curated recipes against EVERY recognised complaint (multi-symptom).

        For each complaint the model similarity (TF-IDF or embedding) is combined with a complaint-type
        compatibility check against the recipe's documented complaint:
          - "tepat": the source documents exactly this complaint (e.g. batuk berdahak -> batuk berdahak).
          - "umum": the source mentions the complaint without distinguishing type (e.g. just "batuk").
          - "konflik": the source documents a conflicting type (batuk kering vs batuk berdahak) -> excluded.
        Only recipes that are relevant are returned (never padded to three).
        """
        symptoms: list[dict[str, Any]] = list(extraction.get("keluhan", []))
        cards: list[dict[str, Any]] = []
        info: dict[str, Any] = {"catatan": [], "mode_effective": mode_used, "kecocokan": {}}
        if (
            not symptoms
            or not self.recipes
            or self.recipe_vectorizer is None
            or self.recipe_tfidf_matrix is None
        ):
            return cards, info

        bonus = {"tepat": 0.30, "umum": 0.10}
        solo_threshold = {"tfidf": 0.35, "semantic": 0.55}

        # Recipes the user named directly by plant name (word-boundary match, no herb synonym expansion)
        plant_text = " ".join(
            [nlp_info.get("corrected_query", "")]
            + [p["nama_tanaman_standar"] for p in nlp_info.get("recognized_local_plants", [])]
        ).lower()
        plant_hits: dict[int, str] = {}
        for idx, rec in enumerate(self.recipes):
            plant_low = (rec.get("nama_tanaman") or "").lower().strip()
            if len(plant_low) >= 3 and re.search(rf"(?<![a-z]){re.escape(plant_low)}(?![a-z])", plant_text):
                plant_hits[idx] = plant_low

        per_key: dict[str, list[tuple[float, int, str]]] = {}
        mode_effective = mode_used
        for sym in symptoms:
            key = sym["key"]
            sd = SYMPTOM_BY_KEY[key]
            sims, m_used = self._phrase_similarity(sd.label, mode_used)
            if mode_used == "semantic" and m_used != "semantic":
                mode_effective = "tfidf"
            entries: list[tuple[float, int, str]] = []
            cov: dict[str, list[str]] = {"tepat": [], "umum": [], "konflik": []}
            for idx, rec in enumerate(self.recipes):
                comp = recipe_symptom_compatibility(key, rec["keluhan_terkait"])
                sim = float(sims[idx])
                code = rec["recipe_code"]
                if comp == "konflik":
                    cov["konflik"].append(code)
                    continue
                if comp in bonus:
                    cov[comp].append(code)
                    score = sim + bonus[comp]
                    jenis = comp
                else:
                    # Not linked by documented complaint text: only a strong model similarity qualifies.
                    if sim < solo_threshold[m_used]:
                        continue
                    score = sim
                    jenis = "model"
                if score < MIN_SIMILARITY_THRESHOLD:
                    continue
                entries.append((score, idx, jenis))
            entries.sort(key=lambda e: (-e[0], self.recipes[e[1]]["id"]))
            per_key[key] = entries
            info["kecocokan"][key] = cov

        if plant_hits:
            plant_entries: list[tuple[float, int, str]] = []
            for idx in plant_hits:
                sims_plant, _ = self._phrase_similarity(plant_hits[idx], mode_used)
                plant_entries.append((0.42 + float(sims_plant[idx]), idx, "nama_tanaman"))
            plant_entries.sort(key=lambda e: (-e[0], self.recipes[e[1]]["id"]))
            per_key["_tanaman"] = plant_entries

        # Round-robin selection so every recognised complaint is represented before filling by rank.
        order_keys = [s["key"] for s in symptoms] + (["_tanaman"] if "_tanaman" in per_key else [])
        pointers = {k: 0 for k in order_keys}
        selected: list[int] = []
        progressed = True
        while len(selected) < top_k and progressed:
            progressed = False
            for k in order_keys:
                lst = per_key.get(k, [])
                while pointers[k] < len(lst):
                    _, idx, _ = lst[pointers[k]]
                    pointers[k] += 1
                    if idx in selected:
                        continue
                    selected.append(idx)
                    progressed = True
                    break
                if len(selected) >= top_k:
                    break

        scored: list[tuple[float, int, list[str], str]] = []
        for idx in selected:
            linked: list[str] = []
            best = 0.0
            kinds: list[str] = []
            for k in order_keys:
                for score, e_idx, jenis in per_key.get(k, []):
                    if e_idx == idx:
                        linked.append(SYMPTOM_BY_KEY[k].label if k in SYMPTOM_BY_KEY else (plant_hits.get(idx) or k))
                        kinds.append(jenis)
                        best = max(best, score)
                        break
            total = min(best + 0.05 * max(0, len(set(linked)) - 1), 0.99)
            if "tepat" in kinds:
                jenis_final = "tepat"
            elif "umum" in kinds:
                jenis_final = "umum"
            elif "nama_tanaman" in kinds:
                jenis_final = "nama_tanaman"
            else:
                jenis_final = "model"
            scored.append((total, idx, list(dict.fromkeys(linked)), jenis_final))
        scored.sort(key=lambda x: (-x[0], self.recipes[x[1]]["id"]))

        model_str = "Semantic Embedding Similarity" if mode_effective == "semantic" else "TF-IDF + Cosine Similarity"
        for total, idx, linked, jenis_final in scored:
            rec = self.recipes[idx]
            tanaman = rec.get("nama_tanaman") or rec.get("nama_ramuan") or "tanaman obat"
            kode = rec.get("recipe_code") or "RAMUAN"
            keluhan_doc = rec["keluhan_terkait"]
            terms_str = ", ".join(linked) if linked else "keluhan Anda"
            if jenis_final == "tepat":
                label_kecocokan = "Sesuai: sumber mencatat keluhan ini secara spesifik"
                catatan = ""
                alasan = generate_recipe_explainability(
                    query_text=terms_str, rec=rec, matched_terms=linked, mode_used=mode_effective
                )
            elif jenis_final == "umum":
                label_kecocokan = "Kecocokan umum: sumber tidak membedakan jenis keluhan"
                notes = [
                    SYMPTOM_BY_KEY[k].catatan_generik
                    for k in (s["key"] for s in symptoms)
                    if SYMPTOM_BY_KEY[k].label in linked and SYMPTOM_BY_KEY[k].catatan_generik
                ]
                catatan = " ".join(dict.fromkeys(notes)) or "Sumber mencatat keluhan ini secara umum."
                alasan = (
                    f"Hasil ini ditemukan karena pertanyaan Anda berkaitan dengan '{terms_str}' dan dokumen "
                    f"{kode} ({tanaman}) memiliki kegunaan tradisional yang terkait secara umum yaitu "
                    f"'{keluhan_doc}' (dihitung menggunakan {model_str}). {catatan} {SCORE_DISCLAIMER_TEXT}"
                )
            elif jenis_final == "nama_tanaman":
                label_kecocokan = "Berdasarkan nama tanaman yang Anda sebutkan"
                catatan = "Ramuan ini muncul karena nama tanamannya disebut pada pertanyaan, bukan karena kecocokan keluhan."
                alasan = (
                    f"Hasil ini ditemukan karena pertanyaan Anda menyebut tanaman '{tanaman}' yang tercatat pada "
                    f"dokumen {kode} dengan kegunaan tradisional '{keluhan_doc}' (dihitung menggunakan {model_str}). "
                    f"{SCORE_DISCLAIMER_TEXT}"
                )
            else:
                label_kecocokan = "Kemiripan teks/makna (tidak tercantum eksplisit pada keluhan dokumen)"
                catatan = "Kecocokan hanya berdasarkan kemiripan model, bukan pencatatan keluhan yang sama pada sumber."
                alasan = (
                    f"Hasil ini ditemukan karena pertanyaan Anda berkaitan dengan '{terms_str}' dan dokumen "
                    f"{kode} ({tanaman}) memiliki kemiripan teks/makna dengan keluhan tersebut "
                    f"(dihitung menggunakan {model_str}). {SCORE_DISCLAIMER_TEXT}"
                )

            enriched_rec = {
                **rec,
                "similarity_score": round(total, 4),
                "score_label": (
                    "Relevansi semantik (bukan ukuran khasiat medis)"
                    if mode_effective == "semantic"
                    else "Relevansi teks/topik TF-IDF (bukan ukuran khasiat medis)"
                ),
                "matched_terms": linked,
                "alasan_relevansi": alasan,
                "peringatan_skor": SCORE_DISCLAIMER_TEXT,
            }
            card = format_recipe_card_dict(
                rec=enriched_rec,
                age_group=age_group,
                vulnerable_flags=vulnerable_flags,
                query_is_vulnerable=query_is_vuln,
                obat_rutin=obat_rutin,
                stop_instructions=stop_instructions,
                stop_instructions_reason=stop_instructions_reason,
            )
            card["keluhan_dicocokkan"] = linked
            card["jenis_kecocokan"] = label_kecocokan
            card["catatan_kecocokan"] = catatan
            cards.append(card)

        # Coverage notes per complaint (transparent about gaps; never hides that a type was excluded)
        for sym in symptoms:
            key = sym["key"]
            sd = SYMPTOM_BY_KEY[key]
            cov = info["kecocokan"].get(key, {"tepat": [], "umum": [], "konflik": []})
            if cov["tepat"]:
                pass
            elif cov["umum"]:
                info["catatan"].append(
                    f"Tidak ada ramuan terkurasi yang khusus mencatat '{sd.label}'. Hanya referensi yang menyebut "
                    f"keluhan ini secara umum yang dapat ditampilkan ({', '.join(cov['umum'])}). {sd.catatan_generik}".strip()
                )
            elif not any(e[2] == "model" for e in per_key.get(key, [])):
                info["catatan"].append(
                    f"Belum ditemukan referensi ramuan yang sesuai untuk '{sd.label}' pada dataset FROTI terkurasi."
                )
            if cov["konflik"]:
                info["catatan"].append(
                    f"Ramuan {', '.join(cov['konflik'])} sengaja tidak ditampilkan untuk '{sd.label}' karena sumber "
                    "mencatatnya untuk jenis keluhan yang berbeda."
                )

        info["mode_effective"] = mode_effective
        return cards, info

    def search(
        self,
        raw_query: str,
        mode: str = "tfidf",
        top_k: int = 5,
        age_group: str = "dewasa_18_59_tahun",
        durasi_keluhan: str = "",
        vulnerable_flags: Optional[list[str]] = None,
        obat_rutin: str = "",
        use_gemini: bool = False,
    ) -> dict[str, Any]:
        """Run query against curated FROTI recipes, symptom knowledge base, and BPOM sources."""
        start_time = time.perf_counter()
        sanitized = sanitize_query_text(raw_query)
        # "Obat rutin: tidak ada" / "belum minum obat" inside the query is a statement, not a complaint or drug name.
        analysis_query, med_none_in_query = strip_medication_none_statements(sanitized)
        nlp_info = preprocess_indonesian_query(analysis_query)
        nlp_info["raw_query"] = raw_query
        effective_query = nlp_info["expanded_query"] or analysis_query
        extracted_durasi = extract_complaint_duration(analysis_query, durasi_keluhan)
        raw_obat_clean = sanitize_query_text(obat_rutin).strip()
        clean_obat_rutin = normalize_medication_input(raw_obat_clean)
        obat_tidak_dilaporkan = med_none_in_query or (bool(raw_obat_clean) and not clean_obat_rutin)

        extraction: Optional[dict[str, Any]] = (
            self.complaint_service.analyze_complaint(
                raw_query=nlp_info["corrected_query"] or analysis_query,
                durasi_input=durasi_keluhan,
                use_gemini=use_gemini,
            )
            if analysis_query
            else None
        )
        symptoms_found: list[dict[str, Any]] = list(extraction["keluhan"]) if extraction else []
        kw_hits: list[str] = list(extraction["tanda_bahaya_kata_kunci"]) if extraction else []
        temp_urgent: Optional[str] = extraction["peringatan_mendesak"] if extraction else None
        stop_instructions = bool(extraction and extraction["instruksi_ramuan_dihentikan"])

        clean_age = age_group if age_group in AGE_GROUP_LABELS else "dewasa_18_59_tahun"
        age_label = AGE_GROUP_LABELS.get(clean_age, "Dewasa (18-59 tahun)")
        v_flags = [f for f in (vulnerable_flags or []) if f]
        if clean_obat_rutin and "obat_rutin" not in v_flags:
            v_flags.append(f"obat_rutin:{clean_obat_rutin}")

        query_is_vuln = is_query_for_vulnerable_group(analysis_query)
        is_vulnerable = (
            clean_age in VULNERABLE_AGE_OR_CONDITIONS
            or len(v_flags) > 0
            or query_is_vuln
            or bool(clean_obat_rutin)
        )
        is_child_group = clean_age in {"anak_6_8_tahun", "anak_9_11_tahun"}

        safety_triggers = detect_safety_triggers(analysis_query)
        if clean_obat_rutin and "interaksi obat medis & suplemen" not in safety_triggers:
            safety_triggers.append("interaksi obat medis & suplemen")
        if is_vulnerable and "kelompok rentan (bayi/balita/hamil/menyusui/lansia/penyakit kronis)" not in safety_triggers:
            safety_triggers.append("kelompok rentan (bayi/balita/hamil/menyusui/lansia/penyakit kronis)")
        if is_child_group and "kelompok usia anak (6-11 tahun)" not in safety_triggers:
            safety_triggers.append("kelompok usia anak (6-11 tahun)")

        emergency_parts = [p for p in (build_emergency_message(kw_hits), temp_urgent) if p]
        emergency_warning = " ".join(emergency_parts) if emergency_parts else None
        stop_instructions = stop_instructions or emergency_warning is not None
        requires_advice = (
            len(safety_triggers) > 0
            or emergency_warning is not None
            or is_vulnerable
            or is_child_group
        )
        safety_banner = SAFETY_WARNING_TEXT if requires_advice else None
        if is_vulnerable:
            vulnerable_warning: Optional[str] = VULNERABLE_CONSUMPTION_WARNING
        elif is_child_group:
            vulnerable_warning = CHILD_AGE_WARNING_TEXT
        else:
            vulnerable_warning = None

        safety_info_section = build_safety_info_section(
            age_group=clean_age,
            age_label=age_label,
            is_vulnerable=is_vulnerable,
            obat_rutin=clean_obat_rutin,
            obat_tidak_dilaporkan=obat_tidak_dilaporkan,
        )

        mode_requested = mode
        mode_used = "tfidf"
        semantic_note: Optional[str] = None

        if mode_requested == "semantic":
            if self.semantic_available and (
                (self.semantic_model is not None and self.semantic_embeddings is not None)
                or (self.gemini_source_embeddings is not None and is_gemini_configured())
            ):
                mode_used = "semantic"
                semantic_note = self.semantic_reason
            else:
                mode_used = "tfidf"
                semantic_note = self.semantic_reason

        # Handle empty query cleanly without crash
        if not sanitized:
            empty_understanding = build_complaint_understanding(
                raw_query=raw_query,
                sanitized_query="",
                keluhan_terdeteksi=[],
                age_group=clean_age,
                age_label=age_label,
                durasi_keluhan=extracted_durasi,
                vulnerable_flags=v_flags,
                obat_rutin=clean_obat_rutin,
                emergency_warning=emergency_warning,
                requires_advice=requires_advice,
                is_irrelevant=False,
            )
            elapsed = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "query": raw_query,
                "sanitized_query": sanitized,
                "mode_requested": mode_requested,
                "mode_used": mode_used,
                "age_group": clean_age,
                "age_group_label": age_label,
                "is_vulnerable_group": is_vulnerable,
                "vulnerable_group_warning": vulnerable_warning,
                "requires_professional_advice": requires_advice,
                "safety_triggers": safety_triggers,
                "safety_banner": safety_banner,
                "emergency_warning": emergency_warning,
                "keluhan_terdeteksi": [],
                "catatan_penyebab_keluhan": None,
                "pemahaman_keluhan": empty_understanding,
                "informasi_keselamatan": safety_info_section,
                "matched_recipes": [],
                "recipe_empty_message": None,
                "message": "Masukkan kata kunci, keluhan gejala, nama tanaman, atau kegunaan tradisional terlebih dahulu.",
                "explainability_note": (
                    "Query kosong tidak menghasilkan perhitungan kemiripan dokumen."
                ),
                "semantic_status_note": semantic_note,
                "nlp_analysis": nlp_info,
                "symptom_diagnosis": None,
                "herbal_recommendations": [],
                "results": [],
                "elapsed_ms": elapsed,
            }

        # 1. Retrieve matching FROTI & curated recipes (capped at max 3 per specification)
        symptom_diagnosis, raw_herbal_recommendations = analyze_symptoms_and_recommend(effective_query)
        max_recipe_limit = min(top_k, 3)
        catatan_cakupan: list[str] = []

        is_haid_ambigu = bool(extraction and extraction.get("is_haid_ambigu"))
        needs_clarification_no_symptom = bool(
            extraction
            and extraction.get("perlu_klarifikasi")
            and not any(
                k in extraction.get("symptom_keys", [])
                for k in [
                    "nyeri_haid",
                    "haid_tidak_teratur",
                    "demam",
                    "batuk_berdahak",
                    "sakit_kepala_sebelah",
                    "sakit_tenggorokan",
                    "leher_kaku",
                    "terkilir",
                    "panas_dalam",
                    "nafsu_makan_berkurang",
                    "perut_kembung",
                    "gangguan_lambung",
                    "masuk_angin",
                ]
            )
        )

        if is_haid_ambigu or needs_clarification_no_symptom:
            matched_recipes = []
            if is_haid_ambigu:
                catatan_cakupan = [
                    "Konteks menstruasi memerlukan klarifikasi keluhan spesifik (nyeri haid atau haid tidak teratur) "
                    "sebelum referensi ramuan terkurasi FROTI dapat ditampilkan."
                ]
            else:
                catatan_cakupan = list(extraction.get("informasi_belum_jelas", []))
        elif extraction and extraction.get("keluhan"):
            matched_recipes, struct_info = self.retrieval_service.retrieve_candidates(
                extraction=extraction,
                nlp_info=nlp_info,
                mode_used=mode_used,
                top_k=max_recipe_limit,
                age_group=clean_age,
                vulnerable_flags=v_flags,
                obat_rutin=clean_obat_rutin,
                query_is_vuln=query_is_vuln,
                stop_instructions=stop_instructions,
                stop_instructions_reason=emergency_warning,
            )
            catatan_cakupan = struct_info.get("catatan", [])
        elif bool(nlp_info.get("recognized_local_plants")):
            matched_recipes = self.search_recipes_by_query(
                sanitized,
                mode_used=mode_used,
                top_k=max_recipe_limit,
                age_group=clean_age,
                vulnerable_flags=v_flags,
                nlp_info=nlp_info,
                obat_rutin=clean_obat_rutin,
                stop_instructions=stop_instructions,
                stop_instructions_reason=emergency_warning,
            )
        else:
            matched_recipes = []

        # Apply vulnerable group & takaran labeling rules to herbal_recommendations as well
        herbal_recommendations: list[dict[str, Any]] = []
        for h_rec in raw_herbal_recommendations:
            rec_copy = dict(h_rec)
            rec_copy["label_takaran"] = MANDATORY_TAKARAN_LABEL
            if stop_instructions:
                rec_copy["dosis_dan_cara_pakai"] = emergency_warning or (
                    "PERINGATAN: Instruksi konsumsi dihentikan karena terdeteksi kondisi medis darurat atau suhu abnormal. "
                    "Segera periksakan diri ke fasilitas kesehatan terdekat."
                )
            elif is_vulnerable:
                rec_copy["dosis_dan_cara_pakai"] = VULNERABLE_CONSUMPTION_WARNING
            herbal_recommendations.append(rec_copy)

        keluhan_terdeteksi: list[str] = []
        if extraction and extraction.get("symptom_labels"):
            keluhan_terdeteksi = list(extraction["symptom_labels"])
        elif matched_recipes:
            keluhan_terdeteksi = list(
                dict.fromkeys(
                    r["keluhan_terkait"].split("(")[0].strip()
                    for r in matched_recipes[:3]
                    if r.get("keluhan_terkait")
                )
            )
            if symptom_diagnosis and symptom_diagnosis.get("matched_symptoms"):
                for sym in symptom_diagnosis["matched_symptoms"]:
                    if sym not in keluhan_terdeteksi:
                        keluhan_terdeteksi.append(sym)
        elif symptom_diagnosis and symptom_diagnosis.get("matched_symptoms"):
            keluhan_terdeteksi = list(symptom_diagnosis["matched_symptoms"])

        catatan_penyebab_keluhan: Optional[str] = None
        if keluhan_terdeteksi:
            catatan_penyebab_keluhan = (
                f"Keluhan seperti {', '.join(keluhan_terdeteksi)} dapat memiliki berbagai penyebab "
                "dan tidak dapat didiagnosis dari pertanyaan singkat. Informasi ramuan dan tanaman "
                "di bawah diambil dari sumber referensi terkurasi (FROTI Kemenkes RI & BPOM RI) "
                "dan bersifat edukatif, bukan resep medis pribadi."
            )

        recipe_empty_message: Optional[str] = None
        if not matched_recipes:
            if catatan_cakupan:
                recipe_empty_message = " ".join(catatan_cakupan)
            else:
                recipe_empty_message = (
                    "Belum tersedia referensi ramuan terverifikasi yang relevan untuk keluhan tersebut. "
                    "Belum ditemukan referensi ramuan yang sesuai pada dataset FROTI terkurasi."
                )

        if not self.sources or self.vectorizer is None or self.tfidf_matrix is None:
            understanding_obj = build_complaint_understanding(
                raw_query=raw_query,
                sanitized_query=sanitized,
                keluhan_terdeteksi=keluhan_terdeteksi,
                age_group=clean_age,
                age_label=age_label,
                durasi_keluhan=extracted_durasi,
                vulnerable_flags=v_flags,
                obat_rutin=clean_obat_rutin,
                emergency_warning=emergency_warning,
                requires_advice=requires_advice,
                is_irrelevant=False,
                extraction=extraction,
                plant_query=bool(nlp_info.get("recognized_local_plants")),
                catatan_cakupan=catatan_cakupan,
                obat_tidak_dilaporkan=obat_tidak_dilaporkan,
            )
            elapsed = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "query": raw_query,
                "sanitized_query": sanitized,
                "mode_requested": mode_requested,
                "mode_used": mode_used,
                "age_group": clean_age,
                "age_group_label": age_label,
                "is_vulnerable_group": is_vulnerable,
                "vulnerable_group_warning": vulnerable_warning,
                "requires_professional_advice": requires_advice,
                "safety_triggers": safety_triggers,
                "safety_banner": safety_banner,
                "emergency_warning": emergency_warning,
                "keluhan_terdeteksi": keluhan_terdeteksi,
                "catatan_penyebab_keluhan": catatan_penyebab_keluhan,
                "pemahaman_keluhan": understanding_obj,
                "informasi_keselamatan": safety_info_section,
                "matched_recipes": matched_recipes,
                "recipe_empty_message": recipe_empty_message,
                "message": "Basis data rujukan BPOM belum tersedia. Jalankan proses impor data terlebih dahulu.",
                "explainability_note": "Indeks pencarian belum terinisialisasi.",
                "semantic_status_note": semantic_note,
                "nlp_analysis": nlp_info,
                "symptom_diagnosis": symptom_diagnosis,
                "herbal_recommendations": herbal_recommendations[:top_k],
                "results": [],
                "elapsed_ms": elapsed,
            }

        # 2. Compute similarity scores against BPOM official sources
        used_semantic_vec = False
        scores: list[float] = []
        explain_note = ""

        if mode_used == "semantic":
            if self.semantic_model is not None and self.semantic_embeddings is not None:
                q_vec = self.semantic_model.encode([effective_query], normalize_embeddings=True)
                doc_norms = np.linalg.norm(self.semantic_embeddings, axis=1, keepdims=True)
                doc_norms[doc_norms == 0] = 1.0
                normed_docs = self.semantic_embeddings / doc_norms
                sims = np.dot(normed_docs, q_vec[0])
                scores = sims.tolist()
                used_semantic_vec = True
                explain_note = (
                    "Relevansi semantik: dokumen ramuan FROTI dan sumber BPOM diperingkat menggunakan "
                    f"kemiripan kosinus vektor embedding ({SEMANTIC_MODEL_NAME}). {SCORE_DISCLAIMER_TEXT}"
                )
            elif self.gemini_source_embeddings is not None and is_gemini_configured():
                q_vec_gem = embed_single_query_gemini(effective_query)
                if q_vec_gem is not None and q_vec_gem.shape[0] == self.gemini_source_embeddings.shape[1]:
                    gem_sims = np.dot(self.gemini_source_embeddings, q_vec_gem)
                    q_tfidf = self.vectorizer.transform([effective_query])
                    tfidf_sims = cosine_similarity(q_tfidf, self.tfidf_matrix).flatten()
                    # Hybrid semantic + lexical score calibrated so irrelevant queries stay below threshold
                    hybrid = np.where(
                        (tfidf_sims > 0.0) | (gem_sims >= 0.64),
                        0.65 * np.clip((gem_sims - 0.50) * 2.0, 0.0, 1.0) + 0.35 * tfidf_sims,
                        0.0,
                    )
                    scores = hybrid.tolist()
                    used_semantic_vec = True
                    explain_note = (
                        f"Relevansi semantik: menggunakan kemiripan vektor Google Gemini Embedding "
                        f"({GEMINI_EMBEDDING_MODEL}) dan TF-IDF untuk menemukan data ramuan FROTI "
                        f"dan rujukan BPOM yang relevan. {SCORE_DISCLAIMER_TEXT}"
                    )
                else:
                    mode_used = "tfidf"
                    semantic_note = "Koneksi ke layanan embedding Gemini sedang sibuk; beralih otomatis ke Baseline TF-IDF."

        if not used_semantic_vec:
            q_tfidf = self.vectorizer.transform([effective_query])
            sims = cosine_similarity(q_tfidf, self.tfidf_matrix).flatten()
            scores = sims.tolist()
            explain_note = (
                "Baseline TF-IDF + Cosine Similarity: mencocokkan keluhan pengguna, nama tanaman, "
                f"dan kegunaan tradisional terhadap data terkurasi FROTI Kemenkes RI dan sumber BPOM RI. {SCORE_DISCLAIMER_TEXT}"
            )

        query_tokens = set(tokenize_indonesian(effective_query))
        ranked_indices = sorted(range(len(scores)), key=lambda i: (-scores[i], self.sources[i]["source_id"]))

        results: list[dict[str, Any]] = []
        for idx in ranked_indices[:top_k]:
            score_val = float(scores[idx])
            if score_val < MIN_SIMILARITY_THRESHOLD:
                continue
            src = self.sources[idx]
            doc_tokens = set(
                tokenize_indonesian(f"{src['judul']} {src['topik']} {src['ringkasan_aman']}")
            )
            matched = sorted(query_tokens.intersection(doc_tokens))
            alasan_bpom = generate_bpom_explainability(
                query_text=sanitized,
                src=src,
                matched_terms=matched,
                mode_used=mode_used,
            )
            results.append(
                {
                    "source_id": src["source_id"],
                    "judul": src["judul"],
                    "topik": src["topik"],
                    "ringkasan": src["ringkasan_aman"],
                    "url": src["source_url"],
                    "otoritas": src["otoritas"],
                    "similarity_score": round(score_val, 4),
                    "score_label": (
                        "Relevansi semantik"
                        if mode_used == "semantic"
                        else "Relevansi teks/topik, bukan akurasi medis"
                    ),
                    "verification_note": "Kecocokan topik, bukan validasi klaim",
                    "matched_terms": matched,
                    "alasan_relevansi": alasan_bpom,
                    "peringatan_skor": SCORE_DISCLAIMER_TEXT,
                }
            )

        # Detect irrelevant / out-of-domain queries when no recipe, symptom, or BPOM source matched
        is_irrel = False
        if not matched_recipes and not results and not (symptom_diagnosis and herbal_recommendations):
            is_irrel = True
            nlp_info["is_irrelevant_query"] = True
            nlp_info["irrelevant_reason"] = (
                "Pertanyaan tidak memiliki kecocokan istilah atau makna di atas ambang batas relevansi "
                "(threshold 0.12) pada korpus ramuan FROTI Kemenkes RI maupun rujukan BPOM RI."
            )

        raw_evidence = self.evidence_service.synthesize_evidence(
            raw_query=sanitized,
            stage1_analysis=extraction or {},
            matched_recipes=matched_recipes,
            bpom_sources=results,
            use_gemini=use_gemini,
        )
        validated_evidence = self.validation_service.validate_citations(
            evidence_analysis=raw_evidence,
            matched_recipes=matched_recipes,
            bpom_sources=results,
            stop_instructions=stop_instructions,
            emergency_warning=emergency_warning,
        )
        grounded_summary_str = validated_evidence.get("executive_summary")
        if symptom_diagnosis is not None and grounded_summary_str:
            symptom_diagnosis["ai_consultation_answer"] = grounded_summary_str
            symptom_diagnosis["ai_provider"] = (
                validated_evidence.get("provider") or "Google Gemini"
            )

        understanding_obj = build_complaint_understanding(
            raw_query=raw_query,
            sanitized_query=sanitized,
            keluhan_terdeteksi=keluhan_terdeteksi,
            age_group=clean_age,
            age_label=age_label,
            durasi_keluhan=extracted_durasi,
            vulnerable_flags=v_flags,
            obat_rutin=clean_obat_rutin,
            emergency_warning=emergency_warning,
            requires_advice=requires_advice,
            is_irrelevant=is_irrel,
            grounded_summary=grounded_summary_str,
            extraction=extraction,
            plant_query=bool(nlp_info.get("recognized_local_plants")),
            catatan_cakupan=catatan_cakupan,
            obat_tidak_dilaporkan=obat_tidak_dilaporkan,
        )

        if matched_recipes or (symptom_diagnosis and herbal_recommendations):
            base_msg = (
                f"Berikut sumber informasi yang relevan: ditemukan {len(matched_recipes)} ramuan "
                f"terkurasi (FROTI Kemenkes RI & Dataset), {len(herbal_recommendations[:top_k])} "
                f"informasi tanaman obat terkait, dan {len(results)} dokumen rujukan resmi BPOM."
            )
        elif not results:
            base_msg = (
                "Belum tersedia referensi ramuan terverifikasi yang relevan untuk keluhan tersebut. "
                "Sumber tepercaya belum ditemukan untuk pertanyaan tersebut pada basis data rujukan BPOM."
            )
        else:
            base_msg = (
                f"Berikut sumber informasi yang relevan ({len(results)} kandidat sumber rujukan BPOM)."
            )

        if requires_advice:
            final_msg = f"{SAFETY_WARNING_TEXT} {base_msg}"
        else:
            final_msg = base_msg

        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "query": raw_query,
            "sanitized_query": sanitized,
            "mode_requested": mode_requested,
            "mode_used": mode_used,
            "age_group": clean_age,
            "age_group_label": age_label,
            "is_vulnerable_group": is_vulnerable,
            "vulnerable_group_warning": vulnerable_warning,
            "requires_professional_advice": requires_advice,
            "safety_triggers": safety_triggers,
            "safety_banner": safety_banner,
            "emergency_warning": emergency_warning,
            "keluhan_terdeteksi": keluhan_terdeteksi,
            "catatan_penyebab_keluhan": catatan_penyebab_keluhan,
            "pemahaman_keluhan": understanding_obj,
            "informasi_keselamatan": safety_info_section,
            "matched_recipes": matched_recipes,
            "recipe_empty_message": recipe_empty_message,
            "message": final_msg,
            "explainability_note": explain_note,
            "semantic_status_note": semantic_note,
            "ai_evidence_analysis": validated_evidence,
            "nlp_analysis": nlp_info,
            "symptom_diagnosis": symptom_diagnosis,
            "herbal_recommendations": herbal_recommendations[:top_k],
            "results": results,
            "elapsed_ms": elapsed,
        }



search_engine = SearchEngineService()

