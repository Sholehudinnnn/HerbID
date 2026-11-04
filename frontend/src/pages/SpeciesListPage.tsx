import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  AlertCircle,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Filter,
  RefreshCw,
  Search,
  X,
} from 'lucide-react';
import { fetchSpeciesList, PlantListResponse } from '../lib/api';
import { HerbLogoIcon } from '../components/BotanicalPlaceholder';
import { PlantCard } from '../components/PlantCard';

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

export const SpeciesListPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  const qParam = searchParams.get('q') || '';
  const familyParam = searchParams.get('family') || '';
  const letterParam = searchParams.get('letter') || '';
  const filterModeParam = searchParams.get('filter') || 'all';
  const sortParam = searchParams.get('sort') || 'az';
  const pageParam = Math.max(1, parseInt(searchParams.get('page') || '1', 10) || 1);

  const [inputQuery, setInputQuery] = useState(qParam);
  const [data, setData] = useState<PlantListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedUrl, setCopiedUrl] = useState(false);

  useEffect(() => {
    setInputQuery(qParam);
  }, [qParam]);

  const loadSpecies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSpeciesList({
        q: qParam,
        family: familyParam,
        letter: letterParam,
        filter_mode: filterModeParam,
        sort: sortParam,
        page: pageParam,
        per_page: 12,
      });
      setData(res);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Gagal memuat katalog tanaman dari server.'
      );
    } finally {
      setLoading(false);
    }
  }, [qParam, familyParam, letterParam, filterModeParam, sortParam, pageParam]);

  useEffect(() => {
    loadSpecies();
  }, [loadSpecies]);

  const updateParams = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([k, v]) => {
      if (!v || v === 'all' || (k === 'page' && v === '1') || (k === 'sort' && v === 'az')) {
        next.delete(k);
      } else {
        next.set(k, v);
      }
    });
    setSearchParams(next);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateParams({ q: inputQuery.trim() || null, page: '1' });
  };

  const handleResetFilters = () => {
    setInputQuery('');
    setSearchParams(new URLSearchParams());
  };

  const handleCopyShareUrl = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 2000);
    } catch {
      // ignore clipboard errors
    }
  };

  const availableLettersSet = new Set(data?.available_letters || []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Page Heading */}
      <div className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <HerbLogoIcon className="w-10 h-10 shrink-0 mt-0.5" />
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-[#1F2937] tracking-tight">
                Database Tanaman Obat Indonesia
              </h1>
              <p className="text-sm sm:text-base text-[#4B5563] mt-1">
                Katalog spesies tanaman obat yang diekstraksi secara transparan dari dataset riset
                dan dipetakan terhadap kandidat rujukan topik BPOM.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={handleCopyShareUrl}
            className="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-xl text-xs font-semibold bg-[#F8FAF8] border border-[#DCE5DF] text-[#166534] hover:bg-[#DCFCE7] transition-colors self-start sm:self-center min-h-[40px]"
            title="Salin tautan pencarian dan halaman saat ini"
          >
            {copiedUrl ? (
              <>
                <Check className="w-4 h-4 text-[#166534]" aria-hidden="true" />
                <span>Tautan Disalin</span>
              </>
            ) : (
              <>
                <Copy className="w-4 h-4" aria-hidden="true" />
                <span>Salin URL Filter</span>
              </>
            )}
          </button>
        </div>

        {/* Wide Search Bar */}
        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-3 pt-2">
          <div className="relative flex-1">
            <Search
              className="w-5 h-5 text-[#4B5563] absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none"
              aria-hidden="true"
            />
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Cari nama tanaman, nama ilmiah, nama daerah, atau famili..."
              aria-label="Cari nama tanaman, nama ilmiah, nama daerah, atau famili"
              className="w-full pl-12 pr-10 py-3 bg-[#F8FAF8] border border-[#DCE5DF] rounded-xl text-sm sm:text-base text-[#1F2937] placeholder-[#4B5563] focus:bg-white focus:border-[#166534]"
            />
            {inputQuery && (
              <button
                type="button"
                onClick={() => {
                  setInputQuery('');
                  updateParams({ q: null, page: '1' });
                }}
                aria-label="Bersihkan kata kunci pencarian"
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-[#4B5563] hover:text-[#1F2937] rounded-md"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          <button
            type="submit"
            className="inline-flex items-center justify-center px-6 py-3 rounded-xl text-sm font-semibold bg-[#166534] text-white hover:bg-[#14532D] transition-colors min-h-[44px]"
          >
            Cari Spesies
          </button>
        </form>

        {/* Filter Controls: A-Z, Local Name Filter, Family Filter, and Sort */}
        <div className="pt-2 border-t border-[#F1F5F9] space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* Filter Kategori / Nama Lokal */}
            <div>
              <label
                htmlFor="species-filter-mode"
                className="block text-xs font-semibold text-[#374151] mb-1"
              >
                Filter Atribut Data
              </label>
              <select
                id="species-filter-mode"
                value={filterModeParam}
                onChange={(e) => updateParams({ filter: e.target.value, page: '1' })}
                className="w-full px-3.5 py-2.5 bg-[#F8FAF8] border border-[#DCE5DF] rounded-xl text-sm text-[#1F2937] min-h-[42px]"
              >
                <option value="all">Semua Spesies Tanaman</option>
                <option value="local_name">Memiliki Sinonim / Nama Lokal Daerah</option>
                <option value="with_source">Memiliki Rujukan Topik BPOM</option>
                <option value="local_only">Hanya Nama Lokal (Data Terbatas)</option>
              </select>
            </div>

            {/* Filter Famili (Honest state if dataset has no family values) */}
            <div>
              <label
                htmlFor="species-family-select"
                className="block text-xs font-semibold text-[#374151] mb-1"
              >
                Famili Botani
              </label>
              <select
                id="species-family-select"
                value={familyParam}
                onChange={(e) => updateParams({ family: e.target.value, page: '1' })}
                disabled={!data || data.available_families.length === 0}
                className="w-full px-3.5 py-2.5 bg-[#F8FAF8] border border-[#DCE5DF] rounded-xl text-sm text-[#1F2937] disabled:opacity-75 disabled:cursor-not-allowed min-h-[42px]"
              >
                {data && data.available_families.length > 0 ? (
                  <>
                    <option value="">Semua Famili</option>
                    {data.available_families.map((fam) => (
                      <option key={fam} value={fam}>
                        {fam}
                      </option>
                    ))}
                  </>
                ) : (
                  <option value="">Famili belum tersedia di dataset</option>
                )}
              </select>
            </div>

            {/* Sort Order */}
            <div>
              <label
                htmlFor="species-sort-select"
                className="block text-xs font-semibold text-[#374151] mb-1"
              >
                Urutkan Berdasarkan
              </label>
              <select
                id="species-sort-select"
                value={sortParam}
                onChange={(e) => updateParams({ sort: e.target.value, page: '1' })}
                className="w-full px-3.5 py-2.5 bg-[#F8FAF8] border border-[#DCE5DF] rounded-xl text-sm text-[#1F2937] min-h-[42px]"
              >
                <option value="az">Nama Tanaman (A - Z)</option>
                <option value="za">Nama Tanaman (Z - A)</option>
                <option value="sources_desc">Jumlah Rujukan BPOM Terbanyak</option>
                <option value="scientific">Nama Ilmiah (A - Z)</option>
              </select>
            </div>
          </div>

          {/* A-Z Alphabet Bar */}
          <div className="space-y-1.5">
            <span className="text-xs font-semibold text-[#374151] flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5 text-[#166534]" aria-hidden="true" />
              <span>Filter Huruf Awal (A - Z):</span>
            </span>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter huruf awal A sampai Z">
              <button
                type="button"
                onClick={() => updateParams({ letter: null, page: '1' })}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors min-h-[36px] ${
                  !letterParam
                    ? 'bg-[#166534] text-white border-[#166534]'
                    : 'bg-[#F8FAF8] text-[#1F2937] border-[#DCE5DF] hover:bg-[#DCFCE7]'
                }`}
              >
                Semua
              </button>
              {ALPHABET.map((char) => {
                const isActive = letterParam.toUpperCase() === char;
                const hasItems = availableLettersSet.has(char);
                return (
                  <button
                    key={char}
                    type="button"
                    onClick={() =>
                      updateParams({ letter: isActive ? null : char, page: '1' })
                    }
                    className={`w-8 h-9 rounded-lg text-xs font-semibold border transition-colors flex items-center justify-center ${
                      isActive
                        ? 'bg-[#166534] text-white border-[#166534]'
                        : hasItems
                        ? 'bg-white text-[#1F2937] border-[#DCE5DF] hover:bg-[#DCFCE7] hover:text-[#166534]'
                        : 'bg-[#F8FAF8] text-[#4B5563] border-[#E2E8F0] opacity-60 hover:opacity-100'
                    }`}
                    aria-label={`Filter huruf ${char}`}
                    aria-pressed={isActive}
                  >
                    {char}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Results Count Bar & Active Filter Reset */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-1">
        <p className="text-sm sm:text-base font-semibold text-[#1F2937]" aria-live="polite">
          {loading
            ? 'Memuat daftar tanaman...'
            : `Ditemukan ${data ? data.total : 0} tanaman`}
          {qParam ? ` untuk kata kunci "${qParam}"` : ''}
          {letterParam ? ` dengan awalan "${letterParam}"` : ''}
        </p>

        {(qParam || letterParam || familyParam || filterModeParam !== 'all' || sortParam !== 'az') && (
          <button
            type="button"
            onClick={handleResetFilters}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#166534] hover:underline self-start sm:self-auto"
          >
            <X className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Reset Semua Filter</span>
          </button>
        )}
      </div>

      {/* Error State */}
      {error && (
        <div
          role="alert"
          className="bg-[#FEE2E2] border border-[#FCA5A5] rounded-2xl p-6 text-[#991B1B] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="w-6 h-6 shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <h2 className="font-bold text-base">Gagal Memuat Katalog Tanaman</h2>
              <p className="text-sm mt-1">{error}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={loadSpecies}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#991B1B] text-white text-sm font-semibold hover:bg-[#7F1D1D] min-h-[44px]"
          >
            <RefreshCw className="w-4 h-4" aria-hidden="true" />
            <span>Coba Lagi</span>
          </button>
        </div>
      )}

      {/* Loading Skeleton / Empty State / 3-Column Species Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 6 }).map((_, idx) => (
            <div
              key={idx}
              className="bg-white rounded-2xl border border-[#DCE5DF] h-80 animate-pulse overflow-hidden"
            >
              <div className="h-40 bg-gray-200" />
              <div className="p-5 space-y-3">
                <div className="h-4 w-24 bg-gray-200 rounded" />
                <div className="h-6 w-40 bg-gray-200 rounded" />
                <div className="h-4 w-32 bg-gray-200 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : data && data.items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-[#DCE5DF] p-10 text-center space-y-3">
          <p className="text-lg font-bold text-[#1F2937]">
            Tanaman Tidak Ditemukan dalam Katalog
          </p>
          <p className="text-sm text-[#4B5563] max-w-md mx-auto">
            Tidak ada spesies tanaman yang cocok dengan pencarian atau filter aktif. Sistem hanya
            menampilkan tanaman yang secara eksplisit tercatat dalam dataset.
          </p>
          <button
            type="button"
            onClick={handleResetFilters}
            className="inline-flex items-center justify-center px-5 py-2.5 rounded-xl text-sm font-semibold bg-[#166534] text-white hover:bg-[#14532D] min-h-[44px]"
          >
            Tampilkan Semua Tanaman
          </button>
        </div>
      ) : data ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.items.map((plant) => (
              <PlantCard key={plant.id} plant={plant} />
            ))}
          </div>

          {/* Pagination Controls */}
          {data.total_pages > 1 && (
            <nav
              aria-label="Navigasi halaman katalog tanaman"
              className="bg-white rounded-2xl border border-[#DCE5DF] p-4 flex flex-col sm:flex-row items-center justify-between gap-4"
            >
              <span className="text-xs sm:text-sm text-[#4B5563]">
                Halaman <strong className="text-[#1F2937]">{data.page}</strong> dari{' '}
                <strong className="text-[#1F2937]">{data.total_pages}</strong> ({data.total} spesies)
              </span>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={data.page <= 1}
                  onClick={() => updateParams({ page: String(data.page - 1) })}
                  className="inline-flex items-center gap-1 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold border border-[#DCE5DF] bg-[#F8FAF8] text-[#1F2937] hover:bg-[#DCFCE7] disabled:opacity-45 disabled:cursor-not-allowed min-h-[42px]"
                >
                  <ChevronLeft className="w-4 h-4" aria-hidden="true" />
                  <span>Sebelumnya</span>
                </button>

                <div className="flex items-center gap-1">
                  {Array.from({ length: data.total_pages }).map((_, idx) => {
                    const pNum = idx + 1;
                    const active = pNum === data.page;
                    return (
                      <button
                        key={pNum}
                        type="button"
                        onClick={() => updateParams({ page: String(pNum) })}
                        aria-current={active ? 'page' : undefined}
                        className={`w-10 h-10 rounded-xl text-xs sm:text-sm font-semibold border transition-colors ${
                          active
                            ? 'bg-[#166534] text-white border-[#166534]'
                            : 'bg-white text-[#1F2937] border-[#DCE5DF] hover:bg-[#DCFCE7]'
                        }`}
                      >
                        {pNum}
                      </button>
                    );
                  })}
                </div>

                <button
                  type="button"
                  disabled={data.page >= data.total_pages}
                  onClick={() => updateParams({ page: String(data.page + 1) })}
                  className="inline-flex items-center gap-1 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold border border-[#DCE5DF] bg-[#F8FAF8] text-[#1F2937] hover:bg-[#DCFCE7] disabled:opacity-45 disabled:cursor-not-allowed min-h-[42px]"
                >
                  <span>Berikutnya</span>
                  <ChevronRight className="w-4 h-4" aria-hidden="true" />
                </button>
              </div>
            </nav>
          )}
        </>
      ) : null}
    </div>
  );
};
