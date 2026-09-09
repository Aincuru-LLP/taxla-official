"""Build the offline NIC vector index used by the 3-tier matcher.

Why this script exists
-----------------------
``NICClassificationService`` runs three tiers in order:

  1. **Keyword** — substring match on the query against each subclass
     description. Cheap, deterministic, but breaks on typos and missing
     vocabulary.
  2. **Vector** — cosine similarity between a TF-IDF vector of the query and
     a precomputed matrix of subclass vectors. Cheap to evaluate (~1 ms for
     1,164 codes), handles fuzzy matches, no model download required.
  3. **LLM rerank** — Ollama qwen2.5 reranks the top-N candidates. Slow,
     expensive; only invoked when tier 1/2 are below confidence.

This script owns the offline vector build. Run it once after
``generate_nic_data.py``::

    python scripts/build_nic_vectors.py

Outputs ``data/nic_2008_vectors.npz`` containing:

  * ``codes``    — ``(N,)`` str array of 5-digit subclass codes.
  * ``vocab``    — ``(V,)`` str array of unique tokens.
  * ``vectors``  — ``(N, V)`` float32 dense matrix (L2-normalised so dot
                   product == cosine similarity). For the current 1,164
                   codes the matrix is ~3.5 MB uncompressed, ~1 MB zipped.

Why not sentence-transformers?
  * No GPU dependency.
  * No model download (~120 MB).
  * No extra ``requirements.txt`` entries.
  * TF-IDF on industry titles captures the vocabulary operators actually
    use to describe businesses; embeddings add little for short technical
    titles.

The file is regenerated whenever ``data/nic_2008.json`` changes.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from typing import Dict, List, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------
# Lowercase, split on non-alpha, drop English stopwords and very short tokens.
# The descriptions are short industry titles (~5-10 words), so aggressive
# tokenisation loses more than it gains.
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
# TF-IDF
# ---------------------------------------------------------------------------
def _build_vocab(documents: List[List[str]]) -> Tuple[List[str], Dict[str, int]]:
    """Build a sorted vocabulary mapping token → column index."""
    counter: Counter[str] = Counter()
    for doc in documents:
        counter.update(set(doc))  # set() so df counts documents, not tokens
    vocab = sorted(counter)
    return vocab, {tok: i for i, tok in enumerate(vocab)}


def _build_vectors(
    documents: List[List[str]],
    vocab_index: Dict[str, int],
) -> np.ndarray:
    """Build a TF-IDF matrix (rows = documents, cols = vocab terms)."""
    vocab_size = len(vocab_index)
    doc_count = len(documents)

    # Document frequencies.
    df = np.zeros(vocab_size, dtype=np.float32)
    for doc in documents:
        for tok in set(doc):
            idx = vocab_index.get(tok)
            if idx is not None:
                df[idx] += 1.0

    # Smoothed IDF: log((N+1)/(df+1)) + 1.
    idf = np.log((doc_count + 1.0) / (df + 1.0)) + 1.0

    # TF = sub-linear term frequency (1 + log(tf)).
    rows = []
    for doc in documents:
        row = np.zeros(vocab_size, dtype=np.float32)
        if not doc:
            rows.append(row)
            continue
        tf = Counter(doc)
        for tok, count in tf.items():
            idx = vocab_index.get(tok)
            if idx is not None:
                row[idx] = 1.0 + math.log(count) if count > 0 else 0.0
        rows.append(row * idf)
    matrix = np.stack(rows, axis=0)

    # L2-normalise rows so dot product == cosine similarity.
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return (matrix / norms).astype(np.float32)


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------
def _load_dataset() -> List[Dict[str, str]]:
    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
    )
    src = os.path.join(data_dir, "nic_2008.json")
    if not os.path.isfile(src):
        raise SystemExit(
            f"Dataset not found at {src}. Run scripts/generate_nic_data.py first."
        )
    with open(src, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    entries = _load_dataset()
    print(f"Loaded {len(entries)} NIC entries")

    descriptions = [e["description"] for e in entries]
    documents = [_tokenise(d) for d in descriptions]

    vocab, vocab_index = _build_vocab(documents)
    print(f"Vocab size: {len(vocab)}")

    vectors = _build_vectors(documents, vocab_index)
    print(f"Vector matrix shape: {vectors.shape}")

    data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
    )
    out_path = os.path.join(data_dir, "nic_2008_vectors.npz")
    np.savez_compressed(
        out_path,
        codes=np.array([e["nic_5digit"] for e in entries], dtype="<U5"),
        vocab=np.array(vocab, dtype="<U32"),
        vectors=vectors,
    )
    print(f"Wrote {out_path} ({os.path.getsize(out_path) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()