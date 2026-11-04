import React from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowLeft } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
      <div className="bg-white rounded-2xl border border-[#DCE5DF] p-8 sm:p-10 text-center space-y-4 shadow-sm">
        <div className="w-12 h-12 rounded-2xl bg-[#FEF3C7] text-[#92400E] flex items-center justify-center mx-auto">
          <AlertTriangle className="w-6 h-6" aria-hidden="true" />
        </div>
        <h1 className="text-2xl font-bold text-[#1F2937]">Halaman Tidak Ditemukan (404)</h1>
        <p className="text-sm sm:text-base text-[#4B5563]">
          Alamat URL yang Anda tuju tidak tersedia pada aplikasi HERB-INFO AI.
        </p>
        <div className="pt-2 flex flex-wrap justify-center gap-3">
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold bg-[#166534] text-white hover:bg-[#14532D] min-h-[44px]"
          >
            <ArrowLeft className="w-4 h-4" aria-hidden="true" />
            <span>Kembali ke Beranda</span>
          </Link>
          <Link
            to="/species"
            className="inline-flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold bg-[#F0FDF4] text-[#166534] border border-[#86EFAC] hover:bg-[#DCFCE7] min-h-[44px]"
          >
            <span>Buka Katalog Tanaman</span>
          </Link>
        </div>
      </div>
    </div>
  );
};
