from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop"))
from blueframe_desktop.resources import create_manifest_from_sources


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); source = args.source_root.resolve()
    names = {
        "asr": "speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        "vad": "speech_fsmn_vad_zh-cn-16k-common-pytorch",
        "punc": "punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
    }
    entries = {
        "third-party/ffmpeg/bin/ffmpeg.exe": source / "_internal/ffmpeg/bin/ffmpeg.exe",
        "third-party/ffmpeg/bin/ffprobe.exe": source / "_internal/ffmpeg/bin/ffprobe.exe",
    }
    for alias, name in names.items():
        model = source / "model/hub/iic" / name
        entries[f"models/{alias}/configuration.json"] = model / "configuration.json"
        entries[f"models/{alias}/model.pt"] = model / "model.pt"
    missing = [str(path) for path in entries.values() if not path.is_file()]
    if missing: raise SystemExit("Missing offline resources: " + ", ".join(missing))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(create_manifest_from_sources(entries), ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__": raise SystemExit(main())
