"""Playwright end-to-end checks (HTML report + trace are uploaded by the workflow)."""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_e2e_index_renders_seeded_companies(page: Page, base_url: str):
    page.goto(base_url + "/", wait_until="domcontentloaded")
    expect(page.locator("#page-title")).to_have_text(re.compile("会员空间"))
    page.wait_for_selector("body[data-ready='1']", timeout=15_000)
    count = page.locator("#company-count")
    expect(count).not_to_have_text("…")
    assert int(count.inner_text()) > 0
    expect(page.locator(".company-row").first).to_be_visible()


@pytest.mark.e2e
def test_e2e_no_console_errors(page: Page, base_url: str):
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.goto(base_url + "/", wait_until="networkidle")
    page.wait_for_selector("body[data-ready='1']", timeout=15_000)
    assert errors == [], errors
