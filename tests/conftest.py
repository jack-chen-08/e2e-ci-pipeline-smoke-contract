"""Shared fixtures. The stack is already running (compose in CI, docker compose locally)."""
from __future__ import annotations

import os

import httpx
import pytest

BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:18000")
ORG_ID = "11111111-1111-1111-1111-111111111111"
SITE_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def api() -> httpx.Client:
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        yield client


@pytest.fixture(scope="session")
def org_site() -> tuple[str, str]:
    return ORG_ID, SITE_ID
