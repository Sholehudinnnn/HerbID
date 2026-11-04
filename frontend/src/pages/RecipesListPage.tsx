import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  AlertCircle,
  BookOpen,
  ExternalLink,
  FlaskConical,
  RefreshCw,
  Search,
  ShieldAlert,
  Users,
} from 'lucide-react';
import { AGE_GROUP_OPTIONS, fetchRecipesList, RecipeCardItem } from '../lib/api';

const QUICK_RECIPE_FILTERS = [
  { label: 'Semua Ramuan (25)', q: '' },
  { label: 'Demam (Sambiloto / Brotowali)', q: 'demam' },
  { label: 'Sakit Kepala Sebelah (Kencur / Teh)', q: 'sakit kepala' },
  { label: 'Sakit Tenggorokan (Sirih)', q: 'tenggorokan' },
  { label: 'Batuk Berdahak (Timi / Akar Manis / Adas)', q: 'batuk' },
  { label: 'Leher Kaku & Masuk Angin (Jahe)', q: 'jahe' },
  { label: 'Terkilir (Kencur / Lengkuas)', q: 'terkilir' },
  { label: 'Panas Dalam (Alang-alang / Cincau)', q: 'panas dalam' },
  { label: 'Nafsu Makan (Temu Hitam / Pepaya)', q: 'nafsu makan' },
  { label: 'Perut Kembung (Kunyit)', q: 'kembung' },
  { label: 'Nyeri Haid & Siklus Haid (Kayu Manis / Andong)', q: 'haid' },
];

export const RecipesListPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const qParam = searchParams.get('q') || '';
  const keluhanParam = searchParams.get('keluhan') || '';
  const ageGroupParam = searchParams.get('age_group') || 'dewasa_18_59_tahun';

  const [searchInput, setSearchInput] = useState(qParam);
  const [ageGroup, setAgeGroup] = useState(ageGroupParam);
  const [recipes, setRecipes] = useState<RecipeCardItem[]>([]);
  const [availableComplaints, setAvailableComplaints] = useState<string[]>([]);
  const [frotiNote, setFrotiNote] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRecipes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchRecipesList({
        q: qParam,
        keluhan: keluhanParam,
        age_group: ageGroupParam,
      });
      setRecipes(res.items);
      setAvailableComplaints(res.available_complaints);
      setFrotiNote(res.froti_reference_note);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Gagal memuat daftar resep ramuan tradisional dari server.'
      );
    } finally {
      setLoading(false);
    }
  }, [qParam, keluhanParam, ageGroupParam]);

  useEffect(() => {
    setSearchInput(qParam);
    setAgeGroup(ageGroupParam);
    loadRecipes();
  }, [qParam, ageGroupParam, loadRecipes]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const next = new URLSearchParams(searchParams);
    if (searchInput.trim()) {
      next.set('q', searchInput.trim());
    } else {
      next.delete('q');
    }
    next.set('age_group', ageGroup);
    setSearchParams(next);
  };

  const handleAgeChange = (newAge: string) => {
    setAgeGroup(newAge);
    const next = new URLSearchParams(searchParams);
    next.set('age_group', newAge);
    setSearchParams(next);
  };

  const handleQuickFilter = (qValue: string) => {
    setSearchInput(qValue);
    const next = new URLSearchParams();
    if (qValue) {
      next.set('q', qValue);
    }
    next.set('age_group', ageGroup);
    setSearchParams(next);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header Banner */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-[#DCFCE7] text-[#166534] text-xs font-bold">
            <FlaskConical className="w-4 h-4" aria-hidden="true" />
            <span>Modul Formularium Ramuan Obat Tradisional Indonesia (FROTI Kemenkes RI)</span>
          </div>
          <span className="px-3 py-1 rounded-lg bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D] text-xs font-bold">
            Takaran dalam referensi tradisional, bukan resep medis pribadi
          </span>
        </div>

        <div className="space-y-2">
          <h1 className="text-2xl sm:text-3xl font-bold text-[#1F2937]">
            Resep Ramuan Obat Tradisional Indonesia (FROTI Terkurasi)
          </h1>
          <p className="text-sm sm:text-base text-[#4B5563] leading-relaxed max-w-4xl">
            Basis data terintegrasi dari <code>data/dataset_obat_tradisional_FROTI_terkurasi.csv</code>{' '}
            (Kepmenkes Nomor HK.01.07/MENKES/187/2017) dan rujukan dokumentasi tradisional. Setiap
            entri menampilkan 8 informasi wajib beserta pengaman kelompok usia dan kelompok rentan.
          </p>
        </div>

        {/* FROTI Reference Banner */}
        <div className="p-4 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] text-xs sm:text-sm text-[#166534] space-y-2">
          <p className="font-semibold">
            Landasan Struktur &amp; Kurasi Referensi (FROTI Kementerian Kesehatan RI &amp; BPOM RI):
          </p>
          <p className="text-[#14532D] leading-relaxed">
            {frotiNote ||
              'Database ramuan terintegrasi dengan Formularium Ramuan Obat Tradisional Indonesia (FROTI - Kepmenkes 187/2017). Semua angka takaran diberi label takaran dalam referensi tradisional, bukan resep medis pribadi.'}
          </p>
          <div className="flex flex-wrap items-center gap-4 pt-1">
            <a
              href="https://repository.kemkes.go.id/book/352"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 font-bold underline underline-offset-4 hover:text-[#14532D]"
            >
              <span>Repositori Buku FROTI Kemenkes RI</span>
              <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
            </a>
            <a
              href="https://jdih.kemkes.go.id/documents/keputusan-menteri-kesehatan-nomor-hk0107menkes1872017"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 font-bold underline underline-offset-4 hover:text-[#14532D]"
            >
              <span>Regulasi Kepmenkes HK.01.07/MENKES/187/2017</span>
              <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
            </a>
          </div>
        </div>

        {/* Search, Age Group Selector & Filter Controls */}
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 md:grid-cols-12 gap-3 pt-2">
          <div className="md:col-span-5 relative">
            <Search
              className="w-4 h-4 text-[#4B5563] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none"
              aria-hidden="true"
            />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Cari keluhan, nama tanaman, nama ilmiah, atau kegunaan..."
              aria-label="Cari resep ramuan tradisional"
              className="w-full pl-10 pr-4 py-3 bg-[#F8FAF8] border border-[#DCE5DF] rounded-xl text-sm text-[#1F2937] placeholder-[#4B5563] focus:bg-white focus:border-[#166534]"
            />
          </div>

          <div className="md:col-span-4 flex items-center gap-2">
            <Users className="w-4 h-4 text-[#166534] shrink-0 hidden sm:block" aria-hidden="true" />
            <select
              aria-label="Pilih Kelompok Usia atau Kondisi"
              value={ageGroup}
              onChange={(e) => handleAgeChange(e.target.value)}
              className="w-full px-3 py-3 bg-[#F8FAF8] border border-[#DCE5DF] rounded-xl text-xs sm:text-sm font-semibold text-[#1F2937] min-h-[44px]"
            >
              {AGE_GROUP_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-3 flex gap-2">
            <button
              type="submit"
              className="flex-1 px-4 py-3 rounded-xl bg-[#166534] text-white text-sm font-semibold hover:bg-[#14532D] transition-colors min-h-[44px]"
            >
              Cari Ramuan
            </button>
            {(qParam || keluhanParam) && (
              <button
                type="button"
                onClick={() => handleQuickFilter('')}
                className="px-3.5 py-3 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] text-xs font-semibold text-[#374151] hover:bg-gray-100 min-h-[44px]"
              >
                Reset
              </button>
            )}
          </div>
        </form>

        {/* Quick Filter Chips */}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="text-xs font-semibold text-[#4B5563]">Filter cepat keluhan/tanaman:</span>
          {QUICK_RECIPE_FILTERS.map((chip) => {
            const active = qParam.toLowerCase() === chip.q.toLowerCase();
            return (
              <button
                key={chip.label}
                type="button"
                onClick={() => handleQuickFilter(chip.q)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-colors ${
                  active
                    ? 'bg-[#166534] text-white'
                    : 'bg-[#F8FAF8] border border-[#DCE5DF] text-[#1F2937] hover:bg-[#DCFCE7] hover:text-[#166534]'
                }`}
              >
                {chip.label}
              </button>
            );
          })}
        </div>
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
              <h2 className="font-bold text-base">Gagal Memuat Daftar Resep</h2>
              <p className="text-sm mt-1">{error}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={loadRecipes}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#991B1B] text-white text-sm font-semibold min-h-[44px]"
          >
            <RefreshCw className="w-4 h-4" aria-hidden="true" />
            <span>Coba Lagi</span>
          </button>
        </div>
      )}

      {/* Loading State */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[1, 2, 3, 4].map((n) => (
            <div
              key={n}
              className="bg-white rounded-2xl border border-[#DCE5DF] p-6 h-64 animate-pulse"
            />
          ))}
        </div>
      ) : recipes.length === 0 ? (
        /* Honest Empty State */
        <div className="bg-white rounded-2xl border border-[#DCE5DF] p-10 text-center space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-[#FEF3C7] text-[#92400E] flex items-center justify-center mx-auto">
            <ShieldAlert className="w-6 h-6" aria-hidden="true" />
          </div>
          <h2 className="text-lg font-bold text-[#1F2937]">
            Belum ditemukan ramuan terverifikasi untuk keluhan tersebut. Anda dapat membaca sumber
            informasi umum yang relevan.
          </h2>
          <p className="text-sm text-[#4B5563] max-w-xl mx-auto">
            Sistem tidak membuat resep atau takaran buatan secara otomatis apabila belum tersedia
            dalam sumber yang telah diperiksa.
          </p>
          <div className="flex flex-wrap justify-center gap-3 pt-2">
            <button
              type="button"
              onClick={() => handleQuickFilter('')}
              className="px-4 py-2.5 rounded-xl bg-[#166534] text-white text-sm font-semibold hover:bg-[#14532D] min-h-[42px]"
            >
              Tampilkan Semua Ramuan Terkurasi
            </button>
          </div>
        </div>
      ) : (
        /* Recipe Cards Grid with all 8 FROTI fields */
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {recipes.map((recipe) => (
            <article
              key={recipe.id}
              className="bg-white rounded-2xl border border-[#DCE5DF] hover:border-[#16A34A] transition-all p-6 shadow-sm flex flex-col justify-between space-y-4"
            >
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="px-2.5 py-0.5 rounded-md font-mono text-xs font-bold bg-[#166534] text-white">
                      {recipe.recipe_code}
                    </span>
                    <span className="px-2.5 py-0.5 rounded-md text-xs font-semibold bg-[#DCFCE7] text-[#166534] border border-[#86EFAC]">
                      {recipe.status_verifikasi}
                    </span>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D] text-[11px] font-bold">
                    {recipe.label_takaran}
                  </span>
                </div>

                {/* 1. Nama tanaman & nama ilmiah + 2. Kegunaan tradisional */}
                <div className="p-3.5 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] space-y-1">
                  <p className="text-xs font-bold uppercase tracking-wider text-[#166534]">
                    1. Tanaman: {recipe.nama_tanaman || recipe.nama_ramuan}{' '}
                    {recipe.nama_ilmiah ? (
                      <span className="font-serif italic font-normal">({recipe.nama_ilmiah})</span>
                    ) : null}{' '}
                    {recipe.bagian_tanaman ? `— ${recipe.bagian_tanaman}` : ''}
                  </p>
                  <h2 className="text-lg font-bold text-[#1F2937]">{recipe.nama_ramuan}</h2>
                  <p className="text-xs font-semibold text-[#166534]">
                    2. Kegunaan Tradisional: {recipe.kegunaan_tradisional || recipe.keluhan_terkait}
                  </p>
                </div>

                {/* 3. Bahan & takaran + 4. Campuran tambahan */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
                  <div className="p-3 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1">
                    <span className="font-bold text-[#374151] block">
                      3. Bahan &amp; Takaran Sumber:
                    </span>
                    <p className="font-semibold text-[#1F2937]">{recipe.takaran_bahan_sumber}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1">
                    <span className="font-bold text-[#374151] block">4. Campuran Tambahan:</span>
                    <p className="font-semibold text-[#1F2937]">
                      {recipe.campuran_tambahan || 'Tidak ada'}
                    </p>
                  </div>
                </div>

                {/* 5. Langkah pembuatan + 6. Cara penggunaan & usia */}
                <div className="p-3 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] text-xs space-y-1.5">
                  <p className="text-[#1F2937]">
                    <strong>5. Langkah Pembuatan:</strong> {recipe.langkah_pembuatan}
                  </p>
                  <div
                    className={`p-2.5 rounded-lg border ${
                      recipe.instruksi_konsumsi_disembunyikan
                        ? 'bg-[#FEE2E2] border-[#FCA5A5] text-[#991B1B]'
                        : 'bg-[#F0FDF4] border-[#86EFAC] text-[#14532D]'
                    }`}
                  >
                    <p className="font-bold">
                      6. Cara Penggunaan ({recipe.rute_penggunaan}) — Usia: {recipe.label_kelompok_usia}
                    </p>
                    <p className="mt-0.5">{recipe.cara_penggunaan}</p>
                    <p className="mt-1 font-semibold">
                      Dosis Kelompok Usia: {recipe.dosis_kelompok_usia}
                    </p>
                  </div>
                </div>

                {/* 7. Larangan, efek samping, interaksi + 8. Sumber & halaman */}
                <div className="p-3 rounded-xl bg-[#FEF3C7]/60 border border-[#FCD34D] text-xs text-[#92400E] space-y-1">
                  <p>
                    <strong>7. Larangan / Kontraindikasi:</strong> {recipe.larangan_kontraindikasi}
                  </p>
                  <p>
                    <strong>Efek Samping &amp; Interaksi Obat:</strong>{' '}
                    {recipe.efek_samping_dan_interaksi}
                  </p>
                </div>

                <div className="p-3 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] text-xs flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 text-[#374151]">
                    <BookOpen className="w-3.5 h-3.5 text-[#166534] shrink-0" aria-hidden="true" />
                    <span>
                      <strong>8. Sumber:</strong> {recipe.sumber_dokumen}{' '}
                      {recipe.halaman_rujukan ? `(${recipe.halaman_rujukan})` : ''}
                    </span>
                  </div>
                  {recipe.tautan_sumber && (
                    <a
                      href={recipe.tautan_sumber}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 font-semibold text-[#166534] underline"
                    >
                      <span>PDF Sumber</span>
                      <ExternalLink className="w-3 h-3" aria-hidden="true" />
                    </a>
                  )}
                </div>
              </div>

              <div className="pt-3 border-t border-[#F1F5F9] flex flex-wrap items-center justify-between gap-3">
                <span className="text-xs font-semibold text-[#166534]">
                  {recipe.jumlah_bahan} Komponen · {recipe.jumlah_langkah} Langkah Terstruktur
                </span>

                <Link
                  to={`/recipes/${recipe.slug}?age_group=${encodeURIComponent(ageGroup)}`}
                  className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-[#166534] text-white text-xs sm:text-sm font-semibold hover:bg-[#14532D] transition-colors min-h-[42px]"
                >
                  <span>Lihat Rincian &amp; Dosis Kelompok Usia</span>
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}

      {/* Available Complaints Reference Footer */}
      {availableComplaints.length > 0 && (
        <section className="bg-white rounded-2xl border border-[#DCE5DF] p-5 text-xs text-[#4B5563] space-y-2">
          <p className="font-bold text-[#1F2937]">
            Cakupan Kategori Keluhan &amp; Kegunaan Tradisional ({recipes.length} Ramuan):
          </p>
          <ul className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-1.5 list-disc list-inside">
            {availableComplaints.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
};
