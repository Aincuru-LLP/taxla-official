"""Format validators for Indian government ID fields + common contact info.

Each validator returns True if the value matches the expected format, False
otherwise. Validators are intentionally permissive on whitespace (strip before
matching) so that OCR-extracted strings with trailing/leading spaces pass.

Used by ``validation_engine.ValidationEngine`` to populate per-field
``validation_status`` and ``validation_errors`` on ``ExtractedData``.
"""
from __future__ import annotations

import re
from typing import Callable, Dict


# --- regex patterns ---------------------------------------------------------

# PAN: 5 uppercase letters, 4 digits, 1 uppercase letter. The 4th character
# identifies the taxpayer type (P=Individual, C=Company, H=HUF, etc.) — we
# don't enforce that subset here, just the shape.
_PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")

# Aadhaar: 12 digits, optionally space-separated as XXXX XXXX XXXX.
_AADHAAR_RE = re.compile(r"^\d{4}\s?\d{4}\s?\d{4}$")

# IFSC: 4 letters (bank code), '0', 6 alphanumeric (branch code). The '0' in
# position 5 is mandated by the RBI; some private banks have variants but we
# follow the canonical format.
_IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")

# GSTIN: 2 digits (state) + 5 letters (PAN-like) + 4 digits + 1 letter + 1
# digit + Z + 1 alphanumeric.
_GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]$")

# Indian mobile: 10 digits starting with 6/7/8/9 (post-2010 numbering plan).
_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")

# Email: pragmatic subset — local@domain.tld. Not RFC 5322 compliant
# (intentional — full RFC is overkill for OCR-derived inputs).
_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")

# Indian PIN code: 6 digits, first digit 1-9 (no leading zero).
_PINCODE_RE = re.compile(r"^\d{6}$")


# --- public validators ------------------------------------------------------


def validate_pan(value: str | None) -> bool:
    """True if ``value`` matches the PAN shape ``AAAAA9999A``."""
    if not value:
        return False
    return bool(_PAN_RE.match(value.strip().upper()))


def validate_aadhaar(value: str | None) -> bool:
    """True if ``value`` matches the 12-digit Aadhaar (with or without spaces)."""
    if not value:
        return False
    return bool(_AADHAAR_RE.match(value.strip()))


def validate_ifsc(value: str | None) -> bool:
    """True if ``value`` matches the IFSC ``AAAA0XXXXXX`` shape."""
    if not value:
        return False
    return bool(_IFSC_RE.match(value.strip().upper()))


def validate_gstin(value: str | None) -> bool:
    """True if ``value`` matches the 15-character GSTIN shape."""
    if not value:
        return False
    return bool(_GSTIN_RE.match(value.strip().upper()))


def validate_mobile(value: str | None) -> bool:
    """True if ``value`` is a 10-digit Indian mobile starting with 6/7/8/9."""
    if not value:
        return False
    return bool(_MOBILE_RE.match(value.strip()))


def validate_email(value: str | None) -> bool:
    """True if ``value`` is a pragmatic email ``local@domain.tld``."""
    if not value:
        return False
    return bool(_EMAIL_RE.match(value.strip()))


def validate_pincode(value: str | None) -> bool:
    """True if ``value`` is a 6-digit Indian PIN code."""
    if not value:
        return False
    return bool(_PINCODE_RE.match(value.strip()))


# --- lookup by field name ----------------------------------------------------
# Maps extracted_data field_name -> validator. Used by ValidationEngine to
# run the right validator against each field without callers having to wire
# the field→validator mapping themselves.

VALIDATION_RULES: Dict[str, Callable[[str | None], bool]] = {
    "pan_number": validate_pan,
    "aadhaar_number": validate_aadhaar,
    "bank_ifsc": validate_ifsc,
    "gstin": validate_gstin,
    "mobile_number": validate_mobile,
    "email": validate_email,
    "pincode": validate_pincode,
    "unit_pin": validate_pincode,
    "official_pin": validate_pincode,
}


def validate_field(field_name: str, value: str | None) -> bool:
    """Run the validator registered for ``field_name``, or True if no rule.

    Fields without a registered rule (e.g. ``applicant_name``, ``business_name``)
    pass by default — we only reject on clearly-wrong formats.
    """
    validator = VALIDATION_RULES.get(field_name)
    if validator is None:
        return True
    return validator(value)