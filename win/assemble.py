#!/usr/bin/env python3
"""Conform an episode from its EDL into a delivery master, and stamp the marks
that 国家广播电视总局令第16号 (effective 2026-09-01) requires.

    python win/assemble.py --dry-run        # validate + plan, encode nothing
    python win/assemble.py                  # technical conform (freeze-fills short units)
    python win/assemble.py --final          # refuses until 节目编号 is issued

What it enforces, and why:

  Rule 1  every clip must have a provenance entry, or it cannot enter a master.
  Rule 5  a unit marked anything other than `both` blocks a global master.
  Rule 7  ffmpeg is the repo-local binary in win/tools — never PATH, so the
          version that made a master is the version recorded in the report.

Art.27  the 片头 carries 剧名 + 节目编号, and an AI-assisted episode carries a
        label in a prominent position. Both are burned in here, not by hand.

Deliberate limitation: `program_number` is EMPTY in edit.json because the
platform issues it on review. A master made without it is a technical conform,
not a deliverable — hence --final refuses.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIN = ROOT / "win" / "tools" / "ffmpeg" / "bin"
FFMPEG = BIN / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
FFPROBE = BIN / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
# The system CJK face, referenced in place — SimHei is not ours to copy into the
# repo, and a font is not an asset this pipeline may silently redistribute.
# In a filtergraph a Windows path needs its colon escaped; the check uses the
# real path.
FONT_FILE = pathlib.Path("C:/Windows/Fonts/simhei.ttf")
# Quoted: the filter parser splits on the colon in C: unless the value is
# quoted, and this build ships without a fontconfig config, so font=SimHei
# (family lookup) is not an option.
FONT_FILTER = r"'C\:/Windows/Fonts/simhei.ttf'"

TERRITORY_OK_FOR_GLOBAL = {"both", "global"}
EPS = 1e-3


def die(msg: str) -> None:
    print(f"assemble: {msg}", file=sys.stderr)
    raise SystemExit(1)


def rel(p: pathlib.Path) -> str:
    """Path relative to the repo root, forward slashes, no drive letter.

    Every path that lands inside the filtergraph must be ASCII and colon-free,
    otherwise ffmpeg's Windows filter parser mangles it.
    """
    return p.relative_to(ROOT).as_posix()


def probe(path: pathlib.Path) -> dict:
    out = subprocess.run(
        [str(FFPROBE), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration",
         "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        die(f"ffprobe failed on {path.name}: {out.stderr.strip()[:300]}")
    d = json.loads(out.stdout)
    st = d["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    return {
        "width": st["width"],
        "height": st["height"],
        "fps": float(num) / float(den),
        "duration": float(d["format"]["duration"]),
        # A container can be 90 s while the video stream is 5 s: the muxer takes
        # the longest stream. Checking format duration alone hides a truncated
        # picture behind correct audio, so track the video stream separately.
        "video_duration": float(st.get("duration") or d["format"]["duration"]),
    }


def provenance_index() -> list:
    """(shot_id, output_basename, entry) for every recorded asset.

    Provenance stores the output as a bare name (`manju_clip_00002_.mp4`) and
    the shot separately (`shot_id: s002`), while the file on disk is
    `s002m_manju_clip_00002_.mp4`. The join is shot_id + '_' + output.
    """
    idx = []
    for p in sorted((ROOT / "spark" / "provenance").rglob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(d, dict) or "entries" not in d:
            continue
        for e in d["entries"]:
            outs = e.get("outputs") or []
            if isinstance(outs, str):
                outs = [outs]
            for o in outs:
                # ComfyUI's history shape: {"filename": ..., "subfolder": ...}
                name = o.get("filename") if isinstance(o, dict) else o
                if name:
                    idx.append((e.get("shot_id", ""),
                                pathlib.PurePosixPath(str(name)).name, e))
    return idx


def provenance_for(clip_name: str, idx: list):
    """The entry that accounts for this clip, or None.

    Exact shot match wins; a prefix match covers the variant rigs
    (s004g -> s004, x002b -> x002).
    """
    if "_" not in clip_name:
        return None
    shot, out = clip_name.split("_", 1)
    for want in (lambda s: s == shot, lambda s: shot.startswith(s) and s):
        for sid, name, e in idx:
            if name == out and want(sid):
                return e
    return None


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(lines, measure, dst: pathlib.Path) -> int:
    """Subtitles sit on the spoken line, not on the whole slot: a 0.86 s line in
    a 7.5 s window must not hold a caption up for 7 s."""
    entries = []
    for ln in lines:
        m = measure.get(ln["id"])
        start = float(ln["window"][0])
        dur = (m["speech_seconds"] if m else (ln["window"][1] - start))
        end = min(start + dur + 0.35, float(ln["window"][1]) + 0.5)
        entries.append((start, end, ln["text"]))
    entries.sort()
    blocks = [
        f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n"
        for i, (a, b, text) in enumerate(entries, 1)
    ]
    dst.write_text("\n".join(blocks), encoding="utf-8")
    return len(entries)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--edit", default="work/laotang_ep01/edit.json")
    ap.add_argument("--out", default="work/laotang_ep01/cut/laotang_ep01_master.mp4")
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--final", action="store_true",
                    help="assert this is a deliverable, not a technical conform")
    ap.add_argument("--allow-hold", action="store_true",
                    help="freeze the last frame to cover units longer than one clip")
    args = ap.parse_args()

    for exe in (FFMPEG, FFPROBE):
        if not exe.exists():
            die(f"missing {exe} — run win/get_ffmpeg.sh first")
    if not FONT_FILE.exists():
        die(f"missing CJK font {FONT_FILE}")

    edit = json.loads((ROOT / args.edit).read_text(encoding="utf-8"))
    episode = edit["episode"]
    comp = edit.get("compliance", {})
    units = edit["units"]
    fps = edit.get("fps", 24)
    W = edit["delivery"]["width"]
    H = edit["delivery"]["height"]
    target = sum(u["out"] - u["in"] for u in units)

    # ---- Rule 1 ---------------------------------------------------------
    # An asset without provenance cannot enter a master, so this runs before
    # anything is planned or encoded.
    idx = provenance_index()
    prov_of, orphans = {}, []
    for u in units:
        e = provenance_for(u["clip"], idx)
        if e is None:
            orphans.append(f"unit {u['n']} ({u['clip']})")
        else:
            prov_of[u["n"]] = e
    if orphans:
        die("Rule 1: no provenance entry for " + ", ".join(orphans)
            + " — refusing to assemble")

    # ---- Rule 5 ---------------------------------------------------------
    # The recorded territory is the authority, not the EDL's copy of it.
    if args.final:
        bad = [u["n"] for u in units
               if prov_of[u["n"]].get("territory") not in TERRITORY_OK_FOR_GLOBAL]
        if bad:
            die(f"global master requested but units {bad} are territory-restricted "
                f"in provenance")

    # ---- Art.27 ---------------------------------------------------------
    program = (comp.get("program_number") or "").strip()
    if args.final and not program:
        die("--final refused: 节目编号 is empty (令第16号 Art.27 requires it in the 片头). "
            "Fill compliance.program_number once the 播出单位 issues it.")

    # ---- duration -------------------------------------------------------
    # A clip is a whole number of frames: 121 frames is 5.0417 s, and "5.5 s" is
    # not a length any clip can have. So the conform counts FRAMES, and the trim
    # stops a sliver inside the last wanted frame. Doing this in seconds let
    # rounding decide: `duration=5.042` and `duration=5.041667` both happen to
    # give 121 frames on a 121-frame clip, but `duration=3.459` gives 84 frames
    # where 83 were meant — one frame of drift per unit, silently.
    clips = {u["clip"]: ROOT / "work" / episode / u["clip"] for u in units}
    info = {}
    frames_of, holds, shortfall = {}, [], []
    print(f"\n{episode}: {len(units)} units, {target:.2f} s target, {W}x{H} @ {fps} fps")
    print(f"{'#':>2} {'shot':7s} {'unit':>6s} {'clip':>6s} {'slack':>9s}")
    for u in units:
        c = clips[u["clip"]]
        if not c.exists():
            die(f"unit {u['n']}: clip missing on disk — {u['clip']}")
        if u["clip"] not in info:
            info[u["clip"]] = probe(c)
        have = info[u["clip"]]["duration"]
        need = u["out"] - u["in"]
        src_in = float(u.get("src_in", 0.0))
        if src_in + need > target + EPS:
            die(f"unit {u['n']}: src_in {src_in:.2f}s + {need:.2f}s runs past the episode")
        n_fr = max(1, round(need * fps))
        have_fr = int(round(have * fps))
        src_fr = int(round(src_in * fps))
        slack_fr = have_fr - src_fr - n_fr
        frames_of[u["n"]] = n_fr
        flag = "" if slack_fr >= 0 else "  SHORT"
        print(f"{u['n']:>2} {u['shot']:7s} {n_fr:4d}fr {have_fr:4d}fr "
              f"{slack_fr:+4d}fr ({slack_fr / fps:+.3f}s){flag}")
        if slack_fr < 0:
            shortfall.append((u["n"], n_fr, have_fr, -slack_fr))
            holds.append((u["n"], -slack_fr))

    print(f"provenance: {len(prov_of)}/{len(units)} units accounted for")
    if shortfall:
        print("\nunits longer than the clip they come from:")
        for n, need, have, short in shortfall:
            print(f"  unit {n}: needs {need} frames, clip is {have}, short {short}")
        print(f"  total short {sum(s[3] for s in shortfall)} frames "
              f"({sum(s[3] for s in shortfall) / fps:.2f} s). "
              f"A clip cannot be longer than it is; every one of these is an editorial call "
              f"(re-time the cut, or freeze/slow the tail).")
        if not args.allow_hold:
            die("refusing to guess. Re-run with --allow-hold to freeze the last frame, "
                "or fix edit.json.")

    # ---- build ----------------------------------------------------------
    outdir = (ROOT / args.out).parent
    outdir.mkdir(parents=True, exist_ok=True)
    srt = outdir / f"{episode}.srt"
    lines_spec = json.loads((ROOT / "work" / "story" /
                             f"vo_lines_{episode}.json").read_text(encoding="utf-8"))["lines"]
    meas_raw = json.loads((ROOT / "work" / episode / "vo" / "MEASURE.json")
                          .read_text(encoding="utf-8"))
    measure = {r["id"]: r for r in meas_raw["lines"]}
    n_subs = write_srt(lines_spec, measure, srt)

    # Chinese never enters the filtergraph: it goes through textfile=.
    ai_txt = outdir / "_ai_label.txt"
    head_txt = outdir / "_header.txt"
    ai_txt.write_text(comp.get("ai_label", "本片由AI辅助生成"), encoding="utf-8")
    header = f"{comp.get('title', '')}　{program or comp.get('program_number_placeholder', '')}"
    head_txt.write_text(header, encoding="utf-8")

    vo_wav = {ln["id"]: ROOT / "work" / episode / "vo" / f"{ln['id']}_{ln['slug']}.wav"
              for ln in lines_spec}
    vo_order = [ln["id"] for ln in lines_spec]

    parts = []
    for i, u in enumerate(units):
        hold_fr = dict(holds).get(u["n"], 0)
        n_fr = frames_of[u["n"]]
        # in/out are timeline positions; the clip is taken from src_in. The trim
        # stops 1 ms inside the last wanted frame so a rounding edge can never
        # hand the concat one frame too many or too few.
        chain = (f"trim=start={float(u.get('src_in', 0.0)):.3f}:"
                 f"duration={n_fr / fps - EPS:.6f},"
                 f"setpts=PTS-STARTPTS,fps={fps}")
        if hold_fr:
            # Exactly the shortfall: padding by a safety margin silently stretches
            # the episode (6 holds x 0.1 s = 0.6 s too long).
            chain += f",tpad=stop_mode=clone:stop_duration={hold_fr / fps:.6f}"
        chain += (f",scale={W}:{H}:force_original_aspect_ratio=decrease,"
                  f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1")
        parts.append(f"[{i}:v]{chain}[v{i}]")

    labels = "".join(f"[v{i}]" for i in range(len(units)))
    graph = parts + [f"{labels}concat=n={len(units)}:v=1:a=0[vcat]"]

    n_base = len(units)
    # ASS units, not pixels: libass lays SRT out on a 288-high canvas, so every
    # value here is multiplied by 1920/288 = 6.67. MarginV=120 therefore puts
    # the caption 800 px up the frame, not 120 — which is what it did.
    # Fontsize=12 -> ~80 px, MarginV=20 -> ~133 px off the bottom.
    graph.append(
        f"[vcat]subtitles={rel(srt)}:force_style="
        f"'Fontname=SimHei,Fontsize=12,PrimaryColour=&HFFFFFF&,"
        f"OutlineColour=&H40000000&,BorderStyle=1,Outline=2,Shadow=0,MarginV=20'[vsub]"
    )
    graph.append(
        f"[vsub]drawtext=fontfile={FONT_FILTER}:textfile={rel(ai_txt)}:fontsize=30:"
        f"fontcolor=white@0.85:box=1:boxcolor=black@0.35:boxborderw=12:x=w-tw-40:y=64[vai]"
    )
    graph.append(
        f"[vai]drawtext=fontfile={FONT_FILTER}:textfile={rel(head_txt)}:fontsize=34:"
        f"fontcolor=white@0.95:box=1:boxcolor=black@0.45:boxborderw=16:x=(w-tw)/2:y=140:"
        f"enable='lt(t,4)'[vout]"
    )

    # audio: a silent bed the length of the cut, VO dropped on its window start
    graph.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={target:.3f},"
                 f"asetpts=PTS-STARTPTS[abase]")
    mix_in = ["[abase]"]
    for k, lid in enumerate(vo_order):
        w = vo_wav[lid]
        if not w.exists():
            die(f"missing VO {w.name}")
        start = float(next(ln["window"][0] for ln in lines_spec if ln["id"] == lid))
        ms = int(round(start * 1000))
        # Mono wav -> stereo with pan, NOT aformat channel_layouts=stereo: that
        # conversion equal-power-spreads a mono source and lands 1/sqrt(2) = -3 dB
        # in each channel, so the whole mix ships 3 dB under the measured wavs.
        # pan copies the channel at unity and is the only reason the dialogue level
        # in the master equals the level the voice pass signed off on.
        graph.append(f"[{n_base + k}:a]aformat=sample_fmts=fltp:sample_rates=48000,"
                     f"pan=stereo|c0=c0|c1=c0,adelay={ms}|{ms}[a{k}]")
        mix_in.append(f"[a{k}]")
    graph.append(f"{''.join(mix_in)}amix=inputs={len(mix_in)}:normalize=0:duration=first[aout]")

    script = outdir / "_filter.txt"
    script.write_text(";\n".join(graph) + "\n", encoding="utf-8")

    cmd = [str(FFMPEG), "-hide_banner", "-y"]
    for u in units:
        cmd += ["-i", rel(clips[u["clip"]])]
    for lid in vo_order:
        cmd += ["-i", rel(vo_wav[lid])]
    # ffmpeg 7 removed -filter_complex_script; the generic "load this option
    # from a file" prefix replaced it. The graph is long (19 trims + 6 VO
    # chains) and passing it as one argv string hits Windows' 32 KB ceiling.
    cmd += ["-/filter_complex", rel(script),
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf),
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", rel(ROOT / args.out)]

    print(f"\nsubs: {n_subs}   VO: {len(vo_order)}   holds: "
          f"{[n for n, _ in holds] or 'none'}")
    print(f"filtergraph: {rel(script)}")
    if args.dry_run:
        print("\n--dry-run: nothing encoded")
        return 0

    print("\nencoding ...")
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        die(f"ffmpeg exited {r.returncode}")

    out = ROOT / args.out
    m = probe(out)
    # The check that matters: audio can carry a 90 s container by itself.
    if abs(m["video_duration"] - target) > 0.25:
        die(f"picture is {m['video_duration']:.2f} s but the cut is {target:.2f} s "
            f"- the concat truncated or over-padded; do not ship this file")
    rep = {
        "episode": episode,
        "output": rel(out),
        "bytes": out.stat().st_size,
        "duration": m["duration"],
        "video_duration": m["video_duration"],
        "width": m["width"], "height": m["height"], "fps": m["fps"],
        "target_seconds": target,
        "units": len(units),
        "subtitles": n_subs,
        "vo_lines": len(vo_order),
        "holds": [{"unit": n, "frozen_frames": s, "frozen_seconds": round(s / fps, 3)}
                  for n, s in holds],
        "program_number": program or None,
        "final": bool(args.final),
        "ffmpeg": subprocess.run([str(FFMPEG), "-hide_banner", "-version"],
                                 capture_output=True, text=True).stdout.splitlines()[0],
    }
    (outdir / "assemble_report.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{rel(out)}  {m['duration']:.2f} s  {m['width']}x{m['height']} @ {m['fps']:.0f}  "
          f"{rep['bytes']/1e6:.1f} MB")
    print(f"report: {rel(outdir / 'assemble_report.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
