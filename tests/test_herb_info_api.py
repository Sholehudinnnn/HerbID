"""Comprehensive Backend Unit, Security, and Integration Tests for HERB-INFO AI."""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pytest
from fastapi.testclient import TestClient

from app.importers.data_importer import ZipSecurityError, safe_extract_zip
from app.main import app, initialize_system
from app.services.evaluation_service import FUNCTIONAL_TEST_QUERIES


@pytest.fixture(scope="module", autouse=True)
def setup_app():
    initialize_system()


client = TestClient(app)


def test_health_and_stats_accuracy():
    """Verify /api/health and /api/stats match the audited dataset counts."""
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    h_data = r_health.json()
    assert h_data["status"] == "ok"
    assert h_data["database_ready"] is True
    assert h_data["tfidf_index_ready"] is True

    r_stats = client.get("/api/stats")
    assert r_stats.status_code == 200
    stats = r_stats.json()
    assert stats["total_plants"] == 30
    assert stats["plants_with_scientific_name"] == 27
    assert stats["plants_local_only"] == 3
    assert stats["total_qa"] == 52
    assert stats["total_sources"] == 9
    assert stats["strict_review_qa_count"] == 14
    assert stats["candidate_topic_links_count"] == 15
    assert stats["unique_questions_with_source_count"] == 14
    assert stats["questions_needing_reference_count"] == 38
    assert stats["evaluation_gold_filled_count"] == 0
    assert stats["evaluation_total_count"] == 52


def test_species_list_count_and_no_non_plants():
    """Test #1: /species loads exact imported plant count and excludes non-plant topics."""
    r = client.get("/api/species?page=1&per_page=50")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 30
    assert len(data["items"]) == 30

    slugs = {item["slug"] for item in data["items"]}
    assert "jahe" in slugs
    assert "kunyit" in slugs
    assert "temulawak" in slugs
    assert "asam-jawa" in slugs
    # Ensure non-plants like bekam, akupunktur, bko, jamu are NOT in Plant table
    for forbidden in ["bekam", "akupunktur", "bko", "jamu", "sinshe", "usada-bali"]:
        assert forbidden not in slugs


def test_species_search_jahe_and_empty_state():
    """Test #2: Searching 'jahe' returns Jahe; searching non-existent species returns empty list."""
    r_jahe = client.get("/api/species?q=jahe")
    assert r_jahe.status_code == 200
    jahe_data = r_jahe.json()
    assert jahe_data["total"] >= 1
    assert any(item["slug"] == "jahe" for item in jahe_data["items"])

    r_empty = client.get("/api/species?q=edelweiss_himalaya_fiktif")
    assert r_empty.status_code == 200
    empty_data = r_empty.json()
    assert empty_data["total"] == 0
    assert empty_data["items"] == []


def test_species_uppercase_and_whitespace_handling():
    """Test #3: Searching with uppercase and excessive whitespace works cleanly."""
    r = client.get("/api/species", params={"q": "   TEMULAWAK   "})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == "temulawak"
    assert data["items"][0]["nama_ilmiah"] == "Curcuma xanthorrhiza"


def test_species_pagination_no_overlap_or_skip():
    """Test #4: Pagination across 3 pages (per_page=12) returns all 30 unique records without overlap."""
    p1 = client.get("/api/species?page=1&per_page=12&sort=az").json()
    p2 = client.get("/api/species?page=2&per_page=12&sort=az").json()
    p3 = client.get("/api/species?page=3&per_page=12&sort=az").json()

    assert len(p1["items"]) == 12
    assert len(p2["items"]) == 12
    assert len(p3["items"]) == 6
    assert p1["total_pages"] == 3

    slugs_p1 = [i["slug"] for i in p1["items"]]
    slugs_p2 = [i["slug"] for i in p2["items"]]
    slugs_p3 = [i["slug"] for i in p3["items"]]

    combined = slugs_p1 + slugs_p2 + slugs_p3
    assert len(combined) == 30
    assert len(set(combined)) == 30


def test_species_detail_and_404():
    """Test #5: Valid slug returns complete species detail; invalid slug returns meaningful 404."""
    r_ok = client.get("/api/species/temulawak")
    assert r_ok.status_code == 200
    detail = r_ok.json()
    assert detail["nama_umum"] == "Temulawak"
    assert detail["nama_ilmiah"] == "Curcuma xanthorrhiza"
    assert detail["famili"] is None  # Not fabricated
    assert detail["sumber_count"] == 2
    assert len(detail["pengetahuan_terkait"]) >= 1
    assert detail["cek_bpom_url"] == "https://cekbpom.pom.go.id/"

    # Local-only plant has nama_ilmiah=None and ringkasan_terkurasi=None
    r_local = client.get("/api/species/asam-jawa")
    assert r_local.status_code == 200
    local_detail = r_local.json()
    assert local_detail["nama_ilmiah"] is None
    assert local_detail["famili"] is None
    assert local_detail["ringkasan_terkurasi"] is None
    assert local_detail["status_verifikasi"] == "Data terbatas"

    r_404 = client.get("/api/species/tanaman-fiktif-tidak-ada")
    assert r_404.status_code == 404
    assert "tidak ditemukan" in r_404.json()["detail"].lower()


def test_tfidf_search_jamu_and_fitofarmaka():
    """Test #6: Baseline TF-IDF returns BPOM-01 for 'perbedaan jamu dan fitofarmaka'."""
    r = client.post(
        "/api/search",
        json={"query": "perbedaan jamu dan fitofarmaka", "mode": "tfidf", "top_k": 5},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["mode_used"] == "tfidf"
    assert data["requires_professional_advice"] is False
    assert len(data["results"]) >= 1
    assert data["results"][0]["source_id"] == "BPOM-01"
    assert "jamu" in data["results"][0]["matched_terms"]
    assert "fitofarmaka" in data["results"][0]["matched_terms"]


def test_clinical_safety_guardrail_pregnancy_dosage():
    """Test #7: Sensitive query 'Saya hamil, berapa dosis jamu yang aman?' triggers safety warning and no dosage."""
    r = client.post(
        "/api/search",
        json={"query": "Saya hamil, berapa dosis jamu yang aman?", "mode": "tfidf", "top_k": 5},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["requires_professional_advice"] is True
    assert (
        "Sistem tidak memberikan diagnosis/dosis/rekomendasi terapi. Konsultasikan dengan apoteker/dokter."
        in data["message"]
    )
    assert len(data["safety_triggers"]) >= 1


def test_empty_query_and_xss_payload_safety():
    """Test #8: Empty query and HTML/JS XSS payloads do not crash or reflect raw tags."""
    r_empty = client.post("/api/search", json={"query": "   ", "mode": "tfidf", "top_k": 5})
    assert r_empty.status_code == 200
    empty_data = r_empty.json()
    assert empty_data["results"] == []

    xss_payload = "<script>alert('xss')</script><img src=x onerror=alert(1)> bahaya BKO"
    r_xss = client.post("/api/search", json={"query": xss_payload, "mode": "tfidf", "top_k": 5})
    assert r_xss.status_code == 200
    xss_data = r_xss.json()
    assert "<script>" not in xss_data["sanitized_query"]
    assert "onerror" not in xss_data["sanitized_query"]
    assert len(xss_data["results"]) >= 1
    assert xss_data["results"][0]["source_id"] == "BPOM-05"


def test_api_validation_top_k_and_query_length():
    """Test #9: API validates top_k bounds (1..20) and max query length (300 chars)."""
    r_bad_topk = client.post("/api/search", json={"query": "jamu", "mode": "tfidf", "top_k": 99})
    assert r_bad_topk.status_code == 422

    r_zero_topk = client.post("/api/search", json={"query": "jamu", "mode": "tfidf", "top_k": 0})
    assert r_zero_topk.status_code == 422

    long_query = "a" * 350
    r_long = client.post("/api/search", json={"query": long_query, "mode": "tfidf", "top_k": 5})
    assert r_long.status_code == 422


def test_semantic_fallback_when_encoder_unavailable():
    """Test #13: Requesting mode='semantic' falls back cleanly to TF-IDF with clear reason if encoder not installed."""
    r = client.post(
        "/api/search",
        json={"query": "Penggolongan Jamu, OHT, Fitofarmaka", "mode": "semantic", "top_k": 3},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["mode_requested"] == "semantic"
    assert data["mode_used"] in ("tfidf", "semantic")
    if data["mode_used"] == "tfidf":
        assert data["semantic_status_note"] is not None
        assert any(term in data["semantic_status_note"] for term in ["bpom_semantic_embeddings", "Gemini", "TF-IDF"])
    assert len(data["results"]) >= 1


def test_sources_and_knowledge_endpoints():
    """Test #11 & #12: Official BPOM sources have valid URLs and no fake product approval claims."""
    r_src = client.get("/api/sources")
    assert r_src.status_code == 200
    src_data = r_src.json()
    assert src_data["total"] == 9
    for item in src_data["items"]:
        assert item["source_url"].startswith("https://")
        assert item["status_review"] == "RUJUKAN_BPOM_PERLU_KURASI_PER_KLAIM"

    r_know = client.get("/api/knowledge?review_filter=strict_only&per_page=50")
    assert r_know.status_code == 200
    know_data = r_know.json()
    assert know_data["total"] == 14


def test_zip_security_rejects_traversal_and_bad_extensions(tmp_path: Path):
    """Verify safe_extract_zip blocks path traversal and disallowed file extensions."""
    traversal_zip = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal_zip, "w") as zf:
        zf.writestr("../evil.csv", "id,name\n1,test")

    with pytest.raises(ZipSecurityError):
        safe_extract_zip(traversal_zip, tmp_path / "out1")

    bad_ext_zip = tmp_path / "bad_ext.zip"
    with zipfile.ZipFile(bad_ext_zip, "w") as zf:
        zf.writestr("malware.exe", "MZ...")

    with pytest.raises(ZipSecurityError):
        safe_extract_zip(bad_ext_zip, tmp_path / "out2")


def test_twenty_functional_queries_suite():
    """Run all 20 functional test queries and verify deterministic non-crashing behavior."""
    assert len(FUNCTIONAL_TEST_QUERIES) == 20
    for item in FUNCTIONAL_TEST_QUERIES:
        r = client.post(
            "/api/search",
            json={"query": item["query"], "mode": "tfidf", "top_k": 5},
        )
        assert r.status_code == 200, f"Failed on {item['id']}: {item['query']}"
        body = r.json()
        if item["category"].startswith("sensitif_"):
            assert body["requires_professional_advice"] is True
        if item["category"] in ("query_tidak_relevan", "nama_lokal_tanpa_sumber_bpom", "query_kosong"):
            assert body["results"] == []


def test_symptom_diagnosis_and_dosage_recommendations():
    """Verify FROTI-based complaint understanding, matched recipes, and safe dosage display."""
    r_fever = client.post(
        "/api/search",
        json={
            "query": "demam bagusnya minum apa gitu dosisnya berapa",
            "mode": "tfidf",
            "top_k": 5,
        },
    )
    assert r_fever.status_code == 200
    f_data = r_fever.json()
    assert "demam" in f_data["keluhan_terdeteksi"]
    assert len(f_data["matched_recipes"]) >= 1
    assert f_data["matched_recipes"][0]["recipe_code"] == "FROTI-001"
    assert "Sambiloto" in f_data["matched_recipes"][0]["nama_tanaman"]
    assert "Takaran dalam referensi tradisional" in f_data["matched_recipes"][0]["label_takaran"]

    r_diare = client.post(
        "/api/search",
        json={"query": "sedang diare bagusnya minum daun apa dan dosisnya", "mode": "tfidf", "top_k": 5},
    )
    assert r_diare.status_code == 200
    d_data = r_diare.json()
    # Diare is not supported in FROTI 2017, honest zero results
    assert len(d_data["matched_recipes"]) == 0
    assert d_data["recipe_empty_message"] is not None



def test_froti_csv_integration_and_eight_required_fields():
    """Verify all 19 FROTI records are imported and expose all 8 required display fields + mandatory takaran label."""
    r_list = client.get("/api/recipes")
    assert r_list.status_code == 200
    data = r_list.json()
    assert data["total"] >= 19
    codes = {item["recipe_code"] for item in data["items"]}
    for idx in range(1, 20):
        assert f"FROTI-{idx:03d}" in codes

    # Search by complaint, plant name, and traditional use
    r_search = client.post(
        "/api/search",
        json={
            "query": "Saya demam, ada informasi ramuan tradisional sambiloto?",
            "mode": "tfidf",
            "top_k": 5,
            "age_group": "dewasa_18_59_tahun",
        },
    )
    assert r_search.status_code == 200
    s_data = r_search.json()
    assert len(s_data["matched_recipes"]) >= 1
    froti_001 = next((m for m in s_data["matched_recipes"] if m["recipe_code"] == "FROTI-001"), None)
    assert froti_001 is not None

    # Verify all 8 required fields on FROTI-001 search result card
    assert froti_001["nama_tanaman"] == "Sambiloto"
    assert "Andrographis paniculata" in (froti_001["nama_ilmiah"] or "")
    assert "Demam" in froti_001["kegunaan_tradisional"]
    assert "10-15 g herba" in froti_001["takaran_bahan_sumber"]
    assert froti_001["label_takaran"] == "Takaran dalam referensi tradisional, bukan resep medis pribadi"
    assert "Takaran dalam referensi tradisional, bukan resep medis pribadi" in froti_001["takaran_bahan_sumber"]
    assert "Air 2 gelas; madu secukupnya" in froti_001["campuran_tambahan"]
    assert "Rebus bahan dengan dua gelas air" in froti_001["langkah_pembuatan"]
    assert froti_001["rute_penggunaan"] == "Minum"
    assert "FROTI: 3 kali 10-15 g herba/hari" in froti_001["cara_penggunaan"]
    assert "Kehamilan, menyusui, alergi" in froti_001["larangan_kontraindikasi"]
    assert "anafilaksis" in froti_001["efek_samping_dan_interaksi"]
    assert "FROTI" in froti_001["sumber_dokumen"]
    assert "15" in froti_001["halaman_rujukan"]


def test_age_group_dosage_and_vulnerable_group_safety_gate():
    """Verify unestablished age dosage fallback and vulnerable group consumption instruction suppression."""
    # 1. Unestablished age group dosage (e.g. anak_6_8_tahun on FROTI-001)
    r_unest = client.get("/api/recipes/froti-001-sambiloto-demam?age_group=anak_6_8_tahun")
    assert r_unest.status_code == 200
    u_data = r_unest.json()
    assert "Dosis belum ditetapkan—konsultasikan dengan dokter atau apoteker" in u_data["dosis_kelompok_usia"]
    assert u_data["instruksi_konsumsi_disembunyikan"] is False

    # 2. Established non-vulnerable age group dosage (anak_6_8_tahun on FROTI-014 Pepaya)
    r_est = client.get("/api/recipes/froti-014-pepaya-nafsu-makan-berkurang?age_group=anak_6_8_tahun")
    assert r_est.status_code == 200
    e_data = r_est.json()
    assert "1/4 cangkir" in e_data["dosis_kelompok_usia"]
    assert "Takaran dalam referensi tradisional, bukan resep medis pribadi" in e_data["dosis_kelompok_usia"]
    assert e_data["instruksi_konsumsi_disembunyikan"] is False

    # 3. Vulnerable groups (balita, bayi, ibu hamil/menyusui, lansia, penyakit kronis/obat rutin)
    for vuln_age in [
        "bayi_0_11_bulan",
        "balita_1_2_tahun",
        "balita_3_5_tahun",
        "lansia_60_plus",
        "ibu_hamil_menyusui",
        "penyakit_kronis_obat_rutin",
    ]:
        r_vuln = client.post(
            "/api/search",
            json={
                "query": "nafsu makan berkurang daun pepaya",
                "mode": "tfidf",
                "top_k": 5,
                "age_group": vuln_age,
            },
        )
        assert r_vuln.status_code == 200
        v_body = r_vuln.json()
        assert v_body["is_vulnerable_group"] is True
        assert v_body["requires_professional_advice"] is True
        assert v_body["vulnerable_group_warning"] is not None
        assert len(v_body["matched_recipes"]) >= 1
        rec0 = v_body["matched_recipes"][0]
        assert rec0["instruksi_konsumsi_disembunyikan"] is True
        assert rec0["aturan_pakai_sumber_asli"] is None
        assert "rekomendasi otomatis" in rec0["cara_penggunaan"]
        assert "Dosis belum ditetapkan—konsultasikan dengan dokter atau apoteker" in rec0["dosis_kelompok_usia"]


def test_nlp_preprocessing_synonyms_typos_local_plants_and_irrelevant_queries():
    """Verify NLP language processing: case/space normalization, synonyms, typos, local plant names, and irrelevant queries."""
    # 1. Typo + local plant name + synonym query
    r_nlp = client.post(
        "/api/search",
        json={
            "query": "   RAMUAN   daun ki oray dan sambilto untuk   demm   ",
            "mode": "tfidf",
            "top_k": 5,
        },
    )
    assert r_nlp.status_code == 200
    body = r_nlp.json()
    nlp = body["nlp_analysis"]
    assert nlp is not None
    assert nlp["normalized_query"] == "ramuan daun ki oray dan sambilto untuk demm"
    assert any(t["asli"] == "sambilto" and t["koreksi"] == "sambiloto" for t in nlp["typo_corrections"])
    assert any(t["asli"] == "demm" and t["koreksi"] == "demam" for t in nlp["typo_corrections"])
    assert any(p["istilah_lokal"] == "ki oray" and p["nama_tanaman_standar"] == "sambiloto" for p in nlp["recognized_local_plants"])
    assert nlp["is_irrelevant_query"] is False
    assert any(m["recipe_code"] == "FROTI-001" for m in body["matched_recipes"])

    # 2. Complaint synonym (migrain -> sakit kepala sebelah -> FROTI-002 / FROTI-003)
    r_syn = client.post(
        "/api/search",
        json={"query": "obat tradisional untuk migrain", "mode": "tfidf", "top_k": 5},
    )
    assert r_syn.status_code == 200
    syn_body = r_syn.json()
    assert any(s["istilah_pengguna"] == "migrain" for s in syn_body["nlp_analysis"]["matched_synonyms"])
    syn_codes = {m["recipe_code"] for m in syn_body["matched_recipes"]}
    assert "FROTI-002" in syn_codes or "FROTI-003" in syn_codes

    # 3. Irrelevant query handling
    r_irrel = client.post(
        "/api/search",
        json={"query": "harga tiket pesawat jakarta surabaya besok pagi", "mode": "tfidf", "top_k": 5},
    )
    assert r_irrel.status_code == 200
    irrel_body = r_irrel.json()
    assert irrel_body["matched_recipes"] == []
    assert irrel_body["results"] == []
    assert irrel_body["nlp_analysis"]["is_irrelevant_query"] is True
    assert irrel_body["nlp_analysis"]["irrelevant_reason"] is not None


def test_explainability_and_semantic_froti_recipes():
    """Verify explainability sentences, score disclaimers, and semantic mode on FROTI recipes."""
    r_sem = client.post(
        "/api/search",
        json={
            "query": "pertanyaan berkaitan dengan batuk berdahak herba timi",
            "mode": "semantic",
            "top_k": 5,
        },
    )
    assert r_sem.status_code == 200
    s_body = r_sem.json()
    assert len(s_body["matched_recipes"]) >= 1
    first_rec = s_body["matched_recipes"][0]
    assert first_rec["alasan_relevansi"] is not None
    assert "Hasil ini ditemukan karena pertanyaan Anda berkaitan dengan" in first_rec["alasan_relevansi"]
    assert "kegunaan tradisional yang sesuai" in first_rec["alasan_relevansi"]
    assert "bukan ukuran khasiat medis" in first_rec["peringatan_skor"]


def test_evaluation_benchmark_30_honesty_and_live_metrics_computation():
    """Verify >=30 evaluation benchmark queries, unlabelled honesty default, and real Hit@1/Recall@3/MRR@10 computation."""
    r_eval = client.get("/api/evaluation")
    assert r_eval.status_code == 200
    e_body = r_eval.json()
    assert "nlp_benchmark_30" in e_body
    bench = e_body["nlp_benchmark_30"]
    assert bench["total_queries"] >= 30
    assert bench["labeled_queries"] == 0
    assert bench["metrics_available"] is False
    assert bench["tfidf_metrics"] is None

    # Compute real Hit@1, Recall@3, and MRR@10 with manual annotations (without saving to CSV)
    r_comp = client.post(
        "/api/evaluation/compute",
        json={
            "annotations": [
                {"id_uji": "EV-01", "gold_relevant_ids": "FROTI-001"},
                {"id_uji": "EV-05", "gold_relevant_ids": "FROTI-005;FROTI-006;FROTI-007"},
                {"id_uji": "EV-33", "gold_relevant_ids": "BPOM-01"},
            ],
            "save_to_csv": False,
        },
    )
    assert r_comp.status_code == 200
    c_body = r_comp.json()
    assert c_body["metrics_available"] is True
    assert c_body["labeled_queries"] == 3
    assert c_body["tfidf_metrics"] is not None
    assert c_body["tfidf_metrics"]["hit_at_1"] == 1.0
    assert c_body["tfidf_metrics"]["recall_at_3"] == 1.0
    assert c_body["tfidf_metrics"]["mrr_at_10"] == 1.0


def test_twelve_smart_herbal_assistant_scenarios(monkeypatch):
    """Verify all 12 mandatory scenarios in Section 13 for HERB-INFO AI Smart Herbal Assistant."""
    # 1. Keluhan batuk berdahak (beserta pemahaman_keluhan, durasi, diagnosis_medis=None, maks 3 hasil)
    r1 = client.post(
        "/api/search",
        json={
            "query": "Aku batuk berdahak sejak kemarin",
            "mode": "tfidf",
            "top_k": 5,
        },
    )
    assert r1.status_code == 200
    b1 = r1.json()
    pk1 = b1["pemahaman_keluhan"]
    assert pk1 is not None
    assert pk1["input_keluhan"] == "Aku batuk berdahak sejak kemarin"
    assert "batuk berdahak" in pk1["keluhan_teridentifikasi"]
    assert pk1["durasi_keluhan"] == "sejak kemarin"
    assert pk1["diagnosis_medis"] is None
    assert 1 <= len(b1["matched_recipes"]) <= 3
    codes1 = {m["recipe_code"] for m in b1["matched_recipes"]}
    assert codes1.intersection({"FROTI-005", "FROTI-006", "FROTI-007"})
    assert b1["matched_recipes"][0]["efek_samping"]
    assert b1["matched_recipes"][0]["interaksi_obat"]

    # 2. Keluhan perut kembung
    r2 = client.post(
        "/api/search",
        json={"query": "Saya sering merasa perut kembung.", "mode": "tfidf", "top_k": 5},
    )
    assert r2.status_code == 200
    b2 = r2.json()
    assert 1 <= len(b2["matched_recipes"]) <= 3
    assert any(m["recipe_code"] in ("FROTI-015", "FROTI-016") for m in b2["matched_recipes"])

    # 3. Keluhan sakit tenggorokan
    r3 = client.post(
        "/api/search",
        json={"query": "Tenggorokan saya terasa sakit.", "mode": "tfidf", "top_k": 5},
    )
    assert r3.status_code == 200
    b3 = r3.json()
    assert any(m["recipe_code"] == "FROTI-004" for m in b3["matched_recipes"])

    # 4. Keluhan nyeri haid
    r4 = client.post(
        "/api/search",
        json={"query": "Saya sedang mengalami nyeri haid.", "mode": "tfidf", "top_k": 5},
    )
    assert r4.status_code == 200
    b4 = r4.json()
    assert 1 <= len(b4["matched_recipes"]) <= 3
    assert any(m["recipe_code"] in ("FROTI-018", "REC-01") for m in b4["matched_recipes"])

    # 5. Pertanyaan dengan sinonim
    r5 = client.post(
        "/api/search",
        json={"query": "Perut saya begah dan penuh gas sejak 2 hari", "mode": "tfidf", "top_k": 5},
    )
    assert r5.status_code == 200
    b5 = r5.json()
    assert b5["pemahaman_keluhan"]["durasi_keluhan"] == "2 hari"
    assert any(m["recipe_code"] == "FROTI-015" for m in b5["matched_recipes"])

    # 6. Pertanyaan dengan salah ketik
    r6 = client.post(
        "/api/search",
        json={"query": "Saya sedang btk berdahak dan demm", "mode": "tfidf", "top_k": 5},
    )
    assert r6.status_code == 200
    b6 = r6.json()
    assert len(b6["nlp_analysis"]["typo_corrections"]) >= 2
    assert len(b6["matched_recipes"]) >= 1

    # 7. Keluhan yang tidak tersedia dalam dataset
    r7 = client.post(
        "/api/search",
        json={"query": "Saya mengalami katarak mata rabun jauh", "mode": "tfidf", "top_k": 5},
    )
    assert r7.status_code == 200
    b7 = r7.json()
    assert b7["matched_recipes"] == []
    assert "Belum tersedia referensi ramuan terverifikasi yang relevan untuk keluhan tersebut." in (
        b7["recipe_empty_message"] or ""
    )

    # 8. Keluhan dengan tanda bahaya
    r8 = client.post(
        "/api/search",
        json={"query": "Saya batuk berdarah disertai sesak napas dan nyeri dada", "mode": "tfidf", "top_k": 5},
    )
    assert r8.status_code == 200
    b8 = r8.json()
    assert b8["emergency_warning"] is not None
    assert b8["requires_professional_advice"] is True
    assert "TANDA BAHAYA MEDIS" in b8["pemahaman_keluhan"]["status_keselamatan"]

    # 9. Kelompok usia anak (dosis belum ditetapkan dalam sumber)
    r9 = client.post(
        "/api/search",
        json={
            "query": "Saya demam, ada informasi ramuan sambiloto?",
            "mode": "tfidf",
            "top_k": 3,
            "age_group": "anak_6_8_tahun",
        },
    )
    assert r9.status_code == 200
    b9 = r9.json()
    froti001_child = next(m for m in b9["matched_recipes"] if m["recipe_code"] == "FROTI-001")
    assert "Dosis belum ditetapkan dalam sumber." in froti001_child["dosis_kelompok_usia"]

    # 10. Pengguna obat rutin
    r10 = client.post(
        "/api/search",
        json={
            "query": "Saya sedang batuk berdahak.",
            "mode": "tfidf",
            "top_k": 3,
            "age_group": "dewasa_18_59_tahun",
            "obat_rutin": "warfarin, amlodipin",
        },
    )
    assert r10.status_code == 200
    b10 = r10.json()
    assert b10["is_vulnerable_group"] is True
    assert b10["requires_professional_advice"] is True
    assert b10["informasi_keselamatan"] is not None
    assert "warfarin, amlodipin" in (b10["informasi_keselamatan"]["peringatan_obat_rutin"] or "")
    assert b10["matched_recipes"][0]["instruksi_konsumsi_disembunyikan"] is True

    # 11. Kegagalan koneksi Gemini (fallback aman berbasis sumber terkurasi tanpa error)
    import app.services.gemini_service as gemini_mod
    import httpx as _httpx

    def _raise_conn_error(*args, **kwargs):
        raise _httpx.ConnectError("Simulated Gemini connection failure")

    monkeypatch.setattr(gemini_mod.httpx, "post", _raise_conn_error)
    gemini_mod._GEMINI_CONSULTATION_CACHE.clear()
    r11 = client.post(
        "/api/search",
        json={
            "query": "Saya sedang batuk berdahak.",
            "mode": "tfidf",
            "top_k": 3,
            "use_gemini": True,
        },
    )
    assert r11.status_code == 200
    b11 = r11.json()
    assert b11["pemahaman_keluhan"]["diagnosis_medis"] is None
    assert b11["pemahaman_keluhan"]["ringkasan_sumber_terkurasi"] is not None
    assert "bukan diagnosis" in b11["pemahaman_keluhan"]["ringkasan_sumber_terkurasi"].lower()

    # 12. Input kosong atau tidak relevan
    r12_empty = client.post("/api/search", json={"query": "   ", "mode": "tfidf", "top_k": 3})
    assert r12_empty.status_code == 200
    b12_empty = r12_empty.json()
    assert b12_empty["matched_recipes"] == []
    assert len(b12_empty["pemahaman_keluhan"]["pertanyaan_klarifikasi"]) >= 1

    r12_irrel = client.post(
        "/api/search",
        json={"query": "rekomendasi laptop gaming murah", "mode": "tfidf", "top_k": 3},
    )
    assert r12_irrel.status_code == 200
    b12_irrel = r12_irrel.json()
    assert b12_irrel["matched_recipes"] == []
    assert b12_irrel["nlp_analysis"]["is_irrelevant_query"] is True


# ======================================================================================
# MANDATORY NLP & MULTI-SYMPTOM REFINEMENT TESTS (CASES A - H)
# ======================================================================================

def test_case_a_batuk_kering_excludes_wet_cough_recipes():
    """Case A: 'Saya batuk kering' -> batuk kering, jangan berikan ramuan batuk berdahak."""
    res = client.post("/api/search", json={"query": "Saya batuk kering", "mode": "tfidf", "top_k": 3})
    assert res.status_code == 200
    data = res.json()
    assert "batuk kering" in data["keluhan_terdeteksi"]
    recipe_codes = [r["recipe_code"] for r in data["matched_recipes"]]
    for wet_code in ["FROTI-005", "FROTI-006", "FROTI-007"]:
        assert wet_code not in recipe_codes
    assert data["pemahaman_keluhan"]["keluhan_utama"] == "batuk kering"


def test_case_b_batuk_berdahak_returns_wet_cough_recipes():
    """Case B: 'Saya batuk berdahak' -> batuk berdahak, ramuan batuk berdahak boleh muncul."""
    res = client.post("/api/search", json={"query": "Saya batuk berdahak", "mode": "tfidf", "top_k": 3})
    assert res.status_code == 200
    data = res.json()
    assert "batuk berdahak" in data["keluhan_terdeteksi"]
    recipe_codes = [r["recipe_code"] for r in data["matched_recipes"]]
    assert any(code in recipe_codes for code in ["FROTI-005", "FROTI-006", "FROTI-007"])


def test_case_c_batuk_tidak_berdahak_understood_as_batuk_kering():
    """Case C: 'Saya batuk tidak berdahak' -> dipahami sebagai batuk kering."""
    res = client.post("/api/search", json={"query": "Saya batuk tidak berdahak", "mode": "tfidf", "top_k": 3})
    assert res.status_code == 200
    data = res.json()
    assert "batuk kering" in data["keluhan_terdeteksi"]
    recipe_codes = [r["recipe_code"] for r in data["matched_recipes"]]
    for wet_code in ["FROTI-005", "FROTI-006", "FROTI-007"]:
        assert wet_code not in recipe_codes


def test_case_d_multi_symptom_batuk_kering_dan_demam():
    """Case D: 'Saya batuk kering dan demam' -> multi-symptom, kenali keduanya."""
    res = client.post("/api/search", json={"query": "Saya batuk kering dan demam", "mode": "tfidf", "top_k": 3})
    assert res.status_code == 200
    data = res.json()
    symptoms = data["pemahaman_keluhan"]["symptoms"]
    assert "batuk kering" in symptoms
    assert "demam" in symptoms
    recipe_codes = [r["recipe_code"] for r in data["matched_recipes"]]
    for wet_code in ["FROTI-005", "FROTI-006", "FROTI-007"]:
        assert wet_code not in recipe_codes
    assert any(code in recipe_codes for code in ["FROTI-001", "RAMUAN-02"])


def test_case_e_temperature_low_urgent_33_degrees():
    """Case E: 'Saya batuk kering dan suhu 33 derajat' -> kenali suhu 33°C, peringatan suhu rendah, instruksi ramuan dihentikan."""
    res = client.post("/api/search", json={"query": "Saya batuk kering dan suhu 33 derajat", "mode": "tfidf", "top_k": 3})
    assert res.status_code == 200
    data = res.json()
    suhu = data["pemahaman_keluhan"]["suhu_tubuh"]
    assert suhu is not None
    assert suhu["nilai_celsius"] == 33.0
    assert suhu["kategori_kode"] == "rendah_mendesak"
    assert data["pemahaman_keluhan"]["instruksi_ramuan_dihentikan"] is True
    assert data["emergency_warning"] is not None
    assert "35" in data["emergency_warning"]
    for rec in data["matched_recipes"]:
        assert rec["instruksi_konsumsi_disembunyikan"] is True


def test_case_f_temperature_fever_38_3():
    """Case F: 'Saya batuk kering dan suhu 38,3' -> kenali suhu 38.3°C, demam, jangan anggap 33 sama dengan 38.3."""
    res = client.post("/api/search", json={"query": "Saya batuk kering dan suhu 38,3", "mode": "tfidf", "top_k": 3})
    assert res.status_code == 200
    data = res.json()
    suhu = data["pemahaman_keluhan"]["suhu_tubuh"]
    assert suhu is not None
    assert abs(suhu["nilai_celsius"] - 38.3) < 0.05
    assert suhu["kategori_kode"] == "demam"
    assert "demam" in data["keluhan_terdeteksi"]


def test_case_g_routine_medication_none_not_warned_as_drug():
    """Case G: Obat rutin: 'tidak ada' -> jangan peringatkan 'tidak ada' sebagai obat."""
    res = client.post(
        "/api/search",
        json={"query": "Saya batuk berdahak", "mode": "tfidf", "top_k": 3, "obat_rutin": "tidak ada"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["informasi_keselamatan"]["peringatan_obat_rutin"] is None
    assert data["pemahaman_keluhan"]["obat_rutin"] is None
    assert "tidak ada obat rutin" in (data["pemahaman_keluhan"]["status_obat_rutin"] or "").lower()

    # Also test inline query statement
    res2 = client.post(
        "/api/search",
        json={"query": "Saya batuk berdahak dan belum minum obat apa pun", "mode": "tfidf", "top_k": 3},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["informasi_keselamatan"]["peringatan_obat_rutin"] is None


def test_case_h_negated_symptom_tidak_pilek():
    """Case H: 'Saya batuk kering dan tidak pilek' -> pilek tidak dimasukkan sebagai keluhan yang dialami."""
    res = client.post(
        "/api/search",
        json={"query": "Saya batuk kering dan tidak pilek", "mode": "tfidf", "top_k": 3},
    )
    assert res.status_code == 200
    data = res.json()
    symptoms = data["pemahaman_keluhan"]["symptoms"]
    assert "batuk kering" in symptoms
    assert "pilek" not in symptoms
    negated_names = [n["nama"] for n in data["pemahaman_keluhan"]["keluhan_dinegasikan"]]
    assert "pilek" in negated_names




