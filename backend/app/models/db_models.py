"""SQLAlchemy ORM models for HERB-INFO AI."""
import json
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Plant(Base):
    __tablename__ = "plants"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(120), unique=True, index=True, nullable=False)
    nama_umum = Column(String(160), index=True, nullable=False)
    nama_ilmiah = Column(String(200), nullable=True, index=True)
    famili = Column(String(120), nullable=True, index=True)
    nama_lokal_json = Column(Text, nullable=False, default="[]")
    ringkasan_terkurasi = Column(Text, nullable=True)
    gambar_url = Column(String(500), nullable=True)
    gambar_lisensi = Column(String(250), nullable=True)
    status_verifikasi = Column(String(80), nullable=False, default="Perlu verifikasi")
    updated_at = Column(String(64), nullable=False)
    sumber_data = Column(String(250), nullable=False)

    plant_references = relationship(
        "PlantReference",
        back_populates="plant",
        cascade="all, delete-orphan",
    )
    qa_links = relationship(
        "PlantQALink",
        back_populates="plant",
        cascade="all, delete-orphan",
    )

    @property
    def nama_lokal(self) -> list[str]:
        try:
            data = json.loads(self.nama_lokal_json or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []


class QAPair(Base):
    __tablename__ = "qa_pairs"

    id = Column(Integer, primary_key=True, index=True)
    pertanyaan = Column(Text, nullable=False)
    jawaban_kaggle_asli = Column(Text, nullable=False)
    topik = Column(String(80), index=True, nullable=False)
    status_validasi = Column(String(80), index=True, nullable=False)
    indikasi_perlu_review_ketat = Column(Boolean, nullable=False, default=False)
    panjang_pertanyaan = Column(Integer, nullable=False, default=0)
    panjang_jawaban = Column(Integer, nullable=False, default=0)

    qa_references = relationship(
        "QAReference",
        back_populates="qa_pair",
        cascade="all, delete-orphan",
    )
    plant_links = relationship(
        "PlantQALink",
        back_populates="qa_pair",
        cascade="all, delete-orphan",
    )


class Source(Base):
    __tablename__ = "sources"

    source_id = Column(String(40), primary_key=True, index=True)
    judul = Column(String(255), nullable=False)
    topik = Column(String(80), index=True, nullable=False)
    ringkasan_aman = Column(Text, nullable=False)
    source_url = Column(String(500), nullable=False)
    otoritas = Column(String(120), nullable=False, default="BPOM RI")
    status_review = Column(String(120), nullable=False)

    qa_references = relationship("QAReference", back_populates="source")
    plant_references = relationship("PlantReference", back_populates="source")


class QAReference(Base):
    __tablename__ = "qa_references"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    qa_id = Column(Integer, ForeignKey("qa_pairs.id"), nullable=False, index=True)
    source_id = Column(String(40), ForeignKey("sources.source_id"), nullable=True, index=True)
    status_kecocokan = Column(String(120), nullable=False)
    klaim_medis_disetujui = Column(Boolean, nullable=False, default=False)

    qa_pair = relationship("QAPair", back_populates="qa_references")
    source = relationship("Source", back_populates="qa_references")


class PlantReference(Base):
    __tablename__ = "plant_references"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False, index=True)
    source_id = Column(String(40), ForeignKey("sources.source_id"), nullable=False, index=True)
    tipe_relasi = Column(String(120), nullable=False)
    catatan_kurasi = Column(Text, nullable=False)

    plant = relationship("Plant", back_populates="plant_references")
    source = relationship("Source", back_populates="plant_references")


class PlantQALink(Base):
    __tablename__ = "plant_qa_links"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False, index=True)
    qa_id = Column(Integer, ForeignKey("qa_pairs.id"), nullable=False, index=True)
    tipe_kaitan = Column(String(80), nullable=False, default="utama")

    plant = relationship("Plant", back_populates="qa_links")
    qa_pair = relationship("QAPair", back_populates="plant_links")


class HerbalRecipe(Base):
    __tablename__ = "herbal_recipes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recipe_code = Column(String(40), unique=True, index=True, nullable=False)
    slug = Column(String(140), unique=True, index=True, nullable=False)
    nama_ramuan = Column(String(200), index=True, nullable=False)
    nama_tanaman = Column(String(160), index=True, nullable=True)
    nama_ilmiah = Column(String(200), index=True, nullable=True)
    bagian_tanaman = Column(String(160), nullable=True)
    rute_penggunaan = Column(String(120), nullable=True)
    deskripsi = Column(Text, nullable=False)
    keluhan_terkait = Column(String(200), index=True, nullable=False)
    takaran_bahan_sumber = Column(Text, nullable=True)
    bahan_tambahan = Column(Text, nullable=True)
    cara_menyiapkan_bahan = Column(Text, nullable=True)
    cara_membuat_sumber = Column(Text, nullable=True)
    aturan_pakai_sumber = Column(Text, nullable=True)
    dosis_kelompok_usia_json = Column(Text, nullable=False, default="{}")
    kelompok_tidak_dianjurkan = Column(Text, nullable=True)
    status_keamanan_dosis = Column(String(200), nullable=True)
    status_verifikasi = Column(String(120), index=True, nullable=False)
    sumber_dokumen = Column(String(255), nullable=True)
    sumber_url = Column(String(500), nullable=True)
    sumber_halaman = Column(String(120), nullable=True)
    reviewer = Column(String(160), nullable=True)
    tanggal_review = Column(String(64), nullable=True)
    peringatan = Column(Text, nullable=False)
    kontraindikasi = Column(Text, nullable=False)

    @property
    def dosis_kelompok_usia_map(self) -> dict[str, str]:
        try:
            data = json.loads(self.dosis_kelompok_usia_json or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    ingredients = relationship(
        "RecipeIngredient",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeIngredient.id.asc()",
    )
    steps = relationship(
        "RecipeStep",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeStep.nomor_langkah.asc()",
    )
    usages = relationship(
        "RecipeUsage",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeUsage.id.asc()",
    )
    sources = relationship(
        "RecipeSource",
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeSource.id.asc()",
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recipe_id = Column(Integer, ForeignKey("herbal_recipes.id"), nullable=False, index=True)
    nama_bahan = Column(String(180), nullable=False)
    jumlah = Column(String(80), nullable=True)
    satuan = Column(String(80), nullable=True)
    catatan = Column(Text, nullable=True)

    recipe = relationship("HerbalRecipe", back_populates="ingredients")


class RecipeStep(Base):
    __tablename__ = "recipe_steps"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recipe_id = Column(Integer, ForeignKey("herbal_recipes.id"), nullable=False, index=True)
    nomor_langkah = Column(Integer, nullable=False)
    deskripsi_langkah = Column(Text, nullable=False)

    recipe = relationship("HerbalRecipe", back_populates="steps")


class RecipeUsage(Base):
    __tablename__ = "recipe_usages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recipe_id = Column(Integer, ForeignKey("herbal_recipes.id"), nullable=False, index=True)
    aturan_penggunaan_dari_sumber = Column(Text, nullable=True)
    status_review_penggunaan = Column(String(120), nullable=False)
    boleh_ditampilkan_publik = Column(Boolean, nullable=False, default=False)

    recipe = relationship("HerbalRecipe", back_populates="usages")


class RecipeSource(Base):
    __tablename__ = "recipe_sources"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recipe_id = Column(Integer, ForeignKey("herbal_recipes.id"), nullable=False, index=True)
    nama_referensi = Column(String(255), nullable=False)
    instansi = Column(String(160), nullable=False)
    url = Column(String(500), nullable=False)
    halaman = Column(String(120), nullable=True)
    status_validasi = Column(String(120), nullable=False)

    recipe = relationship("HerbalRecipe", back_populates="sources")
