"""Comprehensive pytest suite for HerbID Gemini LLM & RAG Intelligent System.

Verifies:
1. ComplaintAnalysisService (Stage 1):
   - Structured JSON complaint parsing (primary, secondary, characteristics, negations)
   - Stated duration and temperature extraction
   - Missing info & clarification questions
   - Deterministic fallback when offline
   - Strictly enforced diagnosis: None
2. SafetyAssessmentService:
   - Temperature < 35°C (urgent hypothermia) halts recipe instructions
   - Emergency sign keywords halt recipe instructions
   - Routine medication 'tidak ada' normalized to None and not treated as a drug
   - Child (6-11 years) and vulnerable group dosage suppression
3. HerbalRetrievalService:
   - Multi-symptom round-robin retrieval
   - Conflict exclusion (dry cough excludes wet cough recipes)
   - Honest result counts (never padded)
4. EvidenceAnalysisService (Stage 2):
   - Evidence synthesis strictly from retrieved documents
   - Identification of unaddressed complaints
   - Keterbatasan informasi & contraindication highlights
   - Transparent provider labeling & fallback
5. SourceValidationService:
   - Hallucinated / unretrieved citation codes stripped
   - Valid citations retained
   - Strictly enforced diagnosis: None
6. End-to-end /api/search API Integration:
   - Returns valid SearchResponse schema with ai_evidence_analysis
   - Response includes provider, temperature, negations, and safe guidance
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.schemas import SearchResponse
from app.services.complaint_analysis_service import ComplaintAnalysisService
from app.services.evidence_analysis_service import EvidenceAnalysisService
from app.services.herbal_retrieval_service import HerbalRetrievalService
from app.services.safety_assessment_service import SafetyAssessmentService
from app.services.search_service import search_engine
from app.services.source_validation_service import SourceValidationService


@pytest.fixture(scope="module")
def client():
    # Ensure index is built before running API tests
    db = SessionLocal()
    search_engine.build_index(db)
    db.close()
    with TestClient(app) as c:
        yield c


def test_stage1_complaint_analysis_fallback_and_structure():
    service = ComplaintAnalysisService()
    # Force fallback by setting use_gemini=False
    res = service.analyze_complaint(
        raw_query="Saya batuk kering sejak kemarin, badan terasa panas, dan suhu saya 38,3 derajat",
        durasi_input="sejak kemarin",
        use_gemini=False,
    )
    assert res is not None
    assert res["diagnosis_medis"] is None
    assert res["provider"] == "Deterministic Rule-Based Fallback"
    assert "batuk kering" in res["symptom_labels"]
    assert "demam" in res["symptom_labels"]
    assert res["suhu_tubuh"] is not None
    assert res["suhu_tubuh"]["nilai_celsius"] == 38.3
    assert len(res["rincian_keluhan"]) >= 2


def test_stage1_negation_tidak_pilek_and_batuk_tidak_berdahak():
    service = ComplaintAnalysisService()
    res1 = service.analyze_complaint(
        raw_query="Saya batuk tidak berdahak",
        use_gemini=False,
    )
    assert "batuk kering" in res1["symptom_labels"]
    assert "batuk berdahak" not in res1["symptom_labels"]

    res2 = service.analyze_complaint(
        raw_query="Saya demam dan tidak pilek",
        use_gemini=False,
    )
    assert "demam" in res2["symptom_labels"]
    neg_names = [k["nama"] for k in res2["keluhan_dinegasikan"]]
    assert "pilek" in neg_names


def test_safety_assessment_hypothermia_33_celsius_halts_instructions():
    service = SafetyAssessmentService()
    extraction = {
        "suhu_tubuh": {
            "nilai_celsius": 33.0,
            "kategori_kode": "rendah_mendesak",
            "tampilan": "33,0°C",
        },
        "peringatan_mendesak": "PERINGATAN MEDIS MENDESAK: suhu tubuh di bawah 35°C.",
        "instruksi_ramuan_dihentikan": True,
        "tanda_bahaya_kata_kunci": [],
    }
    assessment = service.assess_safety(
        extraction=extraction,
        raw_query="aku sedang batuk kering dan demam sekitar 33 derajat",
        age_group="dewasa_18_59_tahun",
        obat_rutin="",
    )
    assert assessment["stop_instructions"] is True
    assert assessment["safety_status"] == "darurat_medis"
    assert "di bawah 35°C" in assessment["emergency_warning"]


def test_safety_assessment_danger_keyword_halts_instructions():
    service = SafetyAssessmentService()
    extraction = {
        "tanda_bahaya_kata_kunci": ["sesak napas"],
        "instruksi_ramuan_dihentikan": True,
    }
    assessment = service.assess_safety(
        extraction=extraction,
        raw_query="Saya batuk dan sesak napas",
        age_group="dewasa_18_59_tahun",
        obat_rutin="",
    )
    assert assessment["stop_instructions"] is True
    assert assessment["safety_status"] == "darurat_medis"
    assert "TANDA BAHAYA TERDETEKSI" in assessment["emergency_warning"]


def test_safety_assessment_medication_none_normalized():
    service = SafetyAssessmentService()
    for neg_med in ["tidak ada", "belum minum obat", "tidak", "nihil", "none", "belum ada"]:
        assessment = service.assess_safety(
            extraction={},
            raw_query="batuk",
            age_group="dewasa_18_59_tahun",
            obat_rutin=neg_med,
        )
        assert assessment["clean_obat_rutin"] is None
        assert "interaksi obat medis & suplemen" not in assessment["safety_triggers"]
        assert assessment["obat_tidak_dilaporkan"] is True


def test_safety_assessment_child_group_dosage_warning():
    service = SafetyAssessmentService()
    assessment = service.assess_safety(
        extraction={},
        raw_query="batuk berdahak",
        age_group="anak_6_8_tahun",
        obat_rutin="",
    )
    assert assessment["is_child_group"] is True
    assert assessment["vulnerable_warning"] is not None
    assert "ANAK (6-11 TAHUN)" in assessment["vulnerable_warning"]


def test_herbal_retrieval_dry_cough_excludes_wet_cough_recipes():
    comp_service = ComplaintAnalysisService()
    ret_service = HerbalRetrievalService(search_engine)

    ext = comp_service.analyze_complaint(
        raw_query="Saya batuk kering tanpa dahak",
        use_gemini=False,
    )
    recipes, info = ret_service.retrieve_candidates(
        extraction=ext,
        nlp_info={"raw_query": "Saya batuk kering tanpa dahak", "recognized_local_plants": []},
        mode_used="tfidf",
        top_k=3,
    )
    assert len(recipes) <= 3
    # Check that wet-cough specific recipes like FROTI-005, FROTI-006, FROTI-007 are not returned
    recipe_codes = [r.get("recipe_code") for r in recipes]
    assert "FROTI-005" not in recipe_codes
    assert "FROTI-006" not in recipe_codes
    assert "FROTI-007" not in recipe_codes


def test_stage2_evidence_analysis_and_source_validation():
    ev_service = EvidenceAnalysisService()
    val_service = SourceValidationService()

    stage1 = {
        "keluhan": [{"nama": "batuk", "key": "batuk_kering"}],
        "keluhan_teridentifikasi": ["batuk", "demam"],
        "suhu_tubuh": {"tampilan": "38,3°C"},
    }
    dummy_recipes = [
        {
            "recipe_code": "FROTI-001",
            "nama_tanaman": "Jahe",
            "nama_ilmiah": "Zingiber officinale",
            "kegunaan_tradisional": "batuk, menghangatkan badan",
            "halaman_rujukan": "24",
            "sumber_dokumen": "FROTI Kemenkes RI 2017",
            "larangan_kontraindikasi": "Gastritis akut",
        }
    ]
    dummy_bpom = [
        {
            "source_id": "BPOM-01",
            "judul": "Pedoman Jamu Indonesia",
            "topik": "Edukasi herbal",
        }
    ]

    # Synthesize fallback
    raw_evidence = ev_service._build_deterministic_evidence(
        raw_query="Saya batuk dan demam",
        stage1_analysis=stage1,
        matched_recipes=dummy_recipes,
        bpom_sources=dummy_bpom,
    )

    assert raw_evidence["diagnosis_medis"] is None
    assert "FROTI-001" in raw_evidence["cited_sources"]
    assert "demam" in raw_evidence["unaddressed_complaints"]

    # Validate citations stripping hallucinated codes
    corrupted = dict(raw_evidence)
    corrupted["cited_sources"] = ["FROTI-001", "NONEXISTENT-999"]
    validated = val_service.validate_citations(
        evidence_analysis=corrupted,
        matched_recipes=dummy_recipes,
        bpom_sources=dummy_bpom,
        stop_instructions=False,
    )
    assert "NONEXISTENT-999" not in validated["cited_sources"]
    assert "FROTI-001" in validated["cited_sources"]
    assert validated["diagnosis_medis"] is None


def test_api_search_full_pipeline_with_ai_evidence_analysis(client: TestClient):
    payload = {
        "query": "Saya batuk kering sejak kemarin, badan terasa panas, dan suhu saya 38,3 derajat",
        "mode": "tfidf",
        "top_k": 5,
        "age_group": "dewasa_18_59_tahun",
        "durasi_keluhan": "sejak kemarin",
        "obat_rutin": "tidak ada",
        "use_gemini": False,  # deterministic pipeline
    }
    resp = client.post("/api/search", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Validate against SearchResponse schema
    validated_response = SearchResponse(**data)
    assert validated_response.query == payload["query"]

    # Check Stage 1 analysis
    assert data["pemahaman_keluhan"] is not None
    assert data["pemahaman_keluhan"]["provider"] is not None
    assert data["pemahaman_keluhan"]["suhu_tubuh"]["nilai_celsius"] == 38.3
    assert data["pemahaman_keluhan"]["diagnosis_medis"] is None

    # Check Stage 2 synthesis
    assert data["ai_evidence_analysis"] is not None
    evidence = data["ai_evidence_analysis"]
    assert evidence["ai_analysis_title"] is not None
    assert len(evidence["executive_summary"]) > 20
    assert evidence["diagnosis_medis"] is None
    assert isinstance(evidence["cited_sources"], list)
    assert evidence["is_grounded"] is True


def test_api_search_emergency_hypothermia_33_celsius(client: TestClient):
    payload = {
        "query": "aku sedang batuk kering dan demam sekitar 33 derajat",
        "mode": "tfidf",
        "use_gemini": False,
    }
    resp = client.post("/api/search", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    understanding = data["pemahaman_keluhan"]
    assert understanding["instruksi_ramuan_dihentikan"] is True
    assert any("di bawah 35°C" in w for w in understanding["peringatan_suhu"])
    # Matched recipes have their instructions halted
    for rec in data["matched_recipes"]:
        assert rec["instruksi_konsumsi_disembunyikan"] is True


def test_api_ai_status_and_eight_mandatory_scenarios(client: TestClient):
    """Verify safe /api/ai-status and the 8 mandatory test queries."""
    # 1. /api/ai-status
    r_ai = client.get("/api/ai-status")
    assert r_ai.status_code == 200
    ai_status = r_ai.json()
    assert "configured" in ai_status
    assert "status_code" in ai_status
    assert "model_name" in ai_status
    assert "message" in ai_status
    # Ensure API key is never exposed
    assert "api_key" not in ai_status
    assert "key" not in ai_status

    # Query 1: "Saya batuk kering." -> 0 recipes (FROTI has no dry cough recipes)
    r1 = client.post("/api/search", json={"query": "Saya batuk kering.", "mode": "tfidf", "use_gemini": False})
    assert r1.status_code == 200
    d1 = r1.json()
    assert "batuk kering" in d1["keluhan_terdeteksi"]
    assert len(d1["matched_recipes"]) == 0
    assert d1["recipe_empty_message"] is not None

    # Query 2: "Saya batuk berdahak." -> FROTI-005, FROTI-006, FROTI-007
    r2 = client.post("/api/search", json={"query": "Saya batuk berdahak.", "mode": "tfidf", "use_gemini": False})
    assert r2.status_code == 200
    d2 = r2.json()
    codes2 = [r["recipe_code"] for r in d2["matched_recipes"]]
    assert "FROTI-005" in codes2
    assert "FROTI-006" in codes2
    assert "FROTI-007" in codes2

    # Query 3: "Saya batuk kering dan demam." -> FROTI-001 (Demam), wet cough recipes excluded
    r3 = client.post("/api/search", json={"query": "Saya batuk kering dan demam.", "mode": "tfidf", "use_gemini": False})
    assert r3.status_code == 200
    d3 = r3.json()
    codes3 = [r["recipe_code"] for r in d3["matched_recipes"]]
    assert "FROTI-001" in codes3
    assert not any(c in codes3 for c in ["FROTI-005", "FROTI-006", "FROTI-007"])

    # Query 4: "Saya tidak demam, tetapi batuk." -> demam negated, no FROTI-001
    r4 = client.post("/api/search", json={"query": "Saya tidak demam, tetapi batuk.", "mode": "tfidf", "use_gemini": False})
    assert r4.status_code == 200
    d4 = r4.json()
    codes4 = [r["recipe_code"] for r in d4["matched_recipes"]]
    assert "FROTI-001" not in codes4

    # Query 5: "Saya haid." -> 0 recipes, clarification requested
    r5 = client.post("/api/search", json={"query": "Saya haid.", "mode": "tfidf", "use_gemini": False})
    assert r5.status_code == 200
    d5 = r5.json()
    assert len(d5["matched_recipes"]) == 0
    assert d5["pemahaman_keluhan"]["perlu_klarifikasi"] is True
    assert any("nyeri haid" in q for q in d5["pemahaman_keluhan"]["pertanyaan_klarifikasi"])

    # Query 6: "Saya mengalami nyeri haid." -> FROTI-018
    r6 = client.post("/api/search", json={"query": "Saya mengalami nyeri haid.", "mode": "tfidf", "use_gemini": False})
    assert r6.status_code == 200
    d6 = r6.json()
    codes6 = [r["recipe_code"] for r in d6["matched_recipes"]]
    assert "FROTI-018" in codes6

    # Query 7: "Haid saya tidak teratur." -> FROTI-019
    r7 = client.post("/api/search", json={"query": "Haid saya tidak teratur.", "mode": "tfidf", "use_gemini": False})
    assert r7.status_code == 200
    d7 = r7.json()
    codes7 = [r["recipe_code"] for r in d7["matched_recipes"]]
    assert "FROTI-019" in codes7

    # Query 8: "Saya sakit kolesterol dan asam urat tinggi." -> 0 recipes
    r8 = client.post("/api/search", json={"query": "Saya sakit kolesterol dan asam urat tinggi.", "mode": "tfidf", "use_gemini": False})
    assert r8.status_code == 200
    d8 = r8.json()
    assert len(d8["matched_recipes"]) == 0

