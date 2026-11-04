/**
 * API Client for HERB-INFO AI Backend
 */

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : (import.meta.env.PROD ? '' : 'http://localhost:8000')
).replace(/\/+$/, '');

export interface StatsData {
  total_plants: number;
  total_qa: number;
  total_sources: number;
  total_recipes: number;
  curated_records: number;
  strict_review_qa_count: number;
  candidate_topic_links_count: number;
  unique_questions_with_source_count: number;
  questions_needing_reference_count: number;
  plants_with_scientific_name: number;
  plants_local_only: number;
  families_available: string[];
  semantic_available: boolean;
  semantic_status: string;
  semantic_reason: string;
  evaluation_gold_filled_count: number;
  evaluation_total_count: number;
  evaluation_note: string;
}

export interface PlantCardItem {
  id: number;
  slug: string;
  nama_umum: string;
  nama_ilmiah: string | null;
  famili: string | null;
  nama_lokal: string[];
  ringkasan_terkurasi: string | null;
  gambar_url: string | null;
  status_verifikasi: string;
  sumber_count: number;
  qa_terkait_count: number;
  updated_at: string;
  sumber_data: string;
}

export interface PlantListResponse {
  items: PlantCardItem[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  query: string;
  family: string;
  sort: string;
  available_families: string[];
  available_letters: string[];
}

export interface SourceItem {
  source_id: string;
  judul: string;
  topik: string;
  ringkasan_aman: string;
  source_url: string;
  otoritas: string;
  status_review: string;
  tipe_relasi?: string | null;
  catatan_kurasi?: string | null;
}

export interface KemenkesReferenceItem {
  ref_id: string;
  judul: string;
  instansi: string;
  jenis_dokumen: string;
  ringkasan: string;
  url: string;
  status_penggunaan: string;
}

export interface RelatedQAItem {
  id: number;
  pertanyaan: string;
  jawaban_kaggle_asli: string;
  topik: string;
  status_validasi: string;
  indikasi_perlu_review_ketat: boolean;
  tipe_kaitan: string;
  peringatan_penelitian: string;
}

export interface PlantDetailData {
  id: number;
  slug: string;
  nama_umum: string;
  nama_ilmiah: string | null;
  famili: string | null;
  nama_lokal: string[];
  ringkasan_terkurasi: string | null;
  gambar_url: string | null;
  gambar_lisensi: string | null;
  status_verifikasi: string;
  updated_at: string;
  sumber_data: string;
  sumber_count: number;
  referensi_bpom: SourceItem[];
  pengetahuan_terkait: RelatedQAItem[];
  peringatan_keamanan: string[];
  cek_bpom_url: string;
}

export interface QARefItem {
  source_id: string | null;
  status_kecocokan: string;
  klaim_medis_disetujui: boolean;
  judul: string | null;
  source_url: string | null;
}

export interface QAPairItem {
  id: number;
  pertanyaan: string;
  jawaban_kaggle_asli: string;
  topik: string;
  status_validasi: string;
  indikasi_perlu_review_ketat: boolean;
  panjang_pertanyaan: number;
  panjang_jawaban: number;
  referensi_bpom: QARefItem[];
  tanaman_terkait: Array<{
    slug: string;
    nama_umum: string;
    tipe_kaitan: string;
  }>;
}

export interface KnowledgeListResponse {
  items: QAPairItem[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  query: string;
  topic: string;
  review_filter: string;
  available_topics: string[];
}

export interface SourceListResponse {
  items: SourceItem[];
  total: number;
  query: string;
  topic: string;
  available_topics: string[];
  kemenkes_references?: KemenkesReferenceItem[];
}

export interface RecipeIngredientItem {
  id: number;
  nama_bahan: string;
  jumlah: string | null;
  satuan: string | null;
  catatan: string | null;
}

export interface RecipeStepItem {
  id: number;
  nomor_langkah: number;
  deskripsi_langkah: string;
}

export interface RecipeUsageItem {
  id: number;
  aturan_penggunaan_dari_sumber: string | null;
  status_review_penggunaan: string;
  boleh_ditampilkan_publik: boolean;
  teks_publik: string;
}

export interface RecipeSourceItem {
  id: number;
  nama_referensi: string;
  instansi: string;
  url: string;
  halaman: string | null;
  status_validasi: string;
}

export interface AgeGroupOption {
  id: string;
  label: string;
  vulnerable: boolean;
}

export const AGE_GROUP_OPTIONS: AgeGroupOption[] = [
  { id: 'dewasa_18_59_tahun', label: 'Dewasa (18-59 tahun)', vulnerable: false },
  { id: 'remaja_12_17_tahun', label: 'Remaja (12-17 tahun)', vulnerable: false },
  { id: 'anak_9_11_tahun', label: 'Anak (9-11 tahun)', vulnerable: false },
  { id: 'anak_6_8_tahun', label: 'Anak (6-8 tahun)', vulnerable: false },
  { id: 'balita_3_5_tahun', label: 'Balita (3-5 tahun) — Kelompok Rentan', vulnerable: true },
  { id: 'balita_1_2_tahun', label: 'Balita (1-2 tahun) — Kelompok Rentan', vulnerable: true },
  { id: 'bayi_0_11_bulan', label: 'Bayi (0-11 bulan) — Kelompok Rentan', vulnerable: true },
  { id: 'lansia_60_plus', label: 'Lansia (60+ tahun) — Kelompok Rentan', vulnerable: true },
  { id: 'ibu_hamil_menyusui', label: 'Ibu Hamil / Menyusui — Kelompok Rentan', vulnerable: true },
  { id: 'penyakit_kronis_obat_rutin', label: 'Penyakit Kronis / Obat Rutin — Kelompok Rentan', vulnerable: true },
];

export interface RecipeCardItem {
  id: number;
  recipe_code: string;
  slug: string;
  nama_ramuan: string;
  nama_tanaman: string;
  nama_ilmiah: string | null;
  bagian_tanaman: string | null;
  kegunaan_tradisional: string;
  keluhan_terkait: string;
  deskripsi: string;
  takaran_bahan_sumber: string;
  label_takaran: string;
  campuran_tambahan: string;
  langkah_pembuatan: string;
  langkah_pembuatan_list: string[];
  rute_penggunaan: string;
  cara_penggunaan: string;
  aturan_pakai_sumber_asli?: string | null;
  kelompok_usia_terpilih: string;
  label_kelompok_usia: string;
  dosis_kelompok_usia: string;
  dosis_per_kelompok_usia: Record<string, string>;
  instruksi_konsumsi_disembunyikan: boolean;
  peringatan_kelompok_rentan: string | null;
  larangan_kontraindikasi: string;
  efek_samping_dan_interaksi: string;
  efek_samping?: string;
  interaksi_obat?: string;
  status_keamanan_dosis: string;
  status_pemeriksaan_kontraindikasi?: string;
  sumber_dokumen: string;
  halaman_rujukan: string;
  tautan_sumber: string | null;
  nama_sumber: string;
  status_verifikasi: string;
  tanggal_review: string | null;
  jumlah_bahan: number;
  jumlah_langkah: number;
  aturan_penggunaan_tersedia: boolean;
  similarity_score?: number | null;
  score_label?: string | null;
  matched_terms?: string[];
  alasan_relevansi?: string | null;
  peringatan_skor?: string;
  keluhan_dicocokkan?: string[];
  jenis_kecocokan?: string | null;
  catatan_kecocokan?: string | null;
}


export interface RecipeDetailData {
  id: number;
  recipe_code: string;
  slug: string;
  nama_ramuan: string;
  nama_tanaman: string;
  nama_ilmiah: string | null;
  bagian_tanaman: string | null;
  kegunaan_tradisional: string;
  keluhan_terkait: string;
  deskripsi: string;
  takaran_bahan_sumber: string;
  label_takaran: string;
  campuran_tambahan: string;
  cara_menyiapkan_bahan: string | null;
  langkah_pembuatan: string;
  rute_penggunaan: string;
  cara_penggunaan: string;
  kelompok_usia_terpilih: string;
  label_kelompok_usia: string;
  dosis_kelompok_usia: string;
  dosis_per_kelompok_usia: Record<string, string>;
  instruksi_konsumsi_disembunyikan: boolean;
  peringatan_kelompok_rentan: string | null;
  kelompok_tidak_dianjurkan: string | null;
  larangan_kontraindikasi: string;
  efek_samping_dan_interaksi: string;
  status_keamanan_dosis: string;
  status_verifikasi: string;
  sumber_dokumen: string;
  sumber_url: string | null;
  sumber_halaman: string | null;
  halaman_rujukan: string;
  tautan_sumber: string | null;
  reviewer: string | null;
  tanggal_review: string | null;
  peringatan: string;
  kontraindikasi: string;
  ingredients: RecipeIngredientItem[];
  steps: RecipeStepItem[];
  usages: RecipeUsageItem[];
  aturan_penggunaan_publik: string;
  sources: RecipeSourceItem[];
  label_edukasi: string;
}

export interface RecipeListResponse {
  items: RecipeCardItem[];
  total: number;
  query: string;
  keluhan: string;
  age_group?: string;
  available_complaints: string[];
  available_age_groups?: Array<{ id: string; label: string; vulnerable?: string }>;
  froti_reference_note: string;
}

export interface SearchResultItem {
  source_id: string;
  judul: string;
  topik: string;
  ringkasan: string;
  url: string;
  otoritas: string;
  similarity_score: number;
  score_label: string;
  verification_note: string;
  matched_terms: string[];
  alasan_relevansi?: string | null;
  peringatan_skor?: string;
}

export interface NlpAnalysisInfo {
  raw_query: string;
  normalized_query: string;
  corrected_query: string;
  expanded_query: string;
  typo_corrections: Array<{ asli: string; koreksi: string }>;
  matched_synonyms: Array<{ istilah_pengguna: string; sinonim_standar: string }>;
  recognized_local_plants: Array<{ istilah_lokal: string; nama_tanaman_standar: string }>;
  is_irrelevant_query: boolean;
  irrelevant_reason: string | null;
}

export interface SymptomDiagnosis {
  detected_condition: string;
  clinical_summary: string;
  matched_symptoms: string[];
  when_to_see_doctor: string;
  ai_consultation_answer?: string | null;
  ai_provider?: string | null;
}

export interface HerbalRecommendationItem {
  qa_id: number;
  nama_herbal: string;
  nama_ilmiah: string | null;
  slug: string | null;
  senyawa_aktif: string;
  khasiat_relevan: string;
  dosis_dan_cara_pakai: string;
  label_takaran?: string;
  peringatan: string;
  sumber_dataset: string;
  relevance_score: number;
}

export interface StructuredComplaintItem {
  key: string;
  nama: string;
  jenis: string;
  peran?: string;
  status: string;
  teks_asli: string;
}

export interface NegatedComplaintItem {
  key: string;
  nama: string;
  teks_asli: string;
}

export interface TemperatureInfo {
  nilai_asli: string;
  nilai_celsius: number;
  satuan: string;
  satuan_asli: string;
  satuan_eksplisit: boolean;
  satuan_diasumsikan: boolean;
  kategori: string;
  kategori_kode: string;
  tampilan: string;
  teks_asli: string;
  valid: boolean;
}

export interface AiRelevanceItem {
  kode_referensi: string;
  nama_ramuan_atau_dokumen: string;
  mengapa_relevan: string;
  keluhan_yang_didukung: string[];
  catatan_sumber?: string | null;
}

export interface AiEvidenceAnalysis {
  ai_analysis_title: string;
  executive_summary: string;
  relevance_explanations: AiRelevanceItem[];
  unaddressed_complaints: string[];
  information_limitations: string[];
  safety_and_contraindication_highlights: string[];
  cited_sources: string[];
  provider: string;
  is_grounded: boolean;
  diagnosis_medis: null;
}

export interface ComplaintUnderstanding {
  input_keluhan: string;
  keluhan_teridentifikasi: string[];
  symptoms?: string[];
  keluhan_utama?: string | null;
  keluhan_tambahan?: string[];
  keluhan_terstruktur?: StructuredComplaintItem[];
  keluhan_dinegasikan?: NegatedComplaintItem[];
  rincian_keluhan?: Array<{
    nama_keluhan: string;
    jenis_karakteristik: string;
    status_disebutkan: string;
    negasi: boolean;
  }>;
  kecukupan_informasi?: string;
  provider?: string | null;
  suhu_tubuh?: TemperatureInfo | null;
  peringatan_suhu?: string[];
  konflik_informasi?: string[];
  peringatan_durasi?: string | null;
  durasi_keluhan: string | null;
  kelompok_usia?: string;
  label_kelompok_usia?: string;
  kondisi_khusus?: string[];
  obat_rutin?: string | null;
  status_obat_rutin?: string | null;
  informasi_belum_jelas: string[];
  pertanyaan_klarifikasi: string[];
  perlu_klarifikasi?: boolean;
  tanda_bahaya_terdeteksi?: string[];
  instruksi_ramuan_dihentikan?: boolean;
  status_keselamatan: string;
  catatan_cakupan_referensi?: string[];
  diagnosis_medis: string | null;
  ringkasan_sumber_terkurasi?: string | null;
}

export interface SafetyInfoSection {
  informasi_usia: string;
  kondisi_wajib_konsultasi: string[];
  batasan_informasi: string[] | string;
  peringatan_obat_rutin?: string | null;
  status_obat_rutin?: string | null;
}

export interface SearchResponse {
  query: string;
  sanitized_query: string;
  mode_requested: string;
  mode_used: string;
  age_group?: string;
  age_group_label?: string;
  durasi_keluhan?: string | null;
  obat_rutin?: string | null;
  is_vulnerable_group?: boolean;
  vulnerable_group_warning?: string | null;
  requires_professional_advice: boolean;
  safety_triggers: string[];
  safety_banner: string | null;
  emergency_warning?: string | null;
  keluhan_terdeteksi: string[];
  catatan_penyebab_keluhan?: string | null;
  pemahaman_keluhan?: ComplaintUnderstanding | null;
  informasi_keselamatan?: SafetyInfoSection | null;
  matched_recipes: RecipeCardItem[];
  recipe_empty_message?: string | null;
  message: string;
  explainability_note: string;
  semantic_status_note: string | null;
  ai_evidence_analysis?: AiEvidenceAnalysis | null;
  nlp_analysis?: NlpAnalysisInfo | null;
  symptom_diagnosis: SymptomDiagnosis | null;
  herbal_recommendations: HerbalRecommendationItem[];
  results: SearchResultItem[];
  elapsed_ms: number;
}

export interface NlpBenchmarkItem {
  id_uji: string;
  kategori_uji: string;
  pertanyaan_uji: string;
  target_korpus: string;
  gold_relevant_ids: string;
  kandidat_dokumen_petunjuk_anotator: string;
  catatan_anotasi: string;
  top3_tfidf: string[];
  top3_semantic: string[];
}

export interface NlpBenchmark30Response {
  status: string;
  total_queries: number;
  labeled_queries: number;
  metrics_available: boolean;
  note: string;
  tfidf_metrics: {
    hit_at_1: number;
    recall_at_3: number;
    mrr_at_10: number;
    labeled_count: number;
  } | null;
  semantic_metrics: {
    hit_at_1: number;
    recall_at_3: number;
    mrr_at_10: number;
    labeled_count: number;
  } | null;
  items: NlpBenchmarkItem[];
}

export interface EvaluationDetailsResponse {
  evaluation: {
    status: string;
    total_rows: number;
    labeled_rows: number;
    metrics_available: boolean;
    note: string;
    tfidf_metrics: Record<string, number> | null;
    semantic_metrics: Record<string, number> | null;
  };
  nlp_benchmark_30?: NlpBenchmark30Response;
  dataset_summary?: {
    total_plants: number;
    plants_with_scientific_name: number;
    plants_local_only: number;
    total_recipes: number;
    froti_recipes: number;
    documented_other_recipes: number;
    total_qa_kaggle: number;
    total_bpom_sources: number;
  };
  nlp_capabilities?: {
    normalisasi_huruf_spasi: boolean;
    sinonim_keluhan_count: number;
    koreksi_typo_count: number;
    istilah_tanaman_lokal_count: number;
    deteksi_query_tidak_relevan: boolean;
    sinonim_samples: Array<{ istilah: string; ekspansi: string }>;
    lokal_samples: Array<{ lokal: string; standar: string }>;
    typo_samples: Array<{ typo: string; koreksi: string }>;
  };
  index_metadata: {
    source_count: number;
    recipe_count?: number;
    froti_recipe_count?: number;
    source_ids: string[];
    recipe_codes?: string[];
    corpus_sha256: string;
    sklearn_version: string;
    tfidf_ready: boolean;
    recipe_tfidf_ready?: boolean;
    semantic_model_name: string;
    semantic_embeddings_present: boolean;
    semantic_embeddings_shape: number[] | null;
    recipe_semantic_embeddings_present?: boolean;
    recipe_semantic_embeddings_shape?: number[] | null;
    gemini_configured?: boolean;
    semantic_available: boolean;
    semantic_status: string;
    semantic_reason: string;
  };
  functional_test_queries: Array<{
    id: string;
    category: string;
    query: string;
    expected_behavior: string;
  }>;
  import_report_summary: Record<string, unknown> | null;
}


async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    let errMsg = `Permintaan gagal (${response.status})`;
    try {
      const errBody = await response.json();
      if (errBody && typeof errBody.detail === 'string') {
        errMsg = errBody.detail;
      }
    } catch {
      // ignore parse error
    }
    const err = new Error(errMsg) as Error & { status?: number };
    err.status = response.status;
    throw err;
  }

  return response.json() as Promise<T>;
}

export function fetchStats(): Promise<StatsData> {
  return fetchJson<StatsData>('/api/stats');
}

export function fetchSpeciesList(params: {
  q?: string;
  family?: string;
  letter?: string;
  filter_mode?: string;
  page?: number;
  per_page?: number;
  sort?: string;
}): Promise<PlantListResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.family) sp.set('family', params.family);
  if (params.letter) sp.set('letter', params.letter);
  if (params.filter_mode && params.filter_mode !== 'all') {
    sp.set('filter_mode', params.filter_mode);
  }
  if (params.page) sp.set('page', String(params.page));
  if (params.per_page) sp.set('per_page', String(params.per_page));
  if (params.sort) sp.set('sort', params.sort);

  const qs = sp.toString();
  return fetchJson<PlantListResponse>(`/api/species${qs ? `?${qs}` : ''}`);
}

export function fetchSpeciesDetail(slug: string): Promise<PlantDetailData> {
  return fetchJson<PlantDetailData>(`/api/species/${encodeURIComponent(slug)}`);
}

export function fetchRecipesList(params: {
  q?: string;
  keluhan?: string;
  age_group?: string;
}): Promise<RecipeListResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.keluhan) sp.set('keluhan', params.keluhan);
  if (params.age_group) sp.set('age_group', params.age_group);
  const qs = sp.toString();
  return fetchJson<RecipeListResponse>(`/api/recipes${qs ? `?${qs}` : ''}`);
}

export function searchRecipes(q: string, age_group?: string): Promise<RecipeListResponse> {
  const sp = new URLSearchParams();
  if (q) sp.set('q', q);
  if (age_group) sp.set('age_group', age_group);
  const qs = sp.toString();
  return fetchJson<RecipeListResponse>(`/api/recipes/search${qs ? `?${qs}` : ''}`);
}

export function fetchRecipeDetail(slug: string, age_group?: string): Promise<RecipeDetailData> {
  const sp = new URLSearchParams();
  if (age_group) sp.set('age_group', age_group);
  const qs = sp.toString();
  return fetchJson<RecipeDetailData>(
    `/api/recipes/${encodeURIComponent(slug)}${qs ? `?${qs}` : ''}`,
  );
}

export function fetchKnowledgeList(params: {
  q?: string;
  topic?: string;
  review_filter?: string;
  page?: number;
  per_page?: number;
}): Promise<KnowledgeListResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.topic) sp.set('topic', params.topic);
  if (params.review_filter && params.review_filter !== 'all') {
    sp.set('review_filter', params.review_filter);
  }
  if (params.page) sp.set('page', String(params.page));
  if (params.per_page) sp.set('per_page', String(params.per_page));

  const qs = sp.toString();
  return fetchJson<KnowledgeListResponse>(`/api/knowledge${qs ? `?${qs}` : ''}`);
}

export function fetchSourcesList(params: {
  q?: string;
  topic?: string;
}): Promise<SourceListResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.topic) sp.set('topic', params.topic);

  const qs = sp.toString();
  return fetchJson<SourceListResponse>(`/api/sources${qs ? `?${qs}` : ''}`);
}

export function executeSmartSearch(payload: {
  query: string;
  mode: 'tfidf' | 'semantic';
  top_k: number;
  age_group?: string;
  durasi_keluhan?: string;
  vulnerable_flags?: string[];
  obat_rutin?: string;
  use_gemini?: boolean;
}): Promise<SearchResponse> {
  return fetchJson<SearchResponse>('/api/search', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchEvaluationDetails(): Promise<EvaluationDetailsResponse> {
  return fetchJson<EvaluationDetailsResponse>('/api/evaluation');
}

export function computeEvaluationWithAnnotations(payload: {
  annotations: Array<{ id_uji: string; gold_relevant_ids: string }>;
  save_to_csv?: boolean;
}): Promise<NlpBenchmark30Response> {
  return fetchJson<NlpBenchmark30Response>('/api/evaluation/compute', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getEdaImageUrl(): string {
  return `${API_BASE_URL}/api/artifacts/eda-image`;
}

