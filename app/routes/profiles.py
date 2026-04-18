from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, func
from app.database import get_db
from app.models import Profile
from app.schemas import ProfileCreate, ProfileResponse, ProfileListItem
from app.services.external_apis import fetch_all
from uuid6 import uuid7
from datetime import datetime, timezone
from typing import Optional

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.post("", status_code=201)
async def create_profile(body: ProfileCreate, db: AsyncSession = Depends(get_db)):
    name = body.name.strip()

    if not name:
        raise HTTPException(
            status_code=400, detail={"status": "error", "message": "Name is required"}
        )


    result = await db.execute(
        select(Profile).where(func.lower(Profile.name) == name.lower())
    )
    existing = result.scalar_one_or_none()

    if existing:
        return {
            "status": "success",
            "message": "Profile already exists",
            "data": ProfileResponse.model_validate(existing),
        }


    enriched = await fetch_all(name)

    profile = Profile(
        id=str(uuid7()),
        name=name.lower(),
        created_at=datetime.now(timezone.utc),
        **enriched
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return {"status": "success", "data": ProfileResponse.model_validate(profile)}


@router.get("")
async def list_profiles(
    gender: Optional[str] = None,
    country_id: Optional[str] = None,
    age_group: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Profile)

    if gender:
        query = query.where(func.lower(Profile.gender) == gender.lower())
    if country_id:
        query = query.where(func.upper(Profile.country_id) == country_id.upper())
    if age_group:
        query = query.where(func.lower(Profile.age_group) == age_group.lower())

    result = await db.execute(query)
    profiles = result.scalars().all()

    return {
        "status": "success",
        "count": len(profiles),
        "data": [ProfileListItem.model_validate(p) for p in profiles],
    }


@router.get("/{id}")
async def get_profile(id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Profile).where(Profile.id == id))
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=404, detail={"status": "error", "message": "Profile not found"}
        )

    return {"status": "success", "data": ProfileResponse.model_validate(profile)}


@router.delete("/{id}", status_code=204)
async def delete_profile(id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Profile).where(Profile.id == id))
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=404, detail={"status": "error", "message": "Profile not found"}
        )

    await db.delete(profile)
    await db.commit()
    return Response(status_code=204)
