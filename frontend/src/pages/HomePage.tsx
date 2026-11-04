import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Database,
  FileSearch,
  FlaskConical,
  RefreshCw,
  Scale,
  Search,
  ShieldAlert,
  Sprout,
} from 'lucide-react';
import {
  AGE_GROUP_OPTIONS,
  fetchRecipesList,
  fetchSpeciesList,
  fetchStats,
  PlantCardItem,
  RecipeCardItem,
  StatsData,
} from '../lib/api';
import { HerbLogoIcon } from '../components/BotanicalPlaceholder';
import { PlantCard } from '../components/PlantCard';

const HERO_EXAMPLE_QUERIES = [
  'Saya sedang batuk berdahak.',
  'Saya sering merasa perut kembung.',
  'Tenggorokan saya terasa sakit.',
  'Saya sedang mengalami nyeri haid.',
  'Informasi ramuan untuk demam',
  'Cara membuat kunyit asam',
  'Manfaat tradisional jahe',
  'Keamanan penggunaan jamu',
];

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedAgeGroup, setSelectedAgeGroup] = useState('dewasa_18_59_tahun');
  const [stats, setStats] = useState<StatsData | null>(null);
  const [featuredRecipes, setFeaturedRecipes] = useState<RecipeCardItem[]>([]);
  const [featuredPlants, setFeaturedPlants] = useState<PlantCardItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadHomeData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsRes, recipesRes, speciesRes] = await Promise.all([
        fetchStats(),
        fetchRecipesList({}),
        fetchSpeciesList({ per_page: 6, sort: 'sources_desc' }),
      ]);
      setStats(statsRes);
      setFeaturedRecipes(recipesRes.items.slice(0, 4));
      setFeaturedPlants(speciesRes.items);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Gagal memuat data beranda dari server lokal.'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHomeData();
  }, [loadHomeData]);

  const handleSearchRamuan = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = searchQuery.trim();
    const sp = new URLSearchParams();
    if (trimmed) sp.set('q', trimmed);
    if (selectedAgeGroup) sp.set('age_group', selectedAgeGroup);
    navigate(`/search?${sp.toString()}`);
  };

  const handleSearchSpecies = () => {
    const trimmed = searchQuery.trim();
    navigate(trimmed ? `/species?q=${encodeURIComponent(trimmed)}` : '/species');
  };

  return (
    <div className="space-y-12 pb-8">
      {/* Educational Disclaimer Top Banner */}
      <div className="bg-[#DCFCE7] border-b border-[#86EFAC]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs sm:text-sm text-[#166534]">
          <div className="flex items-center gap-2 font-semibold">
            <ShieldAlert className="w-4 h-4 shrink-0" aria-hidden="true" />
            <span>Informasi Edukasi - Bukan Pengganti Nasihat Medis</span>
          </div>
          <Link
            to="/about"
            className="font-semibold underline underline-offset-4 shrink-0 hover:text-[#14532D]"
          >
            Metodologi &amp; Batasan Sistem
          </Link>
        </div>
      </div>

      {/* Hero Section: Centered Complaint-Based Herbal Search */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-2">
        <div className="bg-white rounded-2xl border border-[#DCE5DF] shadow-sm p-6 sm:p-10 lg:p-12">
          <div className="max-w-3xl mx-auto text-center space-y-5">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-[#F0FDF4] border border-[#BBF7D0] text-xs font-semibold text-[#166534]">
              <HerbLogoIcon className="w-4 h-4" />
              <span>
                HERB-INFO AI — Intelligent Symptom Understanding &amp; Herbal Information Retrieval
              </span>
            </div>

            <h1 className="text-2xl sm:text-4xl font-bold text-[#1F2937] tracking-tight leading-tight">
              Cari Informasi Ramuan Tradisional Berdasarkan Keluhan
            </h1>

            <p className="text-base sm:text-lg text-[#4B5563] leading-relaxed">
              Jelaskan keluhan kesehatan menggunakan bahasa Indonesia sehari-hari. Sistem cerdas
              memahami keluhan, memeriksa tanda bahaya &amp; keselamatan, serta menemukan maksimal 3
              referensi ramuan tradisional terkurasi dari sumber resmi FROTI Kemenkes &amp; BPOM.
            </p>

            {/* Primary Search Bar in the Center */}
            <form onSubmit={handleSearchRamuan} className="pt-2 space-y-3 text-left">
              <div className="grid grid-cols-1 md:grid-cols-12 gap-2.5">
                <div className="md:col-span-8 relative">
                  <Search
                    className="w-5 h-5 text-[#4B5563] absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none"
                    aria-hidden="true"
                  />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Contoh: Saya demam, ada informasi ramuan tradisional?"
                    aria-label="Cari Informasi Ramuan Tradisional Berdasarkan Keluhan"
                    className="w-full pl-12 pr-4 py-4 bg-[#F8FAF8] border-2 border-[#DCE5DF] rounded-xl text-sm sm:text-base text-[#1F2937] placeholder-[#4B5563] focus:bg-white focus:border-[#166534]"
                  />
                </div>
                <div className="md:col-span-4">
                  <select
                    aria-label="Pilih Kelompok Usia atau Kondisi"
                    value={selectedAgeGroup}
                    onChange={(e) => setSelectedAgeGroup(e.target.value)}
                    className="w-full h-full px-3.5 py-3.5 bg-[#F8FAF8] border-2 border-[#DCE5DF] rounded-xl text-xs sm:text-sm font-semibold text-[#1F2937] focus:border-[#166534]"
                  >
                    {AGE_GROUP_OPTIONS.map((opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-center gap-3 pt-1">
                <button
                  type="submit"
                  className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl text-sm sm:text-base font-semibold bg-[#166534] text-white hover:bg-[#14532D] transition-colors min-h-[46px]"
                >
                  <FileSearch className="w-4 h-4" aria-hidden="true" />
                  <span>Analisis Keluhan &amp; Cari Informasi Ramuan</span>
                </button>

                <button
                  type="button"
                  onClick={handleSearchSpecies}
                  className="inline-flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl text-sm font-semibold bg-[#F0FDF4] text-[#166534] border border-[#86EFAC] hover:bg-[#DCFCE7] transition-colors min-h-[46px]"
                >
                  <Sprout className="w-4 h-4" aria-hidden="true" />
                  <span>Cari di Katalog Tanaman</span>
                </button>

                <Link
                  to="/recipes"
                  className="inline-flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl text-sm font-semibold bg-white text-[#1F2937] border border-[#DCE5DF] hover:border-[#166534] hover:text-[#166534] transition-colors min-h-[46px]"
                >
                  <FlaskConical className="w-4 h-4 text-[#166534]" aria-hidden="true" />
                  <span>Lihat Resep Tradisional</span>
                </Link>
              </div>

              {/* Clickable Example Queries Required in Section 2 */}
              <div className="pt-3 flex flex-wrap items-center justify-center gap-2 text-xs">
                <span className="font-semibold text-[#4B5563]">Contoh pertanyaan populer:</span>
                {HERO_EXAMPLE_QUERIES.map((example) => (
                  <Link
                    key={example}
                    to={`/search?q=${encodeURIComponent(example)}`}
                    className="px-3 py-1.5 rounded-xl bg-[#F0FDF4] text-[#166534] border border-[#BBF7D0] hover:bg-[#DCFCE7] font-medium transition-colors"
                  >
                    {example}
                  </Link>
                ))}
              </div>
            </form>
          </div>
        </div>
      </section>

      {/* Error State */}
      {error && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div
            role="alert"
            className="bg-[#FEE2E2] border border-[#FCA5A5] rounded-2xl p-6 text-[#991B1B] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
          >
            <div className="flex items-start gap-3">
              <AlertCircle className="w-6 h-6 shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <h2 className="font-bold text-base">Gagal Memuat Data dari Server</h2>
                <p className="text-sm mt-1">{error}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={loadHomeData}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#991B1B] text-white text-sm font-semibold hover:bg-[#7F1D1D] min-h-[44px]"
            >
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
              <span>Coba Lagi</span>
            </button>
          </div>
        </section>
      )}

      {/* Curated Herbal Recipes Preview Section */}
      <section
        aria-labelledby="featured-recipes-heading"
        className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-4"
      >
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
          <div>
            <h2 id="featured-recipes-heading" className="text-xl font-bold text-[#1F2937]">
              Resep Ramuan Tradisional Terkurasi
            </h2>
            <p className="text-sm text-[#4B5563]">
              Informasi komposisi bahan, langkah pembuatan, peringatan keselamatan, dan sumber
              referensinya.
            </p>
          </div>
          <Link
            to="/recipes"
            className="inline-flex items-center justify-center px-4 py-2.5 rounded-xl text-sm font-semibold bg-white border border-[#DCE5DF] text-[#166534] hover:bg-[#F0FDF4] transition-colors min-h-[42px]"
          >
            Lihat Semua Resep ({stats?.total_recipes ?? featuredRecipes.length})
          </Link>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {[1, 2].map((n) => (
              <div
                key={n}
                className="bg-white rounded-2xl border border-[#DCE5DF] h-52 animate-pulse p-5"
              />
            ))}
          </div>
        ) : featuredRecipes.length === 0 ? (
          <div className="bg-white rounded-2xl border border-[#DCE5DF] p-6 text-center text-sm text-[#4B5563]">
            Belum ditemukan ramuan terverifikasi. Anda dapat membaca sumber informasi umum yang
            relevan pada menu Sumber Resmi.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {featuredRecipes.map((rec) => (
              <article
                key={rec.id}
                className="bg-white rounded-2xl border border-[#DCE5DF] hover:border-[#16A34A] p-5 shadow-sm flex flex-col justify-between space-y-4 transition-all"
              >
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="px-2.5 py-0.5 rounded-md font-mono text-xs font-bold bg-[#166534] text-white">
                      {rec.recipe_code}
                    </span>
                    <span className="px-2.5 py-0.5 rounded-md text-xs font-semibold bg-[#DCFCE7] text-[#166534] border border-[#86EFAC]">
                      {rec.status_verifikasi}
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-[#1F2937]">{rec.nama_ramuan}</h3>
                  <p className="text-xs font-semibold text-[#166534]">
                    Keluhan dalam Referensi: {rec.keluhan_terkait}
                  </p>
                  <p className="text-xs sm:text-sm text-[#4B5563] line-clamp-2 leading-relaxed">
                    {rec.deskripsi}
                  </p>
                </div>

                <div className="pt-3 border-t border-[#F1F5F9] flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs text-[#4B5563]">{rec.nama_sumber}</span>
                  <Link
                    to={`/recipes/${rec.slug}`}
                    className="inline-flex items-center px-3.5 py-2 rounded-xl bg-[#166534] text-white text-xs font-semibold hover:bg-[#14532D] transition-colors min-h-[38px]"
                  >
                    Lihat Resep dan Peringatan
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {/* Real Database Statistics Section */}
      <section
        aria-labelledby="stats-heading"
        className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-4"
      >
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2">
          <div>
            <h2 id="stats-heading" className="text-xl font-bold text-[#1F2937]">
              Statistik Aktual Basis Data
            </h2>
            <p className="text-sm text-[#4B5563]">
              Dihitung secara langsung dari database SQLite hasil impor dataset asli.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((n) => (
              <div
                key={n}
                className="bg-white rounded-2xl border border-[#DCE5DF] p-5 h-28 animate-pulse"
              >
                <div className="h-4 w-24 bg-gray-200 rounded mb-3" />
                <div className="h-8 w-16 bg-gray-200 rounded" />
              </div>
            ))}
          </div>
        ) : stats ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white rounded-2xl border border-[#DCE5DF] p-5 shadow-sm">
              <div className="flex items-center justify-between text-[#166534] mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">
                  Tanaman Tercatat
                </span>
                <Sprout className="w-5 h-5" aria-hidden="true" />
              </div>
              <p className="text-3xl font-bold text-[#1F2937]">{stats.total_plants}</p>
              <p className="text-xs text-[#4B5563] mt-1">
                {stats.plants_with_scientific_name} bernama ilmiah, {stats.plants_local_only} nama
                lokal saja
              </p>
            </div>

            <div className="bg-white rounded-2xl border border-[#DCE5DF] p-5 shadow-sm">
              <div className="flex items-center justify-between text-[#166534] mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">
                  Resep Terdokumentasi
                </span>
                <FlaskConical className="w-5 h-5" aria-hidden="true" />
              </div>
              <p className="text-3xl font-bold text-[#1F2937]">{stats.total_recipes}</p>
              <p className="text-xs text-[#4B5563] mt-1">
                Komposisi bahan, langkah pembuatan &amp; status verifikasi
              </p>
            </div>

            <div className="bg-white rounded-2xl border border-[#DCE5DF] p-5 shadow-sm">
              <div className="flex items-center justify-between text-[#166534] mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">
                  Rekaman Q&amp;A Riset
                </span>
                <BookOpen className="w-5 h-5" aria-hidden="true" />
              </div>
              <p className="text-3xl font-bold text-[#1F2937]">{stats.total_qa}</p>
              <p className="text-xs text-[#4B5563] mt-1">
                {stats.strict_review_qa_count} entri ditandai untuk tinjauan ketat
              </p>
            </div>

            <div className="bg-white rounded-2xl border border-[#DCE5DF] p-5 shadow-sm">
              <div className="flex items-center justify-between text-[#166534] mb-2">
                <span className="text-xs font-semibold uppercase tracking-wider">
                  Sumber Resmi BPOM
                </span>
                <Database className="w-5 h-5" aria-hidden="true" />
              </div>
              <p className="text-3xl font-bold text-[#1F2937]">{stats.total_sources}</p>
              <p className="text-xs text-[#4B5563] mt-1">
                9 rujukan BPOM RI + struktur FROTI Kemenkes RI
              </p>
            </div>
          </div>
        ) : null}
      </section>

      {/* Shortcut Categories */}
      <section
        aria-labelledby="categories-heading"
        className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-4"
      >
        <h2 id="categories-heading" className="text-xl font-bold text-[#1F2937]">
          Kategori Pintasan Eksplorasi
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link
            to="/recipes"
            className="bg-white rounded-2xl border border-[#DCE5DF] p-5 hover:border-[#16A34A] hover:shadow-sm transition-all group flex flex-col justify-between"
          >
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-xl bg-[#DCFCE7] text-[#166534] flex items-center justify-center">
                <FlaskConical className="w-5 h-5" aria-hidden="true" />
              </div>
              <h3 className="font-bold text-base text-[#1F2937] group-hover:text-[#166534]">
                Resep Tradisional
              </h3>
              <p className="text-xs text-[#4B5563] leading-relaxed">
                Lihat komposisi bahan, langkah pembuatan, peringatan, dan kontraindikasi ramuan
                tradisional yang telah dikurasi.
              </p>
            </div>
            <span className="text-xs font-semibold text-[#166534] mt-4">
              Buka Resep Tradisional
            </span>
          </Link>

          <Link
            to="/species"
            className="bg-white rounded-2xl border border-[#DCE5DF] p-5 hover:border-[#16A34A] hover:shadow-sm transition-all group flex flex-col justify-between"
          >
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-xl bg-[#DCFCE7] text-[#166534] flex items-center justify-center">
                <Sprout className="w-5 h-5" aria-hidden="true" />
              </div>
              <h3 className="font-bold text-base text-[#1F2937] group-hover:text-[#166534]">
                Katalog Tanaman
              </h3>
              <p className="text-xs text-[#4B5563] leading-relaxed">
                Telusuri katalog spesies tanaman obat beserta nama ilmiah, nama daerah, dan rujukan
                topiknya.
              </p>
            </div>
            <span className="text-xs font-semibold text-[#166534] mt-4">
              Buka Katalog Tanaman
            </span>
          </Link>

          <Link
            to="/knowledge?topic=keamanan"
            className="bg-white rounded-2xl border border-[#DCE5DF] p-5 hover:border-[#16A34A] hover:shadow-sm transition-all group flex flex-col justify-between"
          >
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-xl bg-[#FEF3C7] text-[#92400E] flex items-center justify-center">
                <ShieldAlert className="w-5 h-5" aria-hidden="true" />
              </div>
              <h3 className="font-bold text-base text-[#1F2937] group-hover:text-[#166534]">
                Keamanan Herbal
              </h3>
              <p className="text-xs text-[#4B5563] leading-relaxed">
                Pahami risiko Bahan Kimia Obat (BKO), potensi interaksi herbal-obat medis, dan
                peringatan kelompok rentan.
              </p>
            </div>
            <span className="text-xs font-semibold text-[#166534] mt-4">
              Pelajari Keamanan Herbal
            </span>
          </Link>

          <Link
            to="/sources"
            className="bg-white rounded-2xl border border-[#DCE5DF] p-5 hover:border-[#16A34A] hover:shadow-sm transition-all group flex flex-col justify-between"
          >
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-xl bg-[#DCFCE7] text-[#166534] flex items-center justify-center">
                <Scale className="w-5 h-5" aria-hidden="true" />
              </div>
              <h3 className="font-bold text-base text-[#1F2937] group-hover:text-[#166534]">
                Sumber Resmi BPOM &amp; Kemenkes
              </h3>
              <p className="text-xs text-[#4B5563] leading-relaxed">
                Baca rujukan resmi BPOM RI (Jamu, OHT, Fitofarmaka) dan dokumen regulasi FROTI
                Kementerian Kesehatan RI.
              </p>
            </div>
            <span className="text-xs font-semibold text-[#166534] mt-4">
              Buka Sumber Resmi
            </span>
          </Link>
        </div>
      </section>

      {/* Featured Plants Section */}
      <section
        aria-labelledby="explore-plants-heading"
        className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-5"
      >
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
          <div>
            <h2 id="explore-plants-heading" className="text-xl font-bold text-[#1F2937]">
              Jelajahi Katalog Tanaman Obat
            </h2>
            <p className="text-sm text-[#4B5563]">
              Spesies tanaman obat yang tercatat dalam basis data beserta status verifikasinya.
            </p>
          </div>
          <Link
            to="/species"
            className="inline-flex items-center justify-center px-4 py-2.5 rounded-xl text-sm font-semibold bg-white border border-[#DCE5DF] text-[#166534] hover:bg-[#F0FDF4] transition-colors min-h-[42px]"
          >
            Lihat Semua Spesies ({stats ? stats.total_plants : 30})
          </Link>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <div
                key={n}
                className="bg-white rounded-2xl border border-[#DCE5DF] h-80 animate-pulse p-5"
              />
            ))}
          </div>
        ) : featuredPlants.length === 0 ? (
          <div className="bg-white rounded-2xl border border-[#DCE5DF] p-8 text-center space-y-2">
            <p className="font-semibold text-[#1F2937]">Belum ada tanaman tercatat</p>
            <p className="text-sm text-[#4B5563]">
              Pastikan berkas dataset berada di folder data/incoming dan jalankan importer.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {featuredPlants.map((plant) => (
              <PlantCard key={plant.id} plant={plant} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
};
