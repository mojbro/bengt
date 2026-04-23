"""Scheduling tools (PRD §4.3 / §4.4). Registered into the agent's ToolRegistry.

The scheduler is created but NOT started in step 6 — jobs are stored and
listable, but they won't fire. Step 14 starts the scheduler and wires job
firing to invoke the agent loop.

`when` accepts either an ISO 8601 datetime (one-off) or a standard 5-field
cron expression (recurring). Auto-detected at the tool boundary so the LLM
only has one field to populate.
"""

from datetime import datetime, timezone
from typing import Any

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.agent.tools import Tool, ToolRegistry
from app.scheduler import job_fire_placeholder


def _parse_trigger(when: str) -> BaseTrigger:
    # ISO 8601 first (support trailing Z for UTC).
    try:
        dt = datetime.fromisoformat(when.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return DateTrigger(run_date=dt)
    except ValueError:
        pass
    # Fall back to cron. Let APScheduler's own validation surface the error.
    try:
        return CronTrigger.from_crontab(when, timezone=timezone.utc)
    except ValueError as exc:
        raise ValueError(
            f"Could not parse `when` as ISO 8601 datetime or cron expression: "
            f"{when!r} ({exc})"
        ) from exc


def _next_run(job) -> str:
    # `next_run_time` is only populated once the scheduler is running; until
    # then (step 14 starts it) fall back to asking the trigger directly.
    nt = getattr(job, "next_run_time", None)
    if nt is None:
        try:
            nt = job.trigger.get_next_fire_time(None, datetime.now(timezone.utc))
        except Exception:
            nt = None
    return nt.isoformat() if nt else "(unknown)"


def _format_job(job) -> str:
    instruction = job.kwargs.get("instruction", "(no instruction)")
    return f"{job.id} | next: {_next_run(job)} | {instruction}"


def register_scheduler_tools(
    registry: ToolRegistry,
    scheduler: AsyncIOScheduler,
) -> None:
    async def schedule_job(args: dict[str, Any]) -> str:
        when = str(args["when"])
        instruction = str(args["instruction"])
        trigger = _parse_trigger(when)
        job = scheduler.add_job(
            job_fire_placeholder,
            trigger=trigger,
            kwargs={"instruction": instruction},
        )
        return f"scheduled job {job.id} — next: {_next_run(job)}"

    async def list_scheduled_jobs(args: dict[str, Any]) -> str:
        jobs = scheduler.get_jobs()
        if not jobs:
            return "(no scheduled jobs)"
        return "\n".join(_format_job(j) for j in jobs)

    async def cancel_job(args: dict[str, Any]) -> str:
        job_id = str(args["id"])
        try:
            scheduler.remove_job(job_id)
            return f"cancelled job {job_id}"
        except JobLookupError:
            return f"no job with id {job_id}"

    registry.register(
        Tool(
            name="schedule_job",
            description=(
                "Schedule a future invocation of yourself. Use for reminders, "
                "recurring check-ins, or conditional future actions. The `instruction` "
                "is a natural-language message you will receive when the job fires."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "when": {
                        "type": "string",
                        "description": (
                            "ISO 8601 UTC datetime (e.g. '2026-04-25T08:00:00Z') for a "
                            "one-off, OR a standard 5-field cron expression "
                            "(e.g. '0 8 * * 1' for 08:00 every Monday)."
                        ),
                    },
                    "instruction": {
                        "type": "string",
                        "description": (
                            "What the agent should do when the job fires, in natural "
                            "language (e.g. 'Remind the user to prepare for the board meeting')."
                        ),
                    },
                },
                "required": ["when", "instruction"],
            },
            fn=schedule_job,
        )
    )
    registry.register(
        Tool(
            name="list_scheduled_jobs",
            description=(
                "List all pending scheduled jobs with their IDs, next run times, "
                "and instructions."
            ),
            parameters={"type": "object", "properties": {}},
            fn=list_scheduled_jobs,
        )
    )
    registry.register(
        Tool(
            name="cancel_job",
            description="Cancel a pending scheduled job by its ID.",
            parameters={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Job ID as returned by schedule_job / list_scheduled_jobs.",
                    },
                },
                "required": ["id"],
            },
            fn=cancel_job,
        )
    )
