"""3-tier NIC code classification service.

Matching pipeline (run in order — cheapest first):

  1. **Keyword match** — bidirectional substring match between the query
     and each subclass description. Confidence 0.85. Free, deterministic,
     but breaks on typos.

  2. **Vector match** — TF-IDF cosine similarity between the query and a
     precomputed matrix of subclass vectors
     (``data/nic_2008_vectors.npz``). Confidence proportional to the cosine
     score; we treat ``>= 0.55`` as a strong match. ~1 ms for the full
     1,164-row matrix on commodity hardware. Handles typos and partial
     descriptions.

  3. **LLM rerank** — Ollama qwen2.5 picks top-3 with rationale. Slow,
     expensive; only invoked when tiers 1-2 are weak.

Both Tier 1 and Tier 2 results are also threaded into the LLM prompt as
"context candidates" so the LLM can rerank our own best guesses rather
than relying on its (small-model) memory of the NIC handbook.
"""
from __future__ import annotations

import json
import math
import os
import re
import uuid
from collections import Counter
from typing import Dict, List, Optional

import httpx
import numpy as np
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import NICSuggestion


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
NIC_DATA_PATH = os.path.join(_BASE_DIR, "data", "nic_2008.json")
NIC_VECTORS_PATH = os.path.join(_BASE_DIR, "data", "nic_2008_vectors.npz")


# ---------------------------------------------------------------------------
# Tokenisation — mirrors ``scripts/build_nic_vectors.py`` so the query vector
# lives in the same coordinate space as the index.
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "in", "is", "it", "its", "of", "on", "or", "that",
    "the", "this", "to", "was", "were", "will", "with", "i", "ii", "iii",
    "iv", "v", "vi", "vii", "viii", "ix", "x", "n", "e", "c", "no",
})


def _normalise(text: str) -> str:
    # Surround the substitution with spaces so the resulting "nec" survives
    # tokenisation as its own token. The trailing \b in the simpler pattern
    # doesn't match when "n.e.c." sits at end-of-string (period → end is two
    # non-word chars, no boundary).
    return re.sub(r"n\.e\.c\.", " nec ", text.lower())


def _tokenise(text: str) -> List[str]:
    return [
        tok for tok in _TOKEN_RE.findall(_normalise(text))
        if len(tok) > 1 and tok not in _STOPWORDS
    ]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class NICCandidate(BaseModel):
    nic_2digit: str
    nic_4digit: str
    nic_5digit: str
    description: str
    confidence: float
    rationale: Optional[str] = None


# ---------------------------------------------------------------------------
# Confidence thresholds
# ---------------------------------------------------------------------------
_KEYWORD_CONFIDENCE = 0.85   # substring match → trust it
_VECTOR_HIGH = 0.55          # cosine ≥ 0.55 → trust top-1 alone
_VECTOR_LOW = 0.30           # cosine in [0.30, 0.55) → blend with LLM


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class NICClassificationService:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.model_name = "qwen2.5:3b"

        self._nic_data: List[Dict[str, str]] = self._load_json()
        # Build an index by 5-digit code so we can look up descriptions for
        # any candidate returned by tier 2 (vector) without rescanning the list.
        self._nic_index: Dict[str, Dict[str, str]] = {
            entry["nic_5digit"]: entry for entry in self._nic_data
        }

        # Vector index is optional; if the .npz is missing, tier 2 is a no-op
        # and the service degrades gracefully to keyword + LLM.
        self._vectors: Optional[np.ndarray] = None
        self._vocab_index: Optional[Dict[str, int]] = None
        self._codes_array: Optional[np.ndarray] = None
        self._load_vectors()

    # -----------------------------------------------------------------------
    # Loaders
    # -----------------------------------------------------------------------
    def _load_json(self) -> List[Dict[str, str]]:
        if not os.path.isfile(NIC_DATA_PATH):
            return []
        with open(NIC_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_vectors(self) -> None:
        if not os.path.isfile(NIC_VECTORS_PATH):
            return  # tier 2 disabled
        try:
            with np.load(NIC_VECTORS_PATH, allow_pickle=False) as data:
                self._vectors = data["vectors"]
                self._codes_array = data["codes"]
                vocab: np.ndarray = data["vocab"]
                self._vocab_index = {
                    str(tok): i for i, tok in enumerate(vocab.tolist())
                }
        except Exception:
            # Don't let a corrupt index kill the service; tier 2 silently
            # disables and the keyword + LLM tiers keep working.
            self._vectors = None
            self._vocab_index = None
            self._codes_array = None

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------
    async def generate_suggestions(
        self,
        app_id: uuid.UUID,
        business_description: str,
        location_text: str,
        db: AsyncSession,
    ) -> List[NICCandidate]:
        """Produce up to 3 NIC code candidates for the given business.

        Tier 1 (keyword) and Tier 2 (vector) both run; the strongest tier
        wins unless it falls below the LLM-fallback threshold.
        """
        if not self._nic_data:
            return []

        # Tier 1: keyword match.
        keyword_candidates = self._keyword_match(business_description)

        # Tier 2: vector match.
        vector_candidates = self._vector_match(business_description)

        # Decide whether to call the LLM.
        top_keyword = keyword_candidates[0].confidence if keyword_candidates else 0.0
        top_vector = vector_candidates[0].confidence if vector_candidates else 0.0

        if top_keyword >= _KEYWORD_CONFIDENCE:
            candidates = keyword_candidates[:3]
        elif top_vector >= _VECTOR_HIGH:
            candidates = vector_candidates[:3]
        elif top_vector >= _VECTOR_LOW or top_keyword >= 0.50:
            # Marginal match — let LLM rerank, but inject our top picks as
            # context so it doesn't have to rediscover them.
            candidates = await self._run_llm_ranker(
                business_description,
                location_text,
                context_candidates=self._merge_unique(
                    keyword_candidates, vector_candidates
                )[:5],
            )
            if not candidates:
                candidates = self._merge_unique(
                    keyword_candidates, vector_candidates
                )[:3]
        else:
            # No tier 1/2 confidence at all — full LLM rerank with empty context.
            candidates = await self._run_llm_ranker(
                business_description, location_text, context_candidates=[]
            )
            if not candidates:
                candidates = self._merge_unique(
                    keyword_candidates, vector_candidates
                )[:3]

        if not candidates:
            return []

        # Persist to DB.
        for cand in candidates:
            suggestion = NICSuggestion(
                application_id=app_id,
                nic_code_2digit=cand.nic_2digit,
                nic_code_4digit=cand.nic_4digit,
                nic_code_5digit=cand.nic_5digit,
                description=cand.description,
                confidence=cand.confidence,
                rationale=cand.rationale,
            )
            db.add(suggestion)

        return candidates

    # -----------------------------------------------------------------------
    # Tier 1 — keyword
    # -----------------------------------------------------------------------
    def _keyword_match(self, text: str) -> List[NICCandidate]:
        text_lower = text.lower()
        results: List[NICCandidate] = []
        for item in self._nic_data:
            desc = item["description"].lower()
            if desc in text_lower or text_lower in desc:
                results.append(NICCandidate(
                    nic_2digit=item["nic_2digit"],
                    nic_4digit=item["nic_4digit"],
                    nic_5digit=item["nic_5digit"],
                    description=item["description"],
                    confidence=_KEYWORD_CONFIDENCE,
                    rationale="Matched via keyword (substring).",
                ))
        # Sort: longer descriptions (more specific) win.
        results.sort(key=lambda c: len(c.description), reverse=True)
        return results

    # -----------------------------------------------------------------------
    # Tier 2 — vector cosine similarity
    # -----------------------------------------------------------------------
    def _vector_match(self, text: str) -> List[NICCandidate]:
        if self._vectors is None or self._vocab_index is None:
            return []

        tokens = _tokenise(text)
        if not tokens:
            return []

        vocab_size = len(self._vocab_index)
        # Build the query TF vector in the same coordinate space as the index.
        tf = Counter(tokens)
        query = np.zeros(vocab_size, dtype=np.float32)
        for tok, count in tf.items():
            idx = self._vocab_index.get(tok)
            if idx is not None:
                query[idx] = 1.0 + math.log(count) if count > 0 else 0.0
        # We re-derive IDF implicitly by scoring against the L2-normalised
        # index matrix: cosine(query, stored) == dot(query, stored) / ||query||.
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return []
        query = query / query_norm

        scores = self._vectors @ query  # shape (N,)

        # Top-10 indices, sorted descending.
        top_idx = np.argsort(-scores)[:10]
        results: List[NICCandidate] = []
        for idx in top_idx:
            score = float(scores[idx])
            if score <= 0.0:
                continue
            code = str(self._codes_array[idx])
            entry = self._nic_index.get(code)
            if entry is None:
                continue
            confidence = min(1.0, max(0.0, score))
            results.append(NICCandidate(
                nic_2digit=entry["nic_2digit"],
                nic_4digit=entry["nic_4digit"],
                nic_5digit=entry["nic_5digit"],
                description=entry["description"],
                confidence=round(confidence, 4),
                rationale=f"Vector cosine={score:.3f}",
            ))
        return results

    # -----------------------------------------------------------------------
    # Tier 3 — LLM rerank (Ollama)
    # -----------------------------------------------------------------------
    async def _run_llm_ranker(
        self,
        business_description: str,
        location_text: str,
        context_candidates: List[NICCandidate],
    ) -> List[NICCandidate]:
        location = location_text or "India"

        system_prompt = (
            "You are an expert Indian business classifier specializing in the "
            "National Industrial Classification (NIC 2008) handbook. Analyze "
            "the provided business description and select the top 3 most "
            "accurate 5-digit NIC codes. Prefer the codes already suggested "
            "in CONTEXT_CANDIDATES when they fit; only invent new codes if "
            "none of the suggestions match."
        )

        context_lines = []
        for cand in context_candidates:
            context_lines.append(
                f"- {cand.nic_5digit} | {cand.description} "
                f"(score={cand.confidence:.2f})"
            )
        context_block = "\n".join(context_lines) if context_lines else "(none)"

        user_prompt = f"""Business Description: '{business_description}'
Location: '{location}'

CONTEXT_CANDIDATES (from prior matching tiers):
{context_block}

Return JSON output strictly obeying the following schema:
{{
  "suggestions": [
    {{
      "nic_2digit": "10",
      "nic_4digit": "1071",
      "nic_5digit": "10712",
      "description": "Manufacture of biscuits, cakes, pastries and other bakery products",
      "confidence": 0.94,
      "rationale": "Primary business activity involves commercial production of bakery items."
    }}
  ]
}}"""

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.1},
            "format": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/chat", json=payload
                )
                response.raise_for_status()
                data = response.json()
                content = data.get("message", {}).get("content", "")
                parsed = json.loads(content)
                suggestions = parsed.get("suggestions", [])

                candidates = []
                for s in suggestions:
                    candidates.append(NICCandidate(
                        nic_2digit=str(s.get("nic_2digit", "")),
                        nic_4digit=str(s.get("nic_4digit", "")),
                        nic_5digit=str(s.get("nic_5digit", "")),
                        description=str(s.get("description", "")),
                        confidence=float(s.get("confidence", 0.5)),
                        rationale=str(s.get("rationale", "")),
                    ))
                return candidates
        except Exception as exc:
            print(f"Error in LLM NIC classification: {exc}")
            return []

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    @staticmethod
    def _merge_unique(*lists: List[NICCandidate]) -> List[NICCandidate]:
        """Deduplicate by 5-digit code, keeping the first occurrence."""
        seen: set[str] = set()
        out: List[NICCandidate] = []
        for lst in lists:
            for cand in lst:
                if cand.nic_5digit in seen:
                    continue
                seen.add(cand.nic_5digit)
                out.append(cand)
        return out
