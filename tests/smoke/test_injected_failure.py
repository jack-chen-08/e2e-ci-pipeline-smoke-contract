"""Fault-injection switch used to prove AC2 (a single failing case must block the PR).

Skipped by default so the gate stays green. Run with:
    INJECT_FAILURE=1 pytest tests/smoke/test_injected_failure.py
The workflow job `e2e-gate (fault injection demo)` does exactly that on a throwaway branch.
"""
from __future__ import annotations

import os

import pytest


@pytest.mark.smoke
@pytest.mark.skipif(os.getenv("INJECT_FAILURE") != "1", reason="fault injection disabled")
def test_zz_injected_failure_case(api):
    """Case id quoted by the nightly/failure summaries: test_zz_injected_failure_case."""
    response = api.get("/api/v1/companies", params={"limit": 1})
    assert response.status_code == 200
    # Deliberate assertion failure: the pipeline must go red and the merge must be blocked.
    assert len(response.json()) == 999, "injected failure: expected 999 companies"
