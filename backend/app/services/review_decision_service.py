"""ReviewDecisionService — map field-level signals to PASS / REVIEW / FAIL.

Decoupled from extraction. Inputs are the three signals we now carry
separately on ExtractedData:

    * ocr_confidence        (Tesseract's reported confidence for the matched line, 0-1)
    * extraction_confidence (LLM extraction confidence — heuristic from retry count, 0-1)
    * validation_status     (deterministic regex check, PASS / FAIL / UNVERIFIED)

Engineering defaults per Phase 02 follow-up:

    OCR confidence < 0.80                -> REVIEW
    Extraction confidence < 0.85         -> REVIEW
    Validation FAIL                      -> FAIL (mandatory review)
    All three clean (>= thresholds + PASS) -> PASS

Outputs:

    review_decision   PASS | REVIEW | FAIL
    final_confidence  weighted combination 0.4 * ocr + 0.4 * extract + 0.2 * validation
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Engineering defaults — tune per `documents/18_ai_evaluation.md` evaluation dataset.
DEFAULT_OCR_REVIEW_THRESHOLD = 0.80
DEFAULT_EXTRACTION_REVIEW_THRESHOLD = 0.85

PASS = "PASS"
REVIEW = "REVIEW"
FAIL = "FAIL"


@dataclass(frozen=True)
class FieldSignals:
    ocr_confidence: Optional[float] = None  # 0-1
    extraction_confidence: Optional[float] = None  # 0-1
    validation_status: str = "UNVERIFIED"  # PASS | FAIL | UNVERIFIED


@dataclass(frozen=True)
class ReviewDecision:
    review_decision: str  # PASS | REVIEW | FAIL
    final_confidence: float  # 0-1
    rationale: str  # human-readable reason — surfaces in review queue UI


def _validation_score(status: str) -> float:
    if status == "PASS":
        return 1.0
    if status == "FAIL":
        return 0.0
    return 0.5  # UNVERIFIED


class ReviewDecisionService:
    """Stateless. Same inputs always produce the same decision (deterministic)."""

    def __init__(
        self,
        ocr_review_threshold: float = DEFAULT_OCR_REVIEW_THRESHOLD,
        extraction_review_threshold: float = DEFAULT_EXTRACTION_REVIEW_THRESHOLD,
    ):
        self.ocr_review_threshold = ocr_review_threshold
        self.extraction_review_threshold = extraction_review_threshold

    def decide(self, signals: FieldSignals) -> ReviewDecision:
        """Compute review decision + final confidence from the three signals."""
        # Mandatory failure: validation regex failed -> human review required.
        if signals.validation_status == "FAIL":
            return ReviewDecision(
                review_decision=FAIL,
                final_confidence=0.0,
                rationale="Validation regex failed — mandatory review.",
            )

        reasons: list[str] = []
        ocr = signals.ocr_confidence
        extract = signals.extraction_confidence

        if ocr is not None and ocr < self.ocr_review_threshold:
            reasons.append(
                f"OCR confidence {ocr:.2f} < {self.ocr_review_threshold}"
            )
        if extract is not None and extract < self.extraction_review_threshold:
            reasons.append(
                f"Extraction confidence {extract:.2f} < {self.extraction_review_threshold}"
            )

        # Weighted final confidence. Missing signals drop out of the denominator
        # so we don't artificially deflate when only one signal is present.
        weights: list[tuple[float, float]] = []
        if ocr is not None:
            weights.append((0.4, ocr))
        if extract is not None:
            weights.append((0.4, extract))
        weights.append((0.2, _validation_score(signals.validation_status)))

        weight_sum = sum(w for w, _ in weights)
        weighted_sum = sum(w * v for w, v in weights)
        final_confidence = round(weighted_sum / weight_sum, 3) if weight_sum > 0 else 0.0

        if reasons:
            return ReviewDecision(
                review_decision=REVIEW,
                final_confidence=final_confidence,
                rationale="; ".join(reasons),
            )

        return ReviewDecision(
            review_decision=PASS,
            final_confidence=final_confidence,
            rationale="All signals above review thresholds.",
        )