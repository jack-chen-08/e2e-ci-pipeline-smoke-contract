#!/usr/bin/env python3
"""Deterministic seed data for the CI pipeline.

    python seed.py --scenario baseline   # 100 member companies / 300 contacts (fictional)
    python seed.py --scenario empty      # wipe both tables

Every value is fictional: names come from a fixed list, phone numbers are masked.
"""
from __future__ import annotations

import argparse
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.db import Contact, MemberCompany, SessionLocal

ORG_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SITE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

INDUSTRIES = ["manufacturing", "logistics", "retail", "software", "construction",
              "finance", "healthcare", "education", "energy", "agriculture"]
TITLES = ["manager", "director", "engineer", "buyer", "founder"]


def wipe() -> None:
    with SessionLocal() as session:
        session.execute(text("TRUNCATE contacts, member_companies CASCADE"))
        session.commit()


def baseline(companies: int = 100, contacts_per_company: int = 3) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    made = 0
    with SessionLocal() as session:
        for idx in range(companies):
            company = MemberCompany(
                id=uuid.uuid5(uuid.NAMESPACE_URL, f"company-{idx}"),
                org_id=ORG_ID,
                site_id=SITE_ID,
                name=f"Fictional Company {idx:04d}",
                industry=INDUSTRIES[idx % len(INDUSTRIES)],
                employee_count=(idx * 7) % 400,
                contact_count=contacts_per_company,
                created_at=now,
                updated_at=now,
            )
            session.add(company)
            session.flush()  # companies must exist before their contacts hit the FK
            for c in range(contacts_per_company):
                session.add(
                    Contact(
                        id=uuid.uuid5(uuid.NAMESPACE_URL, f"contact-{idx}-{c}"),
                        org_id=ORG_ID,
                        site_id=SITE_ID,
                        company_id=company.id,
                        full_name=f"Fictional Contact {idx:04d}-{c}",
                        title=TITLES[(idx + c) % len(TITLES)],
                        phone=f"+1****{idx:04d}{c}",
                        created_at=now,
                        updated_at=now,
                    )
                )
                made += 1
        session.commit()
    return companies, made


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=["baseline", "empty"], default="baseline")
    ap.add_argument("--companies", type=int, default=int(os.getenv("SEED_COMPANIES", "100")))
    ap.add_argument("--contacts-per-company", type=int,
                    default=int(os.getenv("SEED_CONTACTS_PER_COMPANY", "3")))
    args = ap.parse_args()

    wipe()
    if args.scenario == "empty":
        print("scenario=empty: tables truncated")
        return 0
    companies, contacts = baseline(args.companies, args.contacts_per_company)
    print(f"scenario=baseline: member_companies={companies} contacts={contacts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
