"""Phase 10 — NIC classification service tests.

Covers:
  * Dataset integrity (JSON + vector index shape, prefix invariants).
  * Tier 1 (keyword) — substring match returns expected candidates.
  * Tier 2 (vector) — TF-IDF cosine similarity handles typo'd queries.
  * Tier dispatch — high keyword / high vector confidences short-circuit LLM.
  * Graceful degradation — missing vector index disables tier 2 silently.

Pure-Python tests — no DB session, no Ollama, no Playwright.

Run: pytest backend/tests/test_nic_classification.py -v
"""
from __future__ import annotations

import json
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import asyncio

import numpy as np
import pytest

from app.services.nic_service import (
    NICClassificationService,
    _KEYWORD_CONFIDENCE,
    _VECTOR_HIGH,
    _tokenise,
)


DATA_DIR = os.path.join(PROJECT_ROOT, "data")
JSON_PATH = os.path.join(DATA_DIR, "nic_2008.json")
VECTORS_PATH = os.path.join(DATA_DIR, "nic_2008_vectors.npz")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def dataset():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def vectors():
    with np.load(VECTORS_PATH, allow_pickle=False) as data:
        return {
            "codes": data["codes"],
            "vocab": data["vocab"],
            "vectors": data["vectors"],
        }


@pytest.fixture(scope="module")
def service():
    return NICClassificationService(ollama_url="http://localhost:1")  # no LLM


class _NoopSession:
    """AsyncSession stand-in that swallows adds — tier-skip tests don't need
    a real DB. generate_suggestions() only calls db.add() when it's about to
    persist candidates; for unit tests we don't care."""
    def add(self, _obj):
        pass


# ---------------------------------------------------------------------------
# Dataset integrity
# ---------------------------------------------------------------------------
def test_dataset_has_at_least_1000_codes(dataset):
    assert len(dataset) >= 1000, f"only {len(dataset)} codes"


def test_dataset_required_fields(dataset):
    required = {"nic_2digit", "nic_4digit", "nic_5digit", "description"}
    for entry in dataset:
        assert required.issubset(set(entry.keys()))


def test_dataset_code_widths(dataset):
    pattern_2 = re.compile(r"^\d{2}$")
    pattern_4 = re.compile(r"^\d{4}$")
    pattern_5 = re.compile(r"^\d{5}$")
    for entry in dataset:
        assert pattern_2.match(entry["nic_2digit"])
        assert pattern_4.match(entry["nic_4digit"])
        assert pattern_5.match(entry["nic_5digit"])


def test_dataset_no_duplicate_codes(dataset):
    seen = set()
    for entry in dataset:
        code = entry["nic_5digit"]
        assert code not in seen, f"duplicate {code}"
        seen.add(code)


def test_dataset_prefix_invariants(dataset):
    for entry in dataset:
        assert entry["nic_5digit"].startswith(entry["nic_4digit"]), entry
        assert entry["nic_4digit"].startswith(entry["nic_2digit"]), entry


def test_dataset_descriptions_non_empty(dataset):
    for entry in dataset:
        assert entry["description"].strip(), entry


# ---------------------------------------------------------------------------
# Vector index integrity
# ---------------------------------------------------------------------------
def test_vector_index_shape_matches_dataset(dataset, vectors):
    assert vectors["vectors"].shape[0] == len(dataset)
    assert vectors["vectors"].ndim == 2
    assert vectors["vectors"].dtype == np.float32
    assert vectors["vocab"].size > 0


def test_vector_index_codes_align_to_dataset(dataset, vectors):
    expected = [entry["nic_5digit"] for entry in dataset]
    actual = list(vectors["codes"])
    assert actual == expected


def test_vector_index_rows_l2_normalised(vectors):
    norms = np.linalg.norm(vectors["vectors"], axis=1)
    # Allow a tiny epsilon for floating-point drift.
    assert np.allclose(norms, 1.0, atol=1e-4), (
        f"row norms vary too widely: min={norms.min()} max={norms.max()}"
    )


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------
def test_tokenise_strips_stopwords_and_punctuation():
    tokens = _tokenise("Manufacture of biscuits, cakes and pastries.")
    assert "of" not in tokens
    assert "and" not in tokens
    assert "biscuits" in tokens
    assert "cakes" in tokens
    assert "pastries" in tokens


def test_tokenise_normalises_nec_abbreviation():
    tokens = _tokenise("Manufacture of articles n.e.c.")
    assert "nec" in tokens


# ---------------------------------------------------------------------------
# Tier 1 — keyword match
# ---------------------------------------------------------------------------
def test_keyword_tier_exact_substring_match(service):
    """An exact substring of a known description should land in tier 1 with
    full keyword confidence."""
    text = "Manufacture of biscuits, cakes, pastries and other bakery products"
    candidates = service._keyword_match(text)
    assert candidates, "expected at least one keyword candidate"
    codes = [c.nic_5digit for c in candidates]
    # 10712 is the canonical bakery subclass.
    assert "10712" in codes
    for cand in candidates:
        assert cand.confidence == _KEYWORD_CONFIDENCE


def test_keyword_tier_partial_match(service):
    """Substring containment in either direction should count as a match."""
    candidates = service._keyword_match("bakery")
    codes = [c.nic_5digit for c in candidates]
    assert "10712" in codes


def test_keyword_tier_no_match_for_unknown_query(service):
    candidates = service._keyword_match("xyzzy foobar plugh")
    assert candidates == []


def test_keyword_tier_returns_longer_descriptions_first(service):
    """Specific subclass descriptions should outrank parent-group descriptions."""
    # "Manufacture of wooden furniture" is exactly entry 31001.
    candidates = service._keyword_match("Manufacture of wooden furniture")
    assert candidates, "expected furniture-related candidates"
    lengths = [len(c.description) for c in candidates]
    assert lengths == sorted(lengths, reverse=True)


# ---------------------------------------------------------------------------
# Tier 2 — vector match
# ---------------------------------------------------------------------------
def test_vector_tier_returns_top_n_for_clear_query(service):
    """A canonical bakery query should rank 10712 at the top of the vector
    tier with a non-trivial cosine score. Use discriminating vocabulary
    ('biscuits cakes pastries') so 10712 wins over 46304 (wholesale of
    bakery products) which shares 'bakery products' tokens."""
    candidates = service._vector_match(
        "manufacture of biscuits cakes pastries"
    )
    assert candidates, "vector tier should produce at least one candidate"
    assert candidates[0].nic_5digit == "10712"
    assert candidates[0].confidence > 0.20


def test_vector_tier_handles_typo(service):
    """A typo'd query (no exact substring match) should still rank the right
    subclass in the top-K via cosine similarity. We use a multi-word query
    where the typo'd token ('bakrey') is filtered as OOV but the remaining
    correct tokens ('biscuits', 'cakes') still hit the bakery subclass."""
    keyword_hits = service._keyword_match("biscuits bakrey cakes")
    assert keyword_hits == [], "typo should defeat keyword tier"

    vector_candidates = service._vector_match("biscuits bakrey cakes")
    assert vector_candidates, "vector tier should handle partial-match queries"
    codes = [c.nic_5digit for c in vector_candidates[:10]]
    assert "10712" in codes, (
        f"expected 10712 in {codes}"
    )


def test_vector_tier_deterministic(service):
    a = service._vector_match("software publishing")
    b = service._vector_match("software publishing")
    assert [c.nic_5digit for c in a] == [c.nic_5digit for c in b]


def test_vector_tier_empty_query_returns_empty(service):
    assert service._vector_match("") == []
    assert service._vector_match("of the") == []


# ---------------------------------------------------------------------------
# Tier dispatch — generate_suggestions must short-circuit the LLM
# ---------------------------------------------------------------------------
def test_keyword_high_confidence_skips_llm(monkeypatch, service):
    """When tier 1 returns strong confidence, generate_suggestions must not
    call the LLM tier at all."""

    async def fake_llm(*args, **kwargs):
        raise AssertionError(
            "LLM should not be called when keyword tier has high confidence"
        )

    monkeypatch.setattr(service, "_run_llm_ranker", fake_llm)

    text = "Manufacture of biscuits, cakes, pastries and other bakery products"
    candidates = asyncio.run(
        service.generate_suggestions(
            app_id=None,
            business_description=text,
            location_text="India",
            db=_NoopSession(),
        )
    )
    assert candidates
    assert candidates[0].nic_5digit == "10712"


def test_vector_high_confidence_skips_llm(monkeypatch, service):
    """When tier 1 misses but tier 2 returns a strong match, the LLM tier is
    not called."""

    async def fake_llm(*args, **kwargs):
        raise AssertionError(
            "LLM should not be called when vector tier has high confidence"
        )

    monkeypatch.setattr(service, "_run_llm_ranker", fake_llm)

    # Find a query that triggers vector-high (≥ _VECTOR_HIGH) without
    # hitting any keyword match.
    target_query = None
    target_top = None
    for query in [
        "manufacture of bakery",
        "publishing of books",
        "manufacture of pharmaceutical preparations",
        "retail sale of books",
        "manufacture of dairy products",
        "manufacture of wearing apparel",
        "manufacture of footwear",
    ]:
        if service._keyword_match(query):
            continue
        vector_hits = service._vector_match(query)
        if vector_hits and vector_hits[0].confidence >= _VECTOR_HIGH:
            target_query = query
            target_top = vector_hits[0]
            break

    if target_query is None:
        pytest.skip(
            "could not construct a query that triggers vector-high without "
            "keyword match — dataset / index may have drifted"
        )

    candidates = asyncio.run(
        service.generate_suggestions(
            app_id=None,
            business_description=target_query,
            location_text="India",
            db=_NoopSession(),
        )
    )
    assert candidates
    assert candidates[0].nic_5digit == target_top.nic_5digit


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------
def test_service_survives_missing_vector_index(monkeypatch):
    """If the .npz file is missing, the service must still load and keyword
    tier must still work — vector tier silently disables."""
    monkeypatch.setattr(
        "app.services.nic_service.NIC_VECTORS_PATH",
        "/tmp/__nonexistent_path__.npz",
    )
    svc = NICClassificationService(ollama_url="http://localhost:1")
    assert svc._vectors is None
    assert svc._keyword_match("bakery")  # tier 1 still works
