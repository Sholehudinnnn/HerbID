import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import {
  AlertCircle,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  ExternalLink,
  FlaskConical,
  Info,
  ListOrdered,
  RefreshCw,
  ShieldAlert,
  UserCheck,
  Users,
} from 'lucide-react';
import { AGE_GROUP_OPTIONS, fetchRecipeDetail, RecipeDetailData } from '../lib/api';

export const RecipeDetailPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const ageGroupParam = searchParams.get('age_group') || 'dewasa_18_59_tahun';

  const [ageGroup, setAgeGroup] = useState(ageGroupParam);
  const [recipe, setRecipe] = useState<RecipeDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchRecipeDetail(slug, ageGroupParam);
      setRecipe(res);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Gagal memuat detail resep ramuan dari server.'
      );
    } finally {
      setLoading(false);
    }
  }, [slug, ageGroupParam]);

  useEffect(() => {
    setAgeGroup(ageGroupParam);
    loadDetail();
  }, [ageGroupParam, loadDetail]);

  const handleAgeChange = (newAge: string) => {
    setAgeGroup(newAge);
    setSearchParams({ age_group: newAge });
  };

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="h-10 w-48 bg-gray-200 rounded-xl animate-pulse" />
        <div className="bg-white rounded-2xl border border-[#DCE5DF] p-8 h-96 animate-pulse" />
      </div>
    );
  }

  if (error || !recipe) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-6">
        <Link
          to="/recipes"
          className="inline-flex items-center gap-2 text-sm font-semibold text-[#166534] hover:underline"
        >
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          <span>Kembali ke Daftar Resep Tradisional</span>
        </Link>
        <div
          role="alert"
          className="bg-[#FEE2E2] border border-[#FCA5A5] rounded-2xl p-6 sm:p-8 text-[#991B1B] space-y-4"
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="w-6 h-6 shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <h1 className="text-lg font-bold">Resep Ramuan Tidak Ditemukan</h1>
              <p className="text-sm mt-1">
                {error || 'Data ramuan yang diminta belum tersedia di dalam database.'}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={loadDetail}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#991B1B] text-white text-sm font-semibold min-h-[44px]"
            >
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
              <span>Coba Lagi</span>
            </button>
            <Link
              to="/recipes"
              className="inline-flex items-center px-4 py-2.5 rounded-xl bg-white text-[#991B1B] border border-[#FCA5A5] text-sm font-semibold min-h-[44px]"
            >
              Lihat Daftar Resep
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Top Navigation & Disclaimer Pill */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to={`/recipes?age_group=${encodeURIComponent(ageGroup)}`}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white border border-[#DCE5DF] text-sm font-semibold text-[#166534] hover:bg-[#F0FDF4] transition-colors min-h-[42px]"
        >
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          <span>Kembali ke Daftar Resep Tradisional</span>
        </Link>

        <span className="px-3.5 py-1.5 rounded-xl bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D] text-xs font-bold">
          {recipe.label_takaran}
        </span>
      </div>

      {/* Age Group Selector Bar */}
      <section className="bg-white rounded-2xl border border-[#166534] p-4 sm:p-5 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Users className="w-5 h-5 text-[#166534] shrink-0" aria-hidden="true" />
          <div>
            <label
              htmlFor="detail-age-group-select"
              className="block text-xs sm:text-sm font-bold text-[#1F2937]"
            >
              Pilihan Kelompok Usia / Kondisi Pengguna:
            </label>
            <p className="text-xs text-[#4B5563]">
              Sistem tidak menghitung atau mengarang dosis berdasarkan usia atau berat badan.
            </p>
          </div>
        </div>
        <select
          id="detail-age-group-select"
          value={ageGroup}
          onChange={(e) => handleAgeChange(e.target.value)}
          className="px-3.5 py-2.5 bg-[#F0FDF4] border border-[#86EFAC] rounded-xl text-xs sm:text-sm font-bold text-[#166534] min-h-[42px]"
        >
          {AGE_GROUP_OPTIONS.map((opt) => (
            <option key={opt.id} value={opt.id}>
              {opt.label}
            </option>
          ))}
        </select>
      </section>

      {/* Vulnerable Group Warning if applicable */}
      {recipe.instruksi_konsumsi_disembunyikan && (
        <div
          role="alert"
          className="bg-[#FEE2E2] border-2 border-[#FCA5A5] rounded-2xl p-5 sm:p-6 text-[#991B1B] space-y-2 shadow-sm"
        >
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-6 h-6 shrink-0 mt-0.5" aria-hidden="true" />
            <div className="space-y-1">
              <h2 className="font-bold text-base sm:text-lg">
                Peringatan Kelompok Rentan ({recipe.label_kelompok_usia})
              </h2>
              <p className="text-sm sm:text-base font-semibold">
                {recipe.peringatan_kelompok_rentan}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* SECTION A & B: 1. Nama Tanaman & Nama Ilmiah + 2. Kegunaan Tradisional */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="px-2.5 py-1 rounded-md font-mono text-xs font-bold bg-[#166534] text-white">
            ID: {recipe.recipe_code}
          </span>
          <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-[#DCFCE7] text-[#166534] border border-[#86EFAC]">
            Status: {recipe.status_verifikasi}
          </span>
          <span className="px-2.5 py-1 rounded-md text-xs font-bold bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D]">
            {recipe.label_edukasi}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          <div className="p-4 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] space-y-1">
            <p className="text-xs font-bold uppercase tracking-wider text-[#166534]">
              1. Nama Tanaman &amp; Nama Ilmiah
            </p>
            <h1 className="text-2xl font-bold text-[#1F2937]">
              {recipe.nama_tanaman || recipe.nama_ramuan}
            </h1>
            {recipe.nama_ilmiah && (
              <p className="text-base font-serif italic text-[#166534] font-semibold">
                {recipe.nama_ilmiah}
              </p>
            )}
            {recipe.bagian_tanaman && (
              <p className="text-xs text-[#374151]">
                <strong>Bagian Tanaman yang Digunakan:</strong> {recipe.bagian_tanaman}
              </p>
            )}
          </div>

          <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1">
            <p className="text-xs font-bold uppercase tracking-wider text-[#374151]">
              2. Kegunaan Tradisional / Keluhan
            </p>
            <p className="text-lg font-bold text-[#166534]">
              {recipe.kegunaan_tradisional || recipe.keluhan_terkait}
            </p>
            <p className="text-xs text-[#4B5563]">
              Judul Entri Formularium: <strong>{recipe.nama_ramuan}</strong>
            </p>
          </div>
        </div>

        <p className="text-sm sm:text-base text-[#374151] leading-relaxed">{recipe.deskripsi}</p>

        <div className="p-4 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] text-xs sm:text-sm text-[#14532D] flex items-start gap-3">
          <Info className="w-5 h-5 text-[#166534] shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <p className="font-bold text-[#166534]">{recipe.label_takaran}</p>
            <p className="mt-0.5 leading-relaxed">
              Takaran bahan di halaman ini adalah <strong>takaran dalam referensi tradisional</strong>{' '}
              (Kemenkes RI FROTI / dokumentasi sumber), bukan resep medis pribadi.
            </p>
          </div>
        </div>
      </section>

      {/* SECTION C: 3. Bahan & Takaran dari Sumber + 4. Campuran Tambahan */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-bold text-[#1F2937] flex items-center gap-2">
            <ClipboardList className="w-5 h-5 text-[#166534]" aria-hidden="true" />
            <span>3 &amp; 4. Bahan, Takaran dari Sumber &amp; Campuran Tambahan</span>
          </h2>
          <span className="px-2.5 py-1 rounded-md bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D] text-xs font-bold">
            {recipe.label_takaran}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1">
            <span className="text-xs font-bold uppercase tracking-wider text-[#166534]">
              3. Bahan &amp; Takaran dari Sumber
            </span>
            <p className="text-sm sm:text-base font-bold text-[#1F2937]">
              {recipe.takaran_bahan_sumber}
            </p>
          </div>

          <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1">
            <span className="text-xs font-bold uppercase tracking-wider text-[#166534]">
              4. Campuran Tambahan
            </span>
            <p className="text-sm sm:text-base font-bold text-[#1F2937]">
              {recipe.campuran_tambahan || 'Tidak ada'}
            </p>
            <p className="text-xs text-[#4B5563]">{recipe.label_takaran}</p>
          </div>
        </div>

        {recipe.ingredients.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-[#DCE5DF]">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-[#F0FDF4] text-[#166534] border-b border-[#DCE5DF]">
                  <th className="py-3 px-4 font-bold">Nama Bahan</th>
                  <th className="py-3 px-4 font-bold">Takaran Sumber</th>
                  <th className="py-3 px-4 font-bold">Label Wajib</th>
                  <th className="py-3 px-4 font-bold">Keterangan</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#DCE5DF]">
                {recipe.ingredients.map((ing) => (
                  <tr key={ing.id} className="hover:bg-[#F8FAF8]">
                    <td className="py-3 px-4 font-semibold text-[#1F2937]">{ing.nama_bahan}</td>
                    <td className="py-3 px-4 font-mono text-[#166534] font-semibold">
                      {ing.jumlah || 'Belum tersedia di sumber'}
                    </td>
                    <td className="py-3 px-4 text-xs font-semibold text-[#92400E]">
                      {ing.satuan || recipe.label_takaran}
                    </td>
                    <td className="py-3 px-4 text-xs text-[#4B5563]">{ing.catatan || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* SECTION D: 5. Langkah Pembuatan */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
        <h2 className="text-lg font-bold text-[#1F2937] flex items-center gap-2">
          <ListOrdered className="w-5 h-5 text-[#166534]" aria-hidden="true" />
          <span>5. Langkah Pembuatan (Sesuai Sumber FROTI)</span>
        </h2>

        {recipe.langkah_pembuatan && (
          <div className="p-4 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] text-sm text-[#14532D]">
            <strong>Teks Rujukan Pembuatan:</strong> {recipe.langkah_pembuatan}
          </div>
        )}

        {recipe.steps.length > 0 && (
          <ol className="space-y-3">
            {recipe.steps.map((st) => (
              <li
                key={st.id}
                className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] flex items-start gap-3.5"
              >
                <span className="px-2.5 py-1 rounded-lg bg-[#166534] text-white font-mono text-xs font-bold shrink-0">
                  Langkah {st.nomor_langkah}
                </span>
                <p className="text-sm sm:text-base text-[#1F2937] leading-relaxed">
                  {st.deskripsi_langkah}
                </p>
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* SECTION E: 6. Cara Penggunaan & Keterangan Dosis Kelompok Usia */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-bold text-[#1F2937] flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-[#166534]" aria-hidden="true" />
            <span>
              6. Cara Penggunaan ({recipe.rute_penggunaan}) &amp; Kelompok Usia (
              {recipe.label_kelompok_usia})
            </span>
          </h2>
          <span className="px-2.5 py-1 rounded-md text-xs font-bold bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D]">
            {recipe.label_takaran}
          </span>
        </div>

        <div
          className={`p-4 rounded-xl border text-sm sm:text-base leading-relaxed space-y-2 ${
            recipe.instruksi_konsumsi_disembunyikan
              ? 'bg-[#FEE2E2] border-[#FCA5A5] text-[#991B1B] font-semibold'
              : 'bg-[#F0FDF4] border-[#86EFAC] text-[#14532D]'
          }`}
        >
          <p>{recipe.cara_penggunaan}</p>
          <div className="p-3 rounded-lg bg-white/90 border border-current/20 text-xs sm:text-sm text-[#1F2937]">
            <strong>Dosis Kelompok Usia Terpilih ({recipe.label_kelompok_usia}):</strong>{' '}
            <span>{recipe.dosis_kelompok_usia}</span>
          </div>
        </div>

        {/* Complete Age Group Reference Table */}
        {recipe.dosis_per_kelompok_usia && Object.keys(recipe.dosis_per_kelompok_usia).length > 0 && (
          <div className="space-y-2 pt-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#374151]">
              Tabel Keterangan Dosis Berdasarkan Kelompok Usia pada Sumber Rujukan:
            </h3>
            <div className="overflow-x-auto rounded-xl border border-[#DCE5DF]">
              <table className="w-full text-left border-collapse text-xs sm:text-sm">
                <thead>
                  <tr className="bg-[#F8FAF8] text-[#374151] border-b border-[#DCE5DF]">
                    <th className="py-2.5 px-4 font-bold">Kelompok Usia / Kondisi</th>
                    <th className="py-2.5 px-4 font-bold">Keterangan pada Rujukan FROTI</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#DCE5DF]">
                  {AGE_GROUP_OPTIONS.map((opt) => (
                    <tr
                      key={opt.id}
                      className={opt.id === ageGroup ? 'bg-[#F0FDF4] font-semibold' : ''}
                    >
                      <td className="py-2.5 px-4 text-[#1F2937]">{opt.label}</td>
                      <td className="py-2.5 px-4 text-[#374151]">
                        {recipe.dosis_per_kelompok_usia[opt.id] ||
                          'Dosis belum ditetapkan—konsultasikan dengan dokter atau apoteker'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* SECTION F: 7. Larangan, Efek Samping, dan Interaksi Obat */}
      <section className="bg-white rounded-2xl border-2 border-[#FCA5A5] p-6 sm:p-8 shadow-sm space-y-4">
        <h2 className="text-lg font-bold text-[#991B1B] flex items-center gap-2">
          <ShieldAlert className="w-5 h-5" aria-hidden="true" />
          <span>7. Larangan, Efek Samping &amp; Interaksi Obat</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div className="p-4 rounded-xl bg-[#FEE2E2]/40 border border-[#FCA5A5] space-y-1.5">
            <p className="text-xs font-bold uppercase tracking-wider text-[#991B1B]">
              Larangan / Kontraindikasi:
            </p>
            <p className="text-[#7F1D1D] leading-relaxed">
              {recipe.larangan_kontraindikasi || recipe.kontraindikasi}
            </p>
          </div>

          <div className="p-4 rounded-xl bg-[#FEF3C7]/60 border border-[#FCD34D] space-y-1.5">
            <p className="text-xs font-bold uppercase tracking-wider text-[#92400E]">
              Peringatan Efek Samping &amp; Interaksi Obat:
            </p>
            <p className="text-[#92400E] leading-relaxed">
              {recipe.efek_samping_dan_interaksi || recipe.peringatan}
            </p>
          </div>
        </div>
      </section>

      {/* SECTION G: 8. Sumber Resmi beserta Halaman Rujukan */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
        <h2 className="text-lg font-bold text-[#1F2937] flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-[#166534]" aria-hidden="true" />
          <span>8. Sumber Resmi beserta Halaman Rujukan</span>
        </h2>

        <div className="space-y-3">
          {recipe.sources.map((src) => (
            <div
              key={src.id}
              className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] flex flex-col sm:flex-row sm:items-center justify-between gap-3"
            >
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-2 py-0.5 rounded text-xs font-bold bg-[#DCFCE7] text-[#166534]">
                    {src.instansi}
                  </span>
                  <span className="px-2 py-0.5 rounded text-xs font-mono bg-white border border-[#DCE5DF] text-[#374151]">
                    {src.status_validasi}
                  </span>
                </div>
                <p className="font-bold text-sm text-[#1F2937]">{src.nama_referensi}</p>
                <p className="text-xs text-[#166534] font-semibold">
                  Halaman Rujukan: <strong>{src.halaman || recipe.halaman_rujukan || '-'}</strong>
                </p>
              </div>

              <a
                href={src.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#166534] text-white text-xs font-semibold hover:bg-[#14532D] transition-colors self-start sm:self-auto min-h-[38px]"
              >
                <span>Buka Dokumen Rujukan (PDF)</span>
                <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
              </a>
            </div>
          ))}
        </div>
      </section>

      {/* SECTION H: Status Verifikasi & Peninjauan */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-3">
        <h2 className="text-lg font-bold text-[#1F2937] flex items-center gap-2">
          <UserCheck className="w-5 h-5 text-[#166534]" aria-hidden="true" />
          <span>Status Keamanan Dosis &amp; Metadata Kurasi</span>
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs sm:text-sm">
          <div className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF]">
            <span className="text-xs font-bold uppercase text-[#4B5563]">Status Verifikasi</span>
            <p className="font-bold text-[#166534] mt-1">{recipe.status_verifikasi}</p>
          </div>
          <div className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF]">
            <span className="text-xs font-bold uppercase text-[#4B5563]">Status Keamanan Dosis</span>
            <p className="font-semibold text-[#92400E] mt-1">
              {recipe.status_keamanan_dosis || recipe.reviewer || '-'}
            </p>
          </div>
          <div className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF]">
            <span className="text-xs font-bold uppercase text-[#4B5563]">Tanggal Kurasi</span>
            <p className="font-mono font-semibold text-[#1F2937] mt-1">
              {recipe.tanggal_review || '-'}
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};
