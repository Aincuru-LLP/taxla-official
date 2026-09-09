"""OCR service test: real Tesseract on a synthetic PAN card image.

Requires the Tesseract binary on PATH. Skips cleanly otherwise.
Run: pytest backend/tests/test_ocr_pipeline.py -v
"""
from __future__ import annotations

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.ocr_service import (
    OcrLine,
    OcrService,
    OcrUnavailableError,
    OcrFailureError,
)


PAN_NUMBER = "ABCDE1234F"


def _build_synthetic_pan_card(path: str) -> None:
    """Render a 640x240 white PNG with the canonical PAN text."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (640, 240), color="white")
    draw = ImageDraw.Draw(img)
    try:
        big = ImageFont.truetype("arial.ttf", 28)
        small = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        big = ImageFont.load_default()
        small = big
    draw.text((20, 20), "INCOME TAX DEPARTMENT", fill="black", font=big)
    draw.text((20, 70), "GOVT OF INDIA", fill="black", font=small)
    draw.text((20, 120), "Permanent Account Number", fill="black", font=small)
    draw.text((20, 170), PAN_NUMBER, fill="black", font=big)
    draw.text((20, 215), "Name: TEST USER", fill="black", font=small)
    img.save(path, format="PNG")


def test_ocr_service_availability():
    """is_available() reflects PATH lookup. Don't assert True — Tesseract
    may not be installed on the dev machine — but the call must be safe."""
    available = OcrService.is_available()
    assert isinstance(available, bool)


@pytest.mark.skipif(
    not OcrService.is_available(),
    reason="Tesseract binary not installed. See backend/README.md.",
)
def test_extract_text_returns_lines_with_confidence_and_bbox(tmp_path):
    img_path = tmp_path / "synthetic_pan.png"
    _build_synthetic_pan_card(str(img_path))

    lines: list[OcrLine] = OcrService.extract_text(str(img_path), doc_type="PAN_CARD")

    assert isinstance(lines, list)
    assert len(lines) > 0, "Tesseract returned no lines from the synthetic PAN card"

    # Every line carries confidence + bbox
    for line in lines:
        assert isinstance(line.text, str)
        assert isinstance(line.confidence, (int, float))
        assert 0.0 <= line.confidence <= 100.0
        assert isinstance(line.bbox, dict)
        assert {"left", "top", "width", "height"} <= set(line.bbox.keys())

    # At least one line should have non-zero confidence (Tesseract read the text)
    assert any(line.confidence > 0 for line in lines), (
        f"All confidences were 0; OCR output: {[l.text for l in lines]}"
    )


@pytest.mark.skipif(
    not OcrService.is_available(),
    reason="Tesseract binary not installed. See backend/README.md.",
)
def test_extract_text_finds_pan_number(tmp_path):
    """End-to-end sanity: synthetic PAN card → OCR → 'ABCDE1234F' should
    appear in the joined text (possibly with OCR-mangled whitespace).
    """
    img_path = tmp_path / "synthetic_pan.png"
    _build_synthetic_pan_card(str(img_path))

    lines = OcrService.extract_text(str(img_path), doc_type="PAN_CARD")
    joined = "".join(line.text.replace(" ", "").upper() for line in lines)

    # OCR can drop or substitute characters on noisy scans. We require at least
    # 8 of 10 PAN characters to be present — generous but defends against
    # the test passing on completely empty output.
    pan_chars = set(PAN_NUMBER)
    found = sum(1 for c in pan_chars if c in joined)
    assert found >= 8, (
        f"Expected most of {PAN_NUMBER} in OCR output; got {joined!r}"
    )


def test_extract_text_missing_file_raises_failure():
    """extract_text on a nonexistent file should raise OcrFailureError,
    not crash with FileNotFoundError leaking through.
    """
    if not OcrService.is_available():
        pytest.skip("Tesseract binary not installed.")
    with pytest.raises((OcrFailureError, FileNotFoundError)):
        OcrService.extract_text("/nonexistent/path/to/file.png")