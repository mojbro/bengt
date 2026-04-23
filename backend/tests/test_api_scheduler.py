from datetime import datetime, timedelta, timezone

import pytest
from apscheduler.triggers.date import DateTrigger
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.scheduler import job_fire_placeholder


@pytest.fixture
def settings(tmp_path):
    return Settings(
        vault_path=str(tmp_path / "vault"),
        data_path=str(tmp_path / "data"),
        auth_password="test-pass",
        llm_provider="openai",
        llm_api_key="sk-test",
        llm_model="gpt-4o",
    )


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def authed_client(client):
    assert client.post("/api/auth/login", json={"password": "test-pass"}).status_code == 200
    return client


def _seed_job(client, instruction: str = "ping"):
    scheduler = client.app.state.scheduler
    trigger = DateTrigger(
        run_date=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    return scheduler.add_job(
        job_fire_placeholder, trigger=trigger, kwargs={"instruction": instruction}
    )


def test_scheduler_requires_auth(client):
    assert client.get("/api/scheduler/jobs").status_code == 401
    assert client.delete("/api/scheduler/jobs/x").status_code == 401


def test_list_empty(authed_client):
    r = authed_client.get("/api/scheduler/jobs")
    assert r.status_code == 200
    assert r.json() == []


def test_list_shows_jobs(authed_client):
    job = _seed_job(authed_client, "remind me")
    r = authed_client.get("/api/scheduler/jobs")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["id"] == job.id
    assert data[0]["instruction"] == "remind me"
    assert data[0]["next_run"] is not None


def test_cancel_existing(authed_client):
    job = _seed_job(authed_client)
    r = authed_client.delete(f"/api/scheduler/jobs/{job.id}")
    assert r.status_code == 204
    assert authed_client.get("/api/scheduler/jobs").json() == []


def test_cancel_unknown(authed_client):
    r = authed_client.delete("/api/scheduler/jobs/does-not-exist")
    assert r.status_code == 404
