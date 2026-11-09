import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPEC).resolve().parents[1]
# Package layout: frontend/dist, third-party/ffmpeg, models/asr, models/vad, models/punc.
SOURCE = Path(os.environ.get("BLUEFRAME_RESOURCE_SOURCE", ROOT.parent)).resolve()
GENERATED = ROOT / "packaging" / "generated"
LEGACY_INTERNAL = SOURCE / "_internal"

asr_name = "speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
vad_name = "speech_fsmn_vad_zh-cn-16k-common-pytorch"
punc_name = "punc_ct-transformer_zh-cn-common-vocab272727-pytorch"

datas = [
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    (str(ROOT / "backend" / "alembic"), "backend/alembic"),
    (str(ROOT / "backend" / "alembic.ini"), "backend"),
    (str(SOURCE / "_internal" / "ffmpeg" / "bin"), "third-party/ffmpeg/bin"),
    (str(SOURCE / "_internal" / "ffmpeg" / "LICENSE"), "third-party/ffmpeg"),
    (str(SOURCE / "model" / "hub" / "iic" / asr_name), "models/asr"),
    (str(SOURCE / "model" / "hub" / "iic" / vad_name), "models/vad"),
    (str(SOURCE / "model" / "hub" / "iic" / punc_name), "models/punc"),
    (str(GENERATED / "resource-manifest.json"), "."),
]
binaries = []
hiddenimports = collect_submodules("blueframe") + collect_submodules("blueframe_desktop")
for package in ("funasr", "torch", "torchaudio", "soundfile", "webview", "uvicorn", "alembic"):
    package_datas, package_bins, package_hidden = collect_all(package)
    datas += package_datas; binaries += package_bins; hiddenimports += package_hidden

analysis = Analysis(
    [str(ROOT / "packaging" / "entrypoint.py")],
    pathex=[str(ROOT / "backend"), str(ROOT / "desktop")],
    binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="BlueFrameStudio", console=False, icon=None)
collect = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False, name="BlueFrameStudio")
