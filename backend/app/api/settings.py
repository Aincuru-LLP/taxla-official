"""System Settings and WhatsApp Configuration API for TAXLA Operations Platform."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.models.domain import User

router = APIRouter(prefix="/settings", tags=["Settings"])


class SystemSettingsResponse(BaseModel):
    environment: str
    udyam_target_url: str
    target_mode: str  # "PRODUCTION" | "STAGING_VERCEL"
    otp_timeout_seconds: int
    session_timeout_minutes: int
    auto_retry_max_attempts: int
    playwright_headed_mode: bool


class WhatsAppTemplateItem(BaseModel):
    id: str
    name: str
    category: str
    language: str
    status: str
    body_text: str


@router.get("", response_model=SystemSettingsResponse)
async def get_system_settings(current_user: User = Depends(get_current_user)):
    """Fetch operational system configuration and target URL status."""
    target_url = os.environ.get("UDYAM_TARGET_URL", "https://udyamregistration.gov.in")
    is_staging = "vercel.app" in target_url or "localhost" in target_url or "127.0.0.1" in target_url

    return SystemSettingsResponse(
        environment=os.environ.get("ENVIRONMENT", "production"),
        udyam_target_url=target_url,
        target_mode="STAGING_VERCEL" if is_staging else "PRODUCTION",
        otp_timeout_seconds=int(os.environ.get("OTP_TIMEOUT_SECONDS", "300")),
        session_timeout_minutes=int(os.environ.get("SESSION_TIMEOUT_MINUTES", "60")),
        auto_retry_max_attempts=int(os.environ.get("AUTO_RETRY_MAX_ATTEMPTS", "3")),
        playwright_headed_mode=os.environ.get("PLAYWRIGHT_HEADLESS", "false").lower() == "false",
    )


@router.get("/whatsapp", response_model=Dict[str, Any])
async def get_whatsapp_settings(current_user: User = Depends(get_current_user)):
    """Fetch WhatsApp Cloud API integration status and approved template catalog."""
    templates = [
        WhatsAppTemplateItem(
            id="tpl_01",
            name="requirement_intake_link",
            category="UTILITY",
            language="en",
            status="APPROVED",
            body_text="Welcome to TAXLA! Please submit your requirement details using this secure link: {{1}}",
        ),
        WhatsAppTemplateItem(
            id="tpl_02",
            name="request_missing_info",
            category="UTILITY",
            language="en",
            status="APPROVED",
            body_text="Dear {{1}}, additional details are required for your MSME application ({{2}}): {{3}}",
        ),
        WhatsAppTemplateItem(
            id="tpl_03",
            name="otp_verification_alert",
            category="AUTHENTICATION",
            language="en",
            status="APPROVED",
            body_text="An OTP has been dispatched to your Aadhaar-linked mobile for Udyam registration. Please share the 6-digit code with your TAXLA manager.",
        ),
        WhatsAppTemplateItem(
            id="tpl_04",
            name="certificate_delivery",
            category="UTILITY",
            language="en",
            status="APPROVED",
            body_text="Congratulations {{1}}! Your Udyam Certificate ({{2}}) has been generated successfully. Please find the attached document.",
        ),
    ]

    return {
        "provider": "WhatsApp Cloud API",
        "phone_number_id": os.environ.get("WHATSAPP_PHONE_ID", "109823475912384"),
        "business_account_id": os.environ.get("WHATSAPP_WABA_ID", "901238475912834"),
        "status": "CONNECTED",
        "webhook_url": "/api/v1/webhooks/whatsapp",
        "templates": templates,
    }
