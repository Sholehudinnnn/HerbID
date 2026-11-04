import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  FileCheck2,
  RefreshCw,
  Scale,
  Search,
  ShieldCheck,
  X,
} from 'lucide-react';
import { fetchSourcesList, SourceListResponse } from '../lib/api';

export const SourcesPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const qParam = searchParams.get('q') || '';
  const topicParam = searchParams.get('topic') || '';

  const [inputQ, setInputQ] = useState(qParam);
  const [data, setData] = useState<SourceListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setInputQ(qParam);
  }, [qParam]);

  const loadSources = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSourcesList({ q: qParam, topic: topicParam });
      setData(res);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Gagal memuat daftar sumber resmi BPOM.'
      );
    } finally {
      setLoading(false);
    }
  }, [qParam, topicParam]);

  useEffect(() => {
    loadSources();
  }, [loadSources]);

  const updateParams = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([k, v]) => {
      if (!v) next.delete(k);
      else next.set(k, v);
    });
    setSearchParams(next);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    updateParams({ q: inputQ.trim() || null });
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header & Search */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-[#DCFCE7] text-[#166534] text-xs font-semibold">
          <FileCheck2 className="w-4 h-4" aria-hidden="true" />
          <span>Korpus Rujukan Resmi BPOM (bpom_sumber_resmi.csv)</span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-bold text-[#1F2937]">
          Pusat Referensi &amp; Edukasi BPOM
        </h1>

        <p className="text-sm sm:text-base text-[#4B5563] leading-relaxed">
          Kumpulan 9 rujukan resmi Badan Pengawas Obat dan Makanan (BPOM RI) yang menjadi basis
          indeks pencarian TF-IDF dan semantik pada aplikasi ini. Seluruh tautan mengarah langsung
          ke domain resmi BPOM (<code className="font-mono text-xs">pom.go.id</code>).
        </p>

        <form onSubmit={handleSearch} className="grid grid-cols-1 md:grid-cols-12 gap-3 pt-2">
          <div className="md:col-span-8 relative">
            <Search
              className="w-4 h-4 text-[#4B5563] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none"
              aria-hidden="true"
            />
            <input
              type="text"
              value={inputQ}
              onChange={(e) => setInputQ(e.target.value)}
              placeholder="Cari judul sumber, kode BPOM-01..09, atau kata kunci topik..."
              aria-label="Cari sumber BPOM"
              className="w-full pl-10 pr-9 py-2.5 bg-[#F8FAF8] border border-[#DCE5DF] rounded-xl text-sm text-[#1F2937] min-h-[42px]"
            />
            {inputQ && (
              <button
                type="button"
                onClick={() => {
                  setInputQ('');
                  updateParams({ q: null });
                }}
                aria-label="Bersihkan kata kunci"
                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-[#4B5563]"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          <div className="md:col-span-4">
            <select
              value={topicParam}
              onChange={(e) => updateParams({ topic: e.target.value || null })}
              aria-label="Filter topik sumber BPOM"
              className="w-full px-3.5 py-2.5 bg-[#F8FAF8] border border-[#DCE5DF] rounded-xl text-sm text-[#1F2937] min-h-[42px]"
            >
              <option value="">Semua Topik Sumber ({data?.available_topics.length || 8})</option>
              {(data?.available_topics || []).map((t) => (
                <option key={t} value={t}>
                  Topik: {t}
                </option>
              ))}
            </select>
          </div>
        </form>
      </section>

      {/* Two Educational Panels: Cara Cek Produk & Klasifikasi Jamu/OHT/Fitofarmaka */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Panel 1: Cara Cek Produk */}
        <section className="lg:col-span-5 bg-white rounded-2xl border border-[#DCE5DF] p-6 shadow-sm flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-[#166534]">
              <ShieldCheck className="w-5 h-5" aria-hidden="true" />
              <h2 className="text-lg font-bold text-[#1F2937]">
                Cara Cek Produk &amp; Izin Edar
              </h2>
            </div>

            <p className="text-xs sm:text-sm text-[#4B5563] leading-relaxed">
              Kemunculan nama bahan atau tanaman obat (seperti kunyit, temulawak, atau jahe) pada
              materi edukasi BPOM <strong>tidak berarti</strong> setiap produk komersial berbahan
              tersebut otomatis terdaftar. Status izin edar selalu melekat pada produk spesifik.
            </p>

            <div className="p-4 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] space-y-2 text-xs text-[#166534]">
              <p className="font-bold">Prinsip Cek KLIK (Sumber: BPOM-03):</p>
              <ul className="space-y-1 list-disc list-inside">
                <li>
                  <strong>Kemasan:</strong> Pastikan kondisi kemasan utuh dan tidak rusak.
                </li>
                <li>
                  <strong>Label:</strong> Baca komposisi dan peringatan pada label dengan teliti.
                </li>
                <li>
                  <strong>Izin Edar:</strong> Periksa nomor registrasi resmi BPOM (TR / HT / FF).
                </li>
                <li>
                  <strong>Kedaluwarsa:</strong> Pastikan belum melewati tanggal batas pakai.
                </li>
              </ul>
            </div>
          </div>

          <a
            href="https://cekbpom.pom.go.id/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold bg-[#166534] text-white hover:bg-[#14532D] transition-colors min-h-[44px]"
          >
            <span>Cek Izin Edar di Portal CekBPOM</span>
            <ExternalLink className="w-4 h-4" aria-hidden="true" />
          </a>
        </section>

        {/* Panel 2: Penggolongan Jamu, OHT, Fitofarmaka (BPOM-01) */}
        <section className="lg:col-span-7 bg-white rounded-2xl border border-[#DCE5DF] p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-[#166534]">
              <Scale className="w-5 h-5" aria-hidden="true" />
              <h2 className="text-lg font-bold text-[#1F2937]">
                Tingkatan Pembuktian Obat Bahan Alam
              </h2>
            </div>
            <span className="font-mono text-xs font-semibold px-2.5 py-1 rounded bg-[#DCFCE7] text-[#166534]">
              Rujukan: BPOM-01 &amp; BPOM-06
            </span>
          </div>

          <p className="text-xs sm:text-sm text-[#4B5563]">
            Berdasarkan rujukan resmi BPOM-01 (<em>Penggolongan Jamu, OHT, Fitofarmaka</em>), obat
            bahan alam di Indonesia dibagi menjadi tiga tingkatan pembuktian yang tidak boleh
            disamakan klaimnya:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wider text-[#166534]">
                1. Jamu
              </span>
              <p className="text-xs text-[#374151] leading-relaxed">
                Klaim khasiat didasarkan pada data empiris turun-temurun secara tradisional. Belum
                melalui pengujian preklinik maupun uji klinis formal.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wider text-[#166534]">
                2. Obat Herbal Terstandar (OHT)
              </span>
              <p className="text-xs text-[#374151] leading-relaxed">
                Bahan baku telah distandarisasi dan keamanan serta khasiatnya telah dibuktikan
                secara ilmiah melalui uji preklinik (in vivo/in vitro).
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wider text-[#166534]">
                3. Fitofarmaka
              </span>
              <p className="text-xs text-[#374151] leading-relaxed">
                Tingkatan pembuktian tertinggi: bahan baku terstandarisasi, telah melalui uji
                preklinik dan dibuktikan melalui uji klinis pada manusia.
              </p>
            </div>
          </div>
        </section>
      </div>

      {/* Error State */}
      {error && (
        <div
          role="alert"
          className="bg-[#FEE2E2] border border-[#FCA5A5] rounded-2xl p-6 text-[#991B1B] flex items-center justify-between"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={loadSources}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#991B1B] text-white text-xs font-semibold min-h-[40px]"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Coba Lagi</span>
          </button>
        </div>
      )}

      {/* Sources Grid */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-[#1F2937]">
            Daftar Sumber Resmi ({data ? data.total : 0})
          </h2>
          {(qParam || topicParam) && (
            <button
              type="button"
              onClick={() => {
                setInputQ('');
                setSearchParams(new URLSearchParams());
              }}
              className="text-xs font-semibold text-[#166534] hover:underline"
            >
              Tampilkan Semua 9 Sumber
            </button>
          )}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <div
                key={n}
                className="bg-white rounded-2xl border border-[#DCE5DF] p-6 h-52 animate-pulse"
              />
            ))}
          </div>
        ) : data && data.items.length === 0 ? (
          <div className="bg-white rounded-2xl border border-[#DCE5DF] p-8 text-center">
            <p className="font-bold text-[#1F2937]">Tidak ada sumber BPOM yang cocok</p>
          </div>
        ) : data ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.items.map((src) => (
              <article
                key={src.source_id}
                className="bg-white rounded-2xl border border-[#DCE5DF] p-6 shadow-sm hover:border-[#86EFAC] transition-colors flex flex-col justify-between space-y-4"
              >
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-bold bg-[#DCFCE7] text-[#166534] border border-[#86EFAC]">
                      <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" />
                      <span>Sumber BPOM · {src.source_id}</span>
                    </span>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded bg-[#F8FAF8] border border-[#DCE5DF] text-[#374151]">
                      Topik: {src.topik}
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-[#1F2937] leading-snug">{src.judul}</h3>

                  <p className="text-sm text-[#4B5563] leading-relaxed">{src.ringkasan_aman}</p>
                </div>

                <div className="pt-4 border-t border-[#F1F5F9] space-y-3">
                  <div className="text-[11px] font-mono text-[#92400E] bg-[#FEF3C7]/70 px-2.5 py-1 rounded border border-[#FCD34D]">
                    Status: {src.status_review}
                  </div>

                  <a
                    href={src.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold bg-[#166534] text-white hover:bg-[#14532D] transition-colors min-h-[42px]"
                  >
                    <span>Buka sumber resmi</span>
                    <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                  </a>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
};
