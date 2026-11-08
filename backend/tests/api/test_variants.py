from pathlib import Path

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.auth.service import StandaloneAccountService
from blueframe.jobs.repository import JobRepository
from blueframe.projects.models import ProjectType, SourceRegistration
from blueframe.projects.repository import ProjectRepository
from blueframe.variants.repository import VariantBatchRepository


HEADERS = {"X-BlueFrame-Session": "a" * 64}


def test_variant_api_creates_deterministic_batch_and_queues_worker(migrated_session_factory, tmp_path: Path) -> None:
    projects = ProjectRepository(migrated_session_factory)
    project = projects.create(name="Variants", project_type=ProjectType.VARIANTS, root_path=tmp_path, output_relative_path="out", config={}, idempotency_key="variants-api")
    source = projects.add_sources(project.id, [SourceRegistration(relative_path="master.mp4", size_bytes=1, modified_ns=1, content_fingerprint="f")])[0]
    batches = VariantBatchRepository(migrated_session_factory)
    app = create_app(
        session_token="a" * 64, project_repository=projects, variant_batch_repository=batches,
        job_repository=JobRepository(migrated_session_factory), account_service=StandaloneAccountService(),
    )
    with TestClient(app) as client:
        created = client.post(f"/api/v1/projects/{project.id}/variant-batches", headers=HEADERS, json={
            "source_id": source.id, "count": 3, "seed": 42, "width": 720, "height": 1280,
            "idempotency_key": "batch-one",
        })
        listed = client.get(f"/api/v1/projects/{project.id}/variant-batches", headers=HEADERS)
    assert created.status_code == 202
    assert created.json()["job"]["job_type"] == "render_variant_batch"
    assert len(listed.json()[0]["items"]) == 3
    assert "output_path" not in listed.text
