"""Pydantic schemas for API request validation and response serialization."""
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database_ready: bool
    tfidf_index_ready: bool
    semantic_mode_available: bool
    semantic_status: str


class AIStatusResponse(BaseModel):
    configured: bool
    status_code: str
    accessible: bool
    model_name: str
    message: str
    latency_ms: Optional[float] = None


class StatsResponse(BaseModel):
    total_plants: int
    total_qa: int
    total_sources: int
    total_recipes: int = 0
    curated_records: int
    strict_review_qa_count: int
    candidate_topic_links_count: int
    unique_questions_with_source_count: int
    questions_needing_reference_count: int
    plants_with_scientific_name: int
    plants_local_only: int
    families_available: list[str]
    semantic_available: bool
    semantic_status: str
    semantic_reason: str
    evaluation_gold_filled_count: int
    evaluation_total_count: int
    evaluation_note: str


class SourceBriefSchema(BaseModel):
    source_id: str
    judul: str
    topik: str
    ringkasan_aman: str
    source_url: str
    otoritas: str
    status_review: str
    tipe_relasi: Optional[str] = None
    catatan_kurasi: Optional[str] = None


class RelatedQASchema(BaseModel):
    id: int
    pertanyaan: str
    jawaban_kaggle_asli: str
    topik: str
    status_validasi: str
    indikasi_perlu_review_ketat: bool
    tipe_kaitan: str
    peringatan_penelitian: str


class PlantCardSchema(BaseModel):
    id: int
    slug: str
    nama_umum: str
    nama_ilmiah: Optional[str] = None
    famili: Optional[str] = None
    nama_lokal: list[str]
    ringkasan_terkurasi: Optional[str] = None
    gambar_url: Optional[str] = None
    status_verifikasi: str
    sumber_count: int
    qa_terkait_count: int
    updated_at: str
    sumber_data: str


class PlantListResponse(BaseModel):
    items: list[PlantCardSchema]
    total: int
    page: int
    per_page: int
    total_pages: int
    query: str
    family: str
    sort: str
    available_families: list[str]
    available_letters: list[str]


class PlantDetailSchema(BaseModel):
    id: int
    slug: str
    nama_umum: str
    nama_ilmiah: Optional[str] = None
    famili: Optional[str] = None
    nama_lokal: list[str]
    ringkasan_terkurasi: Optional[str] = None
    gambar_url: Optional[str] = None
    gambar_lisensi: Optional[str] = None
    status_verifikasi: str
    updated_at: str
    sumber_data: str
    sumber_count: int
    referensi_bpom: list[SourceBriefSchema]
    pengetahuan_terkait: list[RelatedQASchema]
    peringatan_keamanan: list[str]
    cek_bpom_url: str


class QARefItemSchema(BaseModel):
    source_id: Optional[str] = None
    status_kecocokan: str
    klaim_medis_disetujui: bool
    judul: Optional[str] = None
    source_url: Optional[str] = None


class QAPairItemSchema(BaseModel):
    id: int
    pertanyaan: str
    jawaban_kaggle_asli: str
    topik: str
    status_validasi: str
    indikasi_perlu_review_ketat: bool
    panjang_pertanyaan: int
    panjang_jawaban: int
    referensi_bpom: list[QARefItemSchema]
    tanaman_terkait: list[dict]


class KnowledgeListResponse(BaseModel):
    items: list[QAPairItemSchema]
    total: int
    page: int
    per_page: int
    total_pages: int
    query: str
    topic: str
    review_filter: str
    available_topics: list[str]


class KemenkesReferenceSchema(BaseModel):
    ref_id: str
    judul: str
    instansi: str
    jenis_dokumen: str
    ringkasan: str
    url: str
    status_penggunaan: str


class SourceListResponse(BaseModel):
    items: list[SourceBriefSchema]
    total: int
    query: str
    topic: str
    available_topics: list[str]
    kemenkes_references: list[KemenkesReferenceSchema] = Field(default_factory=list)


class RecipeIngredientSchema(BaseModel):
    id: int
    nama_bahan: str
    jumlah: Optional[str] = None
    satuan: Optional[str] = None
    catatan: Optional[str] = None


class RecipeStepSchema(BaseModel):
    id: int
    nomor_langkah: int
    deskripsi_langkah: str


class RecipeUsageSchema(BaseModel):
    id: int
    aturan_penggunaan_dari_sumber: Optional[str] = None
    status_review_penggunaan: str
    boleh_ditampilkan_publik: bool
    teks_publik: str


class RecipeSourceSchema(BaseModel):
    id: int
    nama_referensi: str
    instansi: str
    url: str
    halaman: Optional[str] = None
    status_validasi: str


class RecipeCardSchema(BaseModel):
    id: int
    recipe_code: str
    slug: str
    nama_ramuan: str
    nama_tanaman: str = ""
    nama_ilmiah: Optional[str] = None
    bagian_tanaman: Optional[str] = None
    kegunaan_tradisional: str = ""
    keluhan_terkait: str
    deskripsi: str
    takaran_bahan_sumber: str = ""
    label_takaran: str = "Takaran dalam referensi tradisional, bukan resep medis pribadi"
    campuran_tambahan: str = "Tidak ada"
    langkah_pembuatan: str = ""
    langkah_pembuatan_list: list[str] = Field(default_factory=list)
    rute_penggunaan: str = "Minum"
    cara_penggunaan: str = ""
    aturan_pakai_sumber_asli: Optional[str] = None
    kelompok_usia_terpilih: str = "dewasa_18_59_tahun"
    label_kelompok_usia: str = "Dewasa (18-59 tahun)"
    dosis_kelompok_usia: str = "Dosis belum ditetapkan—konsultasikan dengan dokter atau apoteker"
    dosis_per_kelompok_usia: dict[str, str] = Field(default_factory=dict)
    instruksi_konsumsi_disembunyikan: bool = False
    peringatan_kelompok_rentan: Optional[str] = None
    larangan_kontraindikasi: str = ""
    efek_samping: str = ""
    interaksi_obat: str = ""
    efek_samping_dan_interaksi: str = ""
    status_pemeriksaan_kontraindikasi: str = ""
    status_keamanan_dosis: str = ""

    sumber_dokumen: str = ""
    halaman_rujukan: str = ""
    tautan_sumber: Optional[str] = None
    nama_sumber: str
    status_verifikasi: str
    tanggal_review: Optional[str] = None
    jumlah_bahan: int
    jumlah_langkah: int
    aturan_penggunaan_tersedia: bool
    similarity_score: Optional[float] = None
    score_label: Optional[str] = None
    matched_terms: list[str] = Field(default_factory=list)
    alasan_relevansi: Optional[str] = None
    peringatan_skor: str = "Skor relevansi mengukur kemiripan teks/makna terhadap dokumen sumber, bukan ukuran khasiat medis."
    keluhan_dicocokkan: list[str] = Field(default_factory=list)
    jenis_kecocokan: Optional[str] = None
    catatan_kecocokan: Optional[str] = None


class RecipeDetailSchema(BaseModel):
    id: int
    recipe_code: str
    slug: str
    nama_ramuan: str
    nama_tanaman: str = ""
    nama_ilmiah: Optional[str] = None
    bagian_tanaman: Optional[str] = None
    kegunaan_tradisional: str = ""
    keluhan_terkait: str
    deskripsi: str
    takaran_bahan_sumber: str = ""
    label_takaran: str = "Takaran dalam referensi tradisional, bukan resep medis pribadi"
    campuran_tambahan: str = "Tidak ada"
    cara_menyiapkan_bahan: Optional[str] = None
    langkah_pembuatan: str = ""
    rute_penggunaan: str = "Minum"
    cara_penggunaan: str = ""
    kelompok_usia_terpilih: str = "dewasa_18_59_tahun"
    label_kelompok_usia: str = "Dewasa (18-59 tahun)"
    dosis_kelompok_usia: str = "Dosis belum ditetapkan—konsultasikan dengan dokter atau apoteker"
    dosis_per_kelompok_usia: dict[str, str] = Field(default_factory=dict)
    instruksi_konsumsi_disembunyikan: bool = False
    peringatan_kelompok_rentan: Optional[str] = None
    kelompok_tidak_dianjurkan: Optional[str] = None
    larangan_kontraindikasi: str = ""
    efek_samping: str = ""
    interaksi_obat: str = ""
    efek_samping_dan_interaksi: str = ""
    status_pemeriksaan_kontraindikasi: str = ""
    status_keamanan_dosis: str = ""

    status_verifikasi: str
    sumber_dokumen: str = ""
    sumber_url: Optional[str] = None
    sumber_halaman: Optional[str] = None
    halaman_rujukan: str = ""
    tautan_sumber: Optional[str] = None
    reviewer: Optional[str] = None
    tanggal_review: Optional[str] = None
    peringatan: str
    kontraindikasi: str
    ingredients: list[RecipeIngredientSchema]
    steps: list[RecipeStepSchema]
    usages: list[RecipeUsageSchema]
    aturan_penggunaan_publik: str
    sources: list[RecipeSourceSchema]
    label_edukasi: str


class RecipeListResponse(BaseModel):
    items: list[RecipeCardSchema]
    total: int
    query: str
    keluhan: str
    age_group: str = "dewasa_18_59_tahun"
    available_complaints: list[str]
    available_age_groups: list[dict[str, str]] = Field(default_factory=list)
    froti_reference_note: str


class SearchRequest(BaseModel):
    query: str = Field(default="", max_length=300, description="Pertanyaan, keluhan, nama tanaman, atau kegunaan tradisional")
    mode: Literal["tfidf", "semantic"] = Field(default="tfidf", description="Mode pencarian: tfidf atau semantic")
    top_k: int = Field(default=5, ge=1, le=20, description="Jumlah maksimum kandidat sumber yang dikembalikan")
    age_group: str = Field(default="dewasa_18_59_tahun", description="Kelompok usia atau kondisi pengguna")
    durasi_keluhan: str = Field(default="", max_length=120, description="Durasi keluhan (opsional, contoh: sejak kemarin)")
    vulnerable_flags: list[str] = Field(default_factory=list, description="Kondisi khusus kelompok rentan (hamil, menyusui, penyakit_kronis)")
    obat_rutin: str = Field(default="", max_length=200, description="Obat medis yang sedang digunakan, jika relevan")
    use_gemini: bool = Field(default=False, description="Opsional penjelasan berbasis sumber dan analisis Gemini AI (tidak menghasilkan diagnosis atau dosis)")



class SearchResultItem(BaseModel):
    source_id: str
    judul: str
    topik: str
    ringkasan: str
    url: str
    otoritas: str
    similarity_score: float
    score_label: str
    verification_note: str
    matched_terms: list[str]
    alasan_relevansi: Optional[str] = None
    peringatan_skor: str = "Skor relevansi mengukur kemiripan teks/makna terhadap dokumen sumber, bukan ukuran khasiat medis."


class NlpAnalysisSchema(BaseModel):
    raw_query: str
    normalized_query: str
    corrected_query: str
    expanded_query: str
    typo_corrections: list[dict[str, str]] = Field(default_factory=list)
    matched_synonyms: list[dict[str, str]] = Field(default_factory=list)
    recognized_local_plants: list[dict[str, str]] = Field(default_factory=list)
    is_irrelevant_query: bool = False
    irrelevant_reason: Optional[str] = None


class EvaluationAnnotationItemSchema(BaseModel):
    id_uji: str
    gold_relevant_ids: str


class EvaluationComputeRequest(BaseModel):
    annotations: list[EvaluationAnnotationItemSchema] = Field(default_factory=list)
    save_to_csv: bool = False


class SymptomDiagnosisSchema(BaseModel):
    detected_condition: str
    clinical_summary: str
    matched_symptoms: list[str]
    when_to_see_doctor: str
    ai_consultation_answer: Optional[str] = None
    ai_provider: Optional[str] = None


class HerbalRecommendationItem(BaseModel):
    qa_id: int
    nama_herbal: str
    nama_ilmiah: Optional[str] = None
    slug: Optional[str] = None
    senyawa_aktif: str
    khasiat_relevan: str
    dosis_dan_cara_pakai: str
    label_takaran: str = "Takaran dalam referensi tradisional, bukan resep medis pribadi"
    peringatan: str
    sumber_dataset: str
    relevance_score: float


class AiRelevanceItemSchema(BaseModel):
    kode_referensi: str
    nama_ramuan_atau_dokumen: str
    mengapa_relevan: str
    keluhan_yang_didukung: list[str] = Field(default_factory=list)
    catatan_sumber: Optional[str] = None


class AiEvidenceAnalysisSchema(BaseModel):
    ai_analysis_title: str = "Analisis AI HerbID: Sintesis Bukti Ramuan Terkurasi"
    executive_summary: str
    relevance_explanations: list[AiRelevanceItemSchema] = Field(default_factory=list)
    unaddressed_complaints: list[str] = Field(default_factory=list)
    information_limitations: list[str] = Field(default_factory=list)
    safety_and_contraindication_highlights: list[str] = Field(default_factory=list)
    cited_sources: list[str] = Field(default_factory=list)
    provider: str = "Google Gemini"
    is_grounded: bool = True
    diagnosis_medis: Optional[str] = None


class ComplaintUnderstandingSchema(BaseModel):
    input_keluhan: str
    keluhan_teridentifikasi: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(default_factory=list)
    keluhan_utama: Optional[str] = None
    keluhan_tambahan: list[str] = Field(default_factory=list)
    keluhan_terstruktur: list[dict[str, Any]] = Field(default_factory=list)
    keluhan_dinegasikan: list[dict[str, Any]] = Field(default_factory=list)
    rincian_keluhan: list[dict[str, Any]] = Field(default_factory=list)
    kecukupan_informasi: Optional[str] = "cukup"
    provider: Optional[str] = None
    suhu_tubuh: Optional[dict[str, Any]] = None
    peringatan_suhu: list[str] = Field(default_factory=list)
    konflik_informasi: list[str] = Field(default_factory=list)
    peringatan_durasi: Optional[str] = None
    durasi_keluhan: Optional[str] = None
    kelompok_usia: str = "dewasa_18_59_tahun"
    label_kelompok_usia: str = "Dewasa (18-59 tahun)"
    kondisi_khusus: list[str] = Field(default_factory=list)
    obat_rutin: Optional[str] = None
    status_obat_rutin: Optional[str] = None
    informasi_belum_jelas: list[str] = Field(default_factory=list)
    pertanyaan_klarifikasi: list[str] = Field(default_factory=list)
    perlu_klarifikasi: bool = False
    tanda_bahaya_terdeteksi: list[str] = Field(default_factory=list)
    instruksi_ramuan_dihentikan: bool = False
    status_keselamatan: str = "aman_edukatif"
    catatan_cakupan_referensi: list[str] = Field(default_factory=list)
    diagnosis_medis: Optional[str] = None
    ringkasan_sumber_terkurasi: Optional[str] = None


class SafetyInfoSectionSchema(BaseModel):
    informasi_usia: str
    kondisi_wajib_konsultasi: list[str] = Field(default_factory=list)
    batasan_informasi: list[str] = Field(default_factory=list)
    peringatan_obat_rutin: Optional[str] = None
    status_obat_rutin: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    sanitized_query: str
    mode_requested: str
    mode_used: str
    age_group: str = "dewasa_18_59_tahun"
    age_group_label: str = "Dewasa (18-59 tahun)"
    is_vulnerable_group: bool = False
    vulnerable_group_warning: Optional[str] = None
    requires_professional_advice: bool
    safety_triggers: list[str]
    safety_banner: Optional[str] = None
    emergency_warning: Optional[str] = None
    keluhan_terdeteksi: list[str] = Field(default_factory=list)
    catatan_penyebab_keluhan: Optional[str] = None
    pemahaman_keluhan: Optional[ComplaintUnderstandingSchema] = None
    informasi_keselamatan: Optional[SafetyInfoSectionSchema] = None
    matched_recipes: list[RecipeCardSchema] = Field(default_factory=list)
    recipe_empty_message: Optional[str] = None
    message: str
    explainability_note: str
    semantic_status_note: Optional[str] = None
    ai_evidence_analysis: Optional[AiEvidenceAnalysisSchema] = None
    nlp_analysis: Optional[NlpAnalysisSchema] = None
    symptom_diagnosis: Optional[SymptomDiagnosisSchema] = None
    herbal_recommendations: list[HerbalRecommendationItem] = Field(default_factory=list)
    results: list[SearchResultItem]
    elapsed_ms: float


