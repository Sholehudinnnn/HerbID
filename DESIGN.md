# DESIGN.md - HERB-INFO AI

## Design Read
Reading this as: Botanical Encyclopedia & Academic Research Catalog for Indonesian students, researchers, and general public, in an editorial herbal-botanical style inspired by clean scientific species catalogs, dial ENERGY 2 / RHYTHM 2 / MOTION 1.

## Identity & Character
- **Product Name**: HERB-INFO AI (Ensiklopedia dan Pencarian Informasi Tanaman Obat Tradisional Indonesia)
- **Visual Persona**: Herbarium Nusantara Modern. Menggabungkan ketelitian katalog taksonomi botani dengan transparansi akademik (membedakan secara visual antara sumber resmi BPOM dan data riset Q&A Kaggle yang belum terverifikasi medis).
- **Identity Motif**:
  1. Ikon daun botani orisinal HERB-INFO AI dengan tulang daun simetris.
  2. Taksonomi ilmiah (*binomial nomenclature*) menggunakan tipografi serif miring (*italic*) di samping nama lokal Indonesia.
  3. Penanda Tingkat Verifikasi 3-Lapis (Sumber Resmi BPOM vs Perlu Verifikasi Topik vs Materi Riset Kaggle Belum Terverifikasi).

## Three Dials
- **ENERGY**: 2 (Balanced: kontras tipografi tegas pada hero dan kepala halaman, permukaan bersih berfokus pada keterbacaan katalog)
- **RHYTHM**: 2 (Consistent with deliberate breaks: perpaduan grid katalog 3 kolom, panel peringatan klinis/keamanan, dan tata letak ensiklopedia 2 kolom pada halaman detail)
- **MOTION**: 1 (Calm: transisi warna dan elevasi halus 150ms pada hover kartu dan fokus keyboard; tanpa animasi dekoratif berlebihan)

## Color Palette (WCAG AA Verified)
- **Background Primary**: `#F8FAF8` (Off-white sejuk untuk mengurangi kelelahan mata saat membaca katalog)
- **Surface / Card**: `#FFFFFF` dengan border `#E2E8F0` / `#DCE5DF`
- **Brand Primary (Deep Botanical Green)**: `#166534` (Rasio kontras > 7:1 terhadap putih)
- **Brand Accent (Leaf Green)**: `#16A34A` (Untuk indikator aktif, fokus, dan aksen terarah)
- **Text Primary**: `#1F2937` (Rasio kontras > 12:1 terhadap `#F8FAF8` dan `#FFFFFF`)
- **Text Secondary / Muted**: `#4B5563` (Rasio kontras > 7:1 terhadap `#FFFFFF`)
- **Semantic Status Colors**:
  - **Sumber Resmi / Terkurasi**: Latar `#DCFCE7`, Teks `#166534`, Border `#86EFAC`
  - **Perlu Verifikasi / Kandidat Topik**: Latar `#FEF3C7`, Teks `#92400E`, Border `#FCD34D`
  - **Peringatan Keamanan / Review Ketat**: Latar `#FEE2E2`, Teks `#991B1B`, Border `#FCA5A5`

## Typography & Written Reasons (R-31)
- **Heading & UI Sans**: `'Plus Jakarta Sans', 'Inter', system-ui, sans-serif` (Dipilih karena keterbacaan tinggi pada antarmuka berbahasa Indonesia dan proporsi huruf modern untuk tabel/katalog).
- **Scientific Taxonomy Serif**: `'Georgia', 'Cambria', serif` dalam gaya *italic* (Dipilih untuk membedakan nama ilmiah spesies dari teks deskriptif sesuai konvensi botani).
- **Monospace Metadata**: `'Consolas', 'Courier New', monospace` (Digunakan khusus untuk kode `source_id` seperti `BPOM-01`, hash korpus, dan metrik waktu eksekusi pencarian).

## Layout & Component Decisions (R-31)
- **Why this color (`#F8FAF8` + `#166534`)?**: Mencerminkan identitas tanaman obat Indonesia secara tenang dan memenuhi standar kontras WCAG AA tanpa silau putih murni.
- **Why this layout (3-column species grid + 2-column detail encyclopedia)?**: Memudahkan pemindaian cepat 12 spesies per halaman di desktop sekaligus menyediakan ruang baca mendalam pada halaman detail.
- **Why use cards on `/species`?**: Mengelompokkan atribut taksonomi (nama umum, nama ilmiah, famili, nama daerah, jumlah rujukan, dan status verifikasi) menjadi unit visual yang konsisten dan mudah dibandingkan.
- **Why custom botanical SVG placeholders?**: Dataset asli tidak menyertakan foto tanaman terverifikasi; ilustrasi siluet botani generik dengan label jujur mencegah kesalahan identifikasi morfologi tanaman.
