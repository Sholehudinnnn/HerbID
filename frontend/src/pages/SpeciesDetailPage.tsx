import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  FileCheck2,
  Info,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';
import { fetchSpeciesDetail, PlantDetailData } from '../lib/api';
import { BotanicalPlaceholder } from '../components/BotanicalPlaceholder';
import { getVerificationBadgeStyle } from '../components/PlantCard';

type DetailTab = 'ringkasan' | 'nama_lokal' | 'pengetahuan' | 'referensi_keamanan';

export const SpeciesDetailPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const [plant, setPlant] = useState<PlantDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<DetailTab>('ringkasan');
  const [openQaIds, setOpenQaIds] = useState<Record<number, boolean>>({});

  const loadDetail = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    setNotFound(false);
    setError(null);
    try {
      const res = await fetchSpeciesDetail(slug);
      setPlant(res);
    } catch (err) {
      const status = (err as Error & { status?: number }).status;
      if (status === 404) {
        setNotFound(true);
      } else {
        setError(
          err instanceof Error
            ? err.message
            : 'Gagal memuat detail tanaman dari server.'
        );
      }
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  const toggleQaPanel = (qaId: number) => {
    setOpenQaIds((prev) => ({ ...prev, [qaId]: !prev[qaId] }));
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="h-6 w-48 bg-gray-200 rounded animate-pulse" />
        <div className="bg-white rounded-2xl border border-[#DCE5DF] p-6 h-80 animate-pulse" />
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="bg-white rounded-2xl border border-[#DCE5DF] p-8 sm:p-10 text-center space-y-4 shadow-sm">
          <div className="w-12 h-12 rounded-2xl bg-[#FEF3C7] text-[#92400E] flex items-center justify-center mx-auto">
            <AlertTriangle className="w-6 h-6" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-bold text-[#1F2937]">
            Spesies Tanaman Tidak Ditemukan (404)
          </h1>
          <p className="text-sm sm:text-base text-[#4B5563]">
            Tanaman dengan identifier <code className="font-mono bg-gray-100 px-1.5 py-0.5 rounded">{slug}</code> tidak
            terdaftar dalam database HERB-INFO AI. Sistem tidak menampilkan data spekulatif untuk
            entitas yang belum diimpor.
          </p>
          <div className="pt-2">
            <Link
              to="/species"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold bg-[#166534] text-white hover:bg-[#14532D] min-h-[44px]"
            >
              <ArrowLeft className="w-4 h-4" aria-hidden="true" />
              <span>Kembali ke Katalog Tanaman</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (error || !plant) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div
          role="alert"
          className="bg-[#FEE2E2] border border-[#FCA5A5] rounded-2xl p-6 text-[#991B1B] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
        >
          <div>
            <h1 className="font-bold text-lg">Gagal Memuat Halaman Detail</h1>
            <p className="text-sm mt-1">{error}</p>
          </div>
          <button
            type="button"
            onClick={loadDetail}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#991B1B] text-white text-sm font-semibold min-h-[44px]"
          >
            <RefreshCw className="w-4 h-4" aria-hidden="true" />
            <span>Coba Lagi</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Breadcrumb Navigation */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs sm:text-sm text-[#4B5563]">
        <Link
          to="/species"
          className="inline-flex items-center gap-1.5 font-semibold text-[#166534] hover:underline"
        >
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          <span>Katalog Tanaman</span>
        </Link>
        <span>/</span>
        <span className="text-[#1F2937] font-medium">{plant.nama_umum}</span>
      </nav>

      {/* Encyclopedia Header Card: Image/Placeholder Left, Taxonomy & Status Right */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] shadow-sm overflow-hidden">
        <div className="grid grid-cols-1 md:grid-cols-12">
          <div className="md:col-span-5 border-b md:border-b-0 md:border-r border-[#DCE5DF]">
            <BotanicalPlaceholder
              plantName={plant.nama_umum}
              scientificName={plant.nama_ilmiah}
              size="detail"
            />
          </div>

          <div className="md:col-span-7 p-6 sm:p-8 flex flex-col justify-between space-y-5">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`inline-flex items-center px-3 py-1 rounded-lg text-xs font-semibold border ${getVerificationBadgeStyle(
                    plant.status_verifikasi
                  )}`}
                >
                  Status: {plant.status_verifikasi}
                </span>
                <span className="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium bg-[#F8FAF8] border border-[#DCE5DF] text-[#374151]">
                  <FileCheck2 className="w-3.5 h-3.5 text-[#166534]" aria-hidden="true" />
                  <span>{plant.sumber_count} Rujukan Topik BPOM</span>
                </span>
              </div>

              <h1 className="text-2xl sm:text-4xl font-bold text-[#1F2937]">
                {plant.nama_umum}
              </h1>

              {plant.nama_ilmiah ? (
                <p className="text-lg sm:text-xl font-serif italic text-[#166534]">
                  {plant.nama_ilmiah}
                </p>
              ) : (
                <p className="text-sm text-[#4B5563]">
                  Nama ilmiah: <strong>Belum tersedia / Belum diverifikasi</strong>
                </p>
              )}

              <p className="text-xs sm:text-sm text-[#4B5563] leading-relaxed">
                Asal rekaman: {plant.sumber_data}
              </p>
            </div>

            <div className="pt-4 border-t border-[#F1F5F9] flex flex-wrap items-center justify-between gap-3">
              <div className="text-xs text-[#4B5563]">
                Lisensi visual: {plant.gambar_lisensi || 'Ilustrasi siluet botani generik'}
              </div>
              <a
                href={plant.cek_bpom_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-semibold bg-[#166534] text-white hover:bg-[#14532D] transition-colors min-h-[42px]"
              >
                <span>Cek Izin Edar di BPOM</span>
                <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Main Content Layout: 8-col Tabs + 4-col Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left/Main Column: Tabs */}
        <div className="lg:col-span-8 space-y-4">
          {/* Tab Buttons */}
          <div
            role="tablist"
            aria-label="Informasi detail tanaman"
            className="bg-white rounded-2xl border border-[#DCE5DF] p-2 flex flex-wrap gap-1.5"
          >
            {[
              { id: 'ringkasan', label: 'Ringkasan' },
              { id: 'nama_lokal', label: `Nama Lokal (${plant.nama_lokal.length})` },
              {
                id: 'pengetahuan',
                label: `Pengetahuan Terkait (${plant.pengetahuan_terkait.length})`,
              },
              {
                id: 'referensi_keamanan',
                label: `Referensi & Keamanan (${plant.referensi_bpom.length})`,
              },
            ].map((tab) => {
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => setActiveTab(tab.id as DetailTab)}
                  className={`px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-colors min-h-[42px] ${
                    active
                      ? 'bg-[#166534] text-white'
                      : 'text-[#1F2937] hover:bg-[#F0FDF4] hover:text-[#166534]'
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Tab Panels */}
          <div className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm">
            {activeTab === 'ringkasan' && (
              <div className="space-y-4">
                <h2 className="text-lg font-bold text-[#1F2937]">Ringkasan Terkurasi</h2>
                {plant.ringkasan_terkurasi ? (
                  <div className="space-y-3">
                    <p className="text-sm sm:text-base text-[#1F2937] leading-relaxed">
                      {plant.ringkasan_terkurasi}
                    </p>
                    <div className="p-4 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] text-xs text-[#166534]">
                      Catatan Kurasi: Ringkasan di atas disusun berdasarkan pencocokan tingkat topik
                      dengan sumber resmi BPOM dan tidak mengesahkan klaim dosis/terapi dari sumber
                      komunitas.
                    </div>
                  </div>
                ) : (
                  <div className="p-5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-2">
                    <p className="font-semibold text-sm text-[#1F2937]">
                      Belum ada ringkasan terverifikasi
                    </p>
                    <p className="text-xs sm:text-sm text-[#4B5563] leading-relaxed">
                      Spesies <strong>{plant.nama_umum}</strong> belum memiliki ringkasan yang
                      dikurasi dari sumber resmi BPOM dalam dataset saat ini. Anda dapat melihat
                      pertanyaan riset terkait pada tab <strong>Pengetahuan Terkait</strong>.
                    </p>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'nama_lokal' && (
              <div className="space-y-4">
                <h2 className="text-lg font-bold text-[#1F2937]">
                  Nama Umum &amp; Nama Daerah Tercatat
                </h2>
                <div className="space-y-3">
                  <div>
                    <span className="text-xs font-semibold uppercase tracking-wider text-[#4B5563]">
                      Nama Umum Utama
                    </span>
                    <p className="text-base font-bold text-[#1F2937] mt-1">{plant.nama_umum}</p>
                  </div>

                  <div className="pt-2 border-t border-[#F1F5F9]">
                    <span className="text-xs font-semibold uppercase tracking-wider text-[#4B5563]">
                      Nama Lokal / Sinonim pada Dataset
                    </span>
                    {plant.nama_lokal.length > 0 ? (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {plant.nama_lokal.map((lok) => (
                          <span
                            key={lok}
                            className="px-3 py-1.5 rounded-xl bg-[#F0FDF4] border border-[#86EFAC] text-sm font-semibold text-[#166534]"
                          >
                            {lok}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-[#4B5563] mt-1">
                        Belum ada nama daerah tambahan yang tercatat secara eksplisit pada dataset
                        untuk tanaman ini.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'pengetahuan' && (
              <div className="space-y-5">
                <div className="space-y-2">
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-[#FEF3C7] border border-[#FCD34D] text-xs font-bold text-[#92400E]">
                    <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
                    <span>Materi Kaggle - belum diverifikasi secara medis</span>
                  </div>
                  <h2 className="text-lg font-bold text-[#1F2937]">
                    Data Pengetahuan &amp; Tanya Jawab Terkait
                  </h2>
                  <p className="text-xs sm:text-sm text-[#4B5563]">
                    Rekaman Q&amp;A di bawah ini berasal dari korpus penelitian Kaggle. Jawaban
                    mentah disembunyikan di dalam panel riset agar tidak disalahartikan sebagai
                    rekomendasi pengobatan klinis.
                  </p>
                </div>

                {plant.pengetahuan_terkait.length === 0 ? (
                  <p className="text-sm text-[#4B5563]">
                    Tidak ada pertanyaan Q&amp;A yang terhubung dengan tanaman ini.
                  </p>
                ) : (
                  <div className="space-y-4">
                    {plant.pengetahuan_terkait.map((qa) => {
                      const isOpen = !!openQaIds[qa.id];
                      return (
                        <div
                          key={qa.id}
                          className="rounded-xl border border-[#DCE5DF] bg-[#F8FAF8] p-4 space-y-3"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-white border border-[#DCE5DF] text-[#374151]">
                                Q&amp;A #{qa.id}
                              </span>
                              <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D]">
                                Materi Kaggle - belum diverifikasi secara medis
                              </span>
                              {qa.indikasi_perlu_review_ketat && (
                                <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-[#FEE2E2] text-[#991B1B] border border-[#FCA5A5]">
                                  Perlu Tinjauan Ketat
                                </span>
                              )}
                            </div>

                            <span className="text-xs text-[#4B5563]">
                              Kaitan: {qa.tipe_kaitan === 'utama' ? 'Entitas Utama' : 'Disebut dalam Ramuan'}
                            </span>
                          </div>

                          <h3 className="font-bold text-base text-[#1F2937]">{qa.pertanyaan}</h3>

                          <div>
                            <button
                              type="button"
                              onClick={() => toggleQaPanel(qa.id)}
                              aria-expanded={isOpen}
                              className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#166534] bg-white border border-[#DCE5DF] hover:bg-[#DCFCE7] px-3 py-2 rounded-lg transition-colors min-h-[38px]"
                            >
                              <BookOpen className="w-3.5 h-3.5" aria-hidden="true" />
                              <span>
                                {isOpen
                                  ? 'Sembunyikan Teks Mentah Riset'
                                  : 'Buka Panel Riset (Teks Mentah Kaggle)'}
                              </span>
                              {isOpen ? (
                                <ChevronUp className="w-3.5 h-3.5" />
                              ) : (
                                <ChevronDown className="w-3.5 h-3.5" />
                              )}
                            </button>

                            {isOpen && (
                              <div className="mt-3 p-4 rounded-xl bg-white border border-[#FCD34D] space-y-2">
                                <p className="text-xs font-semibold text-[#92400E]">
                                  Peringatan Riset: {qa.peringatan_penelitian}
                                </p>
                                <p className="text-sm text-[#374151] leading-relaxed">
                                  {qa.jawaban_kaggle_asli}
                                </p>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'referensi_keamanan' && (
              <div className="space-y-6">
                {/* BPOM Topic References */}
                <div className="space-y-3">
                  <h2 className="text-lg font-bold text-[#1F2937]">
                    Rujukan Topik BPOM ({plant.referensi_bpom.length})
                  </h2>
                  {plant.referensi_bpom.length === 0 ? (
                    <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] text-sm text-[#4B5563]">
                      Belum ada rujukan topik langsung dari 9 sumber BPOM pada CSV untuk spesies
                      ini. Gunakan tombol <strong>Cek Izin Edar di BPOM</strong> untuk memeriksa
                      produk jadi secara spesifik.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {plant.referensi_bpom.map((ref) => (
                        <div
                          key={ref.source_id}
                          className="p-4 rounded-xl border border-[#DCE5DF] bg-[#F8FAF8] space-y-2"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="font-mono text-xs font-bold px-2.5 py-0.5 rounded bg-[#DCFCE7] text-[#166534] border border-[#86EFAC]">
                              {ref.source_id} ({ref.otoritas})
                            </span>
                            <span className="text-xs font-semibold px-2.5 py-0.5 rounded bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D]">
                              Kecocokan topik, bukan validasi klaim
                            </span>
                          </div>
                          <h3 className="font-bold text-base text-[#1F2937]">{ref.judul}</h3>
                          <p className="text-sm text-[#374151]">{ref.ringkasan_aman}</p>
                          {ref.catatan_kurasi && (
                            <p className="text-xs text-[#4B5563] italic">{ref.catatan_kurasi}</p>
                          )}
                          <div className="pt-1">
                            <a
                              href={ref.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#166534] hover:underline"
                            >
                              <span>Buka Tautan Asli ({ref.source_url})</span>
                              <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Safety Guidelines */}
                <div className="pt-4 border-t border-[#DCE5DF] space-y-3">
                  <div className="flex items-center gap-2 text-[#991B1B]">
                    <ShieldAlert className="w-5 h-5" aria-hidden="true" />
                    <h2 className="text-lg font-bold">Panduan Keamanan &amp; Peringatan Umum</h2>
                  </div>
                  <ul className="space-y-2.5 text-sm text-[#374151]">
                    {plant.peringatan_keamanan.map((warn, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2.5 p-3 rounded-xl bg-[#FEF2F2] border border-[#FECACA]"
                      >
                        <span className="font-bold text-[#991B1B]">{i + 1}.</span>
                        <span>{warn}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Sidebar Informasi Singkat */}
        <aside className="lg:col-span-4 bg-white rounded-2xl border border-[#DCE5DF] p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-2 text-[#166534] border-b border-[#DCE5DF] pb-3">
            <Info className="w-5 h-5" aria-hidden="true" />
            <h2 className="font-bold text-base text-[#1F2937]">Informasi Singkat</h2>
          </div>

          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-xs font-semibold text-[#4B5563]">Nama Umum</dt>
              <dd className="font-semibold text-[#1F2937] mt-0.5">{plant.nama_umum}</dd>
            </div>

            <div className="border-t border-[#F1F5F9] pt-2.5">
              <dt className="text-xs font-semibold text-[#4B5563]">Nama Ilmiah</dt>
              <dd className="mt-0.5">
                {plant.nama_ilmiah ? (
                  <span className="font-serif italic font-semibold text-[#166534]">
                    {plant.nama_ilmiah}
                  </span>
                ) : (
                  <span className="text-[#4B5563]">Belum tersedia / Belum diverifikasi</span>
                )}
              </dd>
            </div>

            <div className="border-t border-[#F1F5F9] pt-2.5">
              <dt className="text-xs font-semibold text-[#4B5563]">Famili</dt>
              <dd className="text-[#1F2937] mt-0.5">
                {plant.famili || 'Belum tersedia / Belum diverifikasi'}
              </dd>
            </div>

            <div className="border-t border-[#F1F5F9] pt-2.5">
              <dt className="text-xs font-semibold text-[#4B5563]">Nama Lokal / Daerah</dt>
              <dd className="text-[#1F2937] mt-0.5">
                {plant.nama_lokal.length > 0
                  ? plant.nama_lokal.join(', ')
                  : 'Belum ada sinonim daerah tambahan'}
              </dd>
            </div>

            <div className="border-t border-[#F1F5F9] pt-2.5">
              <dt className="text-xs font-semibold text-[#4B5563]">Asal Data</dt>
              <dd className="text-[#374151] text-xs mt-0.5 leading-relaxed">
                {plant.sumber_data}
              </dd>
            </div>

            <div className="border-t border-[#F1F5F9] pt-2.5">
              <dt className="text-xs font-semibold text-[#4B5563]">Pembaruan Data</dt>
              <dd className="font-mono text-xs text-[#374151] mt-0.5">{plant.updated_at}</dd>
            </div>

            <div className="border-t border-[#F1F5F9] pt-2.5">
              <dt className="text-xs font-semibold text-[#4B5563]">Jumlah Rujukan Topik BPOM</dt>
              <dd className="font-semibold text-[#166534] mt-0.5">
                {plant.sumber_count} sumber resmi
              </dd>
            </div>
          </dl>

          <div className="pt-3 border-t border-[#DCE5DF]">
            <a
              href={plant.cek_bpom_url}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-xs font-semibold bg-[#F0FDF4] text-[#166534] border border-[#86EFAC] hover:bg-[#DCFCE7] transition-colors min-h-[44px]"
            >
              <span>Cek Izin Edar di BPOM</span>
              <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
            </a>
          </div>
        </aside>
      </div>
    </div>
  );
};
