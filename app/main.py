"""Member-space backend — the surface the CI gate exercises.

Deliberately small: health, a company CRUD slice, one call through to the external
dependency stub, and an HTML page that the Playwright smoke test drives.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import httpx
import redis
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Contact, MemberCompany, SessionLocal

app = FastAPI(title="Member Space Backend (CI drill)", version="0.3.0")
TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    org_id: uuid.UUID
    site_id: uuid.UUID | None = None
    industry: str | None = Field(default=None, max_length=64)
    employee_count: int = Field(default=0, ge=0)


class CompanyOut(CompanyIn):
    id: uuid.UUID
    contact_count: int
    created_at: datetime
    updated_at: datetime


class HealthOut(BaseModel):
    status: str
    db: bool
    redis: bool
    version: str


@app.get("/health", response_model=HealthOut)
def health(session: Session = Depends(get_session)) -> HealthOut:
    db_ok = True
    try:
        session.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover - reported instead of raised
        db_ok = False
    try:
        redis_ok = redis.Redis.from_url(settings.redis_url, socket_timeout=2).ping()
    except Exception:  # pragma: no cover
        redis_ok = False
    if not (db_ok and redis_ok):
        raise HTTPException(status_code=503, detail={"db": db_ok, "redis": redis_ok})
    return HealthOut(status="ok", db=db_ok, redis=bool(redis_ok), version=app.version)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (TEMPLATES / "index.html").read_text(encoding="utf-8")


@app.get("/api/v1/companies", response_model=list[CompanyOut])
def list_companies(limit: int = 20, session: Session = Depends(get_session)):
    rows = session.scalars(
        select(MemberCompany)
        .where(MemberCompany.deleted_at.is_(None))
        .order_by(MemberCompany.name)
        .limit(min(limit, 100))
    ).all()
    return rows


@app.post("/api/v1/companies", response_model=CompanyOut, status_code=201)
def create_company(payload: CompanyIn, session: Session = Depends(get_session)):
    company = MemberCompany(**payload.model_dump(), contact_count=0)
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


@app.get("/api/v1/companies/{company_id}", response_model=CompanyOut)
def get_company(company_id: uuid.UUID, session: Session = Depends(get_session)):
    company = session.get(MemberCompany, company_id)
    if company is None or company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="company_not_found")
    return company


@app.get("/api/v1/companies/{company_id}/contacts")
def list_contacts(company_id: uuid.UUID, session: Session = Depends(get_session)):
    rows = session.scalars(
        select(Contact).where(Contact.company_id == company_id, Contact.deleted_at.is_(None))
    ).all()
    return [
        {"id": str(c.id), "full_name": c.full_name, "title": c.title, "phone": c.phone}
        for c in rows
    ]


@app.get("/api/v1/external/ping")
def external_ping() -> dict:
    """Round-trip through the external dependency stub (integration point, see README)."""
    try:
        response = httpx.get(f"{settings.external_stub_url}/ping", timeout=5)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"external_stub_unreachable: {exc}") from exc
    return {"stub": response.json()}
