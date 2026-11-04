import React from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, ShieldAlert } from 'lucide-react';
import { HerbLogoIcon } from './BotanicalPlaceholder';

export const Footer: React.FC = () => {
  return (
    <footer className="bg-white border-t border-[#DCE5DF] mt-16">
      {/* Mandatory Medical Disclaimer Banner */}
      <div className="bg-[#FEF3C7]/70 border-b border-[#FCD34D]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-col sm:flex-row items-start sm:items-center gap-2.5 text-xs sm:text-sm text-[#92400E]">
          <ShieldAlert className="w-5 h-5 shrink-0 text-[#92400E]" aria-hidden="true" />
          <p className="font-medium">
            Konten ini bersifat edukatif dan bukan pengganti nasihat tenaga kesehatan. Sistem tidak
            memberikan diagnosis, takaran dosis, atau rekomendasi terapi klinis.
          </p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
          <div className="md:col-span-6 space-y-3">
            <div className="flex items-center gap-3">
              <HerbLogoIcon className="w-8 h-8" />
              <span className="font-bold text-base text-[#166534]">HERB-INFO AI</span>
            </div>
            <p className="text-sm text-[#4B5563] max-w-xl leading-relaxed">
              Ensiklopedia dan sistem temu kembali informasi tanaman obat tradisional Indonesia
              untuk proyek mata kuliah Sistem Cerdas. Mengintegrasikan pencarian Baseline TF-IDF,
              audit matriks embedding semantik, serta pemisahan tegas antara rujukan topik BPOM dan
              data penelitian komunitas Kaggle.
            </p>
          </div>

          <div className="md:col-span-3 space-y-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#166534]">
              Halaman Aplikasi
            </h2>
            <ul className="space-y-1.5 text-sm text-[#4B5563]">
              <li>
                <Link to="/species" className="hover:text-[#166534] underline-offset-4 hover:underline">
                  Katalog Tanaman Obat
                </Link>
              </li>
              <li>
                <Link to="/search" className="hover:text-[#166534] underline-offset-4 hover:underline">
                  Pencarian Cerdas (TF-IDF)
                </Link>
              </li>
              <li>
                <Link to="/knowledge" className="hover:text-[#166534] underline-offset-4 hover:underline">
                  Pengetahuan &amp; Tanya Jawab (52 Q&amp;A)
                </Link>
              </li>
              <li>
                <Link to="/sources" className="hover:text-[#166534] underline-offset-4 hover:underline">
                  Pusat Referensi BPOM (9 Sumber)
                </Link>
              </li>
              <li>
                <Link to="/about" className="hover:text-[#166534] underline-offset-4 hover:underline">
                  Metodologi &amp; Keterbatasan Riset
                </Link>
              </li>
            </ul>
          </div>

          <div className="md:col-span-3 space-y-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#166534]">
              Verifikasi Izin Edar Resmi
            </h2>
            <p className="text-xs text-[#4B5563] leading-relaxed">
              Keberadaan nama tanaman di katalog ini tidak berarti produk komersial tertentu telah
              terdaftar. Periksa nomor izin edar secara mandiri di portal resmi BPOM:
            </p>
            <a
              href="https://cekbpom.pom.go.id/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#166534] bg-[#DCFCE7] hover:bg-[#BBF7D0] px-3.5 py-2.5 rounded-xl transition-colors min-h-[40px]"
            >
              <span>Buka CekBPOM Resmi</span>
              <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
            </a>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-[#DCE5DF] flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[#4B5563]">
          <span>HERB-INFO AI : Proyek Sistem Cerdas (Data Riil Terverifikasi Skema)</span>
          <span>Desain Orisinal HERB-INFO AI (Bukan Afiliasi Resmi BPOM RI)</span>
        </div>
      </div>
    </footer>
  );
};
