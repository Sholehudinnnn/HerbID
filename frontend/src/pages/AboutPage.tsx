import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  BookOpen,
  CheckCircle2,
  Cpu,
  Database,
  FileCode2,
  ShieldAlert,
} from 'lucide-react';
import {
  EvaluationDetailsResponse,
  fetchEvaluationDetails,
  getEdaImageUrl,
} from '../lib/api';

const PIPELINE_STEPS = [
  {
    step: '1. Dataset Kaggle',
    desc: '52 rekaman Q&A JSONL pengobatan tradisional Indonesia (belum terverifikasi medis).',
  },
  {
    step: '2. EDA & Pembersihan',
    desc: 'Analisis distribusi panjang teks, penandaan 14 Q&A berisiko tinggi (review ketat).',
  },
  {
    step: '3. Ekstraksi Entitas',
    desc: 'Pemisahan 30 entitas tanaman (27 bernama ilmiah, 3 nama lokal) dari 25 topik non-spesies.',
  },
  {
    step: '4. Baseline TF-IDF',
    desc: 'Indeks deterministik TfidfVectorizer (1-2 gram, stopword ID) terhadap 9 sumber resmi BPOM.',
  },
  {
    step: '5. Embedding Semantik',
    desc: 'Audit matriks bpom_semantic_embeddings.npy (9x384) dari paraphrase-multilingual-MiniLM-L12-v2.',
  },
  {
    step: '6. Pengaman & Web API',
    desc: 'Deteksi topik klinis sensitif, FastAPI + SQLite, dan antarmuka katalog React.',
  },
];

const VALIDATION_DICTIONARY = [
  {
    label: 'BELUM_TERVERIFIKASI',
    badgeClass: 'bg-[#FEF3C7] text-[#92400E] border-[#FCD34D]',
    meaning:
      'Data Q&A berasal dari kontribusi komunitas Kaggle dan belum melewati kurasi dokter atau apoteker.',
  },
  {
    label: 'Perlu Tinjauan Ketat (indikasi_perlu_review_ketat=True)',
    badgeClass: 'bg-[#FEE2E2] text-[#991B1B] border-[#FCA5A5]',
    meaning:
      'Terdapat 14 pertanyaan yang menyinggung kelompok rentan (ibu hamil, bayi, pasca melahirkan), penyakit serius, interaksi obat, atau klaim dosis.',
  },
  {
    label: 'KANDIDAT_TOPIK_PERLU_VERIFIKASI',
    badgeClass: 'bg-[#DCFCE7] text-[#166534] border-[#86EFAC]',
    meaning:
      'Pertanyaan memiliki kemiripan topik dengan salah satu sumber resmi BPOM (15 relasi pada 14 pertanyaan unik), namun bukan pengesahan atas seluruh isi jawaban.',
  },
  {
    label: 'PERLU_REFERENSI_TAMBAHAN',
    badgeClass: 'bg-[#F3F4F6] text-[#374151] border-[#D1D5DB]',
    meaning:
      'Sebanyak 38 pertanyaan belum memiliki rujukan topik langsung di dalam 9 sumber BPOM yang tersedia saat ini.',
  },
  {
    label: 'RUJUKAN_BPOM_PERLU_KURASI_PER_KLAIM',
    badgeClass: 'bg-[#E0F2FE] text-[#075985] border-[#7DD3FC]',
    meaning:
      'Sumber berasal dari domain resmi BPOM, tetapi penggunaannya untuk memvalidasi klaim spesifik tetap memerlukan kurasi manual per klaim.',
  },
];

export const AboutPage: React.FC = () => {
  const [evalData, setEvalData] = useState<EvaluationDetailsResponse | null>(null);
  const [imgError, setImgError] = useState(false);

  useEffect(() => {
    fetchEvaluationDetails()
      .then(setEvalData)
      .catch(() => {
        // non-blocking
      });
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-[#DCFCE7] text-[#166534] text-xs font-semibold">
          <Cpu className="w-4 h-4" aria-hidden="true" />
          <span>Dokumentasi Metodologi Sistem Cerdas</span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-bold text-[#1F2937]">
          Tentang Proyek HERB-INFO AI
        </h1>

        <p className="text-sm sm:text-base text-[#4B5563] leading-relaxed max-w-4xl">
          <strong>HERB-INFO AI</strong> dibangun sebagai prototipe ensiklopedia dan sistem temu
          kembali informasi (<em>information retrieval</em>) tanaman obat tradisional Indonesia.
          Sistem ini dirancang dengan prinsip kejujuran data: tidak mengarang taksonomi, tidak
          mengklaim skor akurasi semu, serta memisahkan rujukan regulasi BPOM dari teks komunitas.
        </p>
      </section>

      {/* Pipeline Flowchart Section */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-5">
        <div className="flex items-center gap-2 text-[#166534]">
          <Database className="w-5 h-5" aria-hidden="true" />
          <h2 className="text-xl font-bold text-[#1F2937]">Alur Metodologi Penelitian</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
          {PIPELINE_STEPS.map((item, idx) => (
            <div
              key={item.step}
              className="relative p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] flex flex-col justify-between"
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs font-bold text-[#166534]">
                  <span>Tahap {idx + 1}</span>
                  {idx < PIPELINE_STEPS.length - 1 && (
                    <ArrowRight className="w-3.5 h-3.5 hidden lg:inline text-[#16A34A]" />
                  )}
                </div>
                <h3 className="font-bold text-sm text-[#1F2937]">{item.step}</h3>
                <p className="text-xs text-[#4B5563] leading-relaxed">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Limitations & Scientific Integrity + EDA Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <section className="lg:col-span-6 bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
          <div className="flex items-center gap-2 text-[#92400E]">
            <AlertTriangle className="w-5 h-5" aria-hidden="true" />
            <h2 className="text-xl font-bold text-[#1F2937]">
              Keterbatasan Dataset &amp; Validitas Klinis
            </h2>
          </div>

          <ul className="space-y-3 text-sm text-[#374151] leading-relaxed">
            <li className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF]">
              <strong>1. Ukuran Sampel Terbatas (52 Q&amp;A):</strong> Korpus tanya-jawab hanya
              berisi 52 baris instruksi dan tidak mewakili seluruh kekayaan etnobotani Indonesia.
            </li>
            <li className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF]">
              <strong>2. Bias &amp; Klaim Komunitas:</strong> Jawaban asli pada dataset Kaggle
              memuat klaim empiris yang belum teruji klinis. Oleh karena itu, sistem menyembunyikan
              teks mentah di balik panel peringatan riset.
            </li>
            <li className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF]">
              <strong>3. Cakupan Sumber BPOM (9 Dokumen Topik):</strong> Rujukan BPOM pada CSV
              berfokus pada regulasi, keamanan BKO, interaksi obat, jamu gendong, serta standar mutu
              bahan baku; sebanyak 38 dari 52 pertanyaan masih berstatus{' '}
              <code className="font-mono text-xs">PERLU_REFERENSI_TAMBAHAN</code>.
            </li>
            <li className="p-3.5 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF]">
              <strong>4. Kemiripan Teks Bukan Bukti Klinis:</strong> Skor{' '}
              <em>cosine similarity</em> pada TF-IDF maupun embedding semantik hanya mengukur
              kedekatan leksikal/topik, bukan efikasi atau keamanan medis.
            </li>
          </ul>
        </section>

        {/* EDA Distribution Image & Evaluation Audit */}
        <section className="lg:col-span-6 bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-5">
          <div className="flex items-center gap-2 text-[#166534]">
            <BarChart3 className="w-5 h-5" aria-hidden="true" />
            <h2 className="text-xl font-bold text-[#1F2937]">
              Artefak EDA &amp; Status Evaluasi Manual
            </h2>
          </div>

          {!imgError ? (
            <div className="rounded-xl border border-[#DCE5DF] overflow-hidden bg-[#F8FAF8] p-3">
              <img
                src={getEdaImageUrl()}
                alt="Grafik distribusi panjang pertanyaan dan jawaban dari HERB_INFO_AI_Hasil_Colab.zip"
                className="w-full h-auto rounded-lg"
                onError={() => setImgError(true)}
              />
              <p className="text-xs text-[#4B5563] mt-2 text-center">
                Visualisasi asli <code>eda_distribusi_panjang.png</code> dari arsip hasil Google
                Colab.
              </p>
            </div>
          ) : (
            <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] text-xs text-[#4B5563]">
              Grafik EDA belum dapat dimuat dari endpoint artefak.
            </div>
          )}

          {/* Evaluation Status Box */}
          <div className="p-4 rounded-xl bg-[#FEF3C7]/60 border border-[#FCD34D] space-y-2">
            <h3 className="font-bold text-sm text-[#92400E]">
              Status Evaluasi Hit@1, Recall@3, dan MRR@10
            </h3>
            <p className="text-xs text-[#92400E] leading-relaxed">
              {evalData?.evaluation.note ||
                'Seluruh 52 baris pada template_evaluasi_manual.csv masih memiliki gold_source_id kosong. Skor akurasi tidak diklaim sebelum anotasi manual selesai.'}
            </p>
          </div>

          {/* Index Metadata Box */}
          {evalData?.index_metadata && (
            <div className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-1.5 text-xs font-mono text-[#374151]">
              <div className="font-sans font-bold text-[#166534] mb-1">
                Metadata Indeks Terverifikasi:
              </div>
              <div>Jumlah Sumber: {evalData.index_metadata.source_count} dokumen</div>
              <div>
                Dimensi Embedding Colab:{' '}
                {evalData.index_metadata.semantic_embeddings_shape
                  ? evalData.index_metadata.semantic_embeddings_shape.join(' x ')
                  : 'N/A'}
              </div>
              <div>Versi scikit-learn: {evalData.index_metadata.sklearn_version}</div>
              <div className="truncate">
                Hash SHA-256 Korpus: {evalData.index_metadata.corpus_sha256}
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Validation Label Dictionary */}
      <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
        <div className="flex items-center gap-2 text-[#166534]">
          <BookOpen className="w-5 h-5" aria-hidden="true" />
          <h2 className="text-xl font-bold text-[#1F2937]">Kamus Label Validasi &amp; Kurasi</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {VALIDATION_DICTIONARY.map((item) => (
            <div
              key={item.label}
              className="p-4 rounded-xl bg-[#F8FAF8] border border-[#DCE5DF] space-y-2"
            >
              <span
                className={`inline-block px-2.5 py-0.5 rounded-md text-xs font-bold border ${item.badgeClass}`}
              >
                {item.label}
              </span>
              <p className="text-xs sm:text-sm text-[#374151] leading-relaxed">{item.meaning}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 20 Functional Test Queries Table */}
      {evalData?.functional_test_queries && (
        <section className="bg-white rounded-2xl border border-[#DCE5DF] p-6 sm:p-8 shadow-sm space-y-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-[#166534]">
              <FileCode2 className="w-5 h-5" aria-hidden="true" />
              <h2 className="text-xl font-bold text-[#1F2937]">
                Daftar 20 Query Uji Fungsional &amp; Pengaman
              </h2>
            </div>
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#166534] bg-[#DCFCE7] px-3 py-1 rounded-lg">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Bukan Gold Label Evaluasi</span>
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs sm:text-sm">
              <thead>
                <tr className="border-b border-[#DCE5DF] bg-[#F8FAF8] text-[#374151]">
                  <th className="py-2.5 px-3 font-semibold">Kode</th>
                  <th className="py-2.5 px-3 font-semibold">Kategori Uji</th>
                  <th className="py-2.5 px-3 font-semibold">Query Uji</th>
                  <th className="py-2.5 px-3 font-semibold">Perilaku Sistem yang Diharapkan</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F1F5F9]">
                {evalData.functional_test_queries.map((fq) => (
                  <tr key={fq.id} className="hover:bg-[#F8FAF8]">
                    <td className="py-2.5 px-3 font-mono font-semibold text-[#166534]">
                      {fq.id}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-xs text-[#4B5563]">
                      {fq.category}
                    </td>
                    <td className="py-2.5 px-3 font-medium text-[#1F2937]">
                      {fq.query.trim() ? fq.query : '(String spasi kosong)'}
                    </td>
                    <td className="py-2.5 px-3 text-[#4B5563]">{fq.expected_behavior}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Medical Non-Replacement Notice */}
      <section className="bg-[#FEF2F2] rounded-2xl border border-[#FCA5A5] p-6 text-[#991B1B] flex items-start gap-3">
        <ShieldAlert className="w-6 h-6 shrink-0 mt-0.5" aria-hidden="true" />
        <div className="space-y-1 text-xs sm:text-sm">
          <h2 className="font-bold text-base">Pernyataan Batasan Tanggung Jawab Medis</h2>
          <p className="leading-relaxed">
            Aplikasi HERB-INFO AI dikembangkan semata-mata untuk tujuan pendidikan dan penelitian
            akademik pada mata kuliah Sistem Cerdas. Sistem ini bukan alat diagnosis medis dan tidak
            menggantikan konsultasi dengan dokter atau apoteker berlisensi.
          </p>
        </div>
      </section>
    </div>
  );
};
