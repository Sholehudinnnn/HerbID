# PROMPT MASTER — MEMBANGUN WEB HERB-INFO AI DI GOOGLE ANTIGRAVITY

> Salin seluruh bagian di bawah ini ke percakapan Agent pada Google Antigravity. Saya menginginkan hasil aplikasi yang benar-benar berjalan, bukan sekadar mockup atau screenshot.

## IDENTITAS & TUJUAN

Kamu adalah senior full-stack engineer, UI/UX designer, data engineer, dan QA engineer. Bangun aplikasi web bernama **HERB-INFO AI — Ensiklopedia dan Pencarian Informasi Tanaman Obat Tradisional Indonesia** untuk proyek mata kuliah Sistem Cerdas. Gunakan **https://herbaldb.site/species** sebagai referensi pengalaman pengguna dan tata letak: navbar hijau-putih, daftar spesies dalam grid kartu tiga kolom desktop, pencarian, pagination, dan halaman detail spesies yang rapi. **Jangan menyalin logo, merek, foto, konten, basis data, maupun kode dari HerbalDB.** Desain harus orisinal dengan identitas HERB-INFO AI, berbahasa Indonesia.

Target utama: pengguna dapat menelusuri katalog tanaman obat, mencari berdasarkan nama lokal/ilmiah/famili, membaca data faktual dan tingkat verifikasinya, membuka sumber resmi BPOM, serta mencoba **pencarian cerdas yang mengembalikan kandidat dokumen relevan** dengan metode TF-IDF (baseline) dan semantic embedding (advanced, jika tersedia).

Jangan hanya menjelaskan arsitektur; **buat semua berkas aplikasi, jalankan server, periksa hasilnya, perbaiki error, tuliskan README, dan laporkan yang benar-benar berhasil diuji.** Jika ada langkah yang memerlukan file pengguna atau keputusan di luar workspace, nyatakan dengan jelas tanpa membuat klaim keberhasilan palsu.

## DATA YANG AKAN SAYA MASUKKAN

Siapkan folder `data/incoming/`. Saya akan meletakkan berkas-berkas berikut:

1. `indonesian_traditional_medicine.jsonl` — 52 rekaman Q&A berformat JSON Lines dengan kunci `instruction`, `input`, `output`; `input` pada contoh saya kosong. Ini berasal dari Kaggle dan **belum terverifikasi secara medis**.
2. `HERB_INFO_AI_Hasil_Colab.zip` — keluaran Google Colab yang berpotensi berisi:
   - `qa_clean_belum_terverifikasi.csv` (`id`, `pertanyaan`, `jawaban_kaggle_asli`, `status_validasi`, dan kolom analisis lainnya);
   - `bpom_sumber_resmi.csv` (`source_id`, `judul`, `topik`, `ringkasan_aman`, `source_url`, `status_review`);
   - `pencocokan_kandidat_bpom.csv` (`id`, `pertanyaan`, `source_id`, `status_kecocokan`, `klaim_medis_disetujui`, `judul`, `source_url`);
   - `tfidf_vectorizer.joblib`, `tfidf_matrix.npz`;
   - `bpom_semantic_embeddings.npy` (mungkin tidak ada jika sel advanced Colab tidak dijalankan);
   - `template_evaluasi_manual.csv`, `eda_distribusi_panjang.png`.

**ZIP asli sudah tersedia dan telah diaudit:** terdiri dari tepat 8 berkas di atas. Isinya adalah **52 Q&A**, **9 sumber BPOM**, **53 baris pemetaan kandidat** (15 relasi bertanda kandidat topik, mencakup 14 pertanyaan unik; 38 pertanyaan belum memiliki rujukan topik langsung), **14 Q&A ditandai untuk peninjauan ketat**, dan matriks embedding **(9, 384)**. **Semua `gold_source_id` evaluasi masih kosong**, jadi jangan menyajikan skor akurasi seolah-olah telah diuji. File ZIP ini harus digunakan sebagai input nyata, bukan contoh dummy. Nilai angka tersebut berguna untuk QA impor, tetapi antarmuka tetap menghitung statistik dari database.

**Aturan ketat tentang data:**

- Import JSONL yang valid dengan benar (`json.loads` per baris). Jangan salah membaca sebagai satu objek JSON tunggal.
- Periksa schema dan validasi jumlah baris; jangan mengasumsikan semua file ada.
- Ekstrak ZIP dengan aman; tolak path traversal, ukuran ekstraksi berlebihan, file berekstensi tak diizinkan, dan file tak dikenali.
- Jangan melakukan deserialisasi `tfidf_vectorizer.joblib` secara otomatis karena format pickle/joblib dapat mengeksekusi kode. Untuk cara paling aman dan reproducible, **latih ulang TF-IDF dari `bpom_sumber_resmi.csv`**. Boleh menyediakan opsi manual mengimpor `.joblib` hanya jika pengguna memercayai provenance filenya dan secara eksplisit memilihnya.
- Data Q&A Kaggle hanya bahan riset dan kandidat informasi, **bukan sumber medis resmi**. Jangan otomatis menampilkan jawaban Kaggle sebagai fakta atau sebagai rekomendasi terapi.
- Rujukan BPOM pada CSV adalah kecocokan **tingkat topik**, bukan verifikasi bahwa seluruh klaim jawaban Kaggle terbukti.
- Saat suatu tanaman hanya diketahui nama lokalnya, simpan `nama_ilmiah=null`, `famili=null` dan tampilkan `Belum tersedia/Belum diverifikasi`. Jangan mengarang nama ilmiah, famili, khasiat, senyawa kimia, dosis, atau status registrasi.
- Tidak semua 52 Q&A berkaitan dengan spesies; Q&A tentang jamu, akupunktur, bekam, regulasi, dan BKO masuk ke halaman **Pengetahuan & Tanya Jawab**, bukan dipaksa menjadi kartu spesies.
- Jika sebagian file belum ada, gunakan hanya **data contoh transparan** yang bersumber dari nama yang eksplisit ditemukan dalam JSONL, dengan label `Contoh belum diverifikasi`. Sediakan halaman instruksi impor. Jangan menulis `3.810 spesies` karena itu angka website referensi, bukan jumlah milik kita.
- Sumber BPOM harus dapat diklik ke URL asli. Nomor izin edar sebuah produk tidak boleh diasumsikan hanya karena nama bahan/tanaman muncul di BPOM. Sediakan tombol `Cek Izin Edar di BPOM` menuju https://cekbpom.pom.go.id/ tanpa menampilkan hasil pemeriksaan palsu.

## STACK & STRUKTUR

Bangun sebagai monorepo sederhana:

```text
herb-info-ai/
  frontend/                # React + TypeScript + Vite + Tailwind CSS
    src/components/
    src/pages/
    src/lib/api.ts
  backend/                 # Python FastAPI + Pydantic + scikit-learn
    app/main.py
    app/routes/
    app/services/
    app/models/
    app/importers/
    requirements.txt
  data/incoming/           # berkas asli yang saya berikan
  data/processed/          # JSON/CSV yang sudah valid
  tests/
  README.md
  .env.example
```

Gunakan SQLite untuk data katalog/prototipe agar ringan dan dapat dipakai offline setelah dependensi dipasang. Gunakan SQLAlchemy atau penyimpanan terstruktur yang jelas. Gunakan `fetch` atau Axios dengan variabel `VITE_API_BASE_URL=http://localhost:8000`; batasi CORS pada origin lokal frontend. Jangan membuat login dan registrasi yang hanya kosmetik; untuk MVP **tidak perlu akun pengguna**.

Library UI: Tailwind CSS, komponen reusable, lucide-react atau ikon sejenis yang punya lisensi jelas. Gunakan dependency stabil yang kompatibel. Jangan membuat ketergantungan layanan berbayar, API key LLM eksternal, database cloud, atau akun pihak ketiga. Jika `sentence-transformers` tidak tersedia, jalankan TF-IDF tanpa crash dan tampilkan status `Mode semantik belum tersedia`.

## ARAH DESAIN: MIRIP KENYAMANAN HERBALDB, TETAPI ORISINAL

Visual: latar putih/off-white `#F8FAF8`, hijau tua `#166534`, hijau aksen `#16A34A`, teks abu gelap `#1F2937`, kartu putih border halus dan shadow ringan, radius 14–18 px, whitespace lega, font Inter atau alternatif sans-serif yang tersedia. Jangan gunakan foto tanaman atau logo dari HerbalDB. Buat ikon daun sederhana HERB-INFO AI yang orisinal. Sediakan placeholder ilustratif ketika foto tidak tersedia; jangan menampilkan gambar tanaman yang salah. Responsif penuh.

### A. Navbar

- Logo `HERB-INFO AI` dengan ikon daun.
- Menu: `Beranda`, `Katalog Tanaman`, `Pencarian Cerdas`, `Pengetahuan`, `Sumber BPOM`, `Tentang`.
- Item aktif beraksen hijau; navbar sticky jika tidak mengganggu; menu hamburger berfungsi di ponsel.
- Tidak ada tombol Login/Register palsu.

### B. `/` — Beranda

- Hero judul `Jelajahi Pengetahuan Tanaman Obat Tradisional Indonesia`.
- Subjudul: `Katalog edukatif berbasis data, pencarian cerdas, dan rujukan resmi`.
- Kolom pencarian utama dengan tombol `Cari tanaman` dan `Cari sumber`.
- Kartu statistik **dihitung dari data asli**: jumlah tanaman tercatat, jumlah Q&A, jumlah sumber BPOM, jumlah record telah dikurasi. Jangan hardcode angka yang tidak sesuai.
- Kategori pintasan yang relevan: `Tanaman`, `Jamu & Tradisi`, `Keamanan`, `Regulasi`.
- Seksi `Jelajahi tanaman`, menampilkan beberapa kartu dari database.
- Banner: `Konten ini bersifat edukatif dan bukan pengganti nasihat tenaga kesehatan`.

### C. `/species` — Daftar Tanaman (halaman yang paling menyerupai referensi)

Komposisi:

1. Heading `Database Tanaman Obat Indonesia` dengan ikon daun.
2. Deskripsi singkat.
3. Search input lebar dengan placeholder `Cari nama tanaman, nama ilmiah, nama daerah, atau famili...`.
4. Filter sederhana: `A–Z`, `Nama lokal`, `Famili` (hanya jika datanya tersedia), dan urutkan.
5. Teks `Ditemukan N tanaman` berdasarkan hasil sebenarnya.
6. Grid **3 kolom desktop**, 2 tablet, 1 mobile. Setiap kartu memuat:
   - nama tanaman; nama ilmiah *italic* bila tervalidasi;
   - famili, atau `Famili belum tersedia`;
   - nama lokal/daerah berupa chip kecil jika tersedia;
   - status verifikasi: `Diverifikasi`, `Perlu verifikasi`, atau `Data terbatas`;
   - jumlah sumber yang relevan (bukan jumlah senyawa rekaan);
   - tautan/tombol `Lihat detail`.
7. Pagination nyata 12 kartu/halaman, kontrol Previous/Next, serta URL query yang dapat disalin (`?q=jahe&page=2`).
8. Loading skeleton, empty state, error state, dan retry bekerja.

### D. `/species/:slug` — Halaman Detail Tanaman

- Breadcrumb kembali ke katalog.
- Layout seperti ensiklopedia: gambar/placeholder di kiri; nama tanaman dan chip status di kanan.
- Tab: `Ringkasan`, `Nama Lokal`, `Pengetahuan Terkait`, `Referensi & Keamanan`.
- Sidebar `Informasi Singkat`: nama ilmiah, famili, nama lokal, asal data, tanggal update, jumlah rujukan.
- `Ringkasan` hanya berisi informasi yang dikurasi; jika belum tersedia tampilkan `Belum ada ringkasan terverifikasi`.
- `Pengetahuan Terkait`: tampilkan pertanyaan dari Kaggle jika benar-benar berkaitan, **dengan label mencolok `Materi Kaggle — belum diverifikasi secara medis`**; untuk publik, jangan sajikan jawaban mentah sebagai panduan pengobatan.
- `Referensi`: judul, instansi, tautan asli, dan status `Kecocokan topik, bukan validasi klaim`.
- `Keamanan`: peringatan umum interaksi obat herbal, kelompok rentan, bahan kimia obat, dan pemeriksaan izin edar, tanpa membuat dosis.
- Jika field kosong, jangan isi dengan contoh fiktif atau klaim palsu.

### E. `/search` — Pencarian Cerdas

Fitur inti Sistem Cerdas:

- Pengguna menulis pertanyaan bebas, misalnya `Apa perbedaan jamu, OHT, dan fitofarmaka?`.
- Dua mode dengan pemilih: `Baseline TF-IDF` dan `Semantik (Advanced)`, mode advanced boleh nonaktif dengan alasan jika dependensi/model belum siap.
- Hasil berupa **kartu kandidat dokumen**, judul BPOM, ringkasan umum yang terkurasi, URL sumber, skor kemiripan diberi label `relevansi, bukan akurasi medis`, serta tanda status verifikasi.
- Terapkan batas minimum relevansi terkalibrasi. Jika skor rendah / tak ada sumber tepercaya, jawab `Sumber tepercaya belum ditemukan`, jangan mengarang.
- Pertanyaan sensitif terkait dosis, kehamilan, menyusui, bayi, kanker, gagal ginjal, kombinasi obat, kondisi darurat harus memunculkan pemberitahuan aman: `Sistem tidak memberikan diagnosis/dosis/rekomendasi terapi. Konsultasikan dengan apoteker/dokter.` Boleh tetap menunjukkan sumber edukasi umum setelah peringatan, tetapi **jangan menghasilkan instruksi penggunaan obat**.
- Tambahkan contoh pertanyaan yang dapat diklik dan riwayat pencarian **lokal sementara** saja (tanpa identitas pengguna).
- Jika CSV rujukan tidak tersedia, tampilkan empty state yang jujur dan petunjuk impor.

### F. `/knowledge` — Pengetahuan dan Tanya Jawab

- Daftar seluruh 52 Q&A sebagai data penelitian, bukan `informasi BPOM`.
- Pencarian kata kunci dan filter topik (contoh: tanaman, jamu, keamanan, regulasi, praktik tradisional).
- Tandai jelas `Belum diverifikasi`, `Perlu tinjauan ketat`, dan bila ada `Sudah dikurasi` hanya berdasarkan anotasi manual sah.
- Hindari menonjolkan jawaban Kaggle yang memuat klaim kesehatan ekstrem atau panduan kelompok rentan. Tampilkan metadata dan penjelasan tentang proses validasi; teks mentah hanya dalam panel riset yang disertai peringatan tegas, tidak sebagai petunjuk konsumsi.

### G. `/sources` — Pusat Referensi BPOM

- Grid/list sumber BPOM dari CSV, pencarian topik, tombol `Buka sumber resmi`, badge `Sumber BPOM`.
- Panel `Cara cek produk` mengarahkan ke https://cekbpom.pom.go.id/ dan menegaskan hasil izin edar spesifik harus dicek manual berdasarkan nama/nomor izin edar.
- Penjelasan ringkas `Jamu, Obat Herbal Terstandar (OHT), Fitofarmaka` hanya berdasarkan sumber resmi yang dicantumkan, tanpa menyamakan tingkatan pembuktiannya.
- Tidak ada klaim `disetujui BPOM` untuk tanaman generik.

### H. `/about` — Tentang Proyek

- Metode penelitian: dataset Kaggle → EDA → feature engineering → baseline TF-IDF → advanced semantic embedding → evaluasi berlabel manual → API → aplikasi web.
- Jelaskan keterbatasan ukuran dataset 52 Q&A, bias data, terbatasnya BPOM sebagai sumber topik, dan mengapa kemiripan tidak sama dengan bukti klinis.
- Tampilkan diagram alur kecil dan kamus label validasi.
- Cantumkan bahwa aplikasi bukan alat diagnosis/pengganti tenaga kesehatan.

## RANCANGAN DATA

Buat skema yang dapat bertumbuh:

```text
Plant {id, slug, nama_umum, nama_ilmiah?, famili?, nama_lokal: string[],
       ringkasan_terkurasi?, gambar_url?, gambar_lisensi?, status_verifikasi,
       updated_at, sumber_data}
QAPair {id, pertanyaan, jawaban_kaggle_asli, topik, status_validasi,
        indikasi_perlu_review_ketat}
Source {source_id, judul, topik, ringkasan_aman, source_url,
        otoritas, status_review}
QAReference {qa_id, source_id, status_kecocokan,
             klaim_medis_disetujui: boolean}
PlantReference {plant_id, source_id, tipe_relasi, catatan_kurasi}
```

Import hanya nama tanaman yang secara eksplisit muncul sebagai entitas tanaman dari Q&A; buang duplikat dan jangan memasukkan objek non-tanaman seperti `jamu`, `bekam`, `akupunktur` sebagai `Plant`. Berikan `data/import_report.json` yang mencatat baris berhasil, gagal, digabung, dilewati, dan alasan. Semua relasi antar tabel harus nyata, bukan hardcode di kartu.

## BACKEND & MODEL PENCARIAN

FastAPI route minimum:

```text
GET /api/health
GET /api/stats
GET /api/species?q=&family=&page=1&per_page=12&sort=az
GET /api/species/{slug}
GET /api/knowledge?q=&topic=&page=1
GET /api/sources?q=&topic=
POST /api/search           # {"query":"...","mode":"tfidf","top_k":5}
```

- Swagger/OpenAPI aktif di `http://localhost:8000/docs`.
- Validasi input, pembatasan panjang query dan `top_k`, penanganan exception terstruktur, dan CORS untuk dev origin saja.
- **Baseline:** TfidfVectorizer+cosine similarity terhadap dokumen **ringkasan sumber BPOM**, bangun ulang deterministik dari CSV. `tfidf_vectorizer.joblib` dalam ZIP cukup diarsipkan sebagai bukti riset; jangan otomatis di-load. Model harus memakai urutan baris sumber yang stabil.
- **Advanced:** Sentence Transformer multilingual, contoh model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, dan cosine/dot similarity terhadap embedding dokumen. Muat model lazily atau sediakan fitur opt-in agar startup aplikasi ringan. Jika file embedding `.npy` tidak cocok jumlah/urutan baris CSV, hitung ulang secara eksplisit setelah verifikasi; jangan diam-diam menggunakan embedding salah.
- Simpan metadata indeks (jumlah sumber, urutan `source_id`, versi model, hash corpus) untuk mencegah mismatch.
- Server wajib dapat berjalan dengan mode baseline saja; advanced opsional. Jangan memerlukan internet saat pencarian TF-IDF telah diindeks.
- Jangan panggil API BPOM tanpa integrasi resmi/izin yang sesuai; tautan sumber resmi cukup untuk MVP.
- Respons pencarian JSON memuat `query`, `mode_requested`, `mode_used`, `requires_professional_advice`, `message`, `results` (source_id, judul, ringkasan, URL, similarity_score, verification_note), serta `elapsed_ms` bila tersedia. Jangan sebut similarity score sebagai confidence klinis.

## EVALUASI DAN EXPLAINABILITY

- Buat script pengujian yang menghasilkan template anotasi manual `gold_source_id` jika belum diisi. **Jangan mengarang label kebenaran atau angka accuracy.**
- Bila gold label memang sudah diisi, hitung dan tampilkan Hit@1, Recall@3, MRR@10 secara benar, bandingkan TF-IDF vs semantic, dan jelaskan jumlah contoh berlabel.
- Explainability sederhana: baseline menyorot istilah yang cocok antara query dan dokumen; advanced menampilkan sumber hasil dan relevansi semantik, **bukan penjelasan sebab-akibat medis**.
- Minimal buat daftar 20 query uji fungsional yang bervariasi (typo, istilah singkatan OHT/BKO, nama lokal, query tak relevan, kelompok rentan, query kosong, XSS, batas panjang input). Jangan jadikan query uji otomatis sebagai gold relevansi.

## TES FUNGSIONAL, KEAMANAN, DAN AKSESIBILITAS

Implementasikan atau jalankan tes berikut:

1. `/species` memuat sesuai jumlah tanaman yang benar-benar diimpor.
2. Pencarian `jahe` menampilkan hasil hanya bila datanya ada; jika tidak, empty state jujur.
3. Pencarian kata dengan kapital/whitespace berlebih tetap ditangani.
4. Pagination tidak mengulang/melompati record.
5. `Lihat detail` mengarah ke slug benar; slug tidak ada menghasilkan halaman 404 bermakna.
6. Mode baseline memberi daftar sumber relevan untuk `perbedaan jamu dan fitofarmaka` bila sumber terkait terimpor.
7. Query `Saya hamil, berapa dosis jamu yang aman?` tidak memberi dosis, melainkan peringatan.
8. Query kosong dan payload HTML/JavaScript tidak menyebabkan crash atau XSS.
9. API punya validasi `top_k` dan batas panjang query.
10. Mobile 375 px, tablet 768 px, dan desktop 1440 px tidak overflow dan navbar berfungsi.
11. Tombol sumber BPOM membuka URL sebenarnya.
12. Tidak ada label `BPOM-approved/terdaftar` tanpa bukti registrasi produk.
13. Jika advanced belum terpasang, TF-IDF tetap berfungsi dan UI menunjukkan alasannya.
14. Jalankan build frontend, unit test backend, dan uji integrasi endpoint yang tersedia. Jangan mengklaim tes lulus jika belum dijalankan.

Gunakan semantic HTML, navigasi keyboard, aria-label yang layak, kontras cukup, dan fokus keyboard terlihat. Hindari tracking dan penyimpanan data kesehatan pribadi.

## OUTPUT WAJIB

1. Kode lengkap frontend + backend yang bisa dijalankan secara lokal pada Windows 11.
2. `README.md` bahasa Indonesia berisi prasyarat, struktur folder, cara meletakkan ZIP/JSONL, menjalankan importer, menjalankan backend dan frontend, cara menguji, dan keterbatasan medis.
3. `.env.example` tanpa data rahasia.
4. Script impor data yang reproducible serta laporan hasil impor.
5. Screenshot hasil browser uji pada desktop dan mobile **hanya jika fitur browser/testing tersedia**.
6. Daftar endpoint dan contoh request/response.
7. Tabel tes: `skenario`, `hasil yang diharapkan`, `hasil nyata`, `lulus/gagal/belum diuji`.
8. Penjelasan status baseline dan advanced yang benar-benar berjalan.

## LANGKAH KERJA YANG WAJIB KAMU IKUTI

**Fase 1: Audit.** Periksa file yang tersedia di workspace dan tampilkan rencana serta schema. Jangan menunda jika file belum tersedia; scaffold aplikasi yang bisa diisi kemudian, tanpa data palsu.

**Fase 2: Data + backend.** Implement importer JSONL/ZIP, database, indeks TF-IDF, API, unit tests. Pastikan error ditangani.

**Fase 3: UI.** Bangun beranda, grid katalog, detail, pencarian cerdas, pengetahuan, sumber BPOM, tentang; gunakan desain yang terinspirasi dari kenyamanan https://herbaldb.site/species tanpa menyalin aset/kode.

**Fase 4: Integrasi.** Hubungkan setiap halaman ke API nyata. Hindari mock data statis jika data sumber sudah tersedia.

**Fase 5: QA.** Jalankan server lokal, inspeksi di browser, perbaiki bug, tes mobile, cek fungsi menu, dokumentasikan hasil nyata.

**Fase 6: Handoff.** Berikan struktur proyek, perintah terminal untuk Windows PowerShell, URL lokal frontend/backend, status tes, keterbatasan, serta langkah selanjutnya.

Mulai kerjakan proyek secara bertahap sekarang. Pada akhir tugas, saya ingin bisa membuka web di `http://localhost:5173` dan API di `http://localhost:8000/docs` (atau port aktual yang dicatat di README). **Jangan berhenti setelah hanya membuat rencana.**
