from blueframe.jobs.models import JobStatus


class InvalidJobTransition(ValueError):
    pass


ALLOWED_TRANSITIONS = {
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.RUNNING: {
        JobStatus.PAUSING,
        JobStatus.CANCELLING,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.INTERRUPTED,
    },
    JobStatus.PAUSING: {JobStatus.PAUSED, JobStatus.FAILED, JobStatus.INTERRUPTED},
    JobStatus.PAUSED: {JobStatus.QUEUED, JobStatus.CANCELLING},
    JobStatus.CANCELLING: {
        JobStatus.CANCELLED,
        JobStatus.FAILED,
        JobStatus.INTERRUPTED,
    },
    JobStatus.INTERRUPTED: {JobStatus.QUEUED, JobStatus.FAILED},
}


def ensure_transition(source: JobStatus, target: JobStatus) -> None:
    if target not in ALLOWED_TRANSITIONS.get(source, set()):
        raise InvalidJobTransition(f"invalid job transition: {source.value} -> {target.value}")
