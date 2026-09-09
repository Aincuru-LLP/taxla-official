"""Unified AI Service interfacing with Ollama Qwen runtime.

NO fake fallbacks, NO Gemini dependencies. Strictly delegates to
DocumentExtractionService and NICClassificationService.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.core.config import settings
from app.services.ai_extractor import DocumentExtractionService
from app.services.nic_service import NICClassificationService
from app.services.ocr_service import OcrService

logger = logging.getLogger(__name__)


class AIService:
    @staticmethod
    async def extract_document_data(file_path: str, document_type: str) -> List[Dict[str, Any]]:
        """Extract structured fields using OCR and local Ollama + Qwen."""
        logger.info("Extracting data from %s (%s) using Ollama %s", file_path, document_type, settings.OLLAMA_MODEL)
        
        provider = OcrService.get_provider()
        lines = provider.extract_text(file_path, document_type)
        raw_text = "\n".join(l.text for l in lines)
        if not raw_text.strip():
            raise RuntimeError(f"OCR produced no extractable text from {file_path}")

        result = await DocumentExtractionService.extract_fields(raw_text, document_type)
        if not result.success:
            raise RuntimeError(f"Ollama extraction failed: {result.error}")

        extracted_list: List[Dict[str, Any]] = []
        for field_name, field_res in result.fields.items():
            if field_res.value is not None:
                extracted_list.append({
                    "field_name": field_name,
                    "field_value": str(field_res.value),
                    "confidence": field_res.extraction_confidence,
                    "validation_status": field_res.validation_status,
                })

        return extracted_list

    @staticmethod
    async def suggest_nic_code(business_description: str) -> List[Dict[str, Any]]:
        """Map business description to 5-digit NIC 2008 codes via 3-tier matching."""
        logger.info("Suggesting NIC code via 3-tier pipeline for: %s", business_description)
        service = NICClassificationService()
        candidates = await service.generate_suggestions(
            app_id=None,
            business_description=business_description,
            location_text="",
            db=None,
        )
        return [c.model_dump() for c in candidates]
