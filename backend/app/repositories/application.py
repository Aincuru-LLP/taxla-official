from typing import List, Optional
import uuid
import hashlib
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.domain import Application, Client, ApplicationUnit, OfficialAddress
from app.models.state import ApplicationState
from app.schemas.application import ApplicationCreate, ApplicationUpdate


def _utc_now() -> datetime:
    """Timezone-aware UTC now. Replaces datetime.utcnow() (deprecated in 3.12+)."""
    return datetime.now(timezone.utc)

class ApplicationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_client_by_pan(self, pan_number: str) -> Optional[Client]:
        stmt = select(Client).where(Client.pan_number == pan_number)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_application(self, obj_in: ApplicationCreate, user_id: Optional[uuid.UUID] = None) -> Application:
        # 1. Enforce Client Uniqueness by PAN
        client = await self.get_client_by_pan(obj_in.pan_number)
        if not client:
            # Create new client
            client = Client(
                branch_id=obj_in.branch_id,
                business_name=obj_in.business_name,
                applicant_name=obj_in.applicant_name,
                mobile_number=obj_in.mobile_number,
                email=obj_in.email,
                pan_number=obj_in.pan_number,
                aadhaar_number_hash=hashlib.sha256(obj_in.aadhaar_number.encode()).hexdigest(),
                gender=obj_in.gender,
                social_category=obj_in.social_category,
                divyang_status=obj_in.divyang_status
            )
            self.db.add(client)
            await self.db.flush() # flush to get client.id

        # 2. Generate Application Number
        year_month = _utc_now().strftime("%Y-%m")
        # In a real system, you'd use a sequence or lock. For now, simple random string or UUID prefix
        app_number = f"UDYAM-{year_month}-{str(uuid.uuid4())[:8].upper()}"

        # 3. Create Application
        application = Application(
            client_id=client.id,
            branch_id=obj_in.branch_id,
            application_number=app_number,
            workflow_type=obj_in.workflow_type,
            status=ApplicationState.NEW.value,
            assigned_to=user_id
        )
        self.db.add(application)
        await self.db.commit()
        await self.db.refresh(application)
        return application

    async def get_application(self, application_id: uuid.UUID) -> Optional[Application]:
        stmt = select(Application).where(Application.id == application_id).options(
            selectinload(Application.client),
            selectinload(Application.official_address),
            selectinload(Application.units),
            selectinload(Application.workflow)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_applications(
        self,
        skip: int = 0,
        limit: int = 20,
        *,
        branch_id: Optional[uuid.UUID] = None,
    ) -> List[Application]:
        """List applications, optionally filtered to a single branch.

        ``branch_id=None`` means "all branches" (SUPER_ADMIN only — enforced
        in the API layer).
        """
        stmt = select(Application).offset(skip).limit(limit)
        if branch_id is not None:
            stmt = stmt.where(Application.branch_id == branch_id)
        stmt = stmt.options(
            selectinload(Application.client),
            selectinload(Application.official_address),
            selectinload(Application.units),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_application(self, application_id: uuid.UUID, obj_in: ApplicationUpdate) -> Optional[Application]:
        application = await self.get_application(application_id)
        if not application:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        
        # Handle deep updates for nested objects (official_address, units)
        official_address_data = update_data.pop("official_address", None)
        units_data = update_data.pop("units", None)

        # Update scalar fields on application
        if update_data:
            for field, value in update_data.items():
                setattr(application, field, value)

        # Update Official Address
        if official_address_data is not None:
            if application.official_address:
                for field, value in official_address_data.items():
                    setattr(application.official_address, field, value)
            else:
                new_address = OfficialAddress(application_id=application.id, **official_address_data)
                self.db.add(new_address)

        # Update Units (For simplicity, replacing all units if provided in update)
        if units_data is not None:
            # Delete existing units
            for existing_unit in application.units:
                await self.db.delete(existing_unit)
            application.units.clear()
            # Add new units
            for unit_data in units_data:
                new_unit = ApplicationUnit(application_id=application.id, **unit_data)
                self.db.add(new_unit)

        await self.db.commit()
        await self.db.refresh(application)
        
        return await self.get_application(application.id)
