"""Template Service for Official 9-Section MSME Client Requirement Documents."""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.domain import Application, ApplicationUnit, OfficialAddress, Template, TemplateVersion


class TemplateService:
    """Generates official 9-Section Udyam Registration Client Requirement Documents."""

    @staticmethod
    def generate_intake_template_structure(
        template_name: str,
        business_type: str,
        org_type: str = "Proprietorship",
        workflow: str = "Udyam Registration",
        prefilled_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Produce the standard 9-section structure, populated with any prefilled fields."""
        data = prefilled_data or {}
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        template_id = f"TMPL-{int(datetime.datetime.now().timestamp())}"
        title = template_name or f"{business_type} MSME Registration Template"

        sections = [
            {
                "section_id": "identity",
                "section_title": "1. IDENTITY DETAILS",
                "fields": [
                    {"key": "aadhaar", "label": "Aadhaar Number", "placeholder": "12-Digit Aadhaar Number", "value": str(data.get("aadhaar") or "")},
                    {"key": "aadhaar_name", "label": "Name as per Aadhaar", "placeholder": "Full Name as on Aadhaar Card", "value": str(data.get("aadhaar_name") or data.get("applicant_name") or "")},
                    {"key": "mobile", "label": "Mobile Number", "placeholder": "10-Digit OTP Linked Mobile", "value": str(data.get("mobile") or data.get("mobile_number") or "")},
                    {"key": "email", "label": "Email Address", "placeholder": "Official Email Address", "value": str(data.get("email") or "")},
                    {"key": "social_category", "label": "Social Category", "placeholder": "General / SC / ST / OBC", "value": str(data.get("social_category") or "")},
                    {"key": "gender", "label": "Gender", "placeholder": "Male / Female / Other", "value": str(data.get("gender") or "")},
                ],
                "documents_required": [
                    {"key": "doc_aadhaar", "label": "Aadhaar Card Copy", "checked": bool(data.get("aadhaar"))},
                    {"key": "doc_pan", "label": "PAN Card Copy", "checked": bool(data.get("pan"))},
                ],
            },
            {
                "section_id": "business",
                "section_title": "2. BUSINESS DETAILS",
                "fields": [
                    {"key": "org_type", "label": "Organisation Type", "placeholder": "", "value": str(data.get("org_type") or org_type), "readonly": True},
                    {"key": "pan", "label": "PAN Number", "placeholder": "10-Character PAN Number", "value": str(data.get("pan") or data.get("pan_number") or "")},
                    {"key": "business_name", "label": "Enterprise / Business Name", "placeholder": "Full Enterprise Name", "value": str(data.get("business_name") or "")},
                    {"key": "incorporation_date", "label": "Incorporation Date", "placeholder": "DD/MM/YYYY", "value": str(data.get("incorporation_date") or "")},
                    {"key": "commenced_status", "label": "Has business commenced operations?", "placeholder": "Yes / No", "value": str(data.get("commenced_status") or "Yes")},
                    {"key": "commencement_date", "label": "Business Commencement Date", "placeholder": "DD/MM/YYYY", "value": str(data.get("commencement_date") or "")},
                ],
            },
            {
                "section_id": "official_address",
                "section_title": "3. OFFICIAL ADDRESS",
                "fields": [
                    {"key": "address_line", "label": "Complete Business Address", "placeholder": "Flat/Door/Block, Building, Street, Area", "value": str(data.get("official_address") or data.get("address_line") or "")},
                    {"key": "city", "label": "City / Town", "placeholder": "City Location", "value": str(data.get("city") or "")},
                    {"key": "district", "label": "District", "placeholder": "e.g. Gurgaon / Chennai", "value": str(data.get("district") or "")},
                    {"key": "state", "label": "State", "placeholder": "e.g. Haryana / Tamil Nadu", "value": str(data.get("state") or "")},
                    {"key": "pin_code", "label": "PIN Code", "placeholder": "6-Digit PIN Code", "value": str(data.get("pin_code") or data.get("pin") or "")},
                ],
            },
            {
                "section_id": "unit_details",
                "section_title": "4. BUSINESS UNIT DETAILS",
                "fields": [
                    {"key": "unit_name", "label": "Unit Name", "placeholder": f"Unit 1 - {business_type}", "value": str(data.get("unit_name") or f"Unit 1 - {business_type}")},
                    {"key": "unit_address", "label": "Unit Address", "placeholder": "Plant / Factory Address", "value": str(data.get("unit_address") or "")},
                    {"key": "unit_district", "label": "District", "placeholder": "District Location", "value": str(data.get("unit_district") or data.get("district") or "")},
                    {"key": "unit_state", "label": "State", "placeholder": "State Location", "value": str(data.get("unit_state") or data.get("state") or "")},
                    {"key": "unit_pin", "label": "PIN Code", "placeholder": "6-Digit PIN Code", "value": str(data.get("unit_pin") or data.get("pin_code") or "")},
                ],
            },
            {
                "section_id": "bank",
                "section_title": "5. BANK DETAILS",
                "fields": [
                    {"key": "bank_name", "label": "Bank Name", "placeholder": "e.g. HDFC Bank / State Bank of India", "value": str(data.get("bank_name") or "")},
                    {"key": "account_number", "label": "Account Number", "placeholder": "Bank Account Number", "value": str(data.get("account_number") or data.get("bank_account_number") or "")},
                    {"key": "ifsc_code", "label": "IFSC Code", "placeholder": "11-Character IFSC Code", "value": str(data.get("ifsc_code") or data.get("bank_ifsc") or "")},
                ],
                "documents_required": [
                    {"key": "doc_bank", "label": "Bank Statement / Cancelled Cheque", "checked": bool(data.get("account_number") or data.get("bank_account_number"))},
                ],
            },
            {
                "section_id": "activity",
                "section_title": "6. BUSINESS ACTIVITY",
                "fields": [
                    {"key": "major_activity", "label": "Major Activity", "placeholder": "Manufacturing / Services / Trading", "value": str(data.get("major_activity") or ("Manufacturing" if "Manufacturing" in business_type else "Services"))},
                    {"key": "activity_description", "label": "Describe Business Activity", "placeholder": f"Detailed activity for {business_type}", "value": str(data.get("activity_description") or f"Activities relating to {business_type}")},
                    {"key": "nic_code", "label": "NIC 5-Digit Code", "placeholder": "e.g. 22209 / 62011", "value": str(data.get("nic_code") or "")},
                ],
            },
            {
                "section_id": "employment",
                "section_title": "7. EMPLOYMENT DETAILS",
                "fields": [
                    {"key": "male_employees", "label": "Male Employees", "placeholder": "Count", "value": str(data.get("male_employees") or "0")},
                    {"key": "female_employees", "label": "Female Employees", "placeholder": "Count", "value": str(data.get("female_employees") or "0")},
                    {"key": "other_employees", "label": "Other Employees", "placeholder": "Count", "value": str(data.get("other_employees") or "0")},
                    {"key": "total_employees", "label": "Total Employees", "placeholder": "Calculated Total", "value": str(int(data.get("male_employees") or 0) + int(data.get("female_employees") or 0) + int(data.get("other_employees") or 0)), "readonly": True},
                ],
            },
            {
                "section_id": "financials",
                "section_title": "8. FINANCIAL DETAILS",
                "fields": [
                    {"key": "investment", "label": "Investment in Plant/Machinery (₹)", "placeholder": "Gross Investment in Plant/Machinery", "value": str(data.get("investment") or data.get("net_investment") or "0")},
                    {"key": "exclusions", "label": "Eligible Exclusions (₹)", "placeholder": "Pollution Control / R&D Exclusions", "value": str(data.get("exclusions") or data.get("eligible_exclusions") or "0")},
                    {"key": "net_investment", "label": "Net Investment (₹)", "placeholder": "Net Investment", "value": str(data.get("net_investment") or data.get("investment") or "0"), "readonly": True},
                    {"key": "total_turnover", "label": "Total Turnover (₹)", "placeholder": "Gross Turnover for Previous FY", "value": str(data.get("total_turnover") or data.get("turnover") or "0")},
                    {"key": "export_turnover", "label": "Export Turnover (₹)", "placeholder": "Turnover from Exports", "value": str(data.get("export_turnover") or "0")},
                    {"key": "net_turnover", "label": "Net Turnover (₹)", "placeholder": "Net Domestic Turnover", "value": str(data.get("net_turnover") or data.get("total_turnover") or "0"), "readonly": True},
                ],
            },
            {
                "section_id": "declarations",
                "section_title": "9. DECLARATIONS",
                "checkboxes": [
                    {
                        "key": "child_labour_declaration",
                        "label": "Child Labour Declaration",
                        "text": "I confirm that the business complies with applicable regulations regarding child labour (Child & Adolescent Labour Prohibition Act).",
                        "checked": True,
                    },
                    {
                        "key": "accuracy_declaration",
                        "label": "Information Accuracy Declaration",
                        "text": "I confirm that all information provided in this requirement document is accurate and complete to the best of my knowledge.",
                        "checked": True,
                    },
                ],
            },
        ]

        return {
            "template_id": template_id,
            "template_name": title,
            "business_type": business_type,
            "org_type": org_type,
            "workflow": workflow,
            "generated_at": timestamp,
            "header": {
                "system_title": "UDYAM REGISTRATION",
                "form_subtitle": "Client Information & Requirement Form",
                "business_type": business_type,
                "org_type": org_type,
            },
            "sections": sections,
        }

    @staticmethod
    async def build_template_for_application(application_id: Any, db: AsyncSession) -> Dict[str, Any]:
        """Load application and compile prefilled template structure."""
        stmt = (
            select(Application)
            .where(Application.id == application_id)
            .options(
                selectinload(Application.client),
                selectinload(Application.official_address),
                selectinload(Application.units),
                selectinload(Application.extracted_data),
            )
        )
        res = await db.execute(stmt)
        app = res.scalars().first()
        if not app:
            raise ValueError(f"Application {application_id} not found")

        prefill: Dict[str, Any] = {}
        if app.client:
            prefill["business_name"] = app.client.business_name
            prefill["applicant_name"] = app.client.applicant_name
            prefill["mobile_number"] = app.client.mobile_number
            prefill["email"] = app.client.email
            prefill["pan_number"] = app.client.pan_number
            prefill["gender"] = app.client.gender
            prefill["social_category"] = app.client.social_category

        if app.official_address:
            addr_parts = [app.official_address.flat, app.official_address.building, app.official_address.road_street, app.official_address.village_town]
            prefill["official_address"] = ", ".join(p for p in addr_parts if p)
            prefill["city"] = app.official_address.city
            prefill["district"] = app.official_address.district
            prefill["state"] = app.official_address.state
            prefill["pin_code"] = app.official_address.pin

        if app.units:
            unit = app.units[0]
            prefill["unit_name"] = unit.unit_name
            u_parts = [unit.flat, unit.building, unit.road_street, unit.village_town]
            prefill["unit_address"] = ", ".join(p for p in u_parts if p)
            prefill["unit_district"] = unit.district
            prefill["unit_state"] = unit.state
            prefill["unit_pin"] = unit.pin

        prefill["bank_name"] = app.bank_name
        prefill["account_number"] = app.bank_account_number
        prefill["ifsc_code"] = app.bank_ifsc
        prefill["major_activity"] = app.major_activity
        prefill["male_employees"] = app.male_employees
        prefill["female_employees"] = app.female_employees
        prefill["other_employees"] = app.other_employees
        prefill["net_investment"] = float(app.net_investment) if app.net_investment else 0
        prefill["total_turnover"] = float(app.total_turnover) if app.total_turnover else 0

        # Also blend in ExtractedData
        if app.extracted_data:
            for ed in app.extracted_data:
                if ed.field_value and ed.field_name not in prefill:
                    prefill[ed.field_name] = ed.field_value

        business_type = app.major_activity or (app.client.business_name if app.client else "MSME Enterprise")
        org_type = app.enterprise_type or "Proprietorship"

        return TemplateService.generate_intake_template_structure(
            template_name=f"{app.client.business_name if app.client else 'MSME'} Requirement Document",
            business_type=business_type,
            org_type=org_type,
            workflow=app.workflow_type or "Udyam Registration",
            prefilled_data=prefill,
        )
