from __future__ import annotations


PROMPT_VERSION = "story-v2"


def story_analysis_prompt(transcript: str, duration_ms: int) -> dict[str, object]:
    return {
        "instruction": (
            "分析短剧字幕，提取剧情摘要、人物、冲突、高能点与可剪辑片段。"
            "高能点要密：平均每 60-90 秒剧情至少给出 1 个高能点，单段时长 10-45 秒，"
            "每段必须能独立看懂（有起承转合或明确冲突），不要只给 2-3 个。"
            "同一高能点不要重复提交。"
            "所有时间必须来自字幕，不得超出媒体时长；高能分数为 0 到 100，按精彩程度区分。"
        ),
        "transcript": transcript,
        "media_duration_ms": duration_ms,
        "prompt_version": PROMPT_VERSION,
    }
