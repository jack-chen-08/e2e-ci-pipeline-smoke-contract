"""Smoke suite — the checks that must pass before a PR can merge.

Case ids are stable (`smoke_health`, `smoke_company_create`, …) because the nightly
failure summary quotes the first ten failing case ids.
"""
from __future__ import annotations

import uuid

import pytest


@pytest.mark.smoke
def test_smoke_health(api):
    response = api.get("/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] is True and body["redis"] is True


@pytest.mark.smoke
def test_smoke_company_list_is_seeded(api):
    response = api.get("/api/v1/companies", params={"limit": 100})
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) > 0, "seed.py --scenario baseline should have created companies"
    assert {"id", "name", "industry", "contact_count"} <= set(rows[0])


@pytest.mark.smoke
def test_smoke_company_create_and_read(api, org_site):
    org_id, site_id = org_site
    payload = {
        "name": f"Fictional Smoke Co {uuid.uuid4().hex[:6]}",
        "org_id": org_id,
        "site_id": site_id,
        "industry": "software",
        "employee_count": 12,
    }
    created = api.post("/api/v1/companies", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == payload["name"]
    assert body["contact_count"] == 0

    fetched = api.get(f"/api/v1/companies/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


@pytest.mark.smoke
def test_smoke_company_validation_rejects_empty_name(api, org_site):
    org_id, site_id = org_site
    response = api.post(
        "/api/v1/companies",
        json={"name": "", "org_id": org_id, "site_id": site_id},
    )
    assert response.status_code == 422


@pytest.mark.smoke
def test_smoke_unknown_company_is_404(api):
    response = api.get(f"/api/v1/companies/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.smoke
def test_smoke_external_stub_roundtrip(api):
    response = api.get("/api/v1/external/ping")
    assert response.status_code == 200, response.text
    assert response.json()["stub"]["status"] == "ok"


@pytest.mark.smoke
def test_smoke_contacts_of_created_company_are_listed(api, org_site):
    org_id, site_id = org_site
    created = api.post(
        "/api/v1/companies",
        json={"name": f"Fictional Contact Host {uuid.uuid4().hex[:6]}", "org_id": org_id, "site_id": site_id},
    )
    assert created.status_code == 201
    company_id = created.json()["id"]
    contacts = api.get(f"/api/v1/companies/{company_id}/contacts")
    assert contacts.status_code == 200
    assert contacts.json() == []
