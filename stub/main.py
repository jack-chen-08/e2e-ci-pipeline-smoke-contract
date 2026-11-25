"""External dependency stub — stands in for the customer-side ERP until S2-INFRA lands.

Integration point (also listed in README): app/main.py calls GET {EXTERNAL_STUB_URL}/ping.
"""
from __future__ import annotations

import os

from fastapi import FastAPI

app = FastAPI(title="External dependency stub", version="0.1.0")


@app.get("/ping")
def ping() -> dict:
    return {"status": "ok", "stub": "erp", "version": app.version}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8081")))
