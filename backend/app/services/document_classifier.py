"""Document Classifier Service.

Classifies uploaded documents into Aadhaar, PAN, Bank Statement, or Unknown
based on filename and initial text indicators.
"""
from __future__ import annotations

import re
from typing import Tuple


class DocumentClassifier:
    """Classifies uploaded documents into canonical types."""

    @staticmethod
    def classify(filename: str, sample_text: str = "") -> Tuple[str, float]:
        """Return (canonical_type, confidence_score)."""
        fn_lower = filename.lower()
        text_lower = sample_text.lower()

        # Aadhaar indicators
        if any(k in fn_lower for k in ["aadhaar", "adhar", "uidai", "aadhar"]) or \
           any(k in text_lower for k in ["unique identification authority", "government of india", "aadhaar", "enrollment no", "dob:"]):
            return "AADHAAR_CARD", 0.98

        # PAN Card indicators
        if any(k in fn_lower for k in ["pan", "pancard", "income_tax"]) or \
           any(k in text_lower for k in ["income tax department", "permanent account number", "govt. of india"]):
            return "PAN_CARD", 0.98

        # Bank Statement / Passbook indicators
        if any(k in fn_lower for k in ["bank", "statement", "passbook", "cheque", "hdfc", "sbi", "icici", "axis", "canara"]) or \
           any(k in text_lower for k in ["account number", "ifsc", "branch", "account statement", "savings account", "current account"]):
            return "BANK_PROOF", 0.95

        # Photo
        if any(k in fn_lower for k in ["photo", "passport_size", "pic", "applicant_img"]):
            return "PHOTO", 0.90

        return "GENERAL_DOCUMENT", 0.70
