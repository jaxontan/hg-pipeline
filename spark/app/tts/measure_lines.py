#!/usr/bin/env python3
"""Measure the rendered voice lines: intelligibility, pitch, rate, and where the speech sits.

Hashes prove a file is the file. They say nothing about whether 苏建国 sounds like a man who would
say that line, so this script puts numbers next to the judgement:

  * ASR round-trip (faster-whisper) -- transcript vs the script, character error rate
  * median F0 and its 10-90 spread -- is the casting plausible, and are the four voices distinct
  * characters per second -- is a line rushed, or is the slot just longer than the speech
  * lead / tail silence inside the wav -- which is what decides where it goes in the cut

Runs on the Spark under app/venv-tts (never venv/):

    app/venv-tts/bin/python app/tts/measure_lines.py --episode laotang_ep01

Writes work/<episode>/vo/MEASURE.json and prints a table. Read-only on the wavs.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

PUNCT = re.compile(r"[\s，。！？、,.!?;；:：\"'“”‘’「」『』()（）—–\-]+")

# The ASR emits traditional characters for part of these lines (鍋 for 锅, 這 for 这), and an exact
# character comparison scores that as a substitution when the audio is perfectly correct. A pinyin
# comparison would need another package (Rule 3), so normalise the handful that actually occur.
TRAD_TO_SIMP = str.maketrans({
    "鍋": "锅", "這": "这", "麼": "么", "個": "个", "們": "们", "說": "说",
    "點": "点", "還": "还", "開": "开", "來": "来", "會": "会", "對": "对",
    "湯": "汤", "你": "你", "誰": "谁", "經": "经", "現": "现", "為": "为",
})


def norm(text: str) -> str:
    return PUNCT.sub("", text).translate(TRAD_TO_SIMP)


def levenshtein(a: str, b: str) -> int:
    if not a:
        return len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def silence_bounds(audio: np.ndarray, sr: int, floor_db: float = -40.0) -> tuple[float, float]:
    """Seconds of silence before and after the speech, threshold relative to the file's peak."""
    if audio.size == 0:
        return 0.0, 0.0
    peak = float(np.max(np.abs(audio))) or 1.0
    thr = peak * (10 ** (floor_db / 20.0))
    loud = np.flatnonzero(np.abs(audio) > thr)
    if loud.size == 0:
        return 0.0, 0.0
    return loud[0] / sr, (audio.size - 1 - loud[-1]) / sr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--spec", default=None, help="line spec, for text/slot (default work/story/vo_lines_<ep>.json)")
    ap.add_argument("--asr", default="models/asr/faster-whisper-small")
    ap.add_argument("--no-asr", action="store_true")
    # The floor matters: at fmin=60 both a low male voice and a female line with octave errors
    # came back with p10 pinned to exactly 60.0, which reads as data and is really a clamp.
    ap.add_argument("--fmin", type=float, default=45.0)
    ap.add_argument("--fmax", type=float, default=600.0)
    args = ap.parse_args()

    aigc = Path(os.environ.get("AIGC") or Path(__file__).resolve().parents[2]).resolve()
    vo = aigc / "work" / args.episode / "vo"
    manifest = json.loads((vo / "VO_MANIFEST.json").read_text(encoding="utf-8"))

    spec_path = Path(args.spec) if args.spec else aigc / "work" / "story" / f"vo_lines_{args.episode}.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    by_id = {ln["id"]: ln for ln in spec["lines"]}

    import librosa
    import soundfile as sf

    asr = None
    if not args.no_asr:
        from faster_whisper import WhisperModel
        asr_dir = aigc / args.asr
        if not (asr_dir / "model.bin").is_file():
            print(f"WARN: no ASR weights at {asr_dir} -- skipping the round-trip", file=sys.stderr)
        else:
            print(f"loading ASR from {asr_dir.relative_to(aigc)} (cpu/int8) ...", flush=True)
            asr = WhisperModel(str(asr_dir), device="cpu", compute_type="int8")

    rows = []
    for item in manifest["lines"]:
        line_id = item["id"]
        meta = by_id.get(line_id, {})
        path = vo / item["file"]
        audio, sr = sf.read(str(path), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        lead, tail = silence_bounds(audio, sr)
        speech = max(len(audio) / sr - lead - tail, 1e-6)
        text = meta.get("text", "")
        chars = len(norm(text))
        rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
        rms_db = 20 * np.log10(max(rms, 1e-9))

        f0, voiced, _ = librosa.pyin(audio, fmin=args.fmin, fmax=args.fmax, sr=sr, frame_length=1024)
        f0v = f0[voiced & ~np.isnan(f0)]
        f0_med = float(np.median(f0v)) if f0v.size else 0.0
        f0_lo = float(np.percentile(f0v, 10)) if f0v.size else 0.0
        f0_hi = float(np.percentile(f0v, 90)) if f0v.size else 0.0
        # Share of frames an octave or more below the median: if that is large the median is a
        # sub-harmonic and the "pitch" is an artefact, not the speaker.
        sub = float(np.mean(f0v < 0.55 * f0_med)) if f0v.size and f0_med else 0.0

        hyp, cer, cer_err = None, None, None
        if asr is not None:
            # Hand the model samples, not a path: PyAV's container API moved the
            # `metadata_errors` keyword, and faster-whisper 1.2.1 still passes it. Decoding
            # with soundfile + librosa also keeps the resample under our control.
            mono16 = librosa.resample(audio, orig_sr=sr, target_sr=16000)
            segments, info = asr.transcribe(mono16, language="zh", beam_size=5, vad_filter=False)
            hyp = "".join(s.text for s in segments).strip()
            ref_n, hyp_n = norm(text), norm(hyp)
            cer_err = levenshtein(ref_n, hyp_n)
            cer = cer_err / max(len(ref_n), 1)

        slot = meta.get("window")
        rows.append({
            "id": line_id,
            "speaker": meta.get("speaker", item.get("speaker")),
            "text": text,
            "file": item["file"],
            "seconds": round(len(audio) / sr, 3),
            "speech_seconds": round(speech, 3),
            "lead_silence": round(lead, 3),
            "tail_silence": round(tail, 3),
            "chars": chars,
            "chars_per_s": round(chars / speech, 2) if chars else None,
            "f0_median_hz": round(f0_med, 1),
            "f0_p10_hz": round(f0_lo, 1),
            "f0_p90_hz": round(f0_hi, 1),
            "rms_dbfs": round(float(rms_db), 1),
            "slot": slot,
            "slot_seconds": round(slot[1] - slot[0], 2) if slot else None,
            "asr_text": hyp,
            "cer": round(cer, 3) if cer is not None else None,
            "cer_errors": f"{cer_err}/{len(norm(text))}" if cer_err is not None else None,
            "f0_sub_fraction": round(sub, 3),
        })

    print()
    print(f"{'id':5s} {'speaker':8s} {'len':>5s} {'speech':>6s} {'lead':>5s} {'tail':>5s} "
          f"{'ch/s':>5s} {'F0 med':>7s} {'F0 10-90':>12s} {'RMS':>6s} {'CER':>5s}")
    for r in rows:
        print(f"{r['id']:5s} {r['speaker']:8s} {r['seconds']:5.2f} {r['speech_seconds']:6.2f} "
              f"{r['lead_silence']:5.2f} {r['tail_silence']:5.2f} "
              f"{(r['chars_per_s'] if r['chars_per_s'] is not None else 0):5.2f} "
              f"{r['f0_median_hz']:7.1f} {r['f0_p10_hz']:5.1f}-{r['f0_p90_hz']:<5.1f} "
              f"{r['rms_dbfs']:6.1f} "
              f"{(r['cer'] if r['cer'] is not None else float('nan')):5.3f}")

    print("\npitch integrity (large f0_sub = the median is a sub-harmonic, not the voice):")
    for r in rows:
        floor = "AT FLOOR" if r["f0_p10_hz"] <= args.fmin + 0.5 else ""
        print(f"  {r['id']:5s} sub={r['f0_sub_fraction']:.2f} p10={r['f0_p10_hz']:6.1f} {floor}")

    if asr is not None:
        print("\nASR round-trip (expected -> heard):")
        for r in rows:
            # A ratio is meaningless on a two-character line: one character IS 50%. Report the
            # absolute count so the reader can see whether it is a homophone or a different word.
            errs = int(r["cer_errors"].split("/")[0]) if r["cer_errors"] else 0
            mark = "ok  " if errs <= 1 else "CHECK"
            print(f"  {mark} {r['id']}  {r['text']}")
            print(f"        -> {r['asr_text']}   ({r['cer_errors']} chars differ)")

    out = vo / "MEASURE.json"
    out.write_text(json.dumps({"episode": args.episode, "lines": rows}, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out.relative_to(aigc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
