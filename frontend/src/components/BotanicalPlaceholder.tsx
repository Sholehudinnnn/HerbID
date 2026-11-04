import React from 'react';

/**
 * Original HERB-INFO AI botanical leaf icon and honest specimen placeholder SVG.
 * Never claims to be an actual photograph of a plant species.
 */
export const HerbLogoIcon: React.FC<{ className?: string }> = ({ className = 'w-7 h-7' }) => (
  <svg
    viewBox="0 0 36 36"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-hidden="true"
  >
    <rect width="36" height="36" rx="10" fill="#166534" />
    <path
      d="M26.5 9.5C18.5 9.5 11.5 14.2 10.2 22.8C10.0 24.1 11.0 25.2 12.3 25.0C20.8 23.7 25.5 16.8 26.5 9.5Z"
      fill="#DCFCE7"
      stroke="#86EFAC"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M9.5 26.5C13.5 22.5 18.2 18.0 23.5 13.5"
      stroke="#166534"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
    <path
      d="M15.5 20.5L13.5 16.8M19.5 17.0L17.8 13.8"
      stroke="#166534"
      strokeWidth="1.4"
      strokeLinecap="round"
    />
  </svg>
);

export const BotanicalPlaceholder: React.FC<{
  plantName: string;
  scientificName?: string | null;
  size?: 'card' | 'detail';
}> = ({ plantName, scientificName, size = 'card' }) => {
  const isRhizome = /jahe|kunyit|temu|kencur|lengkuas|puyang/i.test(plantName);
  const isBarkOrSpice = /kayu|cengkeh|pala|secang/i.test(plantName);

  const heightClass = size === 'detail' ? 'h-64 sm:h-72' : 'h-40';

  return (
    <div
      className={`relative w-full ${heightClass} bg-gradient-to-br from-[#ECFDF3] via-[#F0FDF4] to-[#E6F4EA] border-b border-[#DCE5DF] flex flex-col items-center justify-center p-4 overflow-hidden select-none`}
      role="img"
      aria-label={`Ilustrasi siluet botani untuk ${plantName}. Foto spesimen belum tersedia.`}
    >
      {/* Subtle botanical circle frame */}
      <div className="w-16 h-16 rounded-full bg-white/85 border border-[#BBF7D0] flex items-center justify-center shadow-sm mb-2">
        {isRhizome ? (
          <svg
            viewBox="0 0 32 32"
            className="w-8 h-8 text-[#166534]"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
          >
            <path d="M8 20c0-4 3-7 8-7s8 3 8 7-3 6-8 6-8-2-8-6z" />
            <path d="M12 13c-1-3 0-6 2-8M16 13V6M20 13c1-3 0-5-2-7" strokeLinecap="round" />
            <circle cx="13" cy="19" r="1" fill="currentColor" />
            <circle cx="19" cy="20" r="1" fill="currentColor" />
          </svg>
        ) : isBarkOrSpice ? (
          <svg
            viewBox="0 0 32 32"
            className="w-8 h-8 text-[#166534]"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
          >
            <path d="M16 5l4 6 6 2-4 5 1 7-7-3-7 3 1-7-4-5 6-2 4-6z" strokeLinejoin="round" />
            <circle cx="16" cy="16" r="3" />
          </svg>
        ) : (
          <svg
            viewBox="0 0 32 32"
            className="w-8 h-8 text-[#166534]"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
          >
            <path
              d="M24 8C16 8 9 12.5 8 21c-.2 1.2.8 2.2 2 2 8.5-1 13-7.5 14-15z"
              strokeLinejoin="round"
            />
            <path d="M7 25c4-4 8.5-8.5 13.5-13" strokeLinecap="round" />
          </svg>
        )}
      </div>

      <span className="text-xs font-medium text-[#166534] tracking-wide text-center px-2">
        Ilustrasi Botani Generik
      </span>
      <span className="text-[11px] text-[#4B5563] text-center mt-0.5">
        {scientificName ? (
          <span className="italic font-serif">{scientificName}</span>
        ) : (
          'Foto spesimen terverifikasi belum tersedia'
        )}
      </span>
    </div>
  );
};
