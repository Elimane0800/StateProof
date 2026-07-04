"""SynchronAIse audit service - FastAPI app.

Routes:
  POST /audit          - run/return an audit (called by the GitHub Action).
  GET  /report/{id}    - stored audit for the Studio.
  POST /fix            - prompt-box patch generation.
  GET  /healthz        - liveness + mode.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import audit, fix, inspection, rentals, report
from app.core.config import get_settings, REPO_ROOT
from app.services import demo_loader, registry_store, storage

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
app.include_router(inspection.router)
app.include_router(report.router)
app.include_router(fix.router)
app.include_router(rentals.router)

# Serve CI-rendered screenshots referenced by screenshot_url.
settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=str(settings.artifacts_dir)), name="artifacts")

# Serve demo ground-truth photos when feat/demo is present.
_ground_truth = REPO_ROOT / "demo" / "ground-truth"
if _ground_truth.is_dir():
    app.mount("/demo", StaticFiles(directory=str(_ground_truth)), name="demo")

# Serve uploaded rental videos (video_in_url / video_out_url map here).
settings.uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(settings.uploads_dir)), name="uploads")


@app.on_event("startup")
def _init_registry() -> None:
    """Create the rental registry tables if they do not exist yet."""
    registry_store.init_db()


@app.on_event("startup")
def _seed_mock() -> None:
    """Seed the demo audit so /report is never empty during development."""
    try:
        payload = demo_loader.resolve_mock_payload()
    except Exception:
        return
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
