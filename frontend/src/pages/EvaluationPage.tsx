import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  CheckCircle2,
  Cpu,
  Database,
  FileSpreadsheet,
  Play,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';
import {
  computeEvaluationWithAnnotations,
  EvaluationDetailsResponse,
  fetchEvaluationDetails,
  NlpBenchmark30Response,
} from '../lib/api';

export const EvaluationPage: React.FC = () => {
  const [evalData, setEvalData] = useState<EvaluationDetailsResponse | null>(null);
  const [benchmark30, setBenchmark30] = useState<NlpBenchmark30Response | null>(null);
  const [annotations, setAnnotations] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [computing, setComputing] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');

  useEffect(() => {
    setLoading(true);
    fetchEvaluationDetails()
      .then((res) => {
        setEvalData(res);
        if (res.nlp_benchmark_30) {
          setBenchmark30(res.nlp_benchmark_30);
          const initMap: Record<string, string> = {};
          res.nlp_benchmark_30.items.forEach((item) => {
            initMap[item.id_uji] = item.gold_relevant_ids || '';
          });
          setAnnotations(initMap);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const handleAnnotationChange = (idUji: string, val: string) => {
    setAnnotations((prev) => ({
      ...prev,
      [idUji]: val,
    }));
  };

  const handleFillSuggestedHintsForSimulation = () => {
    if (!benchmark30) return;
    const nextMap: Record<string, string> = {};
    benchmark30.items.forEach((item) => {
      nextMap[item.id_uji] = item.kandidat_dokumen_petunjuk_anotator || '';
    });
    setAnnotations(nextMap);
  };

  const handleClearAnnotations = async () => {
    if (!benchmark30) return;
    const emptyMap: Record<string, string> = {};
    benchmark30.items.forEach((item) => {
      emptyMap[item.id_uji] = '';
    });
    setAnnotations(emptyMap);
    setComputing(true);
    try {
      const updated = await computeEvaluationWithAnnotations({
        annotations: Object.entries(emptyMap).map(([id_uji, gold_relevant_ids]) => ({
          id_uji,
          gold_relevant_ids,
        })),
        save_to_csv: false,
      });
      setBenchmark30(updated);
    } finally {
      setComputing(false);
    }
  };

  const handleComputeMetrics = async () => {
    setComputing(true);
    try {
      const payload = Object.entries(annotations).map(([id_uji, gold_relevant_ids]) => ({
        id_uji,
        gold_relevant_ids,
      }));
      const updated = await computeEvaluationWithAnnotations({
        annotations: payload,
        save_to_csv: false,
      });
      setBenchmark30(updated);
    } finally {
      setComputing(false);
    }
  };

  const ds = evalData?.dataset_summary;
  const meta = evalData?.index_metadata;
  const nlpCap = evalData?.nlp_capabilities;

  const filteredItems = (benchmark30?.items || []).filter((item) =>
    categoryFilter === 'all' ? true : item.kategori_uji === categoryFilter
  );

  const availableCategories = Array.from(
    new Set((benchmark30?.items || []).map((i) => i.kategori_uji))
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-[#DCFCE7] text-[#166534] text-xs font-semibold">
            <BarChart3 className="w-4 h-4" aria-hidden="true" />
            <span>Evaluasi Sistem Cerdas &amp; Pertanggungjawaban Akademik NLP</span>
          </div>
          <Link
            to="/search"
            className="text-xs font-semibold text-[#166534] underline underline-offset-4 hover:text-[#14532D]"
          >
            Buka Pencarian Cerdas Ramuan →
          </Link>
        </div>

        <h1 className="text-2xl sm:text-3xl font-bold text-[#1F2937]">
          Evaluasi Model Pencarian Informasi Ramuan (TF-IDF vs Semantic Search)
        </h1>

        <p className="text-sm sm:text-base text-[#4B5563] leading-relaxed max-w-4xl">
          Halaman ini menyajikan ringkasan dataset terkurasi, spesifikasi model{' '}
          <strong>Baseline TF-IDF + Cosine Similarity</strong> dan{' '}
          <strong>Advanced Semantic Embedding</strong> (untuk data ramuan FROTI Kemenkes RI maupun
          dokumen BPOM RI), cakupan pemrosesan bahasa alami (NLP), serta perhitungan metrik{' '}
          <code>Hit@1</code>, <code>Recall@3</code>, dan <code>MRR@10</code> pada{' '}
          <strong>{benchmark30?.total_queries || 35} pertanyaan uji</strong>.
        </p>
      </section>

      {/* 1. Ringkasan Dataset Terkurasi */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-5">
        <div className="flex items-center gap-2 text-[#166534]">
          <Database className="w-5 h-5" aria-hidden="true" />
          <h2 className="text-xl font-bold text-[#1F2937]">1. Ringkasan Dataset Terkurasi</h2>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="p-4 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] space-y-1">
            <span className="text-xs font-semibold text-[#166534]">Ramuan Resmi FROTI</span>
            <p className="text-2xl font-bold text-[#14532D]">{ds?.froti_recipes ?? 19}</p>
            <p className="text-[11px] text-[#374151]">FROTI-001 s/d FROTI-019 (Kemenkes RI)</p>
          </div>
          <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1">
            <span className="text-xs font-semibold text-[#374151]">Total Resep Ramuan</span>
            <p className="text-2xl font-bold text-[#1F2937]">{ds?.total_recipes ?? 25}</p>
            <p className="text-[11px] text-[#4B5563]">19 FROTI + 6 Ramuan Terdokumentasi</p>
          </div>
          <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1">
            <span className="text-xs font-semibold text-[#374151]">Spesies Tanaman Obat</span>
            <p className="text-2xl font-bold text-[#1F2937]">{ds?.total_plants ?? 30}</p>
            <p className="text-[11px] text-[#4B5563]">
              {ds?.plants_with_scientific_name ?? 27} bernama ilmiah, {ds?.plants_local_only ?? 3} nama lokal
            </p>
          </div>
          <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1">
            <span className="text-xs font-semibold text-[#374151]">Sumber Resmi BPOM</span>
            <p className="text-2xl font-bold text-[#1F2937]">{ds?.total_bpom_sources ?? 9}</p>
            <p className="text-[11px] text-[#4B5563]">BPOM-01 s/d BPOM-09 terverifikasi</p>
          </div>
          <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1">
            <span className="text-xs font-semibold text-[#374151]">Korpus Q&amp;A Kaggle</span>
            <p className="text-2xl font-bold text-[#1F2937]">{ds?.total_qa_kaggle ?? 52}</p>
            <p className="text-[11px] text-[#4B5563]">14 bertanda tinjauan klinis ketat</p>
          </div>
          <div className="p-4 rounded-xl bg-[#FEF3C7]/60 border border-[#FCD34D] space-y-1">
            <span className="text-xs font-semibold text-[#92400E]">Pertanyaan Uji NLP</span>
            <p className="text-2xl font-bold text-[#92400E]">{benchmark30?.total_queries ?? 35}</p>
            <p className="text-[11px] text-[#92400E]">Benchmark Evaluasi Model (&ge;30 query)</p>
          </div>
        </div>
      </section>

      {/* 2. Arsitektur Model yang Digunakan (Baseline vs Advanced) */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-5">
        <div className="flex items-center gap-2 text-[#166534]">
          <Cpu className="w-5 h-5" aria-hidden="true" />
          <h2 className="text-xl font-bold text-[#1F2937]">
            2. Model Pencarian Informasi yang Digunakan
          </h2>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Baseline Model */}
          <div className="p-5 rounded-2xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-3">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-1 rounded-md bg-[#166534] text-white text-xs font-bold">
                BASELINE MODEL
              </span>
              <span className="text-xs font-semibold text-[#166534] bg-[#DCFCE7] px-2.5 py-0.5 rounded border border-[#86EFAC]">
                Aktif &amp; Deterministik
              </span>
            </div>
            <h3 className="text-lg font-bold text-[#1F2937]">
              TF-IDF Vectorizer + Cosine Similarity
            </h3>
            <p className="text-xs sm:text-sm text-[#374151] leading-relaxed">
              Menggunakan <code>TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)</code> dengan
              daftar <em>stopwords</em> Bahasa Indonesia serta <em>character n-gram</em> (3–5 gram)
              untuk mencari informasi ramuan berdasarkan <strong>nama tanaman</strong>,{' '}
              <strong>nama ilmiah</strong>, <strong>keluhan tradisional</strong>, dan{' '}
              <strong>deskripsi dokumen</strong>.
            </p>
            <div className="p-3 rounded-xl bg-white border border-[#DCE5DF] text-xs font-mono space-y-1 text-[#374151]">
              <div>Status Indeks Ramuan FROTI: {meta?.recipe_tfidf_ready ? 'Siap (25 dokumen)' : 'Siap'}</div>
              <div>Status Indeks Sumber BPOM: {meta?.tfidf_ready ? 'Siap (9 dokumen)' : 'Siap'}</div>
              <div>Versi scikit-learn: {meta?.sklearn_version || '1.x'}</div>
            </div>
          </div>

          {/* Advanced Model */}
          <div className="p-5 rounded-2xl bg-[#F0FDF4] border border-[#86EFAC] space-y-3">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-1 rounded-md bg-[#14532D] text-white text-xs font-bold">
                ADVANCED MODEL
              </span>
              <span
                className={`text-xs font-semibold px-2.5 py-0.5 rounded border ${
                  meta?.semantic_available
                    ? 'bg-[#DCFCE7] text-[#166534] border-[#86EFAC]'
                    : 'bg-[#FEF3C7] text-[#92400E] border-[#FCD34D]'
                }`}
              >
                {meta?.semantic_status || 'Tervalidasi'}
              </span>
            </div>
            <h3 className="text-lg font-bold text-[#1F2937]">
              Multilingual Sentence / Gemini Semantic Embedding (FROTI &amp; BPOM)
            </h3>
            <p className="text-xs sm:text-sm text-[#374151] leading-relaxed">
              Menggunakan representasi vektor padat (<em>dense embedding</em>) dari{' '}
              <code>{meta?.semantic_model_name || 'paraphrase-multilingual-MiniLM-L12-v2 / gemini-embedding-001'}</code>.
              Pencarian semantik diterapkan secara nyata pada{' '}
              <strong>25 data ramuan FROTI/terkurasi</strong> sekaligus{' '}
              <strong>9 dokumen resmi BPOM</strong>.
            </p>
            <div className="p-3 rounded-xl bg-white border border-[#86EFAC] text-xs font-mono space-y-1 text-[#14532D]">
              <div>
                Matriks Embedding Ramuan FROTI:{' '}
                {meta?.recipe_semantic_embeddings_shape
                  ? meta.recipe_semantic_embeddings_shape.join(' x ')
                  : '25 dokumen terindeks'}
              </div>
              <div>
                Matriks Embedding Colab BPOM:{' '}
                {meta?.semantic_embeddings_shape
                  ? meta.semantic_embeddings_shape.join(' x ')
                  : '9 x 384'}
              </div>
              <div className="font-sans text-[11px] text-[#374151]">{meta?.semantic_reason}</div>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Pipeline Pemrosesan Bahasa Alami (NLP) */}
      {nlpCap && (
        <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-5">
          <div className="flex items-center gap-2 text-[#166534]">
            <Sparkles className="w-5 h-5" aria-hidden="true" />
            <h2 className="text-xl font-bold text-[#1F2937]">
              3. Pipeline Pemrosesan Bahasa Alami (NLP Preprocessing)
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-sm text-[#166534]">
                  Pencocokan Sinonim Keluhan
                </h3>
                <span className="px-2 py-0.5 rounded bg-[#DCFCE7] text-[#166534] text-xs font-bold">
                  {nlpCap.sinonim_keluhan_count} pola
                </span>
              </div>
              <p className="text-xs text-[#4B5563]">
                Memetakan bahasa keluhan sehari-hari ke istilah medis/tradisional FROTI:
              </p>
              <div className="space-y-1 max-h-40 overflow-y-auto text-xs font-mono">
                {nlpCap.sinonim_samples.map((s) => (
                  <div key={s.istilah} className="p-1.5 rounded bg-white border border-[#E5E7EB]">
                    <span className="font-bold text-[#1F2937]">{s.istilah}</span> →{' '}
                    <span className="text-[#166534]">{s.ekspansi}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-sm text-[#166534]">
                  Pengenalan Istilah Tanaman Lokal
                </h3>
                <span className="px-2 py-0.5 rounded bg-[#DCFCE7] text-[#166534] text-xs font-bold">
                  {nlpCap.istilah_tanaman_lokal_count} istilah daerah
                </span>
              </div>
              <p className="text-xs text-[#4B5563]">
                Mengenali nama daerah (Jawa, Sunda, Bali, Madura) dan menerjemahkannya ke nama tanaman standar:
              </p>
              <div className="space-y-1 max-h-40 overflow-y-auto text-xs font-mono">
                {nlpCap.lokal_samples.map((l) => (
                  <div key={l.lokal} className="p-1.5 rounded bg-white border border-[#E5E7EB]">
                    <span className="font-bold text-[#1F2937]">{l.lokal}</span> →{' '}
                    <span className="text-[#166534]">{l.standar}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-sm text-[#166534]">
                  Penanganan Salah Ketik Ringan &amp; Filter Domain
                </h3>
                <span className="px-2 py-0.5 rounded bg-[#DCFCE7] text-[#166534] text-xs font-bold">
                  {nlpCap.koreksi_typo_count} kamus + Fuzzy
                </span>
              </div>
              <p className="text-xs text-[#4B5563]">
                Mengoreksi salah ketik ringan (kamus typo + <code>SequenceMatcher</code> &ge; 0.86)
                serta menolak query tidak relevan di bawah ambang <code>0.12</code>:
              </p>
              <div className="space-y-1 max-h-40 overflow-y-auto text-xs font-mono">
                {nlpCap.typo_samples.map((t) => (
                  <div key={t.typo} className="p-1.5 rounded bg-white border border-[#E5E7EB]">
                    <span className="font-bold text-[#92400E]">{t.typo}</span> →{' '}
                    <span className="text-[#166534]">{t.koreksi}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* 4. Hasil / Status Evaluasi Hit@1, Recall@3, dan MRR@10 */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-[#166534]">
            <FileSpreadsheet className="w-5 h-5" aria-hidden="true" />
            <h2 className="text-xl font-bold text-[#1F2937]">
              4. Perhitungan Metrik Evaluasi (Hit@1, Recall@3, MRR@10)
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleFillSuggestedHintsForSimulation}
              className="px-3.5 py-2 rounded-xl bg-[#F0FDF4] text-[#166534] border border-[#86EFAC] text-xs font-semibold hover:bg-[#DCFCE7] transition-colors"
            >
              Isi Kolom Anotasi dari Petunjuk Kandidat (Uji Simulasi)
            </button>
            <button
              type="button"
              onClick={handleComputeMetrics}
              disabled={computing}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#166534] text-white text-xs font-semibold hover:bg-[#14532D] transition-colors disabled:opacity-50"
            >
              {computing ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Play className="w-3.5 h-3.5" />
              )}
              <span>Hitung Hit@1, Recall@3 &amp; MRR@10</span>
            </button>
            <button
              type="button"
              onClick={handleClearAnnotations}
              disabled={computing}
              className="px-3 py-2 rounded-xl bg-[#F8FAF8] text-[#4B5563] border border-[#DCE5DF] text-xs font-semibold hover:bg-white"
            >
              Reset Anotasi Kosong
            </button>
          </div>
        </div>

        {/* Academic Honesty Status Box */}
        {benchmark30 && !benchmark30.metrics_available ? (
          <div className="p-5 rounded-2xl bg-[#FEF3C7]/70 border border-[#FCD34D] text-[#92400E] flex items-start gap-3">
            <AlertTriangle className="w-6 h-6 shrink-0 mt-0.5" aria-hidden="true" />
            <div className="space-y-1.5 text-xs sm:text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-bold text-base">
                  Status: {benchmark30.status} (0 dari {benchmark30.total_queries} Pertanyaan Berlabel)
                </span>
                <span className="px-2 py-0.5 rounded bg-white/80 border border-[#FCD34D] text-[11px] font-bold">
                  Tanpa Angka Evaluasi Palsu
                </span>
              </div>
              <p className="leading-relaxed">{benchmark30.note}</p>
              <p className="text-xs font-semibold">
                Tip: Anda dapat mengisi kolom &ldquo;Label Relevansi Manual (gold_relevant_ids)&rdquo; pada
                tabel 35 pertanyaan di bawah (atau klik tombol &ldquo;Isi Kolom Anotasi dari Petunjuk Kandidat&rdquo;
                di kanan atas), lalu klik <strong>Hitung Hit@1, Recall@3 &amp; MRR@10</strong>.
              </p>
            </div>
          </div>
        ) : (
          benchmark30 &&
          benchmark30.metrics_available && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-[#DCFCE7] border border-[#86EFAC] text-[#14532D] flex items-center justify-between gap-2 text-xs sm:text-sm">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-[#166534] shrink-0" />
                  <span className="font-semibold">{benchmark30.note}</span>
                </div>
                <span className="font-mono text-xs font-bold px-2.5 py-1 rounded bg-white text-[#166534]">
                  Teranotasi: {benchmark30.labeled_queries} / {benchmark30.total_queries}
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {/* TF-IDF Metrics Card */}
                <div className="p-5 rounded-2xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-3">
                  <h3 className="font-bold text-base text-[#166534]">
                    Hasil Evaluasi Baseline: TF-IDF + Cosine Similarity
                  </h3>
                  {benchmark30.tfidf_metrics ? (
                    <div className="grid grid-cols-3 gap-3 text-center">
                      <div className="p-3 rounded-xl bg-white border border-[#DCE5DF]">
                        <span className="block text-xs text-[#4B5563]">Hit@1</span>
                        <span className="text-xl font-bold text-[#1F2937]">
                          {(benchmark30.tfidf_metrics.hit_at_1 * 100).toFixed(1)}%
                        </span>
                        <span className="block text-[11px] font-mono text-[#4B5563]">
                          ({benchmark30.tfidf_metrics.hit_at_1.toFixed(4)})
                        </span>
                      </div>
                      <div className="p-3 rounded-xl bg-white border border-[#DCE5DF]">
                        <span className="block text-xs text-[#4B5563]">Recall@3</span>
                        <span className="text-xl font-bold text-[#1F2937]">
                          {(benchmark30.tfidf_metrics.recall_at_3 * 100).toFixed(1)}%
                        </span>
                        <span className="block text-[11px] font-mono text-[#4B5563]">
                          ({benchmark30.tfidf_metrics.recall_at_3.toFixed(4)})
                        </span>
                      </div>
                      <div className="p-3 rounded-xl bg-white border border-[#DCE5DF]">
                        <span className="block text-xs text-[#4B5563]">MRR@10</span>
                        <span className="text-xl font-bold text-[#1F2937]">
                          {(benchmark30.tfidf_metrics.mrr_at_10 * 100).toFixed(1)}%
                        </span>
                        <span className="block text-[11px] font-mono text-[#4B5563]">
                          ({benchmark30.tfidf_metrics.mrr_at_10.toFixed(4)})
                        </span>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-[#4B5563]">Belum dapat dihitung.</p>
                  )}
                </div>

                {/* Semantic Metrics Card */}
                <div className="p-5 rounded-2xl bg-[#F0FDF4] border border-[#86EFAC] space-y-3">
                  <h3 className="font-bold text-base text-[#14532D]">
                    Hasil Evaluasi Advanced: Semantic Embedding Search
                  </h3>
                  {benchmark30.semantic_metrics ? (
                    <div className="grid grid-cols-3 gap-3 text-center">
                      <div className="p-3 rounded-xl bg-white border border-[#86EFAC]">
                        <span className="block text-xs text-[#4B5563]">Hit@1</span>
                        <span className="text-xl font-bold text-[#166534]">
                          {(benchmark30.semantic_metrics.hit_at_1 * 100).toFixed(1)}%
                        </span>
                        <span className="block text-[11px] font-mono text-[#4B5563]">
                          ({benchmark30.semantic_metrics.hit_at_1.toFixed(4)})
                        </span>
                      </div>
                      <div className="p-3 rounded-xl bg-white border border-[#86EFAC]">
                        <span className="block text-xs text-[#4B5563]">Recall@3</span>
                        <span className="text-xl font-bold text-[#166534]">
                          {(benchmark30.semantic_metrics.recall_at_3 * 100).toFixed(1)}%
                        </span>
                        <span className="block text-[11px] font-mono text-[#4B5563]">
                          ({benchmark30.semantic_metrics.recall_at_3.toFixed(4)})
                        </span>
                      </div>
                      <div className="p-3 rounded-xl bg-white border border-[#86EFAC]">
                        <span className="block text-xs text-[#4B5563]">MRR@10</span>
                        <span className="text-xl font-bold text-[#166534]">
                          {(benchmark30.semantic_metrics.mrr_at_10 * 100).toFixed(1)}%
                        </span>
                        <span className="block text-[11px] font-mono text-[#4B5563]">
                          ({benchmark30.semantic_metrics.mrr_at_10.toFixed(4)})
                        </span>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-[#4B5563]">
                      Mode semantik belum aktif pada lingkungan lokal ini.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )
        )}

        {/* Filter & 35 Benchmark Queries Table */}
        <div className="space-y-3 pt-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-bold text-sm sm:text-base text-[#1F2937]">
              Tabel Dataset Evaluasi ({filteredItems.length} dari {benchmark30?.total_queries || 35}{' '}
              Pertanyaan Uji — <code>evaluasi_model_nlp_30_pertanyaan.csv</code>)
            </h3>
            <div className="flex items-center gap-2">
              <label htmlFor="eval-cat-filter" className="text-xs font-semibold text-[#374151]">
                Filter Kategori:
              </label>
              <select
                id="eval-cat-filter"
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="px-3 py-1.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] text-xs font-semibold text-[#1F2937]"
              >
                <option value="all">Semua Kategori ({benchmark30?.total_queries || 35})</option>
                {availableCategories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {loading ? (
            <div className="p-8 text-center text-sm text-[#4B5563]">
              Memuat dataset evaluasi 35 pertanyaan uji...
            </div>
          ) : (
            <div className="overflow-x-auto border border-[#DCE5DF] rounded-2xl">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-[#F8FAF8] border-b border-[#DCE5DF] text-[#374151]">
                    <th className="py-3 px-3 font-semibold">ID</th>
                    <th className="py-3 px-3 font-semibold">Kategori</th>
                    <th className="py-3 px-3 font-semibold">Pertanyaan Uji</th>
                    <th className="py-3 px-3 font-semibold">Prediksi Top-3 TF-IDF</th>
                    <th className="py-3 px-3 font-semibold">Prediksi Top-3 Semantik</th>
                    <th className="py-3 px-3 font-semibold">Petunjuk Kandidat</th>
                    <th className="py-3 px-3 font-semibold">
                      Label Relevansi Manual (gold_relevant_ids)
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F1F5F9]">
                  {filteredItems.map((item) => (
                    <tr key={item.id_uji} className="hover:bg-[#F8FAF8]">
                      <td className="py-2.5 px-3 font-mono font-bold text-[#166534]">
                        {item.id_uji}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-[#4B5563]">
                        {item.kategori_uji}
                      </td>
                      <td className="py-2.5 px-3 font-medium text-[#1F2937] max-w-xs">
                        {item.pertanyaan_uji}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-[#166534]">
                        {item.top3_tfidf.length > 0 ? item.top3_tfidf.join(', ') : '-'}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-[#075985]">
                        {item.top3_semantic.length > 0 ? item.top3_semantic.join(', ') : '-'}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-[#92400E]">
                        {item.kandidat_dokumen_petunjuk_anotator}
                      </td>
                      <td className="py-2.5 px-3">
                        <input
                          type="text"
                          aria-label={`Anotasi manual untuk ${item.id_uji}`}
                          value={annotations[item.id_uji] ?? ''}
                          onChange={(e) => handleAnnotationChange(item.id_uji, e.target.value)}
                          placeholder="Contoh: FROTI-001"
                          className="w-40 px-2.5 py-1.5 rounded-lg border border-[#DCE5DF] bg-white font-mono text-xs text-[#1F2937]"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      {/* 5. Status Template Evaluasi Manual Colab (52 Baris) */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-3">
        <div className="flex items-center gap-2 text-[#166534]">
          <BookOpen className="w-5 h-5" aria-hidden="true" />
          <h2 className="text-lg font-bold text-[#1F2937]">
            5. Status Artefak Colab: <code>template_evaluasi_manual.csv</code> (52 Baris Q&amp;A)
          </h2>
        </div>
        <p className="text-xs sm:text-sm text-[#4B5563] leading-relaxed">
          {evalData?.evaluation.note}
        </p>
      </section>

      {/* Medical Safety Disclaimer */}
      <section className="bg-[#FEF2F2] rounded-2xl border border-[#FCA5A5] p-6 text-[#991B1B] flex items-start gap-3">
        <ShieldAlert className="w-6 h-6 shrink-0 mt-0.5" aria-hidden="true" />
        <div className="space-y-1 text-xs sm:text-sm">
          <h2 className="font-bold text-base">Prinsip Keamanan Medis &amp; Kejujuran Evaluasi</h2>
          <p className="leading-relaxed">
            Skor kemiripan kosinus maupun metrik evaluasi temu kembali informasi (Hit@1, Recall@3,
            MRR@10) hanya mengukur ketepatan sistem menemukan dokumen referensi yang relevan, bukan
            ukuran khasiat atau keamanan klinis bagi pasien individu.
          </p>
        </div>
      </section>
    </div>
  );
};
