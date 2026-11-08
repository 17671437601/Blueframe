from __future__ import annotations


PROMPT_VERSION = "story-v1"


def story_analysis_prompt(transcript: str, duration_ms: int) -> dict[str, object]:
    return {
        "instruction": (
            "分析短剧字幕，提取剧情摘要、人物、冲突、高能点与可剪辑片段。"
            "所有时间必须来自字幕，不得超出媒体时长；高能分数为 0 到 100。"
        ),
        "transcript": transcript,
        "media_duration_ms": duration_ms,
        "prompt_version": PROMPT_VERSION,
    }
