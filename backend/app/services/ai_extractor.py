import httpx
import json
import logging
import re
from typing import Type, Any
from pydantic import ValidationError, BaseModel
from app.core.config import settings
from app.schemas.extraction import (
    PANExtraction,
    AadhaarExtraction,
    BankProofExtraction,
    GeneralDocumentExtraction,
    ExtractionResult,
    FieldResult,
)

logger = logging.getLogger(__name__)

# Bumped when the extraction prompt or schema generation logic changes.
# Recorded against every extraction result for traceability.
EXTRACTION_PROMPT_VERSION = "v2-qwen-structured"
EXTRACTION_SCHEMA_VERSION = "v2-separate-confidence"
EXTRACTION_MODEL_NAME = settings.OLLAMA_MODEL
OLLAMA_URL = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
MODEL_NAME = settings.OLLAMA_MODEL


def _confidence_for_retry(retries_needed: int) -> float:
    """Heuristic mapping from how many LLM retries were needed to a 0-1 confidence.

    The number is a calibration placeholder, not a calibrated probability — it
    communicates to downstream code that "extraction took multiple attempts"
    so review-priority decisions can weight it accordingly.
    """
    if retries_needed <= 0:
        return 0.90
    if retries_needed == 1:
        return 0.70
    return 0.50  # 2+ retries


def _check_field_pattern(field_name: str, value: Any, schema_class: Type[BaseModel]) -> str:
    """Deterministically validate one field value against its schema regex.

    Returns 'PASS' if the value matches (or no pattern is defined), 'FAIL'
    otherwise. This is the validation signal — orthogonal to OCR/extraction
    confidence.
    """
    try:
        properties = schema_class.model_json_schema().get("properties", {})
        field_schema = properties.get(field_name, {})
        pattern = field_schema.get("pattern")
    except Exception:
        return "UNVERIFIED"

    if pattern is None:
        return "PASS"
    if not isinstance(value, str):
        return "FAIL"
    return "PASS" if re.match(pattern + "$", value) else "FAIL"


class DocumentExtractionService:
    @staticmethod
    def get_schema_for_type(doc_type: str) -> Type[BaseModel]:
        doc_type_upper = (doc_type or "").upper()
        if "PAN" in doc_type_upper:
            return PANExtraction
        elif "AADHAAR" in doc_type_upper or "ADHAR" in doc_type_upper:
            return AadhaarExtraction
        elif "BANK" in doc_type_upper or "CHEQUE" in doc_type_upper or "PASSBOOK" in doc_type_upper:
            return BankProofExtraction
        else:
            return GeneralDocumentExtraction

    @staticmethod
    async def extract_fields(ocr_text: str, doc_type: str, max_retries: int = 2) -> ExtractionResult:
        """Extract structured fields from raw OCR text using a local Ollama LLM.

        Returns an ExtractionResult carrying per-field ``extraction_confidence``
        (heuristic from retry count) and ``validation_status`` (PASS/FAIL from
        schema regex). No global ``confidence_score`` is fabricated — see
        ``app/schemas/extraction.py`` for the rationale.
        """
        try:
            schema_class = DocumentExtractionService.get_schema_for_type(doc_type)
        except ValueError as e:
            return ExtractionResult(success=False, error=str(e))

        schema_dict = schema_class.schema()
        properties = schema_dict.get('properties', {})
        fields_desc = "\n".join([f"- {k}: {v.get('description', '')}" for k, v in properties.items()])

        system_prompt = (
            f"You are a strict data extraction AI. Extract the requested fields from the OCR text of a {doc_type}. "
            f"Extract exactly these fields based on their descriptions:\n{fields_desc}\n\n"
            f"Output strictly valid JSON with keys matching the fields above. "
            f"Do not include any conversational text, markdown formatting, or explanations. ONLY output the JSON object."
        )

        last_error: str | None = None
        for attempt in range(max_retries + 1):
            prompt = system_prompt
            if attempt == 0:
                prompt += f"\n\nOCR Text:\n{ocr_text}"
            else:
                prompt += f"\n\nOCR Text:\n{ocr_text}\n\nWarning: Previous attempt failed schema validation. Ensure strict compliance with the JSON schema."

            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    response = await client.post(
                        OLLAMA_URL,
                        json={
                            "model": MODEL_NAME,
                            "prompt": prompt,
                            "stream": False,
                            "format": "json",
                            "options": {
                                "temperature": 0.1
                            }
                        }
                    )

                    if response.status_code != 200:
                        logger.error(f"Ollama API error: {response.text}")
                        last_error = f"Ollama HTTP {response.status_code}"
                        continue

                    result_json = response.json()
                    response_text = result_json.get("response", "")

                    try:
                        if response_text.startswith("```json"):
                            response_text = response_text[7:-3]
                        elif response_text.startswith("```"):
                            response_text = response_text[3:-3]

                        parsed_data = json.loads(response_text)
                        validated_data = schema_class(**parsed_data)
                        validated_dict = validated_data.dict()

                        # Build per-field FieldResults. We mark validation per field
                        # by re-checking the regex; this catches LLM hallucinations
                        # that pass whole-model validation but break a field's pattern.
                        field_results: dict[str, FieldResult] = {}
                        confidence = _confidence_for_retry(attempt)
                        for field_name, field_value in validated_dict.items():
                            field_results[field_name] = FieldResult(
                                value=field_value,
                                extraction_confidence=confidence,
                                validation_status=_check_field_pattern(field_name, field_value, schema_class),
                            )

                        return ExtractionResult(success=True, fields=field_results)

                    except json.JSONDecodeError:
                        logger.warning(f"Attempt {attempt + 1}: LLM did not return valid JSON")
                        last_error = "LLM response was not valid JSON"
                    except ValidationError as e:
                        logger.warning(f"Attempt {attempt + 1}: Pydantic validation failed: {e}")
                        last_error = f"Pydantic validation: {e}"

            except httpx.RequestError as e:
                logger.error(f"HTTP request to Ollama failed: {repr(e)}")
                return ExtractionResult(success=False, error=f"Ollama connection error: {repr(e)}")

        return ExtractionResult(
            success=False,
            error=last_error or f"Max retries ({max_retries}) exceeded for AI extraction validation.",
        )