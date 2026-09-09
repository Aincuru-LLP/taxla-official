"""
Seed Script: Creates default Branch, Super Admin, and Operator users.
Run: python -m scripts.seed_data
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.domain import Base, Branch, User

engine = create_engine(settings.SYNC_DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

def seed():
    with Session() as db:
        # Check if already seeded
        existing_branch = db.execute(select(Branch).where(Branch.code == "TAXLA-HQ")).scalar_one_or_none()
        if existing_branch:
            print("[OK] Seed data already exists. Skipping.")
            return

        # Create Branch
        branch = Branch(
            name="Taxla Headquarters",
            code="TAXLA-HQ",
            address="Mumbai, Maharashtra, India",
            status="ACTIVE"
        )
        db.add(branch)
        db.flush()
        print(f"[OK] Branch created: {branch.name} ({branch.code})")

        # Create Super Admin
        admin = User(
            branch_id=branch.id,
            role="SUPER_ADMIN",
            name="Taxla Admin",
            email="admin@taxla.com",
            password_hash=get_password_hash("Admin@123"),
            status="ACTIVE"
        )
        db.add(admin)
        print(f"[OK] Super Admin created: admin@taxla.com / Admin@123")

        # Create Operator
        operator = User(
            branch_id=branch.id,
            role="OPERATOR",
            name="Taxla Operator",
            email="operator@taxla.com",
            password_hash=get_password_hash("Operator@123"),
            status="ACTIVE"
        )
        db.add(operator)
        print(f"[OK] Operator created: operator@taxla.com / Operator@123")

        # Create Reviewer
        reviewer = User(
            branch_id=branch.id,
            role="REVIEWER_AUDITOR",
            name="Taxla Reviewer",
            email="reviewer@taxla.com",
            password_hash=get_password_hash("Reviewer@123"),
            status="ACTIVE"
        )
        db.add(reviewer)
        print(f"[OK] Reviewer created: reviewer@taxla.com / Reviewer@123")

        db.commit()
        print("\n[SUCCESS] Seed data committed successfully!")

if __name__ == "__main__":
    seed()
