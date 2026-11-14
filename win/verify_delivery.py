#!/usr/bin/env python3
"""Verify a finished episode from the outside, because Jianying is not installed.

    python win/verify_delivery.py                # everything (master, srt, vo, draft, frames)
    python win/verify_delivery.py --skip-frames  # text and spec checks only, ~1 s
    python win/verify_delivery.py --ep laotang_ep02

`draft_content.json` has never been opened by the app, so "it parses" is not
evidence that the delivery is coherent. This checks the one thing the app would
have told us: do the master, the captions, the voice and the draft describe the
same 90 seconds?

  container   ffprobe is the truth: duration, frames, fps, one audio stream.
  mix         volumedetect proves the audio is not silent; silencedetect proves
              each line is audible *where the caption says it is*.
  captions    the SRT must start on its spec window, cover the wav, and not overlap.
  draft       materials must point at real files, absolutely, inside the repo
              (Rule 4); segment times must equal the spec windows.
  holds       the six freeze-filled tails must be frozen, and the live part must
              not be — a static shot and a freeze are indistinguishable without
              a control pair.

Exit 1 on any FAIL. WARN does not fail the build.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIN = ROOT / "win" / "tools" / "ffmpeg" / "bin"
FFMPEG = BIN / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
FFPROBE = BIN / ("ffprobe.exe" if os.name == "nt" else "ffprobe")

FPS = 24
CLIP_FRAMES = 121
CLIP_SECONDS = CLIP_FRAMES / FPS  # 5.0417
TOL = 0.05
# A freeze-fill repeats one source frame, but the master is CRF-encoded, so the
# repeated frame is re-quantised per frame and decodes *nearly* identical, never
# byte-identical. Measured on ep01: frozen pairs 57–65 dB, live control pairs
# 12–31 dB. 45 dB separates the two cleanly and survives a re-encode at another
# CRF. This is the same lesson as HANDOVER gotcha 11: byte identity is not a guard.
HOLD_PSNR_MIN = 45.0

fails: list[str] = []
warns: list[str] = []


def check(ok: bool, label: str, detail: str) -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  {label:<28} {detail}")
    if not ok:
        fails.append(label)
    return ok


def warn(label: str, detail: str) -> None:
    print(f"WARN  {label:<28} {detail}")
    warns.append(label)


def note(label: str, detail: str) -> None:
    print(f"info  {label:<28} {detail}")


def run(cmd: list[str]) -> str:
    """Run a tool and return combined output; these tools report on stderr."""
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.stdout.decode("utf-8", "replace")


def ffprobe(path: pathlib.Path) -> dict:
    out = run([str(FFPROBE), "-v", "error", "-show_entries",
               "stream=index,codec_type,width,height,r_frame_rate,nb_frames,"
               "duration,sample_rate,channels",
               "-show_entries", "format=duration,size,bit_rate",
               "-of", "json", str(path)])
    return json.loads(out)


def parse_srt(path: pathlib.Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        cues.append({"start": start, "end": end, "text": "\n".join(lines[2:]).strip()})
    return cues


def speech_intervals(video: pathlib.Path, duration: float) -> list[tuple[float, float]]:
    """Complement of silencedetect: where there is actually sound."""
    out = run([str(FFMPEG), "-hide_banner", "-nostats", "-i", str(video),
               "-vn", "-af", "silencedetect=noise=-50dB:d=0.30", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*(-?[\d.]+)", out)]
    silences = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else duration
        silences.append((max(0.0, s), min(duration, e)))
    speech, cursor = [], 0.0
    for s, e in silences:
        if s > cursor:
            speech.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < duration:
        speech.append((cursor, duration))
    return [(s, e) for s, e in speech if e - s > 0.02]


def volume(video: pathlib.Path) -> tuple[float, float]:
    out = run([str(FFMPEG), "-hide_banner", "-nostats", "-i", str(video),
               "-vn", "-af", "volumedetect", "-f", "null", "-"])
    mean = re.search(r"mean_volume:\s*(-?[\d.]+)", out)
    peak = re.search(r"max_volume:\s*(-?[\d.]+)", out)
    if not (mean and peak):
        raise SystemExit("verify: volumedetect produced no numbers")
    return float(mean.group(1)), float(peak.group(1))


def level_db(video: pathlib.Path, t: float, dur: float) -> float:
    """Mean level of one line's window in the master, in dBFS."""
    out = run([str(FFMPEG), "-hide_banner", "-nostats", "-ss", f"{t:.3f}", "-t", f"{dur:.3f}",
               "-i", str(video), "-vn", "-af", "volumedetect", "-f", "null", "-"])
    m = re.search(r"mean_volume:\s*(-?[\d.]+)", out)
    if not m:
        raise SystemExit("verify: volumedetect produced no number for a line window")
    return float(m.group(1))


def frame(video: pathlib.Path, t: float, out: pathlib.Path) -> None:
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                    str(out)], check=True)


def psnr(a: pathlib.Path, b: pathlib.Path) -> float:
    out = run([str(FFMPEG), "-hide_banner", "-nostats", "-i", str(a), "-i", str(b),
               "-lavfi", "psnr", "-f", "null", "-"])
    m = re.search(r"average:\s*(\S+)", out)
    if not m:
        return float("nan")
    return float("inf") if m.group(1).lower() in ("inf", "infinity") else float(m.group(1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", default="laotang_ep01")
    ap.add_argument("--skip-frames", action="store_true")
    args = ap.parse_args()

    ep = ROOT / "work" / args.ep
    master = ep / "cut" / f"{args.ep}_conform.mp4"
    report_p = ep / "cut" / "assemble_report.json"
    srt_p = ep / "cut" / f"{args.ep}.srt"
    spec_p = ROOT / "work" / "story" / f"vo_lines_{args.ep}.json"
    edl_p = ep / "edit.json"
    vo_dir = ep / "vo"
    vo_manifest_p = vo_dir / "VO_MANIFEST.json"
    draft_p = ep / "jianying_drafts" / args.ep / "draft_content.json"

    for p in (master, report_p, srt_p, spec_p, edl_p, vo_manifest_p, draft_p):
        if not p.exists():
            print(f"FAIL  missing input            {p.relative_to(ROOT).as_posix()}")
            return 1

    spec = json.loads(spec_p.read_text(encoding="utf-8"))
    lines = spec["lines"]
    manifest = {l["id"]: l for l in json.loads(vo_manifest_p.read_text(encoding="utf-8"))["lines"]}
    report = json.loads(report_p.read_text(encoding="utf-8"))
    edl = json.loads(edl_p.read_text(encoding="utf-8"))
    units = {u["n"]: u for u in edl["units"]}
    target = float(edl["target_seconds"])

    print(f"verify {args.ep} — {master.relative_to(ROOT).as_posix()}")
    print()

    # ---- container -----------------------------------------------------
    pr = ffprobe(master)
    streams = pr["streams"]
    v = next((s for s in streams if s["codec_type"] == "video"), None)
    audio = [s for s in streams if s["codec_type"] == "audio"]
    fdur = float(pr["format"]["duration"])
    check(v is not None, "container.video", "video stream present" if v else "no video stream")
    check(len(audio) == 1, "container.audio", f"{len(audio)} audio stream(s), expect 1")
    check(abs(fdur - target) <= TOL, "container.duration",
          f"{fdur:.3f} s (target {target:.2f} s, tolerance {TOL})")
    if v:
        w, h = v["width"], v["height"]
        num, den = (int(x) for x in v["r_frame_rate"].split("/"))
        fps = num / den
        frames = int(v.get("nb_frames") or 0)
        check((w, h) == (1080, 1920), "container.frame", f"{w}x{h}")
        check(abs(fps - FPS) < 1e-6, "container.fps", f"{fps:g}")
        check(frames == round(target * FPS), "container.frames",
              f"{frames} frames, expect {round(target * FPS)}")
    if audio:
        a = audio[0]
        note("container.audio_format", f"{a.get('sample_rate')} Hz, {a.get('channels')} ch")
        if int(a.get("sample_rate", 0)) != 48000:
            warn("container.audio_rate", f"{a.get('sample_rate')} Hz — the wavs are 24 kHz; "
                 "the encode resampled. Fine, but record it.")

    # ---- mix -----------------------------------------------------------
    mean_db, peak_db = volume(master)
    check(peak_db > -20.0, "mix.not_silent", f"mean {mean_db:.1f} dBFS, peak {peak_db:.1f} dBFS")
    check(peak_db < -1.0, "mix.headroom", f"peak {peak_db:.1f} dBFS (leave ≥1 dB)")
    speech = speech_intervals(master, fdur)
    note("mix.speech_intervals", f"{len(speech)} non-silent interval(s) over {fdur:.2f} s")

    # Each line: audible inside its window, and its onset where the spec says.
    # The invariant is *faithfulness*, not loudness. Absolute per-window comparison
    # is noisy because AAC smears the first/last tens of ms of every line across
    # the window edge, so the per-line check allows a margin and the global total
    # (below) is the strict one.
    run_id = {l["id"]: l for l in lines}
    for lid, meta in manifest.items():
        sp = run_id[lid]
        w0, w1 = float(sp["window"][0]), float(sp["window"][1])
        dur = float(meta["seconds"])
        wav = vo_dir / meta["file"]
        wav_speech = speech_intervals(wav, dur)
        wav_inside = sum(e - s for s, e in wav_speech)
        lo, hi = w0 - 0.25, w0 + dur + 0.25
        inside = sum(max(0.0, min(e, hi) - max(s, lo)) for s, e in speech)
        check(inside >= 0.80 * wav_inside, f"mix.{lid}.faithful",
              f"{inside:.2f} s of sound near the window vs {wav_inside:.2f} s in the wav")
        if inside / dur >= 0.55:
            note(f"mix.{lid}.coverage", f"{inside / dur:.0%} of {dur:.2f} s is sound")
        else:
            warn(f"mix.{lid}.coverage",
                 f"only {inside / dur:.0%} of {dur:.2f} s is sound — long pauses in the read, "
                 f"not a mix error; listen before changing it")
        onsets = [s for s, _ in speech if s >= w0 - 0.30]
        if onsets:
            off = onsets[0] - w0
            check(abs(off) <= 0.35, f"mix.{lid}.onset", f"first sound {off:+.2f} s from the window start")
        else:
            check(False, f"mix.{lid}.onset", "no sound at or after the window start")

    master_total = sum(e - s for s, e in speech)
    measure_p = vo_dir / "MEASURE.json"
    if measure_p.exists():
        # The strict level check: the mix must reproduce the level the voice pass
        # measured on each wav. This is what caught the mono->stereo -3 dB upmix.
        measured = {m["id"]: m for m in json.loads(measure_p.read_text(encoding="utf-8"))["lines"]}
        for lid, meta in manifest.items():
            sp = run_id[lid]
            w0 = float(sp["window"][0])
            dur = float(meta["seconds"])
            got = level_db(master, w0, dur)
            want = float(measured[lid]["rms_dbfs"])
            check(abs(got - want) <= 1.0, f"mix.{lid}.level",
                  f"{got:.1f} dBFS in the master vs {want:.1f} dBFS measured on the wav")
    else:
        warn("mix.levels", f"no {measure_p.name} — cannot compare levels to the voice pass")
    note("mix.total_sound", f"{master_total:.2f} s above -50 dBFS in the master — a shape, "
                            f"not a gate: silencedetect(d=0.30) ignores gaps under 0.3 s")

    # Nothing may sound outside a declared window.
    stray = [(s, e) for s, e in speech
             if not any(s < float(l["window"][1]) + 0.30 and e > float(l["window"][0]) - 0.30
                        for l in lines)]
    check(not stray, "mix.no_stray_audio",
          "every non-silent interval falls inside a declared window"
          if not stray else f"{len(stray)} interval(s) outside all windows: {stray[:3]}")

    # ---- captions ------------------------------------------------------
    cues = parse_srt(srt_p)
    check(len(cues) == len(lines), "srt.count", f"{len(cues)} cues for {len(lines)} lines")

    def unit_at(t: float) -> dict | None:
        for u in units.values():
            if float(u["in"]) <= t < float(u["out"]):
                return u
        return None

    srt_by_line = {l["id"]: None for l in lines}
    for l in lines:
        cue = min(cues, key=lambda c: abs(c["start"] - float(l["window"][0])))
        srt_by_line[l["id"]] = cue
        w0, w1 = float(l["window"][0]), float(l["window"][1])
        dur = float(manifest[l["id"]]["seconds"])
        cdur = cue["end"] - cue["start"]
        check(abs(cue["start"] - w0) <= 0.001, f"srt.{l['id']}.start",
              f"cue starts {cue['start']:.3f} s, window {w0:.2f} s")
        # The spec window is the contract, and a window may deliberately span a cut:
        # vo01 is a voice-over over units 1–2, so its caption *should* run past the
        # end of unit 1. Crossing a cut is reported; overrunning the window is what
        # fails, with a small tolerance for AAC edge smear.
        u = unit_at(cue["start"])
        if u:
            for uu in units.values():
                b = float(uu["out"])
                if cue["start"] < b < cue["end"]:
                    note(f"srt.{l['id']}.crosses_cut",
                         f"caption crosses the cut at {b:.2f} s — intended if the window "
                         f"[{w0:.2f}, {w1:.2f}] spans it")
        check(cue["end"] <= w1 + 0.15, f"srt.{l['id']}.inside_window",
              f"cue ends {cue['end']:.3f} s, window ends {w1:.2f} s")
        if cue["end"] > w1 + 0.05:
            warn(f"srt.{l['id']}.over_slot",
                 f"cue runs {cue['end'] - w1:+.2f} s past the {w1 - w0:.2f} s slot "
                 f"(target_seconds {l['target_seconds']}, wav {dur:.2f} s)")
        check(cdur >= dur - 0.02, f"srt.{l['id']}.covers_audio",
              f"cue {cdur:.3f} s for {dur:.2f} s of speech")
        check(cue["text"] == l["text"], f"srt.{l['id']}.text",
              "text matches the spec character for character"
              if cue["text"] == l["text"] else f"differs from spec: {cue['text']!r}")
    ordered = sorted(cues, key=lambda c: c["start"])
    for a, b in zip(ordered, ordered[1:]):
        if b["start"] < a["end"] - 0.001:
            check(False, "srt.no_overlap", f"cues overlap at {a['end']:.3f} s")
            break
    else:
        check(True, "srt.no_overlap", "no two cues overlap")

    # ---- draft ---------------------------------------------------------
    d = json.loads(draft_p.read_text(encoding="utf-8"))
    mats = d["materials"]
    vids, auds, txts = mats.get("videos", []), mats.get("audios", []), mats.get("texts", [])
    tracks = {t["type"]: t for t in d["tracks"]}
    check(abs(float(d["duration"]) / 1e6 - target) <= TOL, "draft.duration",
          f"{float(d['duration']) / 1e6:.3f} s")

    def inside_repo(p: str) -> bool:
        try:
            pathlib.Path(p).resolve().relative_to(ROOT)
            return True
        except ValueError:
            return False

    media = [(m.get("path"), m.get("type")) for m in (*vids, *auds)]
    bad_abs = [p for p, _ in media if not p or not pathlib.Path(p).is_absolute()]
    bad_root = [p for p, _ in media if p and not inside_repo(p)]
    missing = [p for p, _ in media if p and not pathlib.Path(p).exists()]
    check(not bad_abs, "draft.paths_absolute",
          "every media path is absolute (Rule 4)" if not bad_abs else f"relative: {bad_abs[:3]}")
    check(not bad_root, "draft.paths_in_repo",
          "every media path resolves inside the repo root" if not bad_root else f"outside: {bad_root[:3]}")
    check(not missing, "draft.media_exists",
          f"{len(media)} media file(s) present" if not missing else f"missing: {missing[:3]}")

    check(len(vids) == 1, "draft.video_materials", f"{len(vids)}, expect 1")
    if vids:
        vp = pathlib.Path(vids[0]["path"])
        check(vp.resolve() == master.resolve(), "draft.video_points_at_master",
              vp.name + (" == canonical master" if vp.resolve() == master.resolve()
                         else f" != {master.name}"))
    vsegs = tracks.get("video", {}).get("segments", [])
    vtotal = sum(s["target_timerange"]["duration"] for s in vsegs) / 1e6
    check(len(vsegs) == 1 and abs(vtotal - target) <= TOL, "draft.video_track",
          f"{len(vsegs)} segment(s), {vtotal:.3f} s")

    check(len(auds) == len(lines), "draft.audio_materials", f"{len(auds)}, expect {len(lines)}")
    ase = tracks.get("audio", {}).get("segments", [])
    check(len(ase) == len(lines), "draft.audio_segments", f"{len(ase)}, expect {len(lines)}")
    amat = {m["id"]: m for m in auds}
    for l in lines:
        name = f"vo{l['id'][2:]}_{l['slug']}.wav"
        seg = next((s for s in ase if amat.get(s["material_id"], {}).get("name") == name), None)
        if seg is None:
            check(False, f"draft.{l['id']}", f"no segment for {name}")
            continue
        start = seg["target_timerange"]["start"] / 1e6
        dur = seg["target_timerange"]["duration"] / 1e6
        want = float(l["window"][0])
        wav = float(manifest[l["id"]]["seconds"])
        check(abs(start - want) <= 0.001 and abs(dur - wav) <= 0.01, f"draft.{l['id']}",
              f"starts {start:.3f} s (spec {want:.2f}), {dur:.2f} s (wav {wav:.2f})")

    tse = tracks.get("text", {}).get("segments", [])
    check(len(tse) == len(cues), "draft.text_segments", f"{len(tse)}, expect {len(cues)}")
    tmat = {m["id"]: m for m in txts}
    for l in lines:
        cue = srt_by_line[l["id"]]
        seg = next((s for s in tse
                    if abs(s["target_timerange"]["start"] / 1e6 - cue["start"]) <= 0.001), None)
        if seg is None:
            check(False, f"draft.{l['id']}.text", "no text segment at the cue start")
            continue
        content = json.loads(tmat[seg["material_id"]]["content"])["text"]
        check(content == cue["text"], f"draft.{l['id']}.text",
              "caption text matches the SRT" if content == cue["text"] else f"differs: {content!r}")

    # ---- holds ---------------------------------------------------------
    if args.skip_frames:
        note("holds", "skipped (--skip-frames)")
    else:
        scratch = ROOT / "work" / ".btmp" / "verify_frames"
        scratch.mkdir(parents=True, exist_ok=True)
        holds = report.get("holds", [])
        if not holds:
            warn("holds", "assemble_report lists none — the master has no freeze-fill")
        for h in holds:
            n = h["unit"]
            frozen = float(h["frozen_seconds"])
            u = units[n]
            t_in, t_out = float(u["in"]), float(u["out"])
            live = (t_out - t_in) - frozen
            gap = min(0.7, max(0.15, frozen * 0.6))
            f1 = t_out - frozen + 0.10
            f2 = min(f1 + gap, t_out - 0.02)
            c1 = t_in + max(0.5, live * 0.25)
            c2 = min(c1 + gap, t_in + live - 0.02)
            if f2 <= f1 or c2 <= c1:
                warn(f"hold.u{n}", "window too short to sample")
                continue
            fa, fb = scratch / f"u{n}_f1.png", scratch / f"u{n}_f2.png"
            ca, cb = scratch / f"u{n}_c1.png", scratch / f"u{n}_c2.png"
            frame(master, f1, fa)
            frame(master, f2, fb)
            frame(master, c1, ca)
            frame(master, c2, cb)
            fp = psnr(fa, fb)
            cp = psnr(ca, cb)
            frozen_ok = fp == float("inf") or fp >= HOLD_PSNR_MIN
            control_ok = cp < HOLD_PSNR_MIN
            check(frozen_ok and control_ok, f"hold.u{n}",
                  f"frozen {frozen:.2f} s: hold pair "
                  f"{'inf' if fp == float('inf') else f'{fp:.1f}'} dB (≥{HOLD_PSNR_MIN:g}), "
                  f"live control {cp:.1f} dB (<{HOLD_PSNR_MIN:g})")
            for p in (fa, fb, ca, cb):
                p.unlink(missing_ok=True)
        try:
            scratch.rmdir()
        except OSError:
            pass

    print()
    if fails:
        print(f"DELIVERY NOT VERIFIED — {len(fails)} failure(s): {', '.join(fails)}")
        return 1
    print(f"DELIVERY VERIFIED — {len(warns)} warning(s)" if warns else "DELIVERY VERIFIED — all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
