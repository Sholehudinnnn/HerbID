import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  AlertCircle,
  AlertTriangle,
  BookOpen,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ExternalLink,
  RefreshCw,
  Search,
  Sprout,
  X,
} from 'lucide-react';
import { fetchKnowledgeList, KnowledgeListResponse } from '../lib/api';

export const KnowledgePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const qParam = searchParams.get('q') || '';
  const topicParam = searchParams.get('topic') || '';
  const reviewParam = searchParams.get('review') || 'all';
  const pageParam = Math.max(1, parseInt(searchParams.get('page') || '1', 10) || 1);

  const [inputQ, setInputQ] = useState(qParam);
  const [data, setData] = useState<KnowledgeListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Record<number, boolean>>({});

  useEffect(() => {
    setInputQ(qParam);
  }, [qParam]);

  const loadKnowledge = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchKnowledgeList({
        q: qParam,
        topic: topicParam,
        review_filter: reviewParam,
        page: pageParam,
        per_page: 15,
      });
      setData(res);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Gagal memuat daftar Pengetahuan & Tanya Jawab.'
      );
    } finally {
      setLoading(false);
    }
  }, [qParam, topicParam, reviewParam, pageParam]);

  useEffect(() => {
    loadKnowledge();
  }, [loadKnowledge]);

  const updateParams = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([k, v]) => {
      if (!v || v === 'all' || (k === 'page' && v === '1')) {
        next.delete(k);
      } else {
        next.set(k, v);
      }
    });
    setSearchParams(next);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    updateParams({ q: inputQ.trim() || null, page: '1' });
  };

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header & Research Data Warning */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-[#FEF3C7] border border-[#FCD34D] text-xs font-bold text-[#92400E]">
          <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span>Korpus Penelitian Kaggle (52 Q&amp;A) · Bukan Informasi Resmi BPOM</span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-bold text-[#1F2937]">
          Pengetahuan &amp; Tanya Jawab Tradisional
        </h1>

        <p className="text-sm sm:text-base text-[#4B5563] leading-relaxed">
          Halaman ini mendokumentasikan seluruh 52 pasangan tanya-jawab dari dataset{' '}
          <code className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">
            indonesian_traditional_medicine.jsonl
          </code>{' '}
          (mencakup tanaman, ramuan jamu, akupunktur, bekam, regulasi, dan BKO) beserta status
          validasi dan pemetaan kandidat topik BPOM. Teks jawaban mentah disimpan dalam panel riset
          dan tidak disajikan sebagai petunjuk konsumsi medis.
        </p>

        {/* Search & Filter Controls */}
        <form onSubmit={handleSearch} className="grid grid-cols-1 md:grid-cols-12 gap-3 pt-2">
          <div className="md:col-span-6 relative">
            <Search
              className="w-4 h-4 text-[#4B5563] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none"
              aria-hidden="true"
            />
            <input
              type="text"
              value={inputQ}
              onChange={(e) => setInputQ(e.target.value)}
              placeholder="Cari pertanyaan atau topik (mis. bekam, akupunktur, BKO, jamu gendong)..."
              aria-label="Cari dalam 52 Q&A penelitian"
              className="w-full pl-10 pr-9 py-2.5 bg-[#F8FAF8] border border-[#DCE5DF] rounded-xl text-sm text-[#1F2937] min-h-[42px]"
            />
            {inputQ && (
              <button
                type="button"
                onClick={() => {
                  setInputQ('');
                  updateParams({ q: null, page: '1' });
                }}
                aria-label="Hapus pencarian"
                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-[#4B5563]"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          <div className="md:col-span-3">
            <select
              value={topicParam}
              onChange={(e) => updateParams({ topic: e.target.value, page: '1' })}
              aria-label="Filter topik Q&A"
              className="w-full px-3.5 py-2.5 bg-[#F8FAF8] border border-[#DCE5DF] rounded-xl text-sm text-[#1F2937] min-h-[42px]"
            >
              <option value="">Semua Topik (5 Kategori)</option>
              <option value="tanaman">Topik: Tanaman</option>
              <option value="jamu">Topik: Jamu &amp; Ramuan</option>
              <option value="keamanan">Topik: Keamanan &amp; BKO</option>
              <option value="regulasi">Topik: Regulasi</option>
              <option value="praktik tradisional">Topik: Praktik Tradisional</option>
            </select>
          </div>

          <div className="md:col-span-3">
            <select
              value={reviewParam}
              onChange={(e) => updateParams({ review: e.target.value, page: '1' })}
              aria-label="Filter status tinjauan"
              className="w-full px-3.5 py-2.5 bg-[#F8FAF8] border border-[#DCE5DF] rounded-xl text-sm text-[#1F2937] min-h-[42px]"
            >
              <option value="all">Semua Status Validasi (52)</option>
              <option value="strict_only">Perlu Tinjauan Ketat (14)</option>
              <option value="with_bpom_candidate">Memiliki Kandidat Topik BPOM (14)</option>
            </select>
          </div>
        </form>
      </section>

      {/* Count & Active Reset */}
      <div className="flex items-center justify-between px-1">
        <p className="text-sm font-semibold text-[#1F2937]" aria-live="polite">
          {loading ? 'Memuat rekaman Q&A...' : `Menampilkan ${data?.total || 0} rekaman Q&A penelitian`}
        </p>
        {(qParam || topicParam || reviewParam !== 'all') && (
          <button
            type="button"
            onClick={() => {
              setInputQ('');
              setSearchParams(new URLSearchParams());
            }}
            className="text-xs font-semibold text-[#166534] hover:underline"
          >
            Reset Filter Q&amp;A
          </button>
        )}
      </div>

      {/* Error State */}
      {error && (
        <div
          role="alert"
          className="bg-[#FEE2E2] border border-[#FCA5A5] rounded-2xl p-6 text-[#991B1B] flex items-center justify-between"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={loadKnowledge}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#991B1B] text-white text-xs font-semibold min-h-[40px]"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Coba Lagi</span>
          </button>
        </div>
      )}

      {/* Q&A List */}
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3, 4].map((n) => (
            <div
              key={n}
              className="bg-white rounded-2xl border border-[#DCE5DF] p-6 h-36 animate-pulse"
            />
          ))}
        </div>
      ) : data && data.items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-[#DCE5DF] p-10 text-center space-y-3">
          <p className="text-lg font-bold text-[#1F2937]">Tidak ada rekaman Q&amp;A yang cocok</p>
          <p className="text-sm text-[#4B5563]">
            Ubah kata kunci atau filter topik untuk melihat data penelitian lainnya.
          </p>
        </div>
      ) : data ? (
        <div className="space-y-4">
          {data.items.map((item) => {
            const isOpen = !!expandedIds[item.id];
            const validRefs = item.referensi_bpom.filter((r) => r.source_id);

            return (
              <article
                key={item.id}
                className="bg-white rounded-2xl border border-[#DCE5DF] p-5 sm:p-6 shadow-sm space-y-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-bold px-2.5 py-0.5 rounded bg-[#F8FAF8] border border-[#DCE5DF] text-[#1F2937]">
                      Q&amp;A #{item.id}
                    </span>
                    <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-[#F0FDF4] text-[#166534] border border-[#86EFAC]">
                      Topik: {item.topik}
                    </span>
                    <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D]">
                      Belum diverifikasi ({item.status_validasi})
                    </span>
                    {item.indikasi_perlu_review_ketat && (
                      <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-[#FEE2E2] text-[#991B1B] border border-[#FCA5A5]">
                        Perlu tinjauan ketat
                      </span>
                    )}
                  </div>

                  <span className="text-xs font-mono text-[#4B5563]">
                    {item.panjang_jawaban} karakter
                  </span>
                </div>

                <h2 className="text-lg font-bold text-[#1F2937]">{item.pertanyaan}</h2>

                {/* Related Plant Entities & Candidate BPOM References */}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  {item.tanaman_terkait.map((pt) => (
                    <Link
                      key={pt.slug}
                      to={`/species/${pt.slug}`}
                      className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg bg-[#F0FDF4] text-[#166534] border border-[#BBF7D0] hover:bg-[#DCFCE7]"
                    >
                      <Sprout className="w-3.5 h-3.5" aria-hidden="true" />
                      <span>Spesies: {pt.nama_umum}</span>
                    </Link>
                  ))}

                  {validRefs.length > 0 ? (
                    validRefs.map((ref, idx) => (
                      <a
                        key={`${ref.source_id}-${idx}`}
                        href={ref.source_url || '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg bg-[#FEF3C7]/60 text-[#92400E] border border-[#FCD34D] hover:bg-[#FEF3C7]"
                      >
                        <span>
                          Kandidat Topik {ref.source_id}: {ref.judul}
                        </span>
                        <ExternalLink className="w-3 h-3" aria-hidden="true" />
                      </a>
                    ))
                  ) : (
                    <span className="text-xs text-[#4B5563] bg-[#F8FAF8] px-2.5 py-1 rounded-lg border border-[#E2E8F0]">
                      Status Pemetaan: PERLU_REFERENSI_TAMBAHAN (Klaim Medis Disetujui: Tidak)
                    </span>
                  )}
                </div>

                {/* Collapsible Research Panel for Raw Kaggle Text */}
                <div className="pt-2 border-t border-[#F1F5F9]">
                  <button
                    type="button"
                    onClick={() => toggleExpand(item.id)}
                    aria-expanded={isOpen}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#166534] bg-[#F8FAF8] border border-[#DCE5DF] hover:bg-[#DCFCE7] px-3.5 py-2 rounded-xl transition-colors min-h-[38px]"
                  >
                    <BookOpen className="w-3.5 h-3.5" aria-hidden="true" />
                    <span>
                      {isOpen
                        ? 'Tutup Panel Riset Jawaban Mentah'
                        : 'Buka Panel Riset (Teks Jawaban Kaggle Asli)'}
                    </span>
                    {isOpen ? (
                      <ChevronUp className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </button>

                  {isOpen && (
                    <div className="mt-3 p-4 rounded-xl bg-[#FFFBEB] border border-[#FCD34D] space-y-2">
                      <p className="text-xs font-bold text-[#92400E]">
                        PERINGATAN RISET: Teks di bawah ini berasal dari dataset komunitas Kaggle yang
                        belum diverifikasi secara medis. Jangan gunakan sebagai takaran dosis atau
                        pengganti saran dokter.
                      </p>
                      <p className="text-sm text-[#374151] leading-relaxed">
                        {item.jawaban_kaggle_asli}
                      </p>
                    </div>
                  )}
                </div>
              </article>
            );
          })}

          {/* Pagination */}
          {data.total_pages > 1 && (
            <nav
              aria-label="Navigasi halaman Q&A"
              className="bg-white rounded-2xl border border-[#DCE5DF] p-4 flex items-center justify-between"
            >
              <span className="text-xs sm:text-sm text-[#4B5563]">
                Halaman <strong>{data.page}</strong> dari <strong>{data.total_pages}</strong>
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={data.page <= 1}
                  onClick={() => updateParams({ page: String(data.page - 1) })}
                  className="inline-flex items-center gap-1 px-3.5 py-2 rounded-xl text-xs font-semibold border border-[#DCE5DF] bg-[#F8FAF8] disabled:opacity-45 min-h-[40px]"
                >
                  <ChevronLeft className="w-4 h-4" />
                  <span>Sebelumnya</span>
                </button>
                <button
                  type="button"
                  disabled={data.page >= data.total_pages}
                  onClick={() => updateParams({ page: String(data.page + 1) })}
                  className="inline-flex items-center gap-1 px-3.5 py-2 rounded-xl text-xs font-semibold border border-[#DCE5DF] bg-[#F8FAF8] disabled:opacity-45 min-h-[40px]"
                >
                  <span>Berikutnya</span>
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </nav>
          )}
        </div>
      ) : null}
    </div>
  );
};
