from __future__ import annotations


class FfmpegProgressParser:
    def __init__(self, *, duration_ms: int) -> None:
        if duration_ms <= 0:
            raise ValueError("duration must be positive")
        self.duration_ms = duration_ms
        self._buffer = ""

    def feed(self, data: str) -> list[float]:
        self._buffer += data
        lines = self._buffer.split("\n")
        self._buffer = lines.pop()
        progress: list[float] = []
        for line in lines:
            key, separator, value = line.partition("=")
            if not separator:
                continue
            if key in {"out_time_ms", "out_time_us"}:
                try:
                    elapsed_ms = int(value) / 1000
                except ValueError:
                    continue
                progress.append(min(max(elapsed_ms / self.duration_ms * 100, 0), 99.9))
            elif key == "progress" and value == "end":
                progress.append(100.0)
        return progress
