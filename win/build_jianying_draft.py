#!/usr/bin/env python3
"""Build a Jianying draft for 《老汤》ep01.

Uses the already-conformed 90 s master as the picture track (so the freeze-filled
tail of the six over-long units stays consistent with assemble.py), layers the
six VO wavs at their slot starts, and imports the SRT captions.

Run with the repo-local venv:
    win\\venv_jianying\\Scripts\\python.exe win\\build_jianying_draft.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from pyJianYingDraft import (
    AudioMaterial,
    AudioSegment,
    DraftFolder,
    Timerange,
    TrackSpec,
    TrackType,
    VideoMaterial,
    VideoSegment,
    trange_seconds,
)

ROOT = Path(__file__).resolve().parent.parent
EP = ROOT / "work" / "laotang_ep01"
CONFORM = EP / "cut" / "laotang_ep01_conform.mp4"
VO_DIR = EP / "vo"
SRT = EP / "cut" / "laotang_ep01.srt"
DRAFTS_ROOT = EP / "jianying_drafts"
DRAFT_NAME = "laotang_ep01"

# VO slot starts (seconds) per newsession1.md §6.5; durations from the wavs.
VO_SLOTS = {
    "vo01_sunian_vo.wav": 0.0,
    "vo02_sujianguo.wav": 11.0,
    "vo03_sunian_line.wav": 33.0,
    "vo04_xiaoman.wav": 56.0,
    "vo05_sunian_huoguo.wav": 57.9,
    "vo06_guyan.wav": 76.0,
}


def wav_duration(path: Path) -> float:
    import wave

    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def main() -> None:
    if not CONFORM.is_file():
        raise SystemExit(f"missing conform master: {CONFORM}")
    if not SRT.is_file():
        raise SystemExit(f"missing srt: {SRT}")

    DRAFTS_ROOT.mkdir(parents=True, exist_ok=True)
    folder = DraftFolder(str(DRAFTS_ROOT))
    if folder.has_draft(DRAFT_NAME):
        folder.remove(DRAFT_NAME)
    script = folder.create_draft(DRAFT_NAME, width=1080, height=1920, fps=24)

    # Tracks must be created before segments can be added.
    script.append_track(TrackSpec(TrackType.video, "video"))
    script.append_track(TrackSpec(TrackType.audio, "audio"))

    # Picture track: the finished conform master as one 90 s segment.
    video_material = VideoMaterial(str(CONFORM))
    video_seg = VideoSegment(video_material, trange_seconds(0, duration=90))
    script.add_segment(video_seg, track="video")

    # Voice track.
    for wav_name, start in VO_SLOTS.items():
        wav_path = VO_DIR / wav_name
        if not wav_path.is_file():
            raise SystemExit(f"missing wav: {wav_path}")
        dur = wav_duration(wav_path)
        audio_material = AudioMaterial(str(wav_path))
        audio_seg = AudioSegment(audio_material, trange_seconds(start, duration=dur))
        script.add_segment(audio_seg, track="audio")

    # Captions.
    script.import_srt(str(SRT), track_name="字幕")

    script.save()
    print(f"draft written: {DRAFTS_ROOT / DRAFT_NAME}")
    print(f"duration: {script.duration / 1e6:.3f}s")


if __name__ == "__main__":
    main()