from datetime import datetime, timezone

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.api.deps import require_auth

router = APIRouter(
    prefix="/api/scheduler",
    tags=["scheduler"],
    dependencies=[Depends(require_auth)],
)


class ScheduledJobOut(BaseModel):
    id: str
    instruction: str
    next_run: datetime | None


def get_scheduler(request: Request) -> AsyncIOScheduler:
    return request.app.state.scheduler


def _next_run(job) -> datetime | None:
    nt = getattr(job, "next_run_time", None)
    if nt is not None:
        return nt
    try:
        return job.trigger.get_next_fire_time(None, datetime.now(timezone.utc))
    except Exception:
        return None


def _job_to_out(job) -> ScheduledJobOut:
    return ScheduledJobOut(
        id=job.id,
        instruction=str(job.kwargs.get("instruction") or ""),
        next_run=_next_run(job),
    )


@router.get("/jobs", response_model=list[ScheduledJobOut])
def list_jobs(
    scheduler: AsyncIOScheduler = Depends(get_scheduler),
) -> list[ScheduledJobOut]:
    return [_job_to_out(j) for j in scheduler.get_jobs()]


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_job(
    job_id: str,
    scheduler: AsyncIOScheduler = Depends(get_scheduler),
) -> None:
    try:
        scheduler.remove_job(job_id)
    except JobLookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no job with id {job_id!r}",
        ) from exc
