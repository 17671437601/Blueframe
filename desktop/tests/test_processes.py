from __future__ import annotations

import socket
import sys

import pytest

from blueframe_desktop.processes import (
    _ensure_std_streams,
    find_free_port,
    stop_process,
    wait_for_health,
)


class FakeProcess:
    def __init__(self, wait_results: list[object]) -> None:
        self.wait_results = wait_results
        self.terminated = False
        self.killed = False

    def is_alive(self) -> bool:
        return not self.killed and bool(self.wait_results)

    def terminate(self) -> None:
        self.terminated = True

    def join(self, _timeout: float) -> None:
        result = self.wait_results.pop(0) if self.wait_results else None
        if isinstance(result, BaseException):
            raise result

    def kill(self) -> None:
        self.killed = True


def test_find_free_port_is_loopback_bindable() -> None:
    port = find_free_port()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", port))


def test_wait_for_health_retries_and_redacts_token_from_failure() -> None:
    attempts = iter([False, False, True])
    assert wait_for_health("http://127.0.0.1:43210/health", timeout=1, probe=lambda _: next(attempts), sleep=lambda _: None)

    with pytest.raises(RuntimeError) as error:
        wait_for_health("http://127.0.0.1:43210/health", timeout=0, probe=lambda _: False, sleep=lambda _: None)
    assert "token" not in str(error.value).lower()


def test_stop_process_terminates_then_kills_an_orphan() -> None:
    process = FakeProcess([None, None])
    stop_process(process, timeout=0)
    assert process.terminated is True
    assert process.killed is True


def test_ensure_std_streams_restores_windowed_package_children(monkeypatch) -> None:
    monkeypatch.setattr("sys.stdout", None)
    monkeypatch.setattr("sys.stderr", None)

    _ensure_std_streams()

    assert hasattr(sys.stdout, "write")
    assert hasattr(sys.stderr, "write")
