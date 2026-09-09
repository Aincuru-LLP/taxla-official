"""Validate ``data/nic_2008.json`` and ``data/nic_2008_vectors.npz``.

Runs a battery of checks against the canonical NIC dataset and the offline
vector index. Exits non-zero on the first hard failure so it can be wired
into CI::

    python scripts/validate_nic_dataset.py

Checks
------
  * Each entry has exactly four string fields with the right keys.
  * ``nic_2digit`` is 2 digits; ``nic_4digit`` is 4; ``nic_5digit`` is 5.
  * The 4-digit group starts with the 2-digit division.
  * The 5-digit subclass starts with the 4-digit group.
  * No duplicate 5-digit codes.
  * No empty or whitespace-only descriptions.
  * Vector index exists, has the expected shape, and aligns to the JSON
    (row order matches the JSON entry order, all 5-digit codes present,
    every row has non-zero L2 norm).

All errors are aggregated before exit so a single run reports every defect
instead of stopping at the first one — useful when a copy/paste typo breaks
a whole section.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Dict, List, Tuple

import numpy as np


DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
JSON_PATH = os.path.join(DATA_DIR, "nic_2008.json")
VECTORS_PATH = os.path.join(DATA_DIR, "nic_2008_vectors.npz")

CODE_RE = {
    "nic_2digit": re.compile(r"^\d{2}$"),
    "nic_4digit": re.compile(r"^\d{4}$"),
    "nic_5digit": re.compile(r"^\d{5}$"),
}

REQUIRED_FIELDS = {"nic_2digit", "nic_4digit", "nic_5digit", "description"}

# Hard requirement on dataset size — NIC-2008 has ~1,310 5-digit codes
# handbook-wide; we accept anything ≥ 1,000 (we may not have every code
# in this script's static list).
MIN_EXPECTED_CODES = 1000


def _validate_json() -> Tuple[List[Dict[str, str]], List[str]]:
    errors: List[str] = []
    if not os.path.isfile(JSON_PATH):
        errors.append(f"missing file: {JSON_PATH}")
        return [], errors

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        try:
            entries = json.load(f)
        except json.JSONDecodeError as exc:
            errors.append(f"JSON decode error: {exc}")
            return [], errors

    if not isinstance(entries, list):
        errors.append(f"expected a JSON array at top level, got {type(entries).__name__}")
        return [], errors

    if len(entries) < MIN_EXPECTED_CODES:
        errors.append(
            f"only {len(entries)} entries — expected ≥ {MIN_EXPECTED_CODES}"
        )

    seen: set[str] = set()
    for i, entry in enumerate(entries):
        prefix = f"[entry {i}]"

        # Schema: required fields, all strings.
        missing = REQUIRED_FIELDS - set(entry.keys())
        if missing:
            errors.append(f"{prefix} missing fields: {sorted(missing)}")
            continue
        extras = set(entry.keys()) - REQUIRED_FIELDS
        if extras:
            errors.append(f"{prefix} unexpected fields: {sorted(extras)}")
            continue

        # Width checks.
        for field, pattern in CODE_RE.items():
            value = entry[field]
            if not isinstance(value, str):
                errors.append(f"{prefix} {field}={value!r} is not a string")
                continue
            if not pattern.match(value):
                errors.append(f"{prefix} {field}={value!r} does not match {pattern.pattern}")

        # Prefix relationships.
        if entry["nic_5digit"] in seen:
            errors.append(
                f"{prefix} duplicate 5-digit code {entry['nic_5digit']}"
            )
        seen.add(entry["nic_5digit"])

        if not entry["nic_5digit"].startswith(entry["nic_4digit"]):
            errors.append(
                f"{prefix} subclass {entry['nic_5digit']} does not start "
                f"with group {entry['nic_4digit']}"
            )
        if not entry["nic_4digit"].startswith(entry["nic_2digit"]):
            errors.append(
                f"{prefix} group {entry['nic_4digit']} does not start "
                f"with division {entry['nic_2digit']}"
            )

        # Description non-empty.
        desc = entry["description"]
        if not isinstance(desc, str) or not desc.strip():
            errors.append(f"{prefix} description is empty")

    return entries, errors


def _validate_vectors(entries: List[Dict[str, str]]) -> List[str]:
    errors: List[str] = []
    if not os.path.isfile(VECTORS_PATH):
        errors.append(
            f"missing vector index: {VECTORS_PATH} "
            "(run scripts/build_nic_vectors.py)"
        )
        return errors

    try:
        with np.load(VECTORS_PATH, allow_pickle=False) as data:
            codes = data["codes"]
            vocab = data["vocab"]
            vectors = data["vectors"]
    except Exception as exc:
        errors.append(f"failed to load vector index: {exc}")
        return errors

    expected_codes = [entry["nic_5digit"] for entry in entries]
    if codes.tolist() != expected_codes:
        errors.append(
            "vector index 'codes' does not match JSON entry order"
        )
    if len(codes) != len(entries):
        errors.append(
            f"vector index has {len(codes)} rows, JSON has {len(entries)}"
        )

    if vectors.ndim != 2:
        errors.append(
            f"vectors must be 2-D, got {vectors.ndim}-D shape {vectors.shape}"
        )
    elif vectors.shape[0] != len(entries):
        errors.append(
            f"vector matrix has {vectors.shape[0]} rows, expected {len(entries)}"
        )

    if vectors.ndim == 2 and vectors.shape[0] == len(entries):
        # Each row must have non-zero L2 norm (index was normalised on build).
        norms = np.linalg.norm(vectors, axis=1)
        zero_norm_rows = int(np.sum(norms < 1e-6))
        if zero_norm_rows:
            errors.append(
                f"{zero_norm_rows} rows have zero L2 norm — "
                "index build was incomplete"
            )

    if len(vocab) == 0:
        errors.append("vocab is empty")

    return errors


def main() -> int:
    entries, json_errors = _validate_json()
    vector_errors = [] if json_errors else _validate_vectors(entries)

    total_errors = len(json_errors) + len(vector_errors)
    if total_errors == 0:
        if entries:
            with np.load(VECTORS_PATH, allow_pickle=False) as data:
                shape = data["vectors"].shape
        else:
            shape = "(unavailable)"
        print(
            f"OK — {len(entries)} codes, vector matrix shape {shape}"
        )
        return 0

    print(f"FAIL — {total_errors} defect(s):", file=sys.stderr)
    for err in json_errors + vector_errors:
        print(f"  - {err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())