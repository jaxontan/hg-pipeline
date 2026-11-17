"""Command line for the AIGC-PP2 ComfyUI pipeline.

Examples
--------
  python -m pipeline.cli health
  python -m pipeline.cli lanes
  python -m pipeline.cli image  --lane image_fast --prompt "..." --out man_01
  python -m pipeline.cli video  --lane video_ltx_final --prompt "..." --out shot_001
  python -m pipeline.cli voice  --text "老陈，这搪瓷缸子跟了你二十年了。" --out line_01
  python -m pipeline.cli dialogue --prompt "..." --audio assets/audio/line_01.wav \
                                --ref assets/input/ltx_scene_ref.png --out shot_002
  python -m pipeline.cli animate --prompt "..." --ref a.png --drive b.mp4 --out act_01
  python -m pipeline.cli assemble --shots projects/ep01/shots.json --out projects/ep01/ep01.mp4

Reference-conditioned lanes (consistent characters) and the episode runner:
  python -m pipeline.cli image --ref sheet.png --ref plate.png --prompt "..." --out key_01
  python -m pipeline.cli video --lane video_ltx_i2v --image key_01.png --prompt "..." --out s01
  python -m pipeline.cli talk  --image key_01.png --audio line_01.wav --prompt "..." --out s02
  python -m pipeline.cli produce --show demo --episode ep00 --stage all
See workflows/PRODUCTION_WORKFLOW.md.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

from . import graphs, produce
from .comfy import Comfy, ComfyError
from .manifest import Manifest

DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


class Ctx:
    def __init__(self, config_path: str, project: str):
        with open(config_path, encoding="utf-8") as fh:
            self.cfg = json.load(fh)
        self.root = os.path.dirname(os.path.dirname(os.path.abspath(config_path)))
        self.project = project
        paths = self.cfg["paths"]
        self.outputs = os.path.join(self.root, paths["outputs"])
        self.input_dir = os.path.join(self.root, paths["input"])
        self.audio_dir = os.path.join(self.root, paths["audio"])
        self.projects = os.path.join(self.root, paths["projects"])
        for d in (self.outputs, self.input_dir, self.audio_dir, self.projects):
            os.makedirs(d, exist_ok=True)
        self.comfy = Comfy(self.cfg["host"])
        self.manifest = Manifest(os.path.join(self.projects, project, "manifest.jsonl"))

    # ---- helpers ---------------------------------------------------------
    def lane(self, name: str) -> dict:
        try:
            return self.cfg["lanes"][name]
        except KeyError:
            raise SystemExit(f"unknown lane {name!r}; try: {', '.join(self.cfg['lanes'])}")

    def default(self, key: str):
        return self.cfg["defaults"].get(key)

    def ensure_input(self, path: str) -> str:
        """ComfyUI can only read media from its input dir: copy in, return the bare name."""
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise SystemExit(f"missing input file: {path}")
        if os.path.dirname(path) == os.path.abspath(self.input_dir):
            return os.path.basename(path)
        shutil.copy2(path, self.input_dir)
        return os.path.basename(path)

    def prefix(self, lane: str, name: str) -> str:
        return f"{self.project}/{lane}/{name}"

    def finish(self, entry: dict, t0: float, lane: str, prompt: str, params: dict,
               graph: dict, extra: dict | None = None) -> list[str]:
        files = [self.comfy.relpath(f) for f in self.comfy.files(entry)]
        elapsed = time.time() - t0
        self.manifest.add(lane=lane, prompt=prompt, params=params, graph=graph,
                          files=files, elapsed=elapsed, extra=extra)
        print(f"  done in {elapsed:.1f}s -> " + ", ".join(files))
        return files


def _probe_duration(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", path],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def _fit_frames(seconds: float, fps: float, step: int = 4) -> int:
    raw = max(1, round(seconds * fps) + 1)
    return ((raw - 1) // step) * step + 1


# --------------------------------------------------------------------------- commands
def cmd_health(ctx: Ctx, _args) -> int:
    up = ctx.comfy.health()
    print(f"ComfyUI {'UP' if up else 'DOWN'} at {ctx.cfg['host']}")
    if up:
        q = ctx.comfy.queue()
        print(f"  running={len(q.get('queue_running', []))} pending={len(q.get('queue_pending', []))}")
    return 0 if up else 1


def cmd_lanes(ctx: Ctx, _args) -> int:
    for name, lane in ctx.cfg["lanes"].items():
        res = f"{lane.get('width')}x{lane.get('height')}"
        extra = f" {lane.get('length')}f" if lane.get("length") else ""
        print(f"{name:<20} {lane['engine']:<9} {res}{extra:<8} ~{lane.get('measured_seconds', '?')}s")
    return 0


def _run_graph(ctx: Ctx, graph: dict, lane_name: str, prompt: str, params: dict,
               timeout: float) -> list[str]:
    t0 = time.time()
    try:
        entry = ctx.comfy.run(graph, timeout=timeout,
                              on_tick=lambda t, r: print(f"  t={t:6.1f}s running={r}", flush=True))
    except ComfyError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return []
    return ctx.finish(entry, t0, lane_name, prompt, params, graph)


def cmd_image(ctx: Ctx, args) -> int:
    lane = ctx.lane(args.lane)
    w = args.width or lane["width"]
    h = args.height or lane["height"]
    seed = args.seed if args.seed is not None else ctx.default("seed")
    neg = args.negative if args.negative else None
    if args.ref or lane["engine"] == "flux2_ref":
        if not args.ref:
            raise SystemExit(f"lane {args.lane} needs at least one --ref image")
        if lane["engine"] != "flux2_ref":
            args.lane, lane = "image_ref", ctx.lane("image_ref")
            w, h = args.width or lane["width"], args.height or lane["height"]
        refs = [ctx.ensure_input(r) for r in args.ref]
        graph = graphs.image_ref(lane, args.prompt, refs, w, h, seed,
                                 ctx.prefix(args.lane, args.out))
    else:
        refs = []
        graph = graphs.image(lane, args.prompt, neg, w, h, seed, ctx.prefix(args.lane, args.out))
    params = {"width": w, "height": h, "steps": lane["steps"], "cfg": lane["cfg"], "seed": seed,
              "refs": refs}
    print(f"image [{args.lane}] {w}x{h} seed={seed}")
    _run_graph(ctx, graph, args.lane, args.prompt, params, args.timeout)
    return 0


def cmd_video(ctx: Ctx, args) -> int:
    lane = ctx.lane(args.lane)
    w = args.width or lane["width"]
    h = args.height or lane["height"]
    length = args.length or lane["length"]
    fps = args.fps or lane["fps"]
    seed = args.seed if args.seed is not None else ctx.default("seed")
    neg = args.negative or (ctx.default("negative_ltx") if lane["engine"] == "ltx"
                            else ctx.default("negative_cn"))
    if lane["engine"] == "ltx_i2v":
        if not args.image:
            raise SystemExit(f"lane {args.lane} starts from a keyframe: pass --image")
        if lane.get("audio_driven"):
            raise SystemExit(f"lane {args.lane} is audio-driven: use the `talk` command")
        key = ctx.ensure_input(args.image)
        graph = graphs.ltx_i2v(lane, args.prompt, neg, key, w, h, length, fps, seed,
                               ctx.prefix(args.lane, args.out))
    else:
        key = None
        builder = graphs.BUILDERS[lane["engine"]]
        graph = builder(lane, args.prompt, neg, w, h, length, fps, seed,
                        ctx.prefix(args.lane, args.out))
    params = {"width": w, "height": h, "length": length, "fps": fps, "image": key,
              "two_pass": bool(lane.get("two_pass") or key), "seed": seed}
    print(f"video [{args.lane}] {w}x{h} {length}f @{fps:g} seed={seed}")
    _run_graph(ctx, graph, args.lane, args.prompt, params, args.timeout)
    return 0


def cmd_dialogue(ctx: Ctx, args) -> int:
    lane = ctx.lane(args.lane)
    audio_name = ctx.ensure_input(args.audio)
    ref_name = ctx.ensure_input(args.ref)
    w = args.width or lane["width"]
    h = args.height or lane["height"]
    fps = lane["fps"]
    length = args.length or _fit_frames(_probe_duration(args.audio), fps)
    seed = args.seed if args.seed is not None else ctx.default("seed")
    neg = args.negative or ctx.default("negative_cn")
    graph = graphs.s2v(lane, args.prompt, neg, ref_name, audio_name, w, h, length, seed,
                       ctx.prefix(args.lane, args.out))
    params = {"width": w, "height": h, "length": length, "fps": fps, "seed": seed,
              "audio": audio_name, "ref": ref_name}
    print(f"dialogue [{args.lane}] {w}x{h} {length}f @{fps:g} audio={audio_name}")
    _run_graph(ctx, graph, args.lane, args.prompt, params, args.timeout)
    return 0


def cmd_talk(ctx: Ctx, args) -> int:
    """Keyframe + voice line -> lip-synced shot at production resolution (LTX-2.5)."""
    lane = ctx.lane(args.lane)
    key = ctx.ensure_input(args.image)
    w = args.width or lane["width"]
    h = args.height or lane["height"]
    fps = lane["fps"]
    lead, tail = lane.get("lead_in_s", 0.25), lane.get("tail_s", 0.35)
    frames = int(-(-(_probe_duration(args.audio) + lead + tail) * fps // 8) * 8 + 1)
    padded = os.path.join(ctx.input_dir, f"{args.out}_line.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", args.audio, "-af",
                    f"adelay={int(lead * 1000)}:all=1,apad", "-t", f"{frames / fps:.4f}",
                    "-ar", "48000", padded], check=True)
    seed = args.seed if args.seed is not None else ctx.default("seed")
    neg = args.negative or ctx.default("negative_ltx")
    graph = graphs.ltx_i2v(lane, args.prompt, neg, key, w, h, frames, fps, seed,
                           ctx.prefix(args.lane, args.out), audio=os.path.basename(padded))
    params = {"width": w, "height": h, "length": frames, "fps": fps, "seed": seed,
              "image": key, "audio": os.path.basename(padded)}
    print(f"talk [{args.lane}] {w*2}x{h*2} {frames}f @{fps:g} audio={os.path.basename(args.audio)}")
    _run_graph(ctx, graph, args.lane, args.prompt, params, args.timeout)
    return 0


def cmd_animate(ctx: Ctx, args) -> int:
    lane = ctx.lane(args.lane)
    ref_name = ctx.ensure_input(args.ref)
    drive_name = ctx.ensure_input(args.drive)
    w = args.width or lane["width"]
    h = args.height or lane["height"]
    length = args.length or lane["length"]
    seed = args.seed if args.seed is not None else ctx.default("seed")
    neg = args.negative or ctx.default("negative_cn")
    graph = graphs.animate(lane, args.prompt, neg, ref_name, drive_name, w, h, length, seed,
                           ctx.prefix(args.lane, args.out))
    params = {"width": w, "height": h, "length": length, "seed": seed,
              "ref": ref_name, "drive": drive_name}
    print(f"animate [{args.lane}] {w}x{h} {length}f ref={ref_name} drive={drive_name}")
    _run_graph(ctx, graph, args.lane, args.prompt, params, args.timeout)
    return 0


def cmd_voice(ctx: Ctx, args) -> int:
    vcfg = ctx.cfg["voice"]
    vpy = os.path.join(ctx.root, vcfg["venv_python"])
    model_dir = os.path.join(ctx.root, vcfg["model_dir"])
    out = os.path.join(ctx.audio_dir, f"{args.out}.wav")
    cmd = [vpy, "-m", "pipeline.voice", "--text", args.text, "--instruct", args.instruct,
           "--language", args.language, "--model-dir", model_dir, "--out", out]
    print(f"voice {args.language} -> {os.path.relpath(out, ctx.root)}")
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=ctx.root, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-2000:], proc.stderr[-4000:], file=sys.stderr)
        return proc.returncode
    info = json.loads([l for l in proc.stdout.splitlines() if l.startswith("{")][-1])
    ctx.manifest.add(lane="voice", prompt=args.text,
                     params={"language": args.language, "instruct": args.instruct},
                     graph={"voice": True}, files=[os.path.relpath(out, ctx.root)],
                     elapsed=time.time() - t0, extra=info)
    print(f"  {info['duration_s']}s @ {info['sample_rate']}Hz in {info['gen_s']}s -> {out}")
    return 0


def cmd_assemble(ctx: Ctx, args) -> int:
    argv = [sys.executable, "-m", "pipeline.assemble", "--shots", args.shots, "--out", args.out]
    if args.keep_parts:
        argv.append("--keep-parts")
    argv += ["--fit", args.fit]
    if args.burn_subs:
        argv.append("--burn-subs")
    if args.loudnorm:
        argv.append("--loudnorm")
    if args.label:
        argv += ["--label", args.label]
    return subprocess.run(argv, cwd=ctx.root).returncode


def lane_graph(ctx: Ctx, name: str, lane: dict, prompt: str) -> dict:
    """Build the graph for one lane, using placeholder media where a lane needs a file."""
    eng = lane["engine"]
    builder = graphs.BUILDERS[eng]
    neg = ctx.default("negative_ltx") if eng == "ltx" else ctx.default("negative_cn")
    seed = ctx.default("seed")
    prefix = f"workflows/{name}"
    if eng in ("zimage", "flux2"):
        return builder(lane, prompt, None, lane["width"], lane["height"], seed, prefix)
    if eng == "flux2_ref":
        return builder(lane, prompt, ["CHARACTER_SHEET.png", "LOCATION_PLATE.png"],
                       lane["width"], lane["height"], seed, prefix)
    if eng == "ltx_i2v":
        return builder(lane, prompt, neg, "KEYFRAME.png", lane["width"], lane["height"],
                       lane["length"], lane["fps"], seed, prefix,
                       audio="LINE.wav" if lane.get("audio_driven") else None)
    if eng in ("ltx", "wan_t2v"):
        return builder(lane, prompt, neg, lane["width"], lane["height"], lane["length"],
                       lane["fps"], seed, prefix)
    if eng == "s2v":
        return builder(lane, prompt, neg, "REF.png", "LINE.wav", lane["width"],
                       lane["height"], lane["length"], seed, prefix)
    return builder(lane, prompt, neg, "REF.png", "DRIVE.mp4", lane["width"],
                   lane["height"], lane["length"], seed, prefix)


def cmd_export(ctx: Ctx, _args) -> int:
    outdir = os.path.join(ctx.root, ctx.cfg["paths"]["workflows"])
    os.makedirs(outdir, exist_ok=True)
    for name, lane in ctx.cfg["lanes"].items():
        g = lane_graph(ctx, name, lane, "<prompt goes here>")
        path = os.path.join(outdir, f"{name}.api.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(g, fh, indent=2, ensure_ascii=False)
        print(f"  {name:<20} {len(g):>2} nodes  -> workflows/{name}.api.json")
    return 0


def cmd_describe(ctx: Ctx, args) -> int:
    """Human-readable view of a lane: node types, key settings, and how they are wired."""
    names = [args.lane] if args.lane else list(ctx.cfg["lanes"])
    for name in names:
        lane = ctx.lane(name)
        g = lane_graph(ctx, name, lane, "<prompt>")
        print("=" * 78)
        print(f"{name}  engine={lane['engine']}  {lane.get('width')}x{lane.get('height')}"
              f"  {lane.get('length', '')}{'f' if lane.get('length') else ''}"
              f"  ~{lane.get('measured_seconds', '?')}s measured")
        print("-" * 78)
        for nid, node in g.items():
            ct = node["class_type"]
            info = {k: v for k, v in node["inputs"].items() if not isinstance(v, list)}
            shown = ", ".join(f"{k}={v}" for k, v in info.items()
                              if k not in ("text", "filename_prefix"))
            if len(shown) > 96:
                shown = shown[:93] + "..."
            print(f"  #{nid:>2} {ct:<28} {shown}")
        print("-" * 78)
        for nid, node in g.items():
            for k, v in node["inputs"].items():
                if isinstance(v, list) and len(v) == 2:
                    src = g.get(v[0], {}).get("class_type", "?")
                    print(f"  #{nid:>2} {node['class_type']}.{k}  <-  #{v[0]} {src}")
        print()
    return 0


# --------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="pipeline", description="AIGC-PP2 ComfyUI pipeline")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--project", default="smoke", help="output subfolder / manifest name")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health").set_defaults(fn=cmd_health)
    sub.add_parser("lanes").set_defaults(fn=cmd_lanes)
    sub.add_parser("export-workflows").set_defaults(fn=cmd_export)

    p = sub.add_parser("describe")
    p.add_argument("--lane", help="omit for every lane")
    p.set_defaults(fn=cmd_describe)

    p = sub.add_parser("image")
    p.add_argument("--lane", default="image_fast")
    p.add_argument("--prompt", required=True)
    p.add_argument("--negative")
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--seed", type=int)
    p.add_argument("--ref", action="append",
                   help="reference image (repeatable); the prompt calls them image 1, image 2…")
    p.add_argument("--out", required=True)
    p.add_argument("--timeout", type=float, default=1800)
    p.set_defaults(fn=cmd_image)

    p = sub.add_parser("video")
    p.add_argument("--lane", default="video_ltx_final")
    p.add_argument("--prompt", required=True)
    p.add_argument("--negative")
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--length", type=int)
    p.add_argument("--fps", type=float)
    p.add_argument("--seed", type=int)
    p.add_argument("--image", help="start keyframe (required by video_ltx_i2v)")
    p.add_argument("--out", required=True)
    p.add_argument("--timeout", type=float, default=7200)
    p.set_defaults(fn=cmd_video)

    p = sub.add_parser("talk", help="keyframe + voice wav -> lip-synced shot (LTX-2.5)")
    p.add_argument("--lane", default="video_ltx_talk")
    p.add_argument("--prompt", required=True)
    p.add_argument("--negative")
    p.add_argument("--image", required=True)
    p.add_argument("--audio", required=True)
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--seed", type=int)
    p.add_argument("--out", required=True)
    p.add_argument("--timeout", type=float, default=7200)
    p.set_defaults(fn=cmd_talk)

    p = sub.add_parser("produce", help="run an episode from bible.json + episodes/<ep>.json")
    p.add_argument("--show", required=True, help="projects/<show>/")
    p.add_argument("--episode", help="episodes/<episode>.json")
    p.add_argument("--stage", default="status",
                   help="assets,keyframes,sheet,voice,animatic,video,assemble | all | status")
    p.add_argument("--only", help="comma-separated shot ids (or character/location ids)")
    p.add_argument("--force", action="store_true", help="regenerate even if the file exists")
    p.set_defaults(fn=produce.run)

    p = sub.add_parser("dialogue")
    p.add_argument("--lane", default="video_s2v")
    p.add_argument("--prompt", required=True)
    p.add_argument("--negative")
    p.add_argument("--audio", required=True)
    p.add_argument("--ref", required=True)
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--length", type=int, help="default: derived from the audio length")
    p.add_argument("--seed", type=int)
    p.add_argument("--out", required=True)
    p.add_argument("--timeout", type=float, default=7200)
    p.set_defaults(fn=cmd_dialogue)

    p = sub.add_parser("animate")
    p.add_argument("--lane", default="video_animate")
    p.add_argument("--prompt", required=True)
    p.add_argument("--negative")
    p.add_argument("--ref", required=True)
    p.add_argument("--drive", required=True)
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--length", type=int)
    p.add_argument("--seed", type=int)
    p.add_argument("--out", required=True)
    p.add_argument("--timeout", type=float, default=7200)
    p.set_defaults(fn=cmd_animate)

    p = sub.add_parser("voice")
    p.add_argument("--text", required=True)
    p.add_argument("--instruct", default="中年男性，沙哑低沉的嗓音，说话缓慢，情绪克制")
    p.add_argument("--language", default="Chinese")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_voice)

    p = sub.add_parser("assemble")
    p.add_argument("--shots", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--keep-parts", action="store_true")
    p.add_argument("--fit", choices=("pad", "cover"), default="pad")
    p.add_argument("--burn-subs", action="store_true")
    p.add_argument("--loudnorm", action="store_true")
    p.add_argument("--label")
    p.set_defaults(fn=cmd_assemble)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ctx = Ctx(args.config, getattr(args, "show", None) or args.project)
    return args.fn(ctx, args)


if __name__ == "__main__":
    raise SystemExit(main())
