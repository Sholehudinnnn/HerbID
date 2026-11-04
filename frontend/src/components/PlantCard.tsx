import React from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, FileCheck2 } from 'lucide-react';
import { PlantCardItem } from '../lib/api';
import { BotanicalPlaceholder } from './BotanicalPlaceholder';

export const getVerificationBadgeStyle = (status: string): string => {
  const lower = status.toLowerCase();
  if (lower === 'diverifikasi') {
    return 'bg-[#DCFCE7] text-[#166534] border-[#86EFAC]';
  }
  if (lower.includes('perlu verifikasi')) {
    return 'bg-[#FEF3C7] text-[#92400E] border-[#FCD34D]';
  }
  return 'bg-[#F3F4F6] text-[#374151] border-[#D1D5DB]';
};

export const PlantCard: React.FC<{ plant: PlantCardItem }> = ({ plant }) => {
  return (
    <article className="bg-white rounded-2xl border border-[#DCE5DF] shadow-sm hover:shadow-md hover:border-[#86EFAC] transition-all duration-150 flex flex-col overflow-hidden">
      <BotanicalPlaceholder
        plantName={plant.nama_umum}
        scientificName={plant.nama_ilmiah}
        size="card"
      />

      <div className="p-5 flex-1 flex flex-col justify-between space-y-4">
        <div className="space-y-2.5">
          {/* Status Chip & Reference Counter */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold border ${getVerificationBadgeStyle(
                plant.status_verifikasi
              )}`}
            >
              {plant.status_verifikasi}
            </span>
            <span className="inline-flex items-center gap-1 text-xs font-medium text-[#4B5563]">
              <FileCheck2 className="w-3.5 h-3.5 text-[#166534]" aria-hidden="true" />
              <span>{plant.sumber_count} rujukan BPOM</span>
            </span>
          </div>

          {/* Plant Name & Scientific Name */}
          <div>
            <h3 className="text-lg font-bold text-[#1F2937] leading-snug">
              <Link
                to={`/species/${plant.slug}`}
                className="hover:text-[#166534] transition-colors"
              >
                {plant.nama_umum}
              </Link>
            </h3>
            {plant.nama_ilmiah ? (
              <p className="text-sm font-serif italic text-[#166534] mt-0.5">
                {plant.nama_ilmiah}
              </p>
            ) : (
              <p className="text-xs text-[#4B5563] mt-0.5">
                Nama ilmiah: Belum tersedia / Belum diverifikasi
              </p>
            )}
          </div>

          {/* Family & Local Names */}
          <div className="pt-1 space-y-1.5 text-xs text-[#4B5563]">
            <div className="flex items-center justify-between border-t border-[#F1F5F9] pt-2">
              <span className="font-medium text-[#374151]">Famili:</span>
              <span>{plant.famili ? plant.famili : 'Famili belum tersedia'}</span>
            </div>

            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="font-medium text-[#374151]">Nama lokal:</span>
              {plant.nama_lokal && plant.nama_lokal.length > 0 ? (
                plant.nama_lokal.map((lokal) => (
                  <span
                    key={lokal}
                    className="inline-block bg-[#F0FDF4] text-[#166534] border border-[#BBF7D0] px-2 py-0.5 rounded-md text-[11px] font-medium"
                  >
                    {lokal}
                  </span>
                ))
              ) : (
                <span className="text-[#4B5563]">Hanya tercatat sebagai {plant.nama_umum}</span>
              )}
            </div>
          </div>
        </div>

        {/* Footer CTA */}
        <div className="pt-3 border-t border-[#DCE5DF] flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1 text-xs text-[#4B5563]">
            <BookOpen className="w-3.5 h-3.5 text-[#16A34A]" aria-hidden="true" />
            <span>{plant.qa_terkait_count} Q&amp;A terkait</span>
          </span>

          <Link
            to={`/species/${plant.slug}`}
            className="inline-flex items-center justify-center px-3.5 py-2 rounded-xl text-xs font-semibold bg-[#166534] text-white hover:bg-[#14532D] transition-colors min-h-[38px]"
          >
            Lihat detail
          </Link>
        </div>
      </div>
    </article>
  );
};
