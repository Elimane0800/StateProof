"""SynchronAIse audit service - FastAPI app.

Routes:
  POST /audit          - run/return an audit (called by the GitHub Action).
  GET  /report/{id}    - stored audit for the Studio.
  POST /fix            - prompt-box patch generation.
  GET  /healthz        - liveness + mode.
"""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import audit, fix, report
from app.core.config import get_settings
from app.core.schema import AuditPayload
from app.services import storage

settings = get_settings()

app = FastAPI(
    title="SynchronAIse Audit Service",
    version=__version__,
    description="CI/CD-native design auditor. Classifies drift as Violation / Noise / Evolution.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(audit.router)
app.include_router(report.router)
app.include_router(fix.router)

# Serve CI-rendered screenshots referenced by screenshot_url.
settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=str(settings.artifacts_dir)), name="artifacts")


@app.on_event("startup")
def _seed_mock() -> None:
    """Seed the demo audit so /report is never empty during development."""
    if not settings.mock_path.exists():
        return
    data = json.loads(settings.mock_path.read_text(encoding="utf-8"))
    payload = AuditPayload.model_validate(data)
    if storage.load(payload.audit_id) is None:
        storage.save(payload)


def _health_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "version": __version__,
        "mock_mode": settings.mock_mode,
        "stored_audits": storage.list_ids(),
    }


@app.get("/health")
def health() -> dict[str, object]:
    """Liveness/readiness probe for deploy scripts and Kubernetes."""
    return _health_payload()


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return _health_payload()
