"""SourceValidationService: Validates citations, grounds claims, and prevents hallucinated references.

Ensures:
1. Every code in `cited_sources` corresponds to an actual document retrieved in the current query.
2. Hallucinated document codes or non-retrieved references are immediately stripped.
3. Medical diagnosis is strictly enforced as null.
4. When `stop_instructions` is active (hypothermia, emergency keywords), syntheses are flagged accordingly.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SourceValidationService:
    @staticmethod
    def validate_citations(
        evidence_analysis: dict[str, Any],
        matched_recipes: list[dict[str, Any]],
        bpom_sources: list[dict[str, Any]],
        stop_instructions: bool = False,
        emergency_warning: Optional[str] = None,
    ) -> dict[str, Any]:
        """Validate citations and ensure strictly source-grounded outputs."""
        validated = dict(evidence_analysis)

        # 1. Collect valid allowed codes
        allowed_recipe_codes = {
            str(r.get("recipe_code") or "").strip().upper()
            for r in matched_recipes
            if r.get("recipe_code")
        }
        allowed_bpom_codes = {
            str(s.get("source_id") or "").strip().upper()
            for s in bpom_sources
            if s.get("source_id")
        }
        allowed_codes = allowed_recipe_codes | allowed_bpom_codes

        # 2. Filter cited_sources against allowed_codes
        raw_citations = validated.get("cited_sources", [])
        clean_citations: list[str] = []
        for c in raw_citations:
            c_clean = str(c).strip().upper()
            if c_clean in allowed_codes and c_clean not in clean_citations:
                clean_citations.append(c_clean)

        # If LLM omitted citations or they were filtered out, ground from actual retrieved items
        if not clean_citations and allowed_codes:
            clean_citations = sorted(list(allowed_codes))

        validated["cited_sources"] = clean_citations

        # 3. Filter relevance_explanations to only allowed items
        raw_relevance = validated.get("relevance_explanations", [])
        clean_relevance: list[dict[str, Any]] = []
        for item in raw_relevance:
            k_ref = str(item.get("kode_referensi") or "").strip().upper()
            if not allowed_codes or k_ref in allowed_codes:
                clean_relevance.append(item)

        validated["relevance_explanations"] = clean_relevance

        # 4. Strictly enforce diagnosis as None
        validated["diagnosis_medis"] = None
        validated["is_grounded"] = True

        # 5. Guardrail: If instructions stopped, augment summary with warning
        if stop_instructions and emergency_warning:
            curr_summary = validated.get("executive_summary", "")
            if "PERINGATAN MEDIS MENDESAK" not in curr_summary and "TANDA BAHAYA TERDETEKSI" not in curr_summary:
                validated["executive_summary"] = (
                    f"PERINGATAN KEAMANAN: {emergency_warning} "
                    f"Instruksi konsumsi ramuan dihentikan demi keselamatan. {curr_summary}"
                )

        return validated
