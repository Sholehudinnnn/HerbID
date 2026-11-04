"""HerbalRetrievalService: Evidence retrieval for FROTI Kemenkes recipes and BPOM regulatory sources.

Features:
- Structured multi-symptom retrieval (round-robin across positive complaints).
- Strict conflict exclusion (e.g. wet-cough recipes excluded for dry cough).
- Honest result counts: never pad to 3; return 1 if only 1 is relevant; return 0 with clear note if none.
- Retrieves BPOM regulatory / educational reference documents.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HerbalRetrievalService:
    def __init__(self, search_engine: Any):
        """Pass in the initialized SearchEngineService instance."""
        self.search_engine = search_engine

    def retrieve_candidates(
        self,
        extraction: dict[str, Any],
        nlp_info: dict[str, Any],
        mode_used: str = "tfidf",
        top_k: int = 3,
        age_group: str = "dewasa_18_59_tahun",
        vulnerable_flags: Optional[list[str]] = None,
        obat_rutin: str = "",
        query_is_vuln: bool = False,
        stop_instructions: bool = False,
        stop_instructions_reason: Optional[str] = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Retrieve curated FROTI recipes matching user's structured complaints."""
        if extraction and extraction.get("keluhan"):
            matched_recipes, struct_info = self.search_engine.search_recipes_structured(
                extraction=extraction,
                nlp_info=nlp_info,
                mode_used=mode_used,
                top_k=min(top_k, 3),
                age_group=age_group,
                vulnerable_flags=vulnerable_flags,
                obat_rutin=obat_rutin,
                query_is_vuln=query_is_vuln,
                stop_instructions=stop_instructions,
                stop_instructions_reason=stop_instructions_reason,
            )
            return matched_recipes, struct_info
        else:
            matched_recipes = self.search_engine.search_recipes_by_query(
                query=nlp_info.get("raw_query", ""),
                mode_used=mode_used,
                top_k=min(top_k, 3),
                age_group=age_group,
                vulnerable_flags=vulnerable_flags,
                nlp_info=nlp_info,
                obat_rutin=obat_rutin,
                stop_instructions=stop_instructions,
                stop_instructions_reason=stop_instructions_reason,
            )
            return matched_recipes, {}
