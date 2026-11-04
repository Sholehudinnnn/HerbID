"""FastAPI endpoints for HERB-INFO AI."""
import json
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import IMPORT_REPORT_PATH, PROCESSED_DIR
from app.database import get_db
from app.models.db_models import (
    HerbalRecipe,
    Plant,
    PlantQALink,
    PlantReference,
    QAPair,
    QAReference,
    Source,
)
from app.models.schemas import (
    AIStatusResponse,
    EvaluationComputeRequest,
    HealthResponse,
    KemenkesReferenceSchema,
    KnowledgeListResponse,
    PlantCardSchema,
    PlantDetailSchema,
    PlantListResponse,
    QAPairItemSchema,
    QARefItemSchema,
    RecipeCardSchema,
    RecipeDetailSchema,
    RecipeIngredientSchema,
    RecipeListResponse,
    RecipeSourceSchema,
    RecipeStepSchema,
    RecipeUsageSchema,
    RelatedQASchema,
    SearchRequest,
    SearchResponse,
    SourceBriefSchema,
    SourceListResponse,
    StatsResponse,
)
from app.services.evaluation_service import (
    FUNCTIONAL_TEST_QUERIES,
    evaluate_manual_template,
    evaluate_nlp_benchmark_30,
)
from app.services.gemini_service import check_gemini_status
from app.services.search_service import (
    AVAILABLE_AGE_GROUPS,
    FROTI_QUERY_SYNONYMS,
    LOCAL_PLANT_TERMS_MAP,
    MANDATORY_TAKARAN_LABEL,
    TYPO_CORRECTION_MAP,
    VULNERABLE_CONSUMPTION_WARNING,
    format_recipe_card_dict,
    sanitize_query_text,
    search_engine,
)


router = APIRouter(prefix="/api")

DEFAULT_SAFETY_NOTES = [
    "Konten halaman ini bersifat edukatif dan bukan pengganti diagnosis, resep, atau nasihat tenaga kesehatan (dokter/apoteker).",
    "Bahan alami dan tanaman obat memiliki senyawa aktif yang dapat berinteraksi dengan obat medis konvensional (misalnya pengencer darah, obat diabetes, atau obat antihipertensi).",
    "Kelompok rentan (ibu hamil, ibu menyusui, bayi, anak-anak, lansia, serta penderita gangguan fungsi hati/ginjal) wajib berkonsultasi dengan dokter sebelum mengonsumsi sediaan herbal.",
    "Waspadai produk obat tradisional ilegal yang dicampur Bahan Kimia Obat (BKO). Pastikan kemasan memiliki Nomor Izin Edar resmi BPOM (TR, HT, atau FF) melalui portal CekBPOM.",
]


@router.get("/health", response_model=HealthResponse, tags=["System"])
def get_health(db: Session = Depends(get_db)) -> HealthResponse:
    plant_count = db.query(Plant).count()
    meta = search_engine.get_metadata()
    return HealthResponse(
        status="ok",
        database_ready=plant_count > 0,
        tfidf_index_ready=bool(meta["tfidf_ready"]),
        semantic_mode_available=bool(meta["semantic_available"]),
        semantic_status=str(meta["semantic_status"]),
    )


@router.get("/ai-status", response_model=AIStatusResponse, tags=["System"])
def get_ai_status() -> AIStatusResponse:
    """Safe status endpoint for Google Gemini API integration.
    
    Returns connection status, active model, latency, and human-friendly Indonesian explanation.
    Never exposes API keys or sensitive authorization tokens.
    """
    res = check_gemini_status()
    return AIStatusResponse(**res)


@router.get("/stats", response_model=StatsResponse, tags=["System"])
def get_stats(db: Session = Depends(get_db)) -> StatsResponse:
    total_plants = db.query(Plant).count()
    total_qa = db.query(QAPair).count()
    total_sources = db.query(Source).count()
    total_recipes = db.query(HerbalRecipe).count()

    # Curated records: 9 official BPOM sources + plants with curated BPOM topic summaries
    plants_curated = db.query(Plant).filter(Plant.ringkasan_terkurasi.isnot(None)).count()
    curated_records = total_sources + plants_curated

    strict_review_qa_count = (
        db.query(QAPair).filter(QAPair.indikasi_perlu_review_ketat.is_(True)).count()
    )

    cand_links = (
        db.query(QAReference)
        .filter(QAReference.source_id.isnot(None))
        .all()
    )
    candidate_topic_links_count = len(cand_links)
    unique_q_with_src = len({c.qa_id for c in cand_links})
    questions_needing_ref = max(0, total_qa - unique_q_with_src)

    plants_with_sci = db.query(Plant).filter(Plant.nama_ilmiah.isnot(None)).count()
    plants_local_only = total_plants - plants_with_sci

    families = sorted(
        {
            p.famili
            for p in db.query(Plant).filter(Plant.famili.isnot(None)).all()
            if p.famili
        }
    )

    eval_info = evaluate_manual_template(search_engine)
    meta = search_engine.get_metadata()

    return StatsResponse(
        total_plants=total_plants,
        total_qa=total_qa,
        total_sources=total_sources,
        total_recipes=total_recipes,
        curated_records=curated_records,
        strict_review_qa_count=strict_review_qa_count,
        candidate_topic_links_count=candidate_topic_links_count,
        unique_questions_with_source_count=unique_q_with_src,
        questions_needing_reference_count=questions_needing_ref,
        plants_with_scientific_name=plants_with_sci,
        plants_local_only=plants_local_only,
        families_available=families,
        semantic_available=bool(meta["semantic_available"]),
        semantic_status=str(meta["semantic_status"]),
        semantic_reason=str(meta["semantic_reason"]),
        evaluation_gold_filled_count=int(eval_info["labeled_rows"]),
        evaluation_total_count=int(eval_info["total_rows"]),
        evaluation_note=str(eval_info["note"]),
    )


@router.get("/species", response_model=PlantListResponse, tags=["Species"])
def list_species(
    q: str = Query(default="", max_length=200, description="Kata kunci pencarian tanaman"),
    family: str = Query(default="", max_length=100, description="Filter famili tanaman"),
    letter: str = Query(default="", max_length=5, description="Filter huruf awal A-Z"),
    filter_mode: str = Query(
        default="all",
        max_length=40,
        description="Filter tambahan: all, local_name, with_source, local_only",
    ),
    page: int = Query(default=1, ge=1, description="Nomor halaman"),
    per_page: int = Query(default=12, ge=1, le=50, description="Jumlah kartu per halaman"),
    sort: str = Query(default="az", description="Urutan: az, za, sources_desc, scientific"),
    db: Session = Depends(get_db),
) -> PlantListResponse:
    all_plants = db.query(Plant).all()

    available_families = sorted({p.famili for p in all_plants if p.famili})
    available_letters = sorted({p.nama_umum[0].upper() for p in all_plants if p.nama_umum})

    clean_q = sanitize_query_text(q).lower()
    clean_family = family.strip().lower()
    clean_letter = letter.strip().upper()

    filtered: list[Plant] = []
    for plant in all_plants:
        if clean_family:
            if not plant.famili or plant.famili.lower() != clean_family:
                continue
        if clean_letter and len(clean_letter) == 1:
            if not plant.nama_umum.upper().startswith(clean_letter):
                continue
        if filter_mode == "local_name" and len(plant.nama_lokal) == 0:
            continue
        if filter_mode == "with_source" and len(plant.plant_references) == 0:
            continue
        if filter_mode == "local_only" and plant.nama_ilmiah is not None:
            continue

        if clean_q:
            haystack_parts = [
                plant.nama_umum.lower(),
                (plant.nama_ilmiah or "").lower(),
                (plant.famili or "").lower(),
                " ".join(n.lower() for n in plant.nama_lokal),
            ]
            haystack = " ".join(haystack_parts)
            if clean_q not in haystack:
                continue

        filtered.append(plant)

    # Deterministic sorting with tie-breaker on plant.id
    if sort == "za":
        filtered.sort(key=lambda p: (p.nama_umum.lower(), p.id), reverse=True)
    elif sort == "sources_desc":
        filtered.sort(
            key=lambda p: (-len(p.plant_references), p.nama_umum.lower(), p.id)
        )
    elif sort == "scientific":
        filtered.sort(
            key=lambda p: (
                0 if p.nama_ilmiah else 1,
                (p.nama_ilmiah or p.nama_umum).lower(),
                p.id,
            )
        )
    else:
        filtered.sort(key=lambda p: (p.nama_umum.lower(), p.id))

    total = len(filtered)
    total_pages = max(1, math.ceil(total / per_page)) if total > 0 else 1
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_items = filtered[start_idx:end_idx]

    cards = [
        PlantCardSchema(
            id=p.id,
            slug=p.slug,
            nama_umum=p.nama_umum,
            nama_ilmiah=p.nama_ilmiah,
            famili=p.famili,
            nama_lokal=p.nama_lokal,
            ringkasan_terkurasi=p.ringkasan_terkurasi,
            gambar_url=p.gambar_url,
            status_verifikasi=p.status_verifikasi,
            sumber_count=len(p.plant_references),
            qa_terkait_count=len(p.qa_links),
            updated_at=p.updated_at,
            sumber_data=p.sumber_data,
        )
        for p in page_items
    ]

    return PlantListResponse(
        items=cards,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        query=clean_q,
        family=family.strip(),
        sort=sort,
        available_families=available_families,
        available_letters=available_letters,
    )


@router.get("/species/{slug}", response_model=PlantDetailSchema, tags=["Species"])
def get_species_detail(slug: str, db: Session = Depends(get_db)) -> PlantDetailSchema:
    clean_slug = slug.strip().lower()
    plant = db.query(Plant).filter(Plant.slug == clean_slug).first()
    if not plant:
        raise HTTPException(
            status_code=404,
            detail=f"Spesies dengan slug '{slug}' tidak ditemukan dalam database HERB-INFO AI.",
        )

    refs: list[SourceBriefSchema] = []
    for pr in plant.plant_references:
        if pr.source:
            refs.append(
                SourceBriefSchema(
                    source_id=pr.source.source_id,
                    judul=pr.source.judul,
                    topik=pr.source.topik,
                    ringkasan_aman=pr.source.ringkasan_aman,
                    source_url=pr.source.source_url,
                    otoritas=pr.source.otoritas,
                    status_review=pr.source.status_review,
                    tipe_relasi=pr.tipe_relasi,
                    catatan_kurasi=pr.catatan_kurasi,
                )
            )

    related_qas: list[RelatedQASchema] = []
    for link in sorted(plant.qa_links, key=lambda l: (0 if l.tipe_kaitan == "utama" else 1, l.qa_id)):
        qa = link.qa_pair
        if qa:
            related_qas.append(
                RelatedQASchema(
                    id=qa.id,
                    pertanyaan=qa.pertanyaan,
                    jawaban_kaggle_asli=qa.jawaban_kaggle_asli,
                    topik=qa.topik,
                    status_validasi=qa.status_validasi,
                    indikasi_perlu_review_ketat=qa.indikasi_perlu_review_ketat,
                    tipe_kaitan=link.tipe_kaitan,
                    peringatan_penelitian=(
                        "Materi Kaggle - belum diverifikasi secara medis. "
                        "Teks ini merupakan data penelitian mentah dan bukan panduan pengobatan."
                    ),
                )
            )

    return PlantDetailSchema(
        id=plant.id,
        slug=plant.slug,
        nama_umum=plant.nama_umum,
        nama_ilmiah=plant.nama_ilmiah,
        famili=plant.famili,
        nama_lokal=plant.nama_lokal,
        ringkasan_terkurasi=plant.ringkasan_terkurasi,
        gambar_url=plant.gambar_url,
        gambar_lisensi=plant.gambar_lisensi,
        status_verifikasi=plant.status_verifikasi,
        updated_at=plant.updated_at,
        sumber_data=plant.sumber_data,
        sumber_count=len(refs),
        referensi_bpom=refs,
        pengetahuan_terkait=related_qas,
        peringatan_keamanan=DEFAULT_SAFETY_NOTES,
        cek_bpom_url="https://cekbpom.pom.go.id/",
    )


@router.get("/knowledge", response_model=KnowledgeListResponse, tags=["Knowledge"])
def list_knowledge(
    q: str = Query(default="", max_length=200, description="Pencarian kata kunci Q&A"),
    topic: str = Query(default="", max_length=80, description="Filter topik Q&A"),
    review_filter: str = Query(
        default="all",
        max_length=40,
        description="Filter status: all, strict_only, with_bpom_candidate",
    ),
    page: int = Query(default=1, ge=1, description="Nomor halaman"),
    per_page: int = Query(default=15, ge=1, le=60, description="Jumlah item per halaman"),
    db: Session = Depends(get_db),
) -> KnowledgeListResponse:
    all_qa = db.query(QAPair).order_by(QAPair.id.asc()).all()
    available_topics = sorted({qa.topik for qa in all_qa if qa.topik})

    clean_q = sanitize_query_text(q).lower()
    clean_topic = topic.strip().lower()

    filtered: list[QAPair] = []
    for qa in all_qa:
        if clean_topic and qa.topik.lower() != clean_topic:
            continue
        if review_filter == "strict_only" and not qa.indikasi_perlu_review_ketat:
            continue
        if review_filter == "with_bpom_candidate":
            has_cand = any(r.source_id is not None for r in qa.qa_references)
            if not has_cand:
                continue
        if clean_q:
            haystack = f"{qa.pertanyaan} {qa.jawaban_kaggle_asli} {qa.topik}".lower()
            if clean_q not in haystack:
                continue
        filtered.append(qa)

    total = len(filtered)
    total_pages = max(1, math.ceil(total / per_page)) if total > 0 else 1
    start_idx = (page - 1) * per_page
    page_items = filtered[start_idx : start_idx + per_page]

    items: list[QAPairItemSchema] = []
    for qa in page_items:
        ref_items: list[QARefItemSchema] = []
        for qr in qa.qa_references:
            ref_items.append(
                QARefItemSchema(
                    source_id=qr.source_id,
                    status_kecocokan=qr.status_kecocokan,
                    klaim_medis_disetujui=qr.klaim_medis_disetujui,
                    judul=qr.source.judul if qr.source else None,
                    source_url=qr.source.source_url if qr.source else None,
                )
            )
        linked_plants = [
            {
                "slug": pl.plant.slug,
                "nama_umum": pl.plant.nama_umum,
                "tipe_kaitan": pl.tipe_kaitan,
            }
            for pl in qa.plant_links
            if pl.plant is not None
        ]
        items.append(
            QAPairItemSchema(
                id=qa.id,
                pertanyaan=qa.pertanyaan,
                jawaban_kaggle_asli=qa.jawaban_kaggle_asli,
                topik=qa.topik,
                status_validasi=qa.status_validasi,
                indikasi_perlu_review_ketat=qa.indikasi_perlu_review_ketat,
                panjang_pertanyaan=qa.panjang_pertanyaan,
                panjang_jawaban=qa.panjang_jawaban,
                referensi_bpom=ref_items,
                tanaman_terkait=linked_plants,
            )
        )

    return KnowledgeListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        query=clean_q,
        topic=topic.strip(),
        review_filter=review_filter,
        available_topics=available_topics,
    )


KEMENKES_REFERENCES: list[KemenkesReferenceSchema] = [
    KemenkesReferenceSchema(
        ref_id="KEMENKES-FROTI-01",
        judul="Formularium Ramuan Obat Tradisional Indonesia (FROTI)",
        instansi="Kementerian Kesehatan Republik Indonesia",
        jenis_dokumen="Buku Pedoman Resmi / Repositori Kemenkes RI",
        ringkasan=(
            "Acuan struktur data resep ramuan tradisional Indonesia berdasarkan kategori keluhan, "
            "komposisi bahan, takaran, cara pembuatan, peringatan, dan kontraindikasi. Digunakan "
            "sebagai calon referensi terstruktur untuk kurasi manual ramuan."
        ),
        url="https://repository.kemkes.go.id/book/352",
        status_penggunaan="CALON_REFERENSI_TERSTRUKTUR_IMPOR_MANUAL",
    ),
    KemenkesReferenceSchema(
        ref_id="KEMENKES-FROTI-02",
        judul="Keputusan Menteri Kesehatan RI Nomor HK.01.07/MENKES/187/2017 tentang Formularium Ramuan Obat Tradisional Indonesia",
        instansi="Kementerian Kesehatan Republik Indonesia (JDIH)",
        jenis_dokumen="Regulasi Keputusan Menteri Kesehatan RI",
        ringkasan=(
            "Landasan regulasi penetapan Formularium Ramuan Obat Tradisional Indonesia (FROTI) "
            "bagi tenaga kesehatan dan masyarakat dalam pemanfaatan ramuan tradisional yang aman."
        ),
        url="https://jdih.kemkes.go.id/documents/keputusan-menteri-kesehatan-nomor-hk0107menkes1872017",
        status_penggunaan="LANDASAN_REGULASI_KURASI_RAMUAN",
    ),
]

UNVERIFIED_USAGE_FALLBACK_TEXT = (
    "Informasi takaran atau cara penggunaan belum tersedia dalam sumber yang telah diverifikasi."
)

FROTI_CURATION_NOTE = (
    "Database resep terintegrasi dengan data/dataset_obat_tradisional_FROTI_terkurasi.csv yang "
    "mengacu pada Formularium Ramuan Obat Tradisional Indonesia (FROTI - Kepmenkes Nomor "
    "HK.01.07/MENKES/187/2017) dan rujukan BPOM RI. Seluruh angka takaran adalah takaran dalam "
    "referensi tradisional, bukan resep medis pribadi."
)


def _serialize_recipe_card(
    r: HerbalRecipe,
    age_group: str = "dewasa_18_59_tahun",
) -> RecipeCardSchema:
    primary_source_name = (
        r.sumber_dokumen
        or (f"{r.sources[0].instansi} - {r.sources[0].nama_referensi}" if r.sources else "Kemenkes RI, FROTI")
    )
    has_public_usage = any(
        u.boleh_ditampilkan_publik and bool(u.aturan_penggunaan_dari_sumber)
        for u in r.usages
    )
    langkah_list = [st.deskripsi_langkah for st in r.steps]
    raw_dict = {
        "id": r.id,
        "recipe_code": r.recipe_code,
        "slug": r.slug,
        "nama_ramuan": r.nama_ramuan,
        "nama_tanaman": r.nama_tanaman or r.nama_ramuan,
        "nama_ilmiah": r.nama_ilmiah,
        "bagian_tanaman": r.bagian_tanaman,
        "rute_penggunaan": r.rute_penggunaan or "Minum",
        "keluhan_terkait": r.keluhan_terkait,
        "deskripsi": r.deskripsi,
        "takaran_bahan_sumber": r.takaran_bahan_sumber or "",
        "bahan_tambahan": r.bahan_tambahan or "Tidak ada",
        "cara_membuat_sumber": r.cara_membuat_sumber or " ".join(langkah_list),
        "langkah_list": langkah_list,
        "aturan_pakai_sumber": r.aturan_pakai_sumber or "",
        "dosis_kelompok_usia_map": r.dosis_kelompok_usia_map,
        "peringatan": r.peringatan,
        "kontraindikasi": r.kontraindikasi,
        "status_keamanan_dosis": r.status_keamanan_dosis or "",
        "sumber_dokumen": r.sumber_dokumen or primary_source_name,
        "sumber_url": r.sumber_url,
        "sumber_halaman": r.sumber_halaman or "",
        "nama_sumber": primary_source_name,
        "status_verifikasi": r.status_verifikasi,
        "tanggal_review": r.tanggal_review,
        "jumlah_bahan": len(r.ingredients),
        "jumlah_langkah": len(r.steps),
        "aturan_penggunaan_tersedia": has_public_usage,
    }
    formatted = format_recipe_card_dict(raw_dict, age_group=age_group)
    return RecipeCardSchema(**formatted)


@router.get("/recipes", response_model=RecipeListResponse, tags=["Recipes"])
def list_recipes(
    q: str = Query(default="", max_length=200, description="Kata kunci keluhan, nama tanaman, atau kegunaan tradisional"),
    keluhan: str = Query(default="", max_length=120, description="Filter kategori keluhan"),
    age_group: str = Query(default="dewasa_18_59_tahun", max_length=60, description="Kelompok usia atau kondisi"),
    db: Session = Depends(get_db),
) -> RecipeListResponse:
    all_recipes = db.query(HerbalRecipe).order_by(HerbalRecipe.id.asc()).all()
    available_complaints = sorted({r.keluhan_terkait for r in all_recipes if r.keluhan_terkait})

    clean_q = sanitize_query_text(q).lower()
    clean_keluhan = keluhan.strip().lower()

    filtered: list[RecipeCardSchema] = []
    for r in all_recipes:
        if clean_keluhan and clean_keluhan not in r.keluhan_terkait.lower():
            continue
        if clean_q:
            bahan_str = " ".join(ing.nama_bahan.lower() for ing in r.ingredients)
            haystack = (
                f"{r.recipe_code} {r.nama_ramuan} {r.nama_tanaman or ''} {r.nama_ilmiah or ''} "
                f"{r.keluhan_terkait} {r.deskripsi} {bahan_str}"
            ).lower()
            if clean_q not in haystack and not any(tok in haystack for tok in clean_q.split() if len(tok) >= 3):
                continue
        filtered.append(_serialize_recipe_card(r, age_group=age_group))

    return RecipeListResponse(
        items=filtered,
        total=len(filtered),
        query=clean_q,
        keluhan=keluhan.strip(),
        age_group=age_group,
        available_complaints=available_complaints,
        available_age_groups=AVAILABLE_AGE_GROUPS,
        froti_reference_note=FROTI_CURATION_NOTE,
    )


@router.get("/recipes/search", response_model=RecipeListResponse, tags=["Recipes"])
def search_recipes_endpoint(
    q: str = Query(default="", max_length=200, description="Kata kunci keluhan, nama tanaman, atau kegunaan tradisional"),
    age_group: str = Query(default="dewasa_18_59_tahun", max_length=60, description="Kelompok usia atau kondisi"),
    db: Session = Depends(get_db),
) -> RecipeListResponse:
    all_recipes = db.query(HerbalRecipe).order_by(HerbalRecipe.id.asc()).all()
    available_complaints = sorted({r.keluhan_terkait for r in all_recipes if r.keluhan_terkait})
    clean_q = sanitize_query_text(q)

    if not clean_q:
        cards = [_serialize_recipe_card(r, age_group=age_group) for r in all_recipes]
        return RecipeListResponse(
            items=cards,
            total=len(cards),
            query="",
            keluhan="",
            age_group=age_group,
            available_complaints=available_complaints,
            available_age_groups=AVAILABLE_AGE_GROUPS,
            froti_reference_note=FROTI_CURATION_NOTE,
        )

    matched_dicts = search_engine.search_recipes_by_query(
        clean_q, mode_used="tfidf", top_k=20, age_group=age_group
    )
    cards = [RecipeCardSchema(**m) for m in matched_dicts]
    return RecipeListResponse(
        items=cards,
        total=len(cards),
        query=clean_q,
        keluhan="",
        age_group=age_group,
        available_complaints=available_complaints,
        available_age_groups=AVAILABLE_AGE_GROUPS,
        froti_reference_note=FROTI_CURATION_NOTE,
    )


@router.get("/recipes/{slug}", response_model=RecipeDetailSchema, tags=["Recipes"])
def get_recipe_detail(
    slug: str,
    age_group: str = Query(default="dewasa_18_59_tahun", max_length=60, description="Kelompok usia atau kondisi"),
    db: Session = Depends(get_db),
) -> RecipeDetailSchema:
    clean_slug = slug.strip().lower()
    recipe = db.query(HerbalRecipe).filter(HerbalRecipe.slug == clean_slug).first()
    if not recipe:
        raise HTTPException(
            status_code=404,
            detail=f"Resep ramuan dengan slug '{slug}' tidak ditemukan dalam database HERB-INFO AI.",
        )

    card_info = _serialize_recipe_card(recipe, age_group=age_group)

    ingredients = [
        RecipeIngredientSchema(
            id=ing.id,
            nama_bahan=ing.nama_bahan,
            jumlah=ing.jumlah or "Belum tersedia di sumber",
            satuan=ing.satuan or MANDATORY_TAKARAN_LABEL,
            catatan=ing.catatan,
        )
        for ing in recipe.ingredients
    ]

    steps = [
        RecipeStepSchema(
            id=st.id,
            nomor_langkah=st.nomor_langkah,
            deskripsi_langkah=st.deskripsi_langkah,
        )
        for st in recipe.steps
    ]

    usages: list[RecipeUsageSchema] = []
    public_usage_texts: list[str] = []
    for u in recipe.usages:
        if card_info.instruksi_konsumsi_disembunyikan:
            t_pub = VULNERABLE_CONSUMPTION_WARNING
        elif u.boleh_ditampilkan_publik and u.aturan_penggunaan_dari_sumber:
            t_pub = f"{u.aturan_penggunaan_dari_sumber} ({MANDATORY_TAKARAN_LABEL})"
            public_usage_texts.append(t_pub)
        else:
            t_pub = UNVERIFIED_USAGE_FALLBACK_TEXT
        usages.append(
            RecipeUsageSchema(
                id=u.id,
                aturan_penggunaan_dari_sumber=(
                    u.aturan_penggunaan_dari_sumber
                    if (u.boleh_ditampilkan_publik and not card_info.instruksi_konsumsi_disembunyikan)
                    else None
                ),
                status_review_penggunaan=u.status_review_penggunaan,
                boleh_ditampilkan_publik=u.boleh_ditampilkan_publik and not card_info.instruksi_konsumsi_disembunyikan,
                teks_publik=t_pub,
            )
        )

    if card_info.instruksi_konsumsi_disembunyikan:
        aturan_publik = VULNERABLE_CONSUMPTION_WARNING
    else:
        aturan_publik = (
            " ".join(public_usage_texts)
            if public_usage_texts
            else UNVERIFIED_USAGE_FALLBACK_TEXT
        )

    sources = [
        RecipeSourceSchema(
            id=src.id,
            nama_referensi=src.nama_referensi,
            instansi=src.instansi,
            url=src.url,
            halaman=src.halaman,
            status_validasi=src.status_validasi,
        )
        for src in recipe.sources
    ]

    return RecipeDetailSchema(
        id=recipe.id,
        recipe_code=recipe.recipe_code,
        slug=recipe.slug,
        nama_ramuan=recipe.nama_ramuan,
        nama_tanaman=card_info.nama_tanaman,
        nama_ilmiah=card_info.nama_ilmiah,
        bagian_tanaman=card_info.bagian_tanaman,
        kegunaan_tradisional=card_info.kegunaan_tradisional,
        keluhan_terkait=recipe.keluhan_terkait,
        deskripsi=recipe.deskripsi,
        takaran_bahan_sumber=card_info.takaran_bahan_sumber,
        label_takaran=MANDATORY_TAKARAN_LABEL,
        campuran_tambahan=card_info.campuran_tambahan,
        cara_menyiapkan_bahan=recipe.cara_menyiapkan_bahan,
        langkah_pembuatan=card_info.langkah_pembuatan,
        rute_penggunaan=card_info.rute_penggunaan,
        cara_penggunaan=card_info.cara_penggunaan,
        kelompok_usia_terpilih=card_info.kelompok_usia_terpilih,
        label_kelompok_usia=card_info.label_kelompok_usia,
        dosis_kelompok_usia=card_info.dosis_kelompok_usia,
        dosis_per_kelompok_usia=card_info.dosis_per_kelompok_usia,
        instruksi_konsumsi_disembunyikan=card_info.instruksi_konsumsi_disembunyikan,
        peringatan_kelompok_rentan=card_info.peringatan_kelompok_rentan,
        kelompok_tidak_dianjurkan=recipe.kelompok_tidak_dianjurkan,
        larangan_kontraindikasi=card_info.larangan_kontraindikasi,
        efek_samping_dan_interaksi=card_info.efek_samping_dan_interaksi,
        status_keamanan_dosis=card_info.status_keamanan_dosis,
        status_verifikasi=recipe.status_verifikasi,
        sumber_dokumen=card_info.sumber_dokumen,
        sumber_url=recipe.sumber_url,
        sumber_halaman=recipe.sumber_halaman,
        halaman_rujukan=card_info.halaman_rujukan,
        tautan_sumber=card_info.tautan_sumber,
        reviewer=recipe.reviewer,
        tanggal_review=recipe.tanggal_review,
        peringatan=recipe.peringatan,
        kontraindikasi=recipe.kontraindikasi,
        ingredients=ingredients,
        steps=steps,
        usages=usages,
        aturan_penggunaan_publik=aturan_publik,
        sources=sources,
        label_edukasi="Informasi Edukasi - Bukan Pengganti Nasihat Medis",
    )


@router.get("/sources", response_model=SourceListResponse, tags=["Sources"])
def list_sources(
    q: str = Query(default="", max_length=200, description="Pencarian judul atau ringkasan sumber BPOM"),
    topic: str = Query(default="", max_length=80, description="Filter topik sumber BPOM"),
    db: Session = Depends(get_db),
) -> SourceListResponse:
    all_sources = db.query(Source).order_by(Source.source_id.asc()).all()
    available_topics = sorted({s.topik for s in all_sources if s.topik})

    clean_q = sanitize_query_text(q).lower()
    clean_topic = topic.strip().lower()

    filtered: list[SourceBriefSchema] = []
    for s in all_sources:
        if clean_topic and s.topik.lower() != clean_topic:
            continue
        if clean_q:
            haystack = f"{s.source_id} {s.judul} {s.topik} {s.ringkasan_aman}".lower()
            if clean_q not in haystack:
                continue
        filtered.append(
            SourceBriefSchema(
                source_id=s.source_id,
                judul=s.judul,
                topik=s.topik,
                ringkasan_aman=s.ringkasan_aman,
                source_url=s.source_url,
                otoritas=s.otoritas,
                status_review=s.status_review,
            )
        )

    return SourceListResponse(
        items=filtered,
        total=len(filtered),
        query=clean_q,
        topic=topic.strip(),
        available_topics=available_topics,
        kemenkes_references=KEMENKES_REFERENCES,
    )


@router.post("/search", response_model=SearchResponse, tags=["Search"])
def search_documents(payload: SearchRequest) -> SearchResponse:
    result = search_engine.search(
        raw_query=payload.query,
        mode=payload.mode,
        top_k=payload.top_k,
        age_group=payload.age_group,
        durasi_keluhan=payload.durasi_keluhan,
        vulnerable_flags=payload.vulnerable_flags,
        obat_rutin=payload.obat_rutin,
        use_gemini=payload.use_gemini,
    )
    return SearchResponse(**result)


@router.get("/evaluation", tags=["Evaluation"])
def get_evaluation_details(db: Session = Depends(get_db)) -> dict:
    eval_summary = evaluate_manual_template(search_engine)
    nlp_benchmark_30 = evaluate_nlp_benchmark_30(search_engine)
    index_meta = search_engine.get_metadata()
    import_report: Optional[dict] = None
    if IMPORT_REPORT_PATH.exists():
        try:
            with open(IMPORT_REPORT_PATH, "r", encoding="utf-8") as f:
                import_report = json.load(f)
        except Exception:
            import_report = None

    total_plants = db.query(Plant).count()
    plants_with_sci = db.query(Plant).filter(Plant.nama_ilmiah.isnot(None)).count()
    total_qa = db.query(QAPair).count()
    total_sources = db.query(Source).count()
    total_recipes = db.query(HerbalRecipe).count()
    froti_recipes = (
        db.query(HerbalRecipe).filter(HerbalRecipe.recipe_code.like("FROTI-%")).count()
    )

    return {
        "evaluation": eval_summary,
        "nlp_benchmark_30": nlp_benchmark_30,
        "dataset_summary": {
            "total_plants": total_plants,
            "plants_with_scientific_name": plants_with_sci,
            "plants_local_only": total_plants - plants_with_sci,
            "total_recipes": total_recipes,
            "froti_recipes": froti_recipes,
            "documented_other_recipes": total_recipes - froti_recipes,
            "total_qa_kaggle": total_qa,
            "total_bpom_sources": total_sources,
        },
        "nlp_capabilities": {
            "normalisasi_huruf_spasi": True,
            "sinonim_keluhan_count": len(FROTI_QUERY_SYNONYMS),
            "koreksi_typo_count": len(TYPO_CORRECTION_MAP),
            "istilah_tanaman_lokal_count": len(LOCAL_PLANT_TERMS_MAP),
            "deteksi_query_tidak_relevan": True,
            "sinonim_samples": [
                {"istilah": k, "ekspansi": ", ".join(v)}
                for k, v in list(FROTI_QUERY_SYNONYMS.items())[:12]
            ],
            "lokal_samples": [
                {"lokal": k, "standar": v}
                for k, v in list(LOCAL_PLANT_TERMS_MAP.items())[:12]
            ],
            "typo_samples": [
                {"typo": k, "koreksi": v}
                for k, v in list(TYPO_CORRECTION_MAP.items())[:12]
            ],
        },
        "index_metadata": index_meta,
        "functional_test_queries": FUNCTIONAL_TEST_QUERIES,
        "import_report_summary": import_report,
    }


@router.post("/evaluation/compute", tags=["Evaluation"])
def compute_evaluation_with_annotations(payload: EvaluationComputeRequest) -> dict:
    custom_map = {
        item.id_uji.strip(): item.gold_relevant_ids.strip()
        for item in payload.annotations
        if item.id_uji.strip()
    }
    res = evaluate_nlp_benchmark_30(
        search_engine,
        custom_annotations=custom_map,
        save_to_csv=payload.save_to_csv,
    )
    return res



@router.get("/artifacts/eda-image", tags=["Evaluation"])
def get_eda_image():
    img_path = PROCESSED_DIR / "eda_distribusi_panjang.png"
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Grafik EDA belum tersedia.")
    return FileResponse(img_path, media_type="image/png")
