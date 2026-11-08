from __future__ import annotations

import asyncio
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from blueframe.live.platform import LivePlatformAdapter, StreamSource
from blueframe.live.repository import RecordingRepository


def build_recording_command(ffmpeg: Path, playback_url: str, output_root: Path, *, segment_seconds: int, start_number: int) -> list[str]:
    if segment_seconds < 5: raise ValueError("live segment duration must be at least five seconds")
    return [
        str(ffmpeg), "-hide_banner", "-y",
        "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_at_eof", "1", "-reconnect_delay_max", "10",
        "-i", playback_url, "-map", "0:v?", "-map", "0:a?", "-c", "copy",
        "-f", "segment", "-segment_time", str(segment_seconds), "-segment_start_number", str(start_number),
        "-reset_timestamps", "1", "-segment_format", "matroska", str(output_root / "segment-%06d.mkv"),
    ]


class RecorderProcess(Protocol):
    pid: int
    def poll(self): ...
    def stop(self) -> None: ...


class RecorderLauncher(Protocol):
    def start(self, command: list[str]) -> RecorderProcess: ...


class _SubprocessRecorder:
    def __init__(self, process: subprocess.Popen) -> None: self.process = process
    @property
    def pid(self): return self.process.pid
    def poll(self): return self.process.poll()
    def stop(self) -> None:
        if self.process.poll() is not None: return
        try:
            if self.process.stdin: self.process.stdin.write("q\n"); self.process.stdin.flush()
            self.process.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            self.process.terminate()
            try: self.process.wait(timeout=5)
            except subprocess.TimeoutExpired: self.process.kill(); self.process.wait(timeout=5)


class SubprocessRecorderLauncher:
    def start(self, command: list[str]) -> RecorderProcess:
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return _SubprocessRecorder(process)


class RecordingEngine:
    def __init__(self, repository: RecordingRepository, adapter: LivePlatformAdapter, launcher: RecorderLauncher, ffmpeg: Path, *, segment_seconds: int = 60, clock=lambda: datetime.now(UTC)) -> None:
        self.repository, self.adapter, self.launcher, self.ffmpeg = repository, adapter, launcher, ffmpeg
        self.segment_seconds, self.clock = segment_seconds, clock
        self.processes: dict[str, RecorderProcess] = {}
        self.output_roots: dict[str, Path] = {}

    def start(self, session_id: str, output_root: Path) -> None:
        session = self.repository.get(session_id)
        if session is None or not session.intent_active: raise ValueError("recording intent is inactive")
        output_root.mkdir(parents=True, exist_ok=True)
        resolved = asyncio.run(self.adapter.resolve(StreamSource(
            platform=session.platform.value, source_reference=session.source_reference, display_name=session.display_name,
        )))
        if resolved.expires_at is not None and resolved.expires_at <= self.clock():
            raise RuntimeError("authorized playback URL has expired")
        sequence_numbers = [item.sequence for item in self.repository.list_segments(session_id)]
        sequence_numbers.extend(_sequence(path) for path in output_root.glob("segment-*.mkv") if _sequence(path) is not None)
        start_number = max(sequence_numbers, default=-1) + 1
        command = build_recording_command(
            self.ffmpeg, resolved.playback_url, output_root,
            segment_seconds=self.segment_seconds, start_number=start_number,
        )
        try: process = self.launcher.start(command)
        except Exception as error:
            raise RuntimeError(redact_stream_secret(str(error), resolved.playback_url)) from error
        self.processes[session_id], self.output_roots[session_id] = process, output_root
        self.repository.mark_recording(session_id, process.pid)

    def poll_and_reconnect(self, session_id: str) -> bool:
        session, process = self.repository.get(session_id), self.processes.get(session_id)
        if session is None or not session.intent_active or process is None or process.poll() is None: return False
        self.repository.mark_reconnecting(session_id)
        self.processes.pop(session_id, None)
        self.start(session_id, self.output_roots[session_id])
        return True

    def stop(self, session_id: str) -> None:
        process = self.processes.pop(session_id, None)
        if process is not None: process.stop()
        self.repository.stop_intent(session_id)

    def reconnect(self, session_id: str) -> None:
        process = self.processes.get(session_id)
        if process is not None: process.stop()
        self.poll_and_reconnect(session_id)


def redact_stream_secret(message: str, playback_url: str) -> str:
    redacted = message.replace(playback_url, "[redacted-stream-url]")
    return re.sub(r"(?i)(token|sign|auth|key)=([^&\s]+)", r"\1=[redacted]", redacted)[:500]


def _sequence(path: Path) -> int | None:
    match = re.fullmatch(r"segment-(\d{6})\.mkv", path.name)
    return None if match is None else int(match.group(1))
