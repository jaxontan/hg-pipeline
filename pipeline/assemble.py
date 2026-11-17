"""Episode assembly: normalise every shot to one spec, then concatenate in order.

shots.json is a list, in cut order. Each entry is a path or an object:
  {"file": "outputs/...mp4",        the clip
   "text": "老陈，这缸子…",          optional subtitle line for this shot
   "voice": "assets/audio/x.wav",   optional voice-over mixed on top of the clip's own sound
   "voice_delay": 0.25}             optional seconds before the voice-over starts

Plain `assemble` keeps the original behaviour (letterbox, straight concat). The finishing
options - cover-crop, burned subtitles, loudness, AI-content label - are opt-in flags.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

W, H, FPS = 1080, 1920, 24
FONT = "Noto Sans CJK SC"


def _probe(path: str, entries: str, stream: str | None = None) -> str:
    cmd = ["ffprobe", "-v", "error"]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "default=nw=1:nk=1", path]
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def duration(path: str) -> float:
    return float(_probe(path, "format=duration") or 0)


def has_audio(path: str) -> bool:
    return bool(_probe(path, "stream=index", "a"))


def normalise(src: str, dst: str, fit: str = "pad", voice: str | None = None,
              voice_delay: float = 0.25, crf: int = 18) -> None:
    if fit == "cover":
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
              f"crop={W}:{H},setsar=1,fps={FPS}")
    else:
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={FPS}")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src]
    clip_audio = has_audio(src)
    if not clip_audio:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    if voice:
        cmd += ["-i", voice]
    base = "[0:a]" if clip_audio else "[1:a]"
    fc = f"[0:v]{vf}[v];"
    if voice:
        vi = 1 if clip_audio else 2
        ms = int(voice_delay * 1000)
        fc += (f"{base}aresample=48000,volume=0.45[bed];"
               f"[{vi}:a]aresample=48000,adelay={ms}:all=1[vo];"
               f"[bed][vo]amix=inputs=2:duration=first:normalize=0[a]")
    else:
        fc += f"{base}aresample=48000[a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-shortest",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", dst]
    subprocess.run(cmd, check=True)


MAX_CHARS = 14  # one subtitle line; longer speech becomes several cues, never a paragraph


def split_line(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Break a spoken line into short on-screen phrases at its own punctuation."""
    phrases = [p for p in re.split(r"(?<=[，。？！、；：…,.?!;])", text.strip()) if p.strip()]
    chunks: list[str] = []
    for p in phrases:
        if chunks and len(chunks[-1]) + len(p) <= limit:
            chunks[-1] += p
        else:
            chunks.append(p)
    out = []
    for c in chunks:
        c = c.strip().rstrip("，。、；：,.;")
        while len(c) > limit:           # no punctuation to break on: hard split
            cut = (len(c) + 1) // 2 if len(c) <= 2 * limit else limit
            out.append(c[:cut])
            c = c[cut:]
        if c:
            out.append(c)
    return out


def cues_for(text: str, start: float, end: float) -> list[tuple[float, float, str]]:
    chunks = split_line(text)
    weights = [max(len(c), 3) for c in chunks]
    span, t, cues = end - start, start, []
    for c, w in zip(chunks, weights):
        d = span * w / sum(weights)
        cues.append((t, t + d, c))
        t += d
    return cues


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_srt(path: str, cues: list[tuple[float, float, str]]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for i, (a, b, text) in enumerate(cues, 1):
            fh.write(f"{i}\n{_ts(a)} --> {_ts(b)}\n{text}\n\n")


def _ass_ts(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def write_ass(path: str, cues: list[tuple[float, float, str]], total: float,
              label: str | None) -> None:
    """Subtitles sit above the bottom fifth of the frame, clear of the player's caption and
    buttons; the label goes top-left under the status bar."""
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 0\n"
            f"ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
            f"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            f"BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            f"BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Line,{FONT},84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,"
            f"100,1,0,1,4,1,2,90,90,420,1\n"
            f"Style: Label,{FONT},30,&H30FFFFFF,&H30FFFFFF,&H60000000,&H80000000,0,0,0,0,100,"
            f"100,0,0,1,2,0,7,36,36,150,1\n\n[Events]\n"
            f"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(head)
        if label:
            fh.write(f"Dialogue: 0,{_ass_ts(0)},{_ass_ts(total)},Label,,0,0,0,,{label}\n")
        for a, b, text in cues:
            clean = text.replace("\n", "\\N").replace("{", "(").replace("}", ")")
            fh.write(f"Dialogue: 1,{_ass_ts(a)},{_ass_ts(b)},Line,,0,0,0,,{clean}\n")


def assemble(shots: list, out: str, workdir: str | None = None, keep_parts: bool = False,
             fit: str = "pad", burn_subs: bool = False, loudnorm: bool = False,
             label: str | None = None) -> int:
    if not shots:
        print("no shots in list", file=sys.stderr)
        return 1
    work = workdir or (os.path.splitext(out)[0] + "_parts")
    os.makedirs(work, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    finishing = burn_subs or loudnorm or bool(label)

    parts, cues, t = [], [], 0.0
    for i, shot in enumerate(shots):
        shot = shot if isinstance(shot, dict) else {"file": shot}
        src = shot["file"]
        if not os.path.exists(src):
            print(f"missing: {src}", file=sys.stderr)
            return 1
        dst = os.path.join(work, f"part_{i:03d}.mp4")
        print(f"[{i+1}/{len(shots)}] {os.path.basename(src)}")
        # when a finishing pass re-encodes the picture, keep the intermediate near-lossless
        normalise(src, dst, fit=fit, voice=shot.get("voice"),
                  voice_delay=float(shot.get("voice_delay", 0.25)),
                  crf=12 if (burn_subs or label) else 18)
        d = duration(dst)
        if shot.get("text"):
            cues += cues_for(shot["text"], t + 0.10, t + d - 0.05)
        t += d
        parts.append(dst)

    listing = os.path.join(work, "concat.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for p in parts:
            fh.write(f"file '{os.path.abspath(p)}'\n")
    joined = os.path.join(work, "joined.mp4") if finishing else out
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", listing, "-c", "copy", "-movflags", "+faststart", joined], check=True)

    srt = os.path.splitext(out)[0] + ".srt"
    if cues:
        write_srt(srt, cues)
        print(f"wrote {srt}  ({len(cues)} lines)")

    if finishing:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", joined]
        vf = []
        burned = cues if burn_subs else []
        if burned or label:
            ass = os.path.join(work, "overlay.ass")
            write_ass(ass, burned, t, label)
            esc = os.path.abspath(ass).replace("\\", "/").replace(":", "\\:")
            vf.append(f"ass='{esc}'")
        if vf:
            cmd += ["-vf", ",".join(vf), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-pix_fmt", "yuv420p"]
        else:
            cmd += ["-c:v", "copy"]
        if loudnorm:
            cmd += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
                    "-ar", "48000"]
        else:
            cmd += ["-c:a", "copy"]
        cmd += ["-movflags", "+faststart", out]
        subprocess.run(cmd, check=True)

    print(f"\nwrote {out}  ({t/60:.1f} min, {len(parts)} shots)")
    if not keep_parts:
        for p in parts + [listing] + ([joined, os.path.join(work, "overlay.ass")] if finishing else []):
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.rmdir(work)
        except OSError:
            pass
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Concatenate shots into an episode")
    ap.add_argument("--shots", required=True, help="JSON file: [{file, text?, voice?}, ...]")
    ap.add_argument("--out", required=True, help="output mp4 path")
    ap.add_argument("--workdir", default=None, help="temp dir for normalised parts")
    ap.add_argument("--keep-parts", action="store_true")
    ap.add_argument("--fit", choices=("pad", "cover"), default="pad",
                    help="pad = letterbox (default); cover = fill 9:16 and crop the overflow")
    ap.add_argument("--burn-subs", action="store_true", help="burn each shot's text in")
    ap.add_argument("--loudnorm", action="store_true", help="normalise to -16 LUFS")
    ap.add_argument("--label", help="small on-screen text, e.g. an AI-generated-content notice")
    args = ap.parse_args()
    with open(args.shots, encoding="utf-8") as fh:
        shots = json.load(fh)
    return assemble(shots, args.out, args.workdir, args.keep_parts, args.fit,
                    args.burn_subs, args.loudnorm, args.label)


if __name__ == "__main__":
    raise SystemExit(main())
