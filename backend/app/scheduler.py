"""Scheduler lifecycle.

Step 6 only stands this up — `create_scheduler()` returns an unstarted
AsyncIOScheduler so the agent can add/list/cancel jobs. Step 14 adds
`scheduler.start()` and wires job firing to invoke the agent loop.

UTC throughout to keep the semantics unambiguous; the frontend formats for
the user's local zone when displaying.
"""

from datetime import timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler


def create_scheduler() -> AsyncIOScheduler:
    return AsyncIOScheduler(timezone=timezone.utc)


async def job_fire_placeholder(instruction: str) -> None:
    """Step 14 replaces this with real agent invocation.

    Kept as a module-level async callable so scheduled jobs can reference
    it by attribute name. Never fires in step 6 because we don't start the
    scheduler.
    """
    # Intentionally a no-op until step 14.
    return None
