"""OCR service: provider-pluggable text + confidence + bounding-box extraction.

The Tesseract binary must be installed separately — see backend/README.md.

The public surface (OcrService.is_available / extract_text / tesseract_version)
is unchanged. Internally we delegate to an OcrProvider so we can swap Tesseract
for PaddleOCR / a future provider without touching callers.
"""
from __future__ import annotations

import logging
import shutil
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

import pytesseract
from PIL import Image
from pytesseract import Output

logger = logging.getLogger(__name__)


class OcrUnavailableError(RuntimeError):
    """Raised when the OCR engine binary cannot be located on PATH."""


class OcrFailureError(RuntimeError):
    """Raised when OCR processing fails (corrupt PDF, unreadable image, etc.)."""


@dataclass
class OcrLine:
    text: str
    confidence: float  # 0..100, as reported by image_to_data
    bbox: dict  # {left, top, width, height}

    def to_dict(self) -> dict:
        return asdict(self)


class OcrProvider(ABC):
    """Abstract OCR engine. Implementations: TesseractOcrProvider, future PaddleOcrProvider."""

    @abstractmethod
    def engine_name(self) -> str:
        """Stable identifier persisted into RawOcrResult.ocr_engine (e.g. 'tesseract')."""

    @abstractmethod
    def engine_version(self) -> str | None:
        """Engine version string. Persisted into RawOcrResult.ocr_engine_version."""

    @abstractmethod
    def preprocessing_version(self) -> str:
        """Pipeline-internal preprocessing version. Persisted into RawOcrResult.preprocessing_version."""

    @abstractmethod
    def is_available(self) -> bool:
        """True iff the engine binary is installed and reachable."""

    @abstractmethod
    def extract_text(self, file_path: str, doc_type: str | None = None) -> List[OcrLine]:
        """Run OCR. Raises OcrUnavailableError / OcrFailureError."""


# Common Tesseract install locations on Windows (where the binary is usually
# NOT on PATH). We probe these in is_available() and pin pytesseract's
# tesseract_cmd to the first match so the rest of the pipeline works
# without requiring PATH changes.
_WINDOWS_TESSERACT_CANDIDATES: tuple[str, ...] = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


def _resolve_windows_tesseract() -> str | None:
    """Return the first Windows candidate that exists, else None.

    Side effect: pins ``pytesseract.pytesseract.tesseract_cmd`` to the resolved
    path so any later pytesseract call in this process finds the binary.
    """
    for candidate in _WINDOWS_TESSERACT_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            pytesseract.pytesseract.tesseract_cmd = candidate
            return candidate
    return None


class TesseractOcrProvider(OcrProvider):
    """Tesseract-backed OCR. Cross-platform default (works on Windows + macOS + Linux)."""

    ENGINE_NAME = "tesseract"
    PREPROCESSING_VERSION = "v1-binarize"  # bumped when _preprocess changes

    def engine_name(self) -> str:
        return self.ENGINE_NAME

    def preprocessing_version(self) -> str:
        return self.PREPROCESSING_VERSION

    def engine_version(self) -> str | None:
        try:
            return str(pytesseract.get_tesseract_version())
        except pytesseract.TesseractNotFoundError:
            return None

    def is_available(self) -> bool:
        # PATH lookup first (covers macOS + Linux + Windows-with-tesseract-on-PATH).
        if shutil.which("tesseract") is not None:
            return True
        # Windows fallback: probe the common install locations.
        return _resolve_windows_tesseract() is not None

    def tesseract_version(self) -> str:
        """Return the Tesseract version string. Raises OcrUnavailableError."""
        try:
            return str(pytesseract.get_tesseract_version())
        except pytesseract.TesseractNotFoundError as exc:
            raise OcrUnavailableError(
                "Tesseract binary not found. Install per backend/README.md "
                "('Install Tesseract binary')."
            ) from exc

    def extract_text(self, file_path: str, doc_type: str | None = None) -> List[OcrLine]:
        if not self.is_available():
            raise OcrUnavailableError(
                "Tesseract binary not found on PATH. Install per backend/README.md."
            )

        path = Path(file_path)
        if not path.is_file():
            raise OcrFailureError(f"OCR input not found: {file_path}")

        try:
            pages = self._load_pages(path)
        except OcrFailureError:
            raise
        except Exception as exc:
            raise OcrFailureError(f"Failed to load OCR input {file_path}: {exc}") from exc

        all_lines: List[OcrLine] = []
        for page_index, page in enumerate(pages):
            try:
                preprocessed = self._preprocess(page)
                data = pytesseract.image_to_data(
                    preprocessed, output_type=Output.DICT
                )
            except pytesseract.TesseractError as exc:
                raise OcrFailureError(
                    f"Tesseract failed on page {page_index} of {file_path}: {exc}"
                ) from exc

            page_offset_top = page_index * 2000  # crude vertical separator
            for i, raw_text in enumerate(data.get("text", [])):
                text = (raw_text or "").strip()
                if not text:
                    continue
                try:
                    conf = float(data["conf"][i])
                except (KeyError, ValueError, TypeError):
                    conf = -1.0
                if conf < 0:
                    conf = 0.0
                bbox = {
                    "left": int(data["left"][i]) if data["left"][i] is not None else 0,
                    "top": int(data["top"][i]) + page_offset_top
                    if data["top"][i] is not None
                    else page_offset_top,
                    "width": int(data["width"][i]) if data["width"][i] is not None else 0,
                    "height": int(data["height"][i]) if data["height"][i] is not None else 0,
                }
                all_lines.append(OcrLine(text=text, confidence=conf, bbox=bbox))

        return all_lines

    def _load_pages(self, path: Path) -> List[Image.Image]:
        """Read a file into a list of PIL images (one per PDF page)."""
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            from pdf2image import convert_from_path

            images = convert_from_path(str(path), dpi=300)
            return [img.convert("RGB") for img in images]

        img = Image.open(path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        return [img]

    def _preprocess(self, img: Image.Image) -> Image.Image:
        """Deskew-adjacent preprocessing: grayscale + Otsu binarization.

        We deliberately avoid aggressive deskew here (it can distort small text
        and tanks accuracy on low-DPI scans). The binarize step is enough to
        give Tesseract a clean contrast signal for Indian government IDs.
        """
        import cv2
        import numpy as np

        arr = np.array(img)
        if arr.ndim == 3:
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        else:
            gray = arr
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return Image.fromarray(binary)


# Provider registry — extend by adding entries here when a new engine lands.
_PROVIDER_REGISTRY: dict[str, type[OcrProvider]] = {
    "tesseract": TesseractOcrProvider,
}


class OcrService:
    """Facade — backward-compatible surface (Phase 02 used static methods)."""

    @staticmethod
    def get_provider(name: str | None = None) -> OcrProvider:
        """Resolve the configured OCR provider. Default from settings.OCR_PROVIDER."""
        from app.core.config import settings

        provider_name = (name or settings.OCR_PROVIDER or "tesseract").lower()
        provider_cls = _PROVIDER_REGISTRY.get(provider_name)
        if provider_cls is None:
            raise ValueError(
                f"Unknown OCR provider: {provider_name!r}. "
                f"Available: {list(_PROVIDER_REGISTRY)}"
            )
        return provider_cls()

    @staticmethod
    def is_available(name: str | None = None) -> bool:
        try:
            return OcrService.get_provider(name).is_available()
        except ValueError:
            return False

    @staticmethod
    def tesseract_version() -> str:
        """Backward-compat: returns the Tesseract engine version."""
        return TesseractOcrProvider().tesseract_version()

    @staticmethod
    def extract_text(file_path: str, doc_type: str | None = None, provider: str | None = None) -> List[OcrLine]:
        """Delegate to the configured OCR provider."""
        return OcrService.get_provider(provider).extract_text(file_path, doc_type)