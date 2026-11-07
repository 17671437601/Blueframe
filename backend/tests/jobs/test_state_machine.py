from __future__ import annotations

import importlib

import pytest


def test_transition_matrix_accepts_only_declared_edges() -> None:
    models = importlib.import_module("blueframe.jobs.models")
    machine = importlib.import_module("blueframe.jobs.state_machine")
    status = models.JobStatus
    allowed = {
        (status.QUEUED, status.RUNNING),
        (status.QUEUED, status.CANCELLED),
        (status.RUNNING, status.PAUSING),
        (status.RUNNING, status.CANCELLING),
        (status.RUNNING, status.COMPLETED),
        (status.RUNNING, status.FAILED),
        (status.RUNNING, status.INTERRUPTED),
        (status.PAUSING, status.PAUSED),
        (status.PAUSING, status.FAILED),
        (status.PAUSING, status.INTERRUPTED),
        (status.PAUSED, status.QUEUED),
        (status.PAUSED, status.CANCELLING),
        (status.CANCELLING, status.CANCELLED),
        (status.CANCELLING, status.FAILED),
        (status.CANCELLING, status.INTERRUPTED),
        (status.INTERRUPTED, status.QUEUED),
        (status.INTERRUPTED, status.FAILED),
    }

    for source in status:
        for target in status:
            if (source, target) in allowed:
                machine.ensure_transition(source, target)
            else:
                with pytest.raises(machine.InvalidJobTransition):
                    machine.ensure_transition(source, target)
