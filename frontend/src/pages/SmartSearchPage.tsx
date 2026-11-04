import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  BookOpen,
  Clock,
  ExternalLink,
  FileCheck2,
  FlaskConical,
  History,
  Info,
  Pill,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Sprout,
  Stethoscope,
  Trash2,
  Users,
} from 'lucide-react';
import {
  AGE_GROUP_OPTIONS,
  executeSmartSearch,
  fetchStats,
  SearchResponse,
  StatsData,
} from '../lib/api';

const PRIMARY_EXAMPLE_QUERIES = [
  'Saya sedang batuk berdahak.',
  'Saya sering merasa perut kembung.',
  'Tenggorokan saya terasa sakit.',
  'Saya sedang mengalami nyeri haid.',
  'Informasi ramuan untuk demam',
  'Sakit kepala sebelah kencur atau teh',
  'Nafsu makan berkurang daun pepaya',
  'Terkilir kencur dan lengkuas',
];

const QUICK_SYMPTOM_CHIPS = [
  { label: 'Demam (FROTI-001 Sambiloto)', query: 'Saya demam, ada informasi ramuan tradisional sambiloto?' },
  { label: 'Sakit Kepala Sebelah (FROTI-002/003)', query: 'Sakit kepala sebelah kencur dan pucuk daun teh' },
  { label: 'Sakit Tenggorokan (FROTI-004 Sirih)', query: 'Sakit tenggorokan kumur daun sirih' },
  { label: 'Batuk Berdahak (FROTI-005/006/007)', query: 'Batuk berdahak herba timi akar manis buah adas' },
  { label: 'Leher Kaku & Masuk Angin (FROTI-008/017)', query: 'Leher kaku dan masuk angin rimpang jahe' },
  { label: 'Terkilir (FROTI-009/010)', query: 'Terkilir rimpang kencur dan lengkuas' },
  { label: 'Panas Dalam (FROTI-011/012)', query: 'Panas dalam akar alang-alang dan daun cincau' },
  { label: 'Nafsu Makan (FROTI-013/014)', query: 'Nafsu makan berkurang temu hitam dan daun pepaya' },
  { label: 'Perut Kembung & Lambung (FROTI-015/016)', query: 'Perut kembung kunyit dan gangguan lambung jahe' },
  { label: 'Nyeri Haid & Siklus Haid (FROTI-018/019)', query: 'Nyeri haid kayu manis dan haid tidak teratur daun andong' },
  { label: 'Keamanan & Perbedaan Jamu/Fitofarmaka', query: 'Apa perbedaan jamu dengan fitofarmaka dan interaksi obat?' },
  { label: 'Uji Pengaman Ibu Hamil', query: 'Saya sedang hamil, berapa dosis jamu?' },
];

const SESSION_HISTORY_KEY = 'herb_info_ephemeral_search_history';

function highlightMatchedText(text: string, matchedTerms: string[]): React.ReactNode {
  if (!matchedTerms || matchedTerms.length === 0) return text;
  const escaped = matchedTerms
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .filter(Boolean);
  if (escaped.length === 0) return text;

  const regex = new RegExp(`\\b(${escaped.join('|')})\\b`, 'gi');
  const parts = text.split(regex);
  const lowerSet = new Set(matchedTerms.map((t) => t.toLowerCase()));

  return parts.map((part, idx) =>
    lowerSet.has(part.toLowerCase()) ? (
      <mark
        key={idx}
        className="bg-[#DCFCE7] text-[#166534] font-semibold px-1 rounded"
      >
        {part}
      </mark>
    ) : (
      <React.Fragment key={idx}>{part}</React.Fragment>
    )
  );
}

export const SmartSearchPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || '';
  const initialAge = searchParams.get('age_group') || 'dewasa_18_59_tahun';

  const [query, setQuery] = useState(initialQuery);
  const [mode, setMode] = useState<'tfidf' | 'semantic'>('tfidf');
  const [topK, setTopK] = useState<number>(3);
  const [ageGroup, setAgeGroup] = useState<string>(initialAge);
  const [durasiKeluhan, setDurasiKeluhan] = useState<string>('');
  const [obatRutin, setObatRutin] = useState<string>('');
  const [vulnerableFlags, setVulnerableFlags] = useState<string[]>([]);
  const [useGemini, setUseGemini] = useState<boolean>(true);
  const [stats, setStats] = useState<StatsData | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>(() => {
    try {
      const raw = sessionStorage.getItem(SESSION_HISTORY_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(() => {
        // non-blocking metadata load
      });
  }, []);

  const saveToSessionHistory = (qText: string) => {
    const clean = qText.trim();
    if (!clean) return;
    setHistory((prev) => {
      const next = [clean, ...prev.filter((item) => item !== clean)].slice(0, 6);
      try {
        sessionStorage.setItem(SESSION_HISTORY_KEY, JSON.stringify(next));
      } catch {
        // ignore storage errors
      }
      return next;
    });
  };

  const clearSessionHistory = () => {
    setHistory([]);
    try {
      sessionStorage.removeItem(SESSION_HISTORY_KEY);
    } catch {
      // ignore
    }
  };

  const toggleVulnerableFlag = (flag: string) => {
    setVulnerableFlags((prev) => {
      const next = prev.includes(flag)
        ? prev.filter((item) => item !== flag)
        : [...prev, flag];
      if (query.trim()) {
        runSearch(query, mode, topK, ageGroup, next, durasiKeluhan, obatRutin, useGemini);
      }
      return next;
    });
  };

  const runSearch = useCallback(
    async (
      qToRun: string,
      modeToUse: 'tfidf' | 'semantic',
      kToUse: number,
      ageToUse: string,
      vFlagsToUse: string[],
      durasiToUse: string = '',
      obatToUse: string = '',
      geminiToUse: boolean = true
    ) => {
      setLoading(true);
      setError(null);
      try {
        const res = await executeSmartSearch({
          query: qToRun,
          mode: modeToUse,
          top_k: kToUse,
          age_group: ageToUse,
          durasi_keluhan: durasiToUse.trim() || undefined,
          vulnerable_flags: vFlagsToUse,
          obat_rutin: obatToUse.trim() || undefined,
          use_gemini: geminiToUse,
        });
        setResult(res);
        if (qToRun.trim()) {
          saveToSessionHistory(qToRun);
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Terjadi kesalahan saat memproses pencarian cerdas.'
        );
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (initialQuery) {
      setQuery(initialQuery);
      runSearch(
        initialQuery,
        mode,
        topK,
        ageGroup,
        vulnerableFlags,
        durasiKeluhan,
        obatRutin,
        useGemini
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (trimmed) {
      setSearchParams({ q: trimmed, age_group: ageGroup });
    } else {
      setSearchParams({});
    }
    runSearch(query, mode, topK, ageGroup, vulnerableFlags, durasiKeluhan, obatRutin, useGemini);
  };

  const handleAgeGroupChange = (newAge: string) => {
    setAgeGroup(newAge);
    if (query.trim()) {
      setSearchParams({ q: query.trim(), age_group: newAge });
      runSearch(query, mode, topK, newAge, vulnerableFlags, durasiKeluhan, obatRutin, useGemini);
    }
  };

  const handleExampleClick = (exampleQ: string) => {
    setQuery(exampleQ);
    setSearchParams({ q: exampleQ, age_group: ageGroup });
    runSearch(exampleQ, mode, topK, ageGroup, vulnerableFlags, durasiKeluhan, obatRutin, useGemini);
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header & Search Form */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-[#DCFCE7] text-[#166534] text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" aria-hidden="true" />
            <span>
              HERB-INFO AI — Intelligent Symptom Understanding &amp; Herbal Information Retrieval
            </span>
          </div>
          <span className="px-3 py-1 rounded-lg bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D] text-xs font-bold">
            Takaran dalam referensi tradisional, bukan resep medis pribadi
          </span>
        </div>

        <div className="space-y-2">
          <h1 className="text-2xl sm:text-3xl font-bold text-[#1F2937]">
            Smart Herbal Assistant: Analisis Keluhan &amp; Pencarian Ramuan Tradisional
          </h1>
          <p className="text-sm sm:text-base text-[#4B5563] leading-relaxed">
            Jelaskan keluhan kesehatan menggunakan bahasa Indonesia sehari-hari. Sistem membaca dan
            memahami keluhan, mengenali sinonim &amp; istilah lokal, memeriksa tanda bahaya serta
            aturan keselamatan, lalu menampilkan maksimal 3 referensi ramuan tradisional terkurasi
            dari sumber FROTI Kemenkes RI &amp; BPOM RI.
          </p>
        </div>

        {/* Mode Selector & Short User Condition Clarification Form (Tahap 5) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-1">
          <div className="lg:col-span-5 space-y-2.5">
            <span className="block text-xs font-semibold text-[#374151]">
              Pilih Model Temu Kembali Informasi (Retrieval Model):
            </span>
            <div
              className="grid grid-cols-1 sm:grid-cols-2 gap-2.5"
              role="radiogroup"
              aria-label="Metode pencarian"
            >
              <button
                type="button"
                role="radio"
                aria-checked={mode === 'tfidf'}
                onClick={() => setMode('tfidf')}
                className={`p-3.5 rounded-xl border text-left transition-all ${
                  mode === 'tfidf'
                    ? 'bg-[#F0FDF4] border-[#166534] ring-1 ring-[#166534]'
                    : 'bg-[#F8FAF8] border-[#DCE5DF] hover:bg-white'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-sm text-[#166534]">
                    Model A: TF-IDF + Cosine
                  </span>
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-[#DCFCE7] text-[#166534]">
                    Baseline
                  </span>
                </div>
                <p className="text-xs text-[#4B5563] mt-1">
                  Pencocokan bobot kata &amp; n-gram keluhan terhadap dataset FROTI &amp; BPOM.
                </p>
              </button>

              <button
                type="button"
                role="radio"
                aria-checked={mode === 'semantic'}
                onClick={() => setMode('semantic')}
                className={`p-3.5 rounded-xl border text-left transition-all ${
                  mode === 'semantic'
                    ? 'bg-[#F0FDF4] border-[#166534] ring-1 ring-[#166534]'
                    : 'bg-[#F8FAF8] border-[#DCE5DF] hover:bg-white'
                }`}
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="font-bold text-sm text-[#1F2937]">
                    Model B: Semantic Search
                  </span>
                  <span
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded ${
                      stats?.semantic_available
                        ? 'bg-[#DCFCE7] text-[#166534]'
                        : 'bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D]'
                    }`}
                  >
                    {stats?.semantic_available ? 'Embedding Aktif' : 'Fallback TF-IDF'}
                  </span>
                </div>
                <p className="text-xs text-[#4B5563] mt-1">
                  Memahami kemiripan makna kalimat keluhan dengan dokumen sumber terkurasi.
                </p>
              </button>
            </div>

            <div className="p-3 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] flex items-center justify-between gap-2">
              <label className="inline-flex items-center gap-2 text-xs font-semibold text-[#14532D] cursor-pointer">
                <input
                  type="checkbox"
                  checked={useGemini}
                  onChange={(e) => setUseGemini(e.target.checked)}
                  className="w-4 h-4 rounded accent-[#166534]"
                />
                <span className="flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-[#166534]" />
                  <span>Aktifkan Analisis Cerdas Gemini AI &amp; Sintesis Bukti RAG</span>
                </span>
              </label>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-white text-[#166534] border border-[#86EFAC]">
                Non-Diagnosis
              </span>
            </div>
          </div>

          {/* Tahap 5: Form Singkat Klarifikasi Kondisi Pengguna */}
          <div className="lg:col-span-7 p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-1 border-b border-[#E5E7EB] pb-2">
              <span className="text-xs font-bold text-[#166534] flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Form Singkat Klarifikasi Kondisi Pengguna (Pemeriksaan Keselamatan)</span>
              </span>
              <span className="text-[11px] font-semibold text-[#4B5563]">
                Maks. 3 Referensi Ramuan Teratas
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
              <div className="sm:col-span-5 space-y-1">
                <label
                  htmlFor="search-age-group-select"
                  className="block text-xs font-semibold text-[#374151]"
                >
                  1. Kelompok Usia:
                </label>
                <select
                  id="search-age-group-select"
                  value={ageGroup}
                  onChange={(e) => handleAgeGroupChange(e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-[#DCE5DF] rounded-xl text-xs font-semibold text-[#1F2937] min-h-[38px]"
                >
                  {AGE_GROUP_OPTIONS.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="sm:col-span-3 space-y-1">
                <label
                  htmlFor="search-durasi-input"
                  className="block text-xs font-semibold text-[#374151]"
                >
                  2. Durasi Keluhan:
                </label>
                <input
                  id="search-durasi-input"
                  type="text"
                  value={durasiKeluhan}
                  onChange={(e) => setDurasiKeluhan(e.target.value)}
                  placeholder="Misal: sejak kemarin, 2 hari"
                  className="w-full px-3 py-2 bg-white border border-[#DCE5DF] rounded-xl text-xs text-[#1F2937] min-h-[38px]"
                />
              </div>

              <div className="sm:col-span-4 space-y-1">
                <label
                  htmlFor="search-obat-input"
                  className="block text-xs font-semibold text-[#374151]"
                >
                  3. Obat yang Sedang Digunakan:
                </label>
                <input
                  id="search-obat-input"
                  type="text"
                  value={obatRutin}
                  onChange={(e) => setObatRutin(e.target.value)}
                  placeholder="Misal: warfarin, amlodipin / kosongkan"
                  className="w-full px-3 py-2 bg-white border border-[#DCE5DF] rounded-xl text-xs text-[#1F2937] min-h-[38px]"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-1 border-t border-[#E5E7EB]">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-[11px] font-bold text-[#4B5563]">
                  4. Kondisi Khusus:
                </span>
                <label className="inline-flex items-center gap-1.5 text-xs font-medium text-[#991B1B] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={
                      ageGroup === 'ibu_hamil_menyusui' ||
                      vulnerableFlags.includes('ibu_hamil_menyusui')
                    }
                    onChange={() => toggleVulnerableFlag('ibu_hamil_menyusui')}
                    className="w-3.5 h-3.5 rounded accent-[#991B1B]"
                  />
                  <span>Hamil / Menyusui</span>
                </label>
                <label className="inline-flex items-center gap-1.5 text-xs font-medium text-[#991B1B] cursor-pointer">
                  <input
                    type="checkbox"
                    checked={
                      ageGroup === 'penyakit_kronis_obat_rutin' ||
                      vulnerableFlags.includes('penyakit_kronis_obat_rutin')
                    }
                    onChange={() => toggleVulnerableFlag('penyakit_kronis_obat_rutin')}
                    className="w-3.5 h-3.5 rounded accent-[#991B1B]"
                  />
                  <span>Penyakit Kronis</span>
                </label>
              </div>

              <div className="flex items-center gap-1.5">
                <label htmlFor="search-topk-select" className="text-[11px] font-semibold text-[#374151]">
                  Batas Hasil:
                </label>
                <select
                  id="search-topk-select"
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="px-2 py-1 bg-white border border-[#DCE5DF] rounded-lg text-xs text-[#1F2937]"
                >
                  <option value={3}>Maks 3 Ramuan</option>
                  <option value={5}>Top 5 Dokumen</option>
                  <option value={10}>Top 10 Dokumen</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Search Input Form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="relative">
            <Search
              className="w-5 h-5 text-[#4B5563] absolute left-4 top-4 pointer-events-none"
              aria-hidden="true"
            />
            <input
              type="text"
              maxLength={300}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Contoh: Saya sedang batuk berdahak. / Saya sering merasa perut kembung. / Tenggorokan saya terasa sakit."
              aria-label="Masukkan keluhan kesehatan dengan bahasa sehari-hari"
              className="w-full pl-12 pr-20 py-3.5 bg-[#F8FAF8] border-2 border-[#DCE5DF] rounded-xl text-sm sm:text-base text-[#1F2937] placeholder-[#4B5563] focus:bg-white focus:border-[#166534]"
            />
            <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-xs font-mono text-[#4B5563]">
              {query.length}/300
            </span>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold bg-[#166534] text-white hover:bg-[#14532D] disabled:opacity-60 transition-colors min-h-[44px]"
            >
              <Search className="w-4 h-4" aria-hidden="true" />
              <span>{loading ? 'Menganalisis Keluhan...' : 'Analisis Keluhan'}</span>
            </button>

            <span className="text-xs text-[#4B5563]">
              Sistem bersifat edukatif, bukan alat diagnosis medis, dan tidak menghitung/mengarang dosis usia atau berat badan.
            </span>
          </div>
        </form>

        {/* Clickable Primary Example Queries */}
        <div className="pt-3 border-t border-[#F1F5F9] space-y-2">
          <span className="text-xs font-semibold text-[#166534] flex items-center gap-1.5">
            <FlaskConical className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Contoh Pertanyaan Pencarian Ramuan (Klik untuk Menguji):</span>
          </span>
          <div className="flex flex-wrap gap-2">
            {PRIMARY_EXAMPLE_QUERIES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => handleExampleClick(ex)}
                className="text-xs font-semibold px-3 py-1.5 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] text-[#166534] hover:bg-[#DCFCE7] transition-colors text-left"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>

        {/* Quick FROTI & Symptom Chips */}
        <div className="pt-3 border-t border-[#F1F5F9] space-y-2">
          <span className="text-xs font-semibold text-[#374151] flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-[#166534]" aria-hidden="true" />
            <span>Pintasan Entri Formularium FROTI Kemenkes &amp; Keluhan Tradisional:</span>
          </span>
          <div className="flex flex-wrap gap-2">
            {QUICK_SYMPTOM_CHIPS.map((chip) => (
              <button
                key={chip.label}
                type="button"
                onClick={() => handleExampleClick(chip.query)}
                className="text-xs px-3 py-1.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] text-[#1F2937] hover:bg-[#DCFCE7] hover:text-[#166534] hover:border-[#86EFAC] transition-colors text-left"
              >
                {chip.label}
              </button>
            ))}
          </div>
        </div>

        {/* Ephemeral Session History */}
        {history.length > 0 && (
          <div className="pt-3 border-t border-[#F1F5F9] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#4B5563] mr-1">
                <History className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Riwayat Sesi Lokal:</span>
              </span>
              {history.map((hItem) => (
                <button
                  key={hItem}
                  type="button"
                  onClick={() => handleExampleClick(hItem)}
                  className="text-xs px-2.5 py-1 rounded-lg bg-white border border-[#DCE5DF] text-[#374151] hover:border-[#166534]"
                >
                  {hItem}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={clearSessionHistory}
              className="inline-flex items-center gap-1 text-xs font-semibold text-[#991B1B] hover:underline self-start sm:self-auto"
            >
              <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Hapus Riwayat</span>
            </button>
          </div>
        )}
      </section>

      {/* Error State */}
      {error && (
        <div
          role="alert"
          className="bg-[#FEE2E2] border border-[#FCA5A5] rounded-2xl p-6 text-[#991B1B] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="w-6 h-6 shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <h2 className="font-bold text-base">Pencarian Gagal Diproses</h2>
              <p className="text-sm mt-1">{error}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => runSearch(query, mode, topK, ageGroup, vulnerableFlags, durasiKeluhan, obatRutin, useGemini)}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#991B1B] text-white text-sm font-semibold min-h-[44px]"
          >
            <RefreshCw className="w-4 h-4" aria-hidden="true" />
            <span>Coba Lagi</span>
          </button>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="space-y-4">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              className="bg-white rounded-2xl border border-[#DCE5DF] p-6 h-36 animate-pulse"
            />
          ))}
        </div>
      )}

      {/* Search Results Area */}
      {!loading && result && (
        <section aria-live="polite" className="space-y-6">
          {/* Emergency Warning Banner if Emergency Symptoms Detected */}
          {result.emergency_warning && (
            <div
              role="alert"
              className="bg-[#991B1B] text-white rounded-2xl p-5 sm:p-6 shadow-md flex items-start gap-3"
            >
              <ShieldAlert className="w-7 h-7 shrink-0 mt-0.5" aria-hidden="true" />
              <div className="space-y-1">
                <h2 className="font-bold text-base sm:text-lg">
                  Peringatan Kegawatdaruratan Medis
                </h2>
                <p className="text-sm sm:text-base">{result.emergency_warning}</p>
              </div>
            </div>
          )}

          {/* Vulnerable Group Warning Banner (Infants, Toddlers, Pregnant/Breastfeeding, Elderly, Chronic Illness/Meds) */}
          {(result.is_vulnerable_group || result.requires_professional_advice) && (
            <div
              role="alert"
              className="bg-[#FEE2E2] border-2 border-[#FCA5A5] rounded-2xl p-5 sm:p-6 text-[#991B1B] space-y-2 shadow-sm"
            >
              <div className="flex items-start gap-3">
                <ShieldAlert className="w-6 h-6 shrink-0 mt-0.5" aria-hidden="true" />
                <div className="space-y-1.5">
                  <h2 className="font-bold text-base sm:text-lg">
                    Peringatan Keselamatan Medis &amp; Anjuran Pemeriksaan Profesional (
                    {result.age_group_label || 'Kelompok Rentan'})
                  </h2>
                  <p className="text-sm sm:text-base font-semibold">
                    {result.vulnerable_group_warning ||
                      'Informasi ini bersifat edukatif. Kondisi yang Anda sebutkan memerlukan pertimbangan tenaga kesehatan. Sistem tidak memberikan diagnosis, resep, atau dosis pengobatan personal.'}
                  </p>
                  {result.safety_triggers.length > 0 && (
                    <p className="text-xs sm:text-sm text-[#7F1D1D]">
                      Kategori perhatian medis terdeteksi:{' '}
                      <strong>{result.safety_triggers.join(', ')}</strong>. Untuk balita, bayi, ibu
                      hamil/menyusui, lansia, serta pengguna dengan penyakit kronis atau obat
                      rutin, instruksi konsumsi tidak ditampilkan sebagai rekomendasi otomatis.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Execution Metadata & Explainability Summary */}
          <div className="bg-white rounded-2xl border border-[#DCE5DF] p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs sm:text-sm">
            <div className="space-y-1">
              <p className="font-semibold text-[#1F2937]">{result.message}</p>
              <p className="text-xs text-[#4B5563]">{result.explainability_note}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2 shrink-0 font-mono text-xs text-[#4B5563]">
              <span className="px-2.5 py-1 rounded-lg bg-[#F0FDF4] text-[#166534] border border-[#86EFAC] font-sans font-semibold">
                Usia: {result.age_group_label || 'Dewasa (18-59 tahun)'}
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-[#F8FAF8] border border-[#DCE5DF]">
                Mode: {result.mode_used.toUpperCase()}
              </span>
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#F8FAF8] border border-[#DCE5DF]">
                <Clock className="w-3.5 h-3.5 text-[#166534]" aria-hidden="true" />
                <span>{result.elapsed_ms} ms</span>
              </span>
            </div>
          </div>

          {/* NLP Preprocessing Pipeline Summary (Normalization, Typo, Synonyms, Local Plants, Irrelevant Check) */}
          {result.nlp_analysis && result.nlp_analysis.normalized_query && (
            <div className="bg-white rounded-2xl border border-[#DCE5DF] p-4 sm:p-5 space-y-2.5 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-bold text-[#166534] uppercase tracking-wider">
                  Pipeline Pemrosesan Bahasa Alami (NLP Preprocessing)
                </span>
                <Link
                  to="/evaluation"
                  className="text-xs font-semibold text-[#166534] underline underline-offset-4 hover:text-[#14532D]"
                >
                  Lihat Halaman Evaluasi Model &amp; Benchmark 35 Query
                </Link>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
                <div className="p-2.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF]">
                  <span className="block font-semibold text-[#374151]">1. Normalisasi Teks:</span>
                  <span className="font-mono text-[#166534]">
                    {result.nlp_analysis.normalized_query}
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF]">
                  <span className="block font-semibold text-[#374151]">
                    2. Koreksi Salah Ketik (Typo):
                  </span>
                  {result.nlp_analysis.typo_corrections.length > 0 ? (
                    <span className="text-[#92400E] font-semibold">
                      {result.nlp_analysis.typo_corrections
                        .map((t) => `${t.asli} → ${t.koreksi}`)
                        .join(', ')}
                    </span>
                  ) : (
                    <span className="text-[#4B5563]">Tidak ada salah ketik terdeteksi</span>
                  )}
                </div>
                <div className="p-2.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF]">
                  <span className="block font-semibold text-[#374151]">
                    3. Istilah Tanaman Lokal:
                  </span>
                  {result.nlp_analysis.recognized_local_plants.length > 0 ? (
                    <span className="text-[#166534] font-semibold">
                      {result.nlp_analysis.recognized_local_plants
                        .map((p) => `${p.istilah_lokal} → ${p.nama_tanaman_standar}`)
                        .join(', ')}
                    </span>
                  ) : (
                    <span className="text-[#4B5563]">Menggunakan nama umum standar</span>
                  )}
                </div>
                <div className="p-2.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF]">
                  <span className="block font-semibold text-[#374151]">
                    4. Ekspansi Sinonim Keluhan:
                  </span>
                  {result.nlp_analysis.matched_synonyms.length > 0 ? (
                    <span className="text-[#166534] font-semibold">
                      {result.nlp_analysis.matched_synonyms
                        .map((s) => `${s.istilah_pengguna} → ${s.sinonim_standar}`)
                        .join('; ')}
                    </span>
                  ) : (
                    <span className="text-[#4B5563]">Istilah langsung tanpa ekspansi</span>
                  )}
                </div>
              </div>
              {result.nlp_analysis.is_irrelevant_query && result.nlp_analysis.irrelevant_reason && (
                <div className="p-3 rounded-xl bg-[#FEF3C7] border border-[#FCD34D] text-[#92400E] font-medium">
                  <strong>Deteksi Pertanyaan Tidak Relevan / Di Luar Cakupan: </strong>
                  {result.nlp_analysis.irrelevant_reason}
                </div>
              )}
            </div>
          )}


          {/* A. CARA AI MEMAHAMI KELUHAN (INTELLIGENT SYMPTOM UNDERSTANDING) */}
          {result.pemahaman_keluhan && (
            <div className="bg-white rounded-2xl border-2 border-[#166534] p-5 sm:p-6 shadow-sm space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E5E7EB] pb-3">
                <h2 className="text-base sm:text-lg font-bold text-[#166534] flex items-center gap-2">
                  <Activity className="w-5 h-5" aria-hidden="true" />
                  <span>A. Cara AI Memahami Keluhan (Intelligent Symptom Understanding)</span>
                </h2>
                <div className="flex flex-wrap items-center gap-2">
                  {result.pemahaman_keluhan.provider && (
                    <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-[#DCFCE7] text-[#166534] border border-[#86EFAC] flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-[#166534]" />
                      <span>{result.pemahaman_keluhan.provider}</span>
                    </span>
                  )}
                  {result.pemahaman_keluhan.kecukupan_informasi && (
                    <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-[#F0FDF4] text-[#166534] border border-[#BBF7D0]">
                      Status: {result.pemahaman_keluhan.kecukupan_informasi}
                    </span>
                  )}
                  <span className="px-2.5 py-1 rounded-md text-xs font-mono font-bold bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D]">
                    diagnosis_medis: null
                  </span>
                </div>
              </div>

              {/* Temperature & Danger Warnings if any */}
              {result.pemahaman_keluhan.peringatan_suhu && result.pemahaman_keluhan.peringatan_suhu.length > 0 && (
                <div className="p-4 rounded-xl bg-red-50 border-2 border-red-400 space-y-2 text-red-900">
                  <div className="flex items-center gap-2 font-bold text-sm text-red-800">
                    <AlertTriangle className="w-5 h-5 text-red-600 shrink-0" aria-hidden="true" />
                    <span>Pemeriksaan Suhu Tubuh &amp; Peringatan Keselamatan Medis</span>
                  </div>
                  {result.pemahaman_keluhan.peringatan_suhu.map((warn, wIdx) => (
                    <p key={wIdx} className="text-xs sm:text-sm font-semibold leading-relaxed">
                      {warn}
                    </p>
                  ))}
                  {result.pemahaman_keluhan.instruksi_ramuan_dihentikan && (
                    <p className="text-xs font-bold text-red-700 bg-red-100/80 p-2 rounded-lg border border-red-300">
                      Pemberian instruksi takaran ramuan dihentikan secara otomatis demi keselamatan pengguna.
                    </p>
                  )}
                </div>
              )}

              {/* Information Conflict Warning if any */}
              {result.pemahaman_keluhan.konflik_informasi && result.pemahaman_keluhan.konflik_informasi.length > 0 && (
                <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs sm:text-sm space-y-1">
                  <span className="font-bold flex items-center gap-1.5 text-amber-800">
                    <Info className="w-4 h-4 text-amber-600" aria-hidden="true" />
                    Klarifikasi Data Suhu &amp; Pernyataan:
                  </span>
                  <ul className="list-disc list-inside space-y-0.5">
                    {result.pemahaman_keluhan.konflik_informasi.map((konflikItem, kIdx) => (
                      <li key={kIdx} className="font-medium">{konflikItem}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Multi-Symptom Structure Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs sm:text-sm">
                {/* 1. Keluhan Utama & Tambahan */}
                <div className="p-3.5 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] space-y-2">
                  <span className="font-bold text-[#166534] block uppercase text-[11px] tracking-wider">
                    Keluhan yang Dikenali:
                  </span>
                  {result.pemahaman_keluhan.keluhan_utama ? (
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-white bg-[#166534] px-1.5 py-0.5 rounded">
                          Utama
                        </span>
                        <span className="font-bold text-[#166534]">
                          {result.pemahaman_keluhan.keluhan_utama}
                        </span>
                      </div>
                      {result.pemahaman_keluhan.keluhan_tambahan && result.pemahaman_keluhan.keluhan_tambahan.length > 0 && (
                        <div className="space-y-1 pt-1 border-t border-[#BBF7D0]">
                          <span className="text-[10px] font-semibold text-[#4B5563] block">Keluhan Tambahan:</span>
                          <div className="flex flex-wrap gap-1">
                            {result.pemahaman_keluhan.keluhan_tambahan.map((t) => (
                              <span key={t} className="px-2 py-0.5 rounded-md bg-[#DCFCE7] text-[#166534] font-medium text-xs border border-[#86EFAC]">
                                {t}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : result.pemahaman_keluhan.keluhan_teridentifikasi.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {result.pemahaman_keluhan.keluhan_teridentifikasi.map((k) => (
                        <span
                          key={k}
                          className="px-2.5 py-1 rounded-lg bg-[#166534] text-white font-semibold text-xs"
                        >
                          {k}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-[#4B5563]">
                      Belum teridentifikasi topik keluhan spesifik dalam dataset
                    </span>
                  )}

                  {/* Negated Symptoms if any */}
                  {result.pemahaman_keluhan.keluhan_dinegasikan && result.pemahaman_keluhan.keluhan_dinegasikan.length > 0 && (
                    <div className="pt-2 border-t border-[#BBF7D0] space-y-1">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280] block">
                        Dinyatakan Tidak Dialami (Negasi):
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {result.pemahaman_keluhan.keluhan_dinegasikan.map((neg, nIdx) => (
                          <span key={nIdx} className="px-2 py-0.5 rounded-md bg-gray-100 text-gray-700 font-medium text-xs border border-gray-300 line-through">
                            {neg.nama}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* 2. Jenis Keluhan & Suhu Tubuh */}
                <div className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-2">
                  <span className="font-bold text-[#374151] block uppercase text-[11px] tracking-wider">
                    Jenis Keluhan &amp; Suhu Tubuh:
                  </span>
                  {result.pemahaman_keluhan.keluhan_terstruktur && result.pemahaman_keluhan.keluhan_terstruktur.length > 0 ? (
                    <div className="space-y-1 text-xs">
                      {result.pemahaman_keluhan.keluhan_terstruktur.map((item, idx) => (
                        <p key={idx} className="text-[#1F2937]">
                          <strong className="text-[#166534] capitalize">{item.nama}:</strong>{' '}
                          <span className="text-[#4B5563]">{item.jenis}</span>
                        </p>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-[#6B7280]">Karakteristik spesifik belum tercatat.</p>
                  )}

                  {/* Temperature Recognition */}
                  {result.pemahaman_keluhan.suhu_tubuh && (
                    <div className="pt-2 border-t border-[#DCE5DF] space-y-0.5">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-[#374151] block">
                        Angka Suhu yang Dikenali:
                      </span>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="px-2 py-0.5 rounded-md font-mono font-bold text-xs bg-[#166534] text-white">
                          {result.pemahaman_keluhan.suhu_tubuh.tampilan}
                        </span>
                        <span className="text-xs text-[#4B5563]">
                          {result.pemahaman_keluhan.suhu_tubuh.kategori}
                        </span>
                      </div>
                    </div>
                  )}

                  <div className="pt-1.5 border-t border-[#DCE5DF]">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280] block">
                      Durasi Keluhan:
                    </span>
                    <p className="font-semibold text-[#1F2937] text-xs">
                      {result.pemahaman_keluhan.durasi_keluhan || 'Belum disebutkan pengguna'}
                    </p>
                  </div>
                </div>

                {/* 3. Status Keselamatan & Obat Rutin */}
                <div className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-2">
                  <span className="font-bold text-[#374151] block uppercase text-[11px] tracking-wider">
                    Status Pemeriksaan Keselamatan:
                  </span>
                  <p className="font-semibold text-[#92400E] text-xs sm:text-sm">
                    {result.pemahaman_keluhan.status_keselamatan}
                  </p>
                  <div className="pt-2 border-t border-[#DCE5DF] space-y-0.5 text-xs">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#4B5563] block">
                      Status Obat Rutin:
                    </span>
                    <p className="text-[#374151] font-medium">
                      {result.pemahaman_keluhan.status_obat_rutin ||
                        (result.pemahaman_keluhan.obat_rutin
                          ? `Obat rutin dilaporkan: ${result.pemahaman_keluhan.obat_rutin}`
                          : 'Obat rutin tidak dilaporkan')}
                    </p>
                  </div>
                </div>
              </div>

              {/* Coverage Reference Notes if any */}
              {result.pemahaman_keluhan.catatan_cakupan_referensi && result.pemahaman_keluhan.catatan_cakupan_referensi.length > 0 && (
                <div className="p-3.5 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] space-y-1 text-xs text-[#14532D]">
                  <span className="font-bold block text-[11px] uppercase tracking-wider text-[#166534]">
                    Catatan Cakupan Referensi FROTI:
                  </span>
                  <ul className="list-disc list-inside space-y-0.5">
                    {result.pemahaman_keluhan.catatan_cakupan_referensi.map((cNote, cIdx) => (
                      <li key={cIdx}>{cNote}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Clarification section */}
              {(result.pemahaman_keluhan.informasi_belum_jelas.length > 0 ||
                result.pemahaman_keluhan.pertanyaan_klarifikasi.length > 0) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs sm:text-sm">
                  {result.pemahaman_keluhan.informasi_belum_jelas.length > 0 && (
                    <div className="p-3.5 rounded-xl bg-[#FEF3C7]/60 border border-[#FCD34D] space-y-1 text-[#92400E]">
                      <span className="font-bold block text-[11px] uppercase tracking-wider">
                        Informasi yang Masih Belum Jelas:
                      </span>
                      <ul className="list-disc list-inside space-y-0.5">
                        {result.pemahaman_keluhan.informasi_belum_jelas.map((infoItem, idx) => (
                          <li key={idx}>{infoItem}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {result.pemahaman_keluhan.pertanyaan_klarifikasi.length > 0 && (
                    <div className="p-3.5 rounded-xl bg-[#F0FDF4] border border-[#BBF7D0] space-y-1 text-[#14532D]">
                      <span className="font-bold block text-[11px] uppercase tracking-wider text-[#166534]">
                        Pertanyaan Klarifikasi Kondisi Pengguna:
                      </span>
                      <ol className="list-decimal list-inside space-y-0.5 font-medium">
                        {result.pemahaman_keluhan.pertanyaan_klarifikasi.map((qItem, idx) => (
                          <li key={idx}>{qItem}</li>
                        ))}
                      </ol>
                    </div>
                  )}
                </div>
              )}

              {result.catatan_penyebab_keluhan && (
                <div className="bg-[#F0FDF4] border border-[#86EFAC] rounded-xl p-3.5 text-xs sm:text-sm text-[#14532D] flex items-start gap-2.5">
                  <Info className="w-4 h-4 text-[#166534] shrink-0 mt-0.5" aria-hidden="true" />
                  <div>
                    <span className="font-bold text-[#166534]">Catatan Edukasi Keluhan: </span>
                    <span>{result.catatan_penyebab_keluhan}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* SINTESIS & ANALISIS BUKTI RAMUAN (TAHAP KEDUA: GEMINI RAG & SOURCE GROUNDING) */}
          {result.ai_evidence_analysis && (
            <div className="bg-gradient-to-br from-emerald-50 via-white to-teal-50/50 rounded-2xl border-2 border-[#166534] p-5 sm:p-6 shadow-sm space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E5E7EB] pb-3">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-lg bg-[#166534] text-white">
                    <Sparkles className="w-5 h-5" aria-hidden="true" />
                  </div>
                  <div>
                    <h2 className="text-base sm:text-lg font-bold text-[#166534]">
                      {result.ai_evidence_analysis.ai_analysis_title || 'Analisis AI HerbID: Sintesis Bukti Ramuan Terkurasi'}
                    </h2>
                    <p className="text-xs text-[#4B5563]">
                      Sintesis RAG berbasis dokumen FROTI Kemenkes RI &amp; referensi resmi BPOM RI
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-[#DCFCE7] text-[#166534] border border-[#86EFAC] flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5 text-[#166534]" />
                    <span>{result.ai_evidence_analysis.provider || 'Google Gemini'}</span>
                  </span>
                  <span className="px-2.5 py-1 rounded-md text-xs font-mono font-bold bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D]">
                    diagnosis_medis: null
                  </span>
                </div>
              </div>

              {/* Ringkasan Eksekutif Analisis AI */}
              <div className="p-4 rounded-xl bg-white border border-[#86EFAC] shadow-xs space-y-2">
                <div className="text-xs font-bold uppercase tracking-wider text-[#166534] flex items-center gap-1.5">
                  <FileCheck2 className="w-4 h-4 text-[#166534]" />
                  <span>Ringkasan Eksekutif Analisis AI Berbasis Bukti:</span>
                </div>
                <p className="text-sm sm:text-base text-[#1F2937] leading-relaxed">
                  {result.ai_evidence_analysis.executive_summary}
                </p>
              </div>

              {/* Mengapa Setiap Dokumen Relevan */}
              {result.ai_evidence_analysis.relevance_explanations && result.ai_evidence_analysis.relevance_explanations.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[#374151] flex items-center gap-1.5">
                    <BookOpen className="w-4 h-4 text-[#166534]" />
                    <span>Relevansi Bukti per Dokumen yang Ditemukan:</span>
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {result.ai_evidence_analysis.relevance_explanations.map((item, idx) => (
                      <div
                        key={idx}
                        className="p-3.5 rounded-xl bg-white border border-[#DCE5DF] space-y-2 text-xs"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-1.5">
                          <span className="font-mono font-bold px-2 py-0.5 rounded bg-[#166534] text-white text-[11px]">
                            {item.kode_referensi}
                          </span>
                          {item.catatan_sumber && (
                            <span className="text-[11px] font-medium text-[#4B5563]">
                              {item.catatan_sumber}
                            </span>
                          )}
                        </div>
                        <h4 className="font-bold text-[#1F2937] text-sm">
                          {item.nama_ramuan_atau_dokumen}
                        </h4>
                        <p className="text-[#374151] leading-relaxed">
                          {item.mengapa_relevan}
                        </p>
                        {item.keluhan_yang_didukung && item.keluhan_yang_didukung.length > 0 && (
                          <div className="flex flex-wrap items-center gap-1 pt-1">
                            <span className="font-semibold text-[#166534]">Mendukung keluhan:</span>
                            {item.keluhan_yang_didukung.map((k, kIdx) => (
                              <span
                                key={kIdx}
                                className="px-2 py-0.5 rounded bg-[#DCFCE7] text-[#166534] font-semibold text-[11px] border border-[#86EFAC]"
                              >
                                {k}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Keluhan yang Belum Memiliki Referensi dalam Dokumen Terkurasi */}
              {result.ai_evidence_analysis.unaddressed_complaints && result.ai_evidence_analysis.unaddressed_complaints.length > 0 && (
                <div className="p-3.5 rounded-xl bg-[#FEF3C7]/80 border border-[#FCD34D] text-xs sm:text-sm text-[#92400E] space-y-1">
                  <div className="font-bold flex items-center gap-1.5">
                    <AlertCircle className="w-4 h-4 text-[#B45309]" />
                    <span>Keluhan Tanpa Referensi Ramuan dalam Korpus Terkurasi:</span>
                  </div>
                  <p className="text-xs text-[#78350F] leading-relaxed">
                    Dokumen terkurasi yang tersedia belum memiliki formula ramuan khusus untuk keluhan berikut:
                  </p>
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {result.ai_evidence_analysis.unaddressed_complaints.map((u, uIdx) => (
                      <span
                        key={uIdx}
                        className="px-2.5 py-0.5 rounded-md bg-white border border-[#FCD34D] text-[#92400E] font-semibold text-xs"
                      >
                        {u}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Kontraindikasi & Hal yang Perlu Diperhatikan */}
              {result.ai_evidence_analysis.safety_and_contraindication_highlights &&
                result.ai_evidence_analysis.safety_and_contraindication_highlights.length > 0 && (
                  <div className="p-3.5 rounded-xl bg-red-50/70 border border-red-200 text-xs sm:text-sm text-red-900 space-y-1.5">
                    <span className="font-bold flex items-center gap-1.5 text-red-800">
                      <ShieldAlert className="w-4 h-4 text-red-600" />
                      <span>Kontraindikasi &amp; Peringatan Khusus yang Tercatat:</span>
                    </span>
                    <ul className="list-disc list-inside space-y-0.5 text-xs">
                      {result.ai_evidence_analysis.safety_and_contraindication_highlights.map((h, hIdx) => (
                        <li key={hIdx} className="leading-relaxed">{h}</li>
                      ))}
                    </ul>
                  </div>
                )}

              {/* Keterbatasan Informasi Tradisional & Rujukan Tervalidasi */}
              <div className="pt-2 border-t border-[#E5E7EB] flex flex-wrap items-center justify-between gap-2 text-xs text-[#4B5563]">
                {result.ai_evidence_analysis.cited_sources && result.ai_evidence_analysis.cited_sources.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-semibold text-[#1F2937]">Kode Referensi Tervalidasi:</span>
                    {result.ai_evidence_analysis.cited_sources.map((c, cIdx) => (
                      <span
                        key={cIdx}
                        className="font-mono text-[11px] px-2 py-0.5 rounded bg-white text-[#166534] border border-[#86EFAC] font-bold"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                )}
                <span className="italic text-[11px] text-[#6B7280]">
                  Semua klaim ramuan bersumber dari FROTI Kemenkes RI dan rujukan resmi BPOM RI.
                </span>
              </div>
            </div>
          )}

          {/* B. INFORMASI RAMUAN TRADISIONAL (MAKSIMAL 3 HASIL — TAHAP 8B) */}
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 px-1">
              <h2 className="text-lg sm:text-xl font-bold text-[#1F2937] flex items-center gap-2">
                <FlaskConical className="w-5 h-5 text-[#166534]" aria-hidden="true" />
                <span>
                  B. Informasi Ramuan Tradisional Terkurasi (Maksimal 3 Hasil — Ditemukan:{' '}
                  {result.matched_recipes.length})
                </span>
              </h2>
              <Link
                to={`/recipes?age_group=${encodeURIComponent(ageGroup)}`}
                className="text-xs font-semibold text-[#166534] underline underline-offset-4 hover:text-[#14532D]"
              >
                Lihat Semua Data Ramuan FROTI (25 Entri)
              </Link>
            </div>

            {result.matched_recipes.length > 0 ? (
              <div className="space-y-5">
                {result.matched_recipes.map((rec) => (
                  <article
                    key={rec.id}
                    className="bg-white rounded-2xl border-2 border-[#86EFAC] p-5 sm:p-6 shadow-sm space-y-4"
                  >
                    {/* Top Badges */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#F1F5F9] pb-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="px-2.5 py-1 rounded-md font-mono text-xs font-bold bg-[#166534] text-white">
                          {rec.recipe_code}
                        </span>
                        <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-[#DCFCE7] text-[#166534] border border-[#86EFAC]">
                          {rec.status_verifikasi}
                        </span>
                        <span className="px-2.5 py-1 rounded-md text-xs font-bold bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D]">
                          {rec.label_takaran}
                        </span>
                      </div>
                      {rec.similarity_score !== undefined && rec.similarity_score !== null && (
                        <div className="flex flex-col items-end gap-0.5">
                          <span className="font-mono text-xs font-semibold text-[#166534] bg-[#F0FDF4] px-2.5 py-1 rounded-lg border border-[#BBF7D0]">
                            Skor Relevansi: {rec.similarity_score.toFixed(4)}
                          </span>
                          <span className="text-[10px] text-[#92400E] font-medium">
                            {rec.score_label || 'Bukan ukuran khasiat medis'}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Compatibility / Matching Category Badge */}
                    {rec.jenis_kecocokan && (
                      <div className="flex flex-wrap items-center gap-2 p-2.5 rounded-xl bg-[#F0FDF4] border border-[#BBF7D0] text-xs">
                        <span className="font-bold text-[#166534]">Kesesuaian Sumber:</span>
                        <span className="px-2 py-0.5 rounded-md font-medium text-[#166534] bg-white border border-[#86EFAC]">
                          {rec.jenis_kecocokan}
                        </span>
                        {rec.keluhan_dicocokkan && rec.keluhan_dicocokkan.length > 0 && (
                          <span className="text-[11px] text-[#4B5563]">
                            (dicocokkan untuk: {rec.keluhan_dicocokkan.join(', ')})
                          </span>
                        )}
                        {rec.catatan_kecocokan && (
                          <span className="text-[11px] text-[#6B7280] italic block w-full">
                            {rec.catatan_kecocokan}
                          </span>
                        )}
                      </div>
                    )}

                    {/* Explainability Box: Why this document appeared + matched terms + score disclaimer */}
                    {(rec.alasan_relevansi || (rec.matched_terms && rec.matched_terms.length > 0)) && (
                      <div className="p-3 rounded-xl bg-[#F0FDF4]/80 border border-[#BBF7D0] space-y-1.5 text-xs text-[#14532D]">
                        {rec.alasan_relevansi && (
                          <p className="leading-relaxed">
                            <strong className="text-[#166534]">Alasan Hasil Dipilih (Explainability): </strong>
                            {rec.alasan_relevansi}
                          </p>
                        )}
                        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                          {rec.matched_terms && rec.matched_terms.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1">
                               <span className="font-semibold text-[#374151]">Kata yang cocok:</span>
                              {rec.matched_terms.map((term) => (
                                <span
                                  key={term}
                                  className="px-2 py-0.5 rounded bg-[#DCFCE7] text-[#166534] font-mono text-[11px] font-bold border border-[#86EFAC]"
                                >
                                  {term}
                                </span>
                              ))}
                            </div>
                          )}
                          <span className="text-[11px] font-semibold text-[#92400E]">
                            {rec.peringatan_skor ||
                              'Skor relevansi mengukur kemiripan teks/makna, bukan ukuran khasiat medis.'}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* 1. Nama Ramuan, Nama Tanaman & Nama Ilmiah + 2. Kegunaan Tradisional */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="p-3.5 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] space-y-1">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-[#166534]">
                          1. Nama Ramuan, Nama Tanaman &amp; Nama Ilmiah
                        </span>
                        <h3 className="text-lg font-bold text-[#1F2937]">
                          {rec.nama_ramuan}
                        </h3>
                        <p className="text-xs sm:text-sm font-semibold text-[#1F2937]">
                          Tanaman Utama: {rec.nama_tanaman || rec.nama_ramuan}
                        </p>
                        {rec.nama_ilmiah && (
                          <p className="text-sm font-serif italic text-[#166534] font-semibold">
                            {rec.nama_ilmiah}
                          </p>
                        )}
                        {rec.bagian_tanaman && (
                          <p className="text-xs text-[#374151]">
                            <strong>Bagian Tanaman:</strong> {rec.bagian_tanaman}
                          </p>
                        )}
                      </div>

                      <div className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-[#374151]">
                          2. Kegunaan Tradisional
                        </span>
                        <p className="text-base font-bold text-[#166534]">
                          {rec.kegunaan_tradisional || rec.keluhan_terkait}
                        </p>
                        <p className="text-xs text-[#4B5563]">
                          Topik Keluhan Terkait: <strong>{rec.keluhan_terkait}</strong>
                        </p>
                      </div>
                    </div>

                    {/* 3. Bahan dan Takaran dari Sumber + 4. Campuran Tambahan */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1.5">
                        <div className="flex flex-wrap items-center justify-between gap-1">
                          <span className="text-[11px] font-bold uppercase tracking-wider text-[#374151]">
                            3. Bahan &amp; Takaran dari Sumber
                          </span>
                          <span className="px-2 py-0.5 rounded bg-[#FEF3C7] text-[#92400E] text-[10px] font-bold">
                            {rec.label_takaran}
                          </span>
                        </div>
                        <p className="text-sm font-semibold text-[#1F2937]">
                          {rec.takaran_bahan_sumber}
                        </p>
                      </div>

                      <div className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1.5">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-[#374151]">
                          4. Campuran Tambahan
                        </span>
                        <p className="text-sm font-semibold text-[#1F2937]">
                          {rec.campuran_tambahan || 'Tidak ada'}
                        </p>
                        <p className="text-[11px] text-[#4B5563]">
                          Label: {rec.label_takaran}
                        </p>
                      </div>
                    </div>

                    {/* 5. Langkah Pembuatan + 6. Cara Penggunaan yang Terdokumentasi */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1.5">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-[#374151]">
                          5. Langkah Pembuatan
                        </span>
                        {rec.langkah_pembuatan_list && rec.langkah_pembuatan_list.length > 0 ? (
                          <ol className="list-decimal list-inside text-xs sm:text-sm text-[#1F2937] space-y-1">
                            {rec.langkah_pembuatan_list.map((stText, sIdx) => (
                              <li key={sIdx}>{stText}</li>
                            ))}
                          </ol>
                        ) : (
                          <p className="text-xs sm:text-sm text-[#1F2937]">
                            {rec.langkah_pembuatan}
                          </p>
                        )}
                      </div>

                      <div
                        className={`p-3.5 rounded-xl border space-y-2 ${
                          rec.instruksi_konsumsi_disembunyikan
                            ? 'bg-[#FEE2E2] border-[#FCA5A5] text-[#991B1B]'
                            : 'bg-[#F0FDF4] border-[#86EFAC] text-[#14532D]'
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-1">
                          <span className="text-[11px] font-bold uppercase tracking-wider">
                            6. Cara Penggunaan yang Terdokumentasi ({rec.rute_penggunaan})
                          </span>
                          <span className="px-2 py-0.5 rounded bg-white/80 text-[11px] font-bold border border-current/20">
                            Usia: {rec.label_kelompok_usia}
                          </span>
                        </div>

                        {rec.instruksi_konsumsi_disembunyikan ? (
                          <div className="space-y-1.5 text-xs sm:text-sm">
                            <p className="font-bold">{rec.peringatan_kelompok_rentan}</p>
                            <p className="font-semibold">{rec.dosis_kelompok_usia}</p>
                          </div>
                        ) : (
                          <div className="space-y-1.5 text-xs sm:text-sm">
                            <p className="font-semibold">{rec.cara_penggunaan}</p>
                            <div className="p-2 rounded-lg bg-white/90 border border-[#86EFAC] text-xs text-[#1F2937]">
                              <strong>Keterangan Dosis Kelompok Usia ({rec.label_kelompok_usia}):</strong>{' '}
                              <span>{rec.dosis_kelompok_usia}</span>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* 7. Larangan, Efek Samping & Interaksi Obat + 8. Sumber & Halaman Referensi */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="p-3.5 rounded-xl bg-[#FEF3C7]/60 border border-[#FCD34D] space-y-1.5 text-xs sm:text-sm text-[#92400E]">
                        <span className="text-[11px] font-bold uppercase tracking-wider flex items-center gap-1">
                          <ShieldAlert className="w-3.5 h-3.5" aria-hidden="true" />
                          <span>7. Larangan, Efek Samping &amp; Interaksi Obat</span>
                        </span>
                        <p>
                          <strong>Larangan / Kontraindikasi:</strong>{' '}
                          {rec.larangan_kontraindikasi || 'Lihat rincian sumber'}
                        </p>
                        <p>
                          <strong>Efek Samping:</strong>{' '}
                          {rec.efek_samping || rec.efek_samping_dan_interaksi || 'Lihat rincian sumber'}
                        </p>
                        <p>
                          <strong>Interaksi Obat:</strong>{' '}
                          {rec.interaksi_obat || rec.efek_samping_dan_interaksi || 'Lihat rincian sumber'}
                        </p>
                        {rec.status_pemeriksaan_kontraindikasi && (
                          <p className="text-[11px] font-semibold text-[#78350F] pt-1 border-t border-[#FCD34D]">
                            Status Pemeriksaan: {rec.status_pemeriksaan_kontraindikasi}
                          </p>
                        )}
                      </div>

                      <div className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] flex flex-col justify-between space-y-2 text-xs sm:text-sm">
                        <div className="space-y-1">
                          <span className="text-[11px] font-bold uppercase tracking-wider text-[#374151] flex items-center gap-1">
                            <BookOpen className="w-3.5 h-3.5 text-[#166534]" aria-hidden="true" />
                            <span>8. Sumber dan Halaman Referensi</span>
                          </span>
                          <p className="font-bold text-[#1F2937]">{rec.sumber_dokumen}</p>
                          <p className="text-xs font-semibold text-[#166534]">
                            Rujukan: {rec.halaman_rujukan || 'Tercantum pada dokumen sumber'}
                          </p>
                          {rec.status_keamanan_dosis && (
                            <p className="text-[11px] text-[#4B5563]">
                              Status Dosis: {rec.status_keamanan_dosis}
                            </p>
                          )}
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[#E5E7EB]">
                          {rec.tautan_sumber && (
                            <a
                              href={rec.tautan_sumber}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs font-semibold text-[#166534] underline underline-offset-4 hover:text-[#14532D]"
                            >
                              <span>Buka Sumber Referensi</span>
                              <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                            </a>
                          )}
                          <Link
                            to={`/recipes/${rec.slug}?age_group=${encodeURIComponent(ageGroup)}`}
                            className="inline-flex items-center justify-center px-3.5 py-2 rounded-xl bg-[#166534] text-white text-xs font-semibold hover:bg-[#14532D] transition-colors"
                          >
                            Lihat Bahan dan Cara Membuat
                          </Link>
                        </div>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              result.sanitized_query && (
                <div className="bg-white rounded-2xl border border-[#DCE5DF] p-5 text-sm text-[#374151] flex items-start gap-3">
                  <Info className="w-5 h-5 text-[#92400E] shrink-0 mt-0.5" aria-hidden="true" />
                  <p>
                    {result.recipe_empty_message ||
                      'Belum tersedia referensi ramuan terverifikasi yang relevan untuk keluhan tersebut.'}
                  </p>
                </div>
              )
            )}
          </div>

          {/* C. INFORMASI KESELAMATAN (TAHAP 8C) */}
          {result.informasi_keselamatan && (
            <div className="bg-white rounded-2xl border-2 border-[#FCD34D] p-5 sm:p-6 shadow-sm space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#FDE68A] pb-3">
                <h2 className="text-base sm:text-lg font-bold text-[#92400E] flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5" aria-hidden="true" />
                  <span>C. Informasi Keselamatan &amp; Batasan Penggunaan</span>
                </h2>
                <span className="px-2.5 py-1 rounded-md text-xs font-bold bg-[#FEF3C7] text-[#92400E]">
                  Keamanan Pengguna
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs sm:text-sm">
                <div className="p-3.5 rounded-xl bg-[#FEF3C7]/40 border border-[#FCD34D] space-y-1.5">
                  <span className="font-bold text-[#92400E] block uppercase text-[11px] tracking-wider">
                    1. Informasi Kelompok Usia:
                  </span>
                  <p className="text-[#1F2937] font-medium">
                    {result.informasi_keselamatan.informasi_usia}
                  </p>
                  {result.informasi_keselamatan.peringatan_obat_rutin && (
                    <div className="mt-2 p-2.5 rounded-lg bg-[#FEE2E2] border border-[#FCA5A5] text-[#991B1B] font-semibold">
                      {result.informasi_keselamatan.peringatan_obat_rutin}
                    </div>
                  )}
                </div>

                <div className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1.5">
                  <span className="font-bold text-[#374151] block uppercase text-[11px] tracking-wider">
                    2. Kondisi yang Memerlukan Konsultasi Tenaga Kesehatan:
                  </span>
                  <ul className="list-disc list-inside space-y-1 text-[#374151]">
                    {result.informasi_keselamatan.kondisi_wajib_konsultasi.map((cond, idx) => (
                      <li key={idx}>{cond}</li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] text-xs text-[#4B5563]">
                <strong className="text-[#1F2937]">3. Batasan Informasi yang Tersedia: </strong>
                <span>
                  {Array.isArray(result.informasi_keselamatan.batasan_informasi)
                    ? result.informasi_keselamatan.batasan_informasi.join(' ')
                    : result.informasi_keselamatan.batasan_informasi}
                </span>
              </div>
            </div>
          )}

          {/* 2. SYMPTOM ANALYSIS & HERBAL KNOWLEDGE BASE */}
          {result.symptom_diagnosis && (
            <div className="space-y-5">
              <div className="bg-white rounded-2xl border border-[#166534] p-6 shadow-sm space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-[#166534] text-white text-xs font-bold">
                    <Stethoscope className="w-4 h-4" aria-hidden="true" />
                    <span>Informasi Edukasi Tanaman Obat Terkait Keluhan (Dataset Q&amp;A)</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {result.symptom_diagnosis.matched_symptoms.map((sym) => (
                      <span
                        key={sym}
                        className="px-2.5 py-0.5 rounded-md bg-[#DCFCE7] text-[#166534] border border-[#86EFAC] text-xs font-bold"
                      >
                        {sym}
                      </span>
                    ))}
                  </div>
                </div>

                <h3 className="text-xl font-bold text-[#1F2937]">
                  {result.symptom_diagnosis.detected_condition}
                </h3>

                <p className="text-sm sm:text-base text-[#374151] leading-relaxed">
                  {result.symptom_diagnosis.clinical_summary}
                </p>

                {result.symptom_diagnosis.ai_consultation_answer && (
                  <div className="p-4 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] space-y-1.5 text-xs sm:text-sm text-[#14532D]">
                    <span className="font-bold text-[#166534] block uppercase text-[11px] tracking-wider">
                      Ringkasan Penjelasan Terpandu Data ({result.symptom_diagnosis.ai_provider || 'Grounded Summary'}):
                    </span>
                    <p className="whitespace-pre-line leading-relaxed">
                      {result.symptom_diagnosis.ai_consultation_answer}
                    </p>
                  </div>
                )}

                <div className="p-3.5 rounded-xl bg-[#FEF3C7]/70 border border-[#FCD34D] text-xs sm:text-sm text-[#92400E] flex items-start gap-2.5">
                  <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
                  <div>
                    <span className="font-bold">Kapan Harus ke Dokter: </span>
                    <span>{result.symptom_diagnosis.when_to_see_doctor}</span>
                  </div>
                </div>
              </div>

              {/* Herbal Plant Cards Related to Complaint */}
              {result.herbal_recommendations.length > 0 && (
              <div className="space-y-4">
                <h3 className="text-lg font-bold text-[#1F2937] flex items-center gap-2 px-1">
                  <Pill className="w-5 h-5 text-[#166534]" aria-hidden="true" />
                  <span>
                    Tanaman Obat Terkait dalam Dokumentasi Etnomedisin (
                    {result.herbal_recommendations.length})
                  </span>
                </h3>

                {result.herbal_recommendations.map((rec, idx) => (
                  <article
                    key={`${rec.qa_id}-${rec.nama_herbal}`}
                    className="bg-white rounded-2xl border border-[#DCE5DF] p-5 sm:p-6 shadow-sm space-y-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2 mb-1.5">
                          <span className="px-2.5 py-0.5 rounded-md text-xs font-bold bg-[#166534] text-white">
                            Tanaman #{idx + 1}
                          </span>
                          <span className="px-2.5 py-0.5 rounded-md text-xs font-semibold bg-[#F0FDF4] text-[#166534] border border-[#86EFAC]">
                            {rec.sumber_dataset}
                          </span>
                          <span className="px-2.5 py-0.5 rounded-md text-xs font-bold bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D]">
                            {rec.label_takaran || 'Takaran dalam referensi tradisional, bukan resep medis pribadi'}
                          </span>
                        </div>
                        <h4 className="text-xl font-bold text-[#1F2937]">{rec.nama_herbal}</h4>
                        {rec.nama_ilmiah && (
                          <p className="text-sm font-serif italic text-[#166534]">
                            {rec.nama_ilmiah}
                          </p>
                        )}
                      </div>

                      {rec.slug && (
                        <Link
                          to={`/species/${rec.slug}`}
                          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-[#F0FDF4] text-[#166534] border border-[#86EFAC] hover:bg-[#DCFCE7] transition-colors min-h-[38px]"
                        >
                          <Sprout className="w-3.5 h-3.5" aria-hidden="true" />
                          <span>Lihat Detail Spesies</span>
                        </Link>
                      )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-12 gap-3 text-sm">
                      <div className="md:col-span-4 p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF]">
                        <span className="text-xs font-bold uppercase tracking-wider text-[#4B5563] flex items-center gap-1">
                          <FlaskConical className="w-3.5 h-3.5 text-[#166534]" aria-hidden="true" />
                          <span>Senyawa Fitokimia</span>
                        </span>
                        <p className="font-semibold text-[#1F2937] mt-1">{rec.senyawa_aktif}</p>
                      </div>

                      <div className="md:col-span-8 p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF]">
                        <span className="text-xs font-bold uppercase tracking-wider text-[#4B5563]">
                          Pemanfaatan Tradisional pada Sumber
                        </span>
                        <p className="text-[#1F2937] mt-1 leading-relaxed">{rec.khasiat_relevan}</p>
                      </div>
                    </div>

                    <div
                      className={`p-4 rounded-xl border space-y-1.5 ${
                        result.is_vulnerable_group
                          ? 'bg-[#FEE2E2] border-[#FCA5A5] text-[#991B1B]'
                          : 'bg-[#F0FDF4] border border-[#86EFAC] text-[#14532D]'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 text-xs font-bold uppercase tracking-wider">
                        <span className="flex items-center gap-1.5">
                          <Pill className="w-4 h-4" aria-hidden="true" />
                          <span>Catatan Penyiapan Tradisional dari Sumber</span>
                        </span>
                        <span>
                          {rec.label_takaran || 'Takaran dalam referensi tradisional, bukan resep medis pribadi'}
                        </span>
                      </div>
                      <p className="text-sm leading-relaxed">{rec.dosis_dan_cara_pakai}</p>
                    </div>

                    <div className="text-xs text-[#4B5563] flex items-start gap-2 pt-1">
                      <Info className="w-4 h-4 text-[#92400E] shrink-0 mt-0.5" aria-hidden="true" />
                      <span>
                        <strong className="text-[#374151]">Peringatan &amp; Kontraindikasi:</strong>{' '}
                        {rec.peringatan}
                      </span>
                    </div>
                  </article>
                ))}
              </div>
              )}
            </div>
          )}

          {/* D. REFERENSI & DOKUMEN RUJUKAN RESMI (TAHAP 8D) */}
          {(result.matched_recipes.length > 0 || result.results.length > 0) && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 px-1">
                <h3 className="text-lg font-bold text-[#1F2937] flex items-center gap-2">
                  <BookOpen className="w-5 h-5 text-[#166534]" aria-hidden="true" />
                  <span>
                    D. Referensi &amp; Tautan Sumber Resmi yang Dapat Dibuka Pengguna (
                    {result.results.length} Dokumen BPOM)
                  </span>
                </h3>
                <Link
                  to="/sources"
                  className="text-xs font-semibold text-[#166534] underline underline-offset-4 hover:text-[#14532D]"
                >
                  Buka Semua Direktori Sumber Resmi
                </Link>
              </div>
              {result.results.map((item, idx) => (
                <article
                  key={item.source_id}
                  className="bg-white rounded-2xl border border-[#DCE5DF] p-5 sm:p-6 shadow-sm hover:border-[#86EFAC] transition-colors space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="px-2.5 py-0.5 rounded-md font-mono text-xs font-bold bg-[#166534] text-white">
                        #{idx + 1} · {item.source_id}
                      </span>
                      <span className="px-2.5 py-0.5 rounded-md text-xs font-semibold bg-[#DCFCE7] text-[#166534] border border-[#86EFAC]">
                        Topik: {item.topik}
                      </span>
                      <span className="px-2.5 py-0.5 rounded-md text-xs font-semibold bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D]">
                        {item.verification_note}
                      </span>
                    </div>

                    <div className="text-right">
                      <span className="font-mono text-xs font-bold text-[#166534] bg-[#F0FDF4] px-2.5 py-1 rounded-lg border border-[#BBF7D0]">
                        Skor: {item.similarity_score.toFixed(4)} ({item.score_label})
                      </span>
                    </div>
                  </div>

                  <h4 className="text-lg font-bold text-[#1F2937]">
                    {highlightMatchedText(item.judul, item.matched_terms)}
                  </h4>

                  <p className="text-sm sm:text-base text-[#374151] leading-relaxed">
                    {highlightMatchedText(item.ringkasan, item.matched_terms)}
                  </p>

                  {item.matched_terms.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      <span className="text-xs font-semibold text-[#4B5563]">
                        Istilah yang cocok:
                      </span>
                      {item.matched_terms.map((term) => (
                        <span
                          key={term}
                          className="text-xs font-mono px-2 py-0.5 rounded bg-[#F0FDF4] text-[#166534] border border-[#BBF7D0]"
                        >
                          {term}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="pt-2 border-t border-[#F1F5F9] flex flex-wrap items-center justify-between gap-2 text-xs text-[#4B5563]">
                    <span className="inline-flex items-center gap-1.5 font-medium text-[#166534]">
                      <FileCheck2 className="w-4 h-4" aria-hidden="true" />
                      <span>Otoritas: {item.otoritas}</span>
                    </span>
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 font-semibold text-[#166534] underline underline-offset-4 hover:text-[#14532D] py-1"
                    >
                      <span>Buka Tautan Sumber Resmi BPOM</span>
                      <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                    </a>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
};
