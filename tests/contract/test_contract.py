"""Contract checks: responses must match the OpenAPI document the backend publishes.

No third-party schema library: the served OpenAPI document *is* the contract, and these
tests assert (a) the documented paths exist, (b) every response key is a documented
property, (c) every documented required property is present, (d) status codes match.
"""
from __future__ import annotations

import uuid

import pytest

DOCUMENTED_PATHS = {
    "/health",
    "/api/v1/companies",
    "/api/v1/companies/{company_id}",
    "/api/v1/companies/{company_id}/contacts",
    "/api/v1/external/ping",
}


@pytest.fixture(scope="module")
def spec(api):
    response = api.get("/openapi.json")
    assert response.status_code == 200, response.text
    return response.json()


def _resolve(spec: dict, ref: str) -> dict:
    assert ref.startswith("#/"), ref
    node = spec
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _schema_of(spec: dict, node: dict) -> dict:
    return _resolve(spec, node["$ref"]) if "$ref" in node else node


@pytest.mark.contract
def test_contract_documents_expected_paths(spec):
    missing = DOCUMENTED_PATHS - set(spec["paths"])
    assert not missing, f"undocumented endpoints: {sorted(missing)}"


@pytest.mark.contract
def test_contract_company_list_matches_schema(spec, api):
    schema = _schema_of(spec, spec["paths"]["/api/v1/companies"]["get"]["responses"]["200"]
                        ["content"]["application/json"]["schema"])
    item = _schema_of(spec, schema["items"])
    properties = set(item["properties"])
    required = set(item.get("required", []))

    rows = api.get("/api/v1/companies", params={"limit": 5}).json()
    assert rows, "seeded baseline should not be empty"
    for row in rows:
        assert set(row) <= properties, f"undocumented fields: {set(row) - properties}"
        assert required <= set(row), f"missing required fields: {required - set(row)}"


@pytest.mark.contract
def test_contract_create_response_and_status(spec, api, org_site):
    org_id, site_id = org_site
    post = spec["paths"]["/api/v1/companies"]["post"]
    assert "201" in post["responses"], "create must be documented as 201"

    response = api.post(
        "/api/v1/companies",
        json={"name": f"Fictional Contract Co {uuid.uuid4().hex[:6]}", "org_id": org_id, "site_id": site_id},
    )
    assert response.status_code == 201
    schema = _schema_of(spec, post["responses"]["201"]["content"]["application/json"]["schema"])
    body = response.json()
    assert set(body) <= set(schema["properties"])
    assert set(schema.get("required", [])) <= set(body)


@pytest.mark.contract
def test_contract_error_shape_is_detail(spec, api):
    response = api.get(f"/api/v1/companies/{uuid.uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body, body
    assert isinstance(body["detail"], str)


@pytest.mark.contract
def test_contract_health_schema(spec, api):
    schema = spec["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert "properties" in schema, "health response schema should be inline"
    body = api.get("/health").json()
    assert set(schema.get("required", [])) <= set(body)
    assert set(body) <= set(schema["properties"])
