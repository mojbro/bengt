"""Scheduler factory. Started by the lifespan; the actual fire callable
lives in `app.scheduler_runner` so that module dependencies are kept tidy.

UTC throughout so triggers are unambiguous; the frontend formats for the
user's local zone when displaying.
"""

from datetime import timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.scheduler_runner import fire_scheduled_job as _fire_scheduled_job


def create_scheduler() -> AsyncIOScheduler:
    return AsyncIOScheduler(timezone=timezone.utc)


# Re-export so existing call sites that imported this name keep working.
# scheduler_tools adds jobs with this as the callable.
job_fire = _fire_scheduled_job

# Backwards-compat alias for anything still referencing the pre-step-14 name.
job_fire_placeholder = _fire_scheduled_job
