"""Full diagnostic trace: what data does UDYAM-2026-09-60BF71EF actually carry?"""
import asyncio, uuid, re
from app.core.database import AsyncSessionLocal
from app.models.domain import (
    Application, ApplicationRequirement, ExtractedData,
    Client, OfficialAddress, NicReview,
)
from sqlalchemy import select
from sqlalchemy.orm import selectinload

APP_ID = uuid.UUID("84a46a5c-0ec8-4912-9408-1282ad1baa44")
DEMO_AADHAAR = "361105197807"
DEMO_PAN = "AAGCF9455K"


async def full_trace():
    async with AsyncSessionLocal() as db:
        app_res = await db.execute(
            select(Application).where(Application.id == APP_ID)
            .options(
                selectinload(Application.client),
                selectinload(Application.official_address),
                selectinload(Application.units),
            )
        )
        app = app_res.scalars().first()
        client = app.client
        addr = app.official_address

        print("=" * 60)
        print("APPLICATION")
        print("=" * 60)
        for attr in [
            "id", "application_number", "status", "enterprise_type",
            "bank_name", "bank_account_number", "bank_ifsc",
            "male_employees", "female_employees", "other_employees",
            "major_activity", "total_turnover", "net_investment",
            "incorporation_date",
        ]:
            print(f"  {attr:30s} = {getattr(app, attr, '???')}")

        print()
        print("=" * 60)
        print("CLIENT")
        print("=" * 60)
        if client:
            for attr in [
                "applicant_name", "business_name", "mobile_number",
                "email", "pan_number", "aadhaar_number_hash",
                "gender", "social_category",
            ]:
                print(f"  {attr:30s} = {getattr(client, attr, '???')}")
        else:
            print("  CLIENT IS NULL!")

        print()
        print("=" * 60)
        print("OFFICIAL ADDRESS")
        print("=" * 60)
        if addr:
            for attr in ["flat", "building", "village_town", "block", "road_street", "city", "state", "district", "pin"]:
                print(f"  {attr:30s} = {getattr(addr, attr, '???')}")
        else:
            print("  ** ADDRESS IS NULL — ALL address fields will use DEMO hardcodes **")

        print()
        print("=" * 60)
        print("UNITS")
        print("=" * 60)
        units = app.units or []
        print(f"  Count: {len(units)}")
        for u in units:
            print(f"    name={u.unit_name}, city={u.city}, pin={u.pin}")
        if not units:
            print("  ** NO UNITS — snapshot.units will be EMPTY, no unit added to portal **")

        print()
        print("=" * 60)
        print("APPLICATION REQUIREMENTS")
        print("=" * 60)
        req_res = await db.execute(
            select(ApplicationRequirement).where(ApplicationRequirement.application_id == APP_ID)
        )
        reqs = {r.requirement_key: r.value for r in req_res.scalars().all()}
        for k, v in reqs.items():
            print(f"  {k:30s} = {v}")
        if not reqs:
            print("  ** NO REQUIREMENTS **")

        print()
        print("=" * 60)
        print("EXTRACTED DATA")
        print("=" * 60)
        ext_res = await db.execute(
            select(ExtractedData).where(ExtractedData.application_id == APP_ID)
        )
        ext_dict = {e.field_name: e.field_value for e in ext_res.scalars().all() if e.field_name}
        for k, v in ext_dict.items():
            print(f"  {k:30s} = {v}")
        if not ext_dict:
            print("  ** NO EXTRACTED DATA **")

        print()
        print("=" * 60)
        print("NIC REVIEW")
        print("=" * 60)
        nic = (await db.execute(select(NicReview).where(NicReview.application_id == APP_ID))).scalars().first()
        if nic:
            print(f"  selected_codes: {nic.selected_codes}")
        else:
            print("  ** NO NIC REVIEW — will use fallback NIC code 62011 **")

        # Simulate snapshot builder
        print()
        print("=" * 60)
        print("SIMULATED SNAPSHOT RESOLUTION")
        print("=" * 60)

        raw_aadhaar = (
            reqs.get("aadhaar_number") or reqs.get("aadhaar")
            or ext_dict.get("aadhaar_number") or ext_dict.get("aadhaar")
        )
        cleaned_aadhaar = re.sub(r"\D", "", raw_aadhaar) if raw_aadhaar else ""
        aadhaar_num = cleaned_aadhaar if len(cleaned_aadhaar) == 12 else DEMO_AADHAAR
        is_demo_a = (aadhaar_num == DEMO_AADHAAR)
        print(f"  raw_aadhaar input:  {repr(raw_aadhaar)}")
        print(f"  cleaned digits:     {repr(cleaned_aadhaar)}")
        print(f"  FINAL aadhaar_num:  {aadhaar_num}")
        print(f"  ** USES DEMO? **    {is_demo_a}")

        raw_pan = (
            reqs.get("pan_number") or reqs.get("pan")
            or ext_dict.get("pan_number") or ext_dict.get("pan")
            or (client.pan_number if client else None)
        )
        cleaned_pan = raw_pan.strip().upper() if raw_pan else ""
        pan_num = cleaned_pan if re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", cleaned_pan) else DEMO_PAN
        is_demo_p = (pan_num == DEMO_PAN)
        print(f"  raw_pan input:      {repr(raw_pan)}")
        print(f"  cleaned_pan:        {repr(cleaned_pan)}")
        print(f"  FINAL pan_num:      {pan_num}")
        print(f"  ** USES DEMO? **    {is_demo_p}")

        aadhaar_name = (
            reqs.get("aadhaar_name")
            or ext_dict.get("aadhaar_name")
            or ext_dict.get("applicant_name")
            or (client.applicant_name if client else None)
            or "C KANAKARAJ"
        )
        is_demo_name = (aadhaar_name == "C KANAKARAJ")
        print(f"  aadhaar_name:       {aadhaar_name}")
        print(f"  ** USES DEMO? **    {is_demo_name}")

        # Summary
        print()
        print("=" * 60)
        print("VERDICT")
        print("=" * 60)
        problems = []
        if is_demo_a:
            problems.append("Aadhaar -> DEMO (no valid 12-digit aadhaar stored)")
        if is_demo_p:
            problems.append("PAN -> DEMO (no valid PAN stored)")
        if is_demo_name:
            problems.append("Aadhaar Name -> DEMO (no name found)")
        if not addr:
            problems.append("Official Address -> ALL DEMO (no OfficialAddress row)")
        if not units:
            problems.append("Units -> EMPTY (no ApplicationUnit rows)")
        if not nic:
            problems.append("NIC code -> DEMO 62011 (no NicReview)")
        if problems:
            print("  MOCK/DEMO DATA WILL BE USED FOR:")
            for p in problems:
                print(f"    - {p}")
        else:
            print("  All fields resolve to actual customer data.")

asyncio.run(full_trace())
