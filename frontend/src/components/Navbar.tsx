import React, { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { HerbLogoIcon } from './BotanicalPlaceholder';

const NAV_ITEMS = [
  { to: '/', label: 'Beranda', end: true },
  { to: '/search', label: 'Cari Ramuan', end: false },
  { to: '/recipes', label: 'Resep Tradisional', end: false },
  { to: '/species', label: 'Katalog Tanaman', end: false },
  { to: '/knowledge', label: 'Pengetahuan', end: false },
  { to: '/sources', label: 'Sumber Resmi', end: false },
  { to: '/evaluation', label: 'Evaluasi Model', end: false },
  { to: '/about', label: 'Tentang', end: false },
];


export const Navbar: React.FC = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname, location.search]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && mobileOpen) {
        setMobileOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [mobileOpen]);

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-sm border-b border-[#DCE5DF]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link
            to="/"
            className="flex items-center gap-3 group rounded-lg py-1 px-1"
            aria-label="Beranda HERB-INFO AI"
          >
            <HerbLogoIcon className="w-9 h-9 shrink-0 transition-transform duration-150 group-hover:scale-105" />
            <div className="flex flex-col">
              <span className="font-bold text-lg leading-tight tracking-tight text-[#166534]">
                HERB-INFO AI
              </span>
              <span className="text-[11px] text-[#4B5563] leading-tight hidden sm:inline">
                Ensiklopedia &amp; Rujukan Tanaman Obat Indonesia
              </span>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-1" aria-label="Navigasi utama">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `px-3.5 py-2 rounded-xl text-sm font-medium transition-colors min-h-[40px] flex items-center ${
                    isActive
                      ? 'bg-[#DCFCE7] text-[#166534] font-semibold'
                      : 'text-[#1F2937] hover:bg-[#F0FDF4] hover:text-[#166534]'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* Mobile Hamburger Button */}
          <div className="flex md:hidden">
            <button
              type="button"
              onClick={() => setMobileOpen((prev) => !prev)}
              className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] p-2.5 rounded-xl text-[#1F2937] hover:text-[#166534] hover:bg-[#F0FDF4] border border-transparent hover:border-[#DCE5DF]"
              aria-expanded={mobileOpen}
              aria-controls="mobile-navigation-menu"
              aria-label={mobileOpen ? 'Tutup menu navigasi' : 'Buka menu navigasi'}
            >
              {mobileOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Dropdown Menu */}
      {mobileOpen && (
        <nav
          id="mobile-navigation-menu"
          aria-label="Navigasi seluler"
          className="md:hidden border-t border-[#DCE5DF] bg-white px-4 pt-2 pb-4 space-y-1 shadow-md"
        >
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block px-4 py-3 rounded-xl text-base font-medium min-h-[44px] ${
                  isActive
                    ? 'bg-[#DCFCE7] text-[#166534] font-semibold'
                    : 'text-[#1F2937] hover:bg-[#F0FDF4] hover:text-[#166534]'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  );
};
