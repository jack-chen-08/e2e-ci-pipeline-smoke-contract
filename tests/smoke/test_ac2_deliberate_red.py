"""AC2 demonstration branch: exactly one deliberately failing case.

Purpose: prove that a single red case turns `e2e-gate` red and that the merge
button is then blocked by the `main-require-e2e-gate` ruleset (required status
check). Nothing in this file is meant to be merged — it lives only on the
throwaway branch `ci/demo-red-gate`, so the gate on `main` stays green.
"""
from __future__ import annotations

import pytest


@pytest.mark.smoke
def test_ac2_deliberate_red_case(api):
    response = api.get("/api/v1/companies", params={"limit": 1})
    assert response.status_code == 200
    # The one red case: the gate must fail and the merge must be blocked.
    assert len(response.json()) == 999, "AC2 demo: deliberate failure, expected 999 companies"
