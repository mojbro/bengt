from datetime import datetime, timedelta, timezone

import pytest

from app.agent import ToolRegistry
from app.agent.scheduler_tools import register_scheduler_tools
from app.scheduler import create_scheduler


@pytest.fixture
def registry_and_scheduler():
    scheduler = create_scheduler()
    reg = ToolRegistry()
    register_scheduler_tools(reg, scheduler)
    yield reg, scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)


async def test_scheduler_tools_registered(registry_and_scheduler):
    reg, _ = registry_and_scheduler
    assert set(reg.names()) == {
        "schedule_job",
        "list_scheduled_jobs",
        "cancel_job",
    }


async def test_schedule_one_off_iso_utc(registry_and_scheduler):
    reg, scheduler = registry_and_scheduler
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    out = await reg.invoke(
        "schedule_job",
        {"when": future, "instruction": "ping"},
    )
    assert "scheduled job" in out
    assert len(scheduler.get_jobs()) == 1


async def test_schedule_one_off_z_suffix(registry_and_scheduler):
    reg, scheduler = registry_and_scheduler
    future = datetime(2099, 1, 1, 9, 0, tzinfo=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    await reg.invoke(
        "schedule_job",
        {"when": future, "instruction": "future ping"},
    )
    assert len(scheduler.get_jobs()) == 1


async def test_schedule_one_off_naive_assumed_utc(registry_and_scheduler):
    from apscheduler.triggers.date import DateTrigger

    reg, scheduler = registry_and_scheduler
    await reg.invoke(
        "schedule_job",
        {"when": "2099-01-01T09:00:00", "instruction": "naive"},
    )
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    trigger = jobs[0].trigger
    assert isinstance(trigger, DateTrigger)
    assert trigger.run_date.tzinfo is not None


async def test_schedule_cron(registry_and_scheduler):
    reg, scheduler = registry_and_scheduler
    out = await reg.invoke(
        "schedule_job",
        {"when": "0 8 * * 1", "instruction": "Monday morning"},
    )
    assert "scheduled job" in out
    assert len(scheduler.get_jobs()) == 1


async def test_schedule_rejects_garbage(registry_and_scheduler):
    reg, _ = registry_and_scheduler
    with pytest.raises(ValueError):
        await reg.invoke(
            "schedule_job",
            {"when": "not a real trigger", "instruction": "nope"},
        )


async def test_list_empty(registry_and_scheduler):
    reg, _ = registry_and_scheduler
    out = await reg.invoke("list_scheduled_jobs", {})
    assert out == "(no scheduled jobs)"


async def test_list_with_jobs(registry_and_scheduler):
    reg, _ = registry_and_scheduler
    await reg.invoke(
        "schedule_job",
        {"when": "2099-01-01T09:00:00Z", "instruction": "ping A"},
    )
    await reg.invoke(
        "schedule_job",
        {"when": "2099-01-02T09:00:00Z", "instruction": "ping B"},
    )
    out = await reg.invoke("list_scheduled_jobs", {})
    assert "ping A" in out
    assert "ping B" in out


async def test_cancel_existing(registry_and_scheduler):
    reg, scheduler = registry_and_scheduler
    await reg.invoke(
        "schedule_job",
        {"when": "2099-01-01T09:00:00Z", "instruction": "to cancel"},
    )
    job_id = scheduler.get_jobs()[0].id
    out = await reg.invoke("cancel_job", {"id": job_id})
    assert "cancelled" in out
    assert len(scheduler.get_jobs()) == 0


async def test_cancel_unknown(registry_and_scheduler):
    reg, _ = registry_and_scheduler
    out = await reg.invoke("cancel_job", {"id": "does-not-exist"})
    assert "no job" in out
