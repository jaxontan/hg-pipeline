"""Episode runner: drives the lanes from a show bible and an episode shot list.

Stages run in this order and each one is resumable - a finished file is never regenerated
unless you pass --force (optionally narrowed with --only):

  assets     character sheets (face + full body) and location plates      -> assets/input/<show>/
  keyframes  one reference-conditioned still per shot                     -> outputs/<show>/image_ref/
  sheet      contact sheet of every keyframe, for review                  -> projects/<show>/<ep>/
  voice      every dialogue line, one model load                          -> assets/audio/<show>/
  animatic   keyframes + voice cut together, no GPU video                 -> projects/<show>/<ep>/
  video      keyframe -> shot (LTX i2v), or keyframe + line -> lip-sync   -> outputs/<show>/video_ltx_*/
  assemble   cover-crop, subtitles, loudness, concat                      -> projects/<show>/<ep>/<ep>.mp4

Each stage loads one model family, so a whole episode costs three model swaps, not one per shot.
"""
from __future__ import annotations

import glob
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time

from . import assemble as asm
from . import director, graphs
from .comfy import ComfyError

STAGES = ["assets", "keyframes", "sheet", "voice", "animatic", "video", "assemble"]
KEY_LANE, I2V_LANE, TALK_LANE = "image_ref", "video_ltx_i2v", "video_ltx_talk"
S2V_LANE = "video_s2v"   # per-shot fallback: "talk_lane": "video_s2v"
SHEET_W, SHEET_H = 896, 1152


class Run:
    def __init__(self, ctx, show: director.Show, ep: str | None, only: set[str], force: bool):
        self.ctx, self.show, self.ep, self.only, self.force = ctx, show, ep, only, force
        self.in_dir = os.path.join(ctx.input_dir, show.name)
        self.audio_dir = os.path.join(ctx.audio_dir, show.name)
        os.makedirs(self.in_dir, exist_ok=True)
        os.makedirs(self.audio_dir, exist_ok=True)
        self.episode = show.episode(ep) if ep else None
        self.ep_dir = os.path.join(show.dir, ep) if ep else None
        if self.ep_dir:
            os.makedirs(self.ep_dir, exist_ok=True)
        self.failed: list[str] = []

    # ---- plumbing ---------------------------------------------------------
    def want(self, key: str) -> bool:
        return not self.only or key in self.only

    def shots(self):
        return [s for s in self.episode["shots"] if self.want(s["id"])]

    def input_path(self, rel: str) -> str:
        return os.path.join(self.ctx.input_dir, rel)

    def latest(self, lane: str, name: str, ext: str) -> str | None:
        pat = os.path.join(self.ctx.outputs, self.show.name, lane, f"{name}_[0-9]*_.{ext}")
        files = sorted(glob.glob(pat))
        return files[-1] if files else None

    def submit(self, graph: dict, lane: str, prompt: str, params: dict, tag: str) -> str | None:
        t0 = time.time()
        print(f"  [{lane}] {tag}", flush=True)
        try:
            entry = self.ctx.comfy.run(graph, timeout=7200)
        except ComfyError as e:
            print(f"  FAILED {tag}: {e}", file=sys.stderr)
            self.failed.append(tag)
            return None
        files = self.ctx.finish(entry, t0, lane, prompt, params, graph)
        return os.path.join(self.ctx.outputs, files[0]) if files else None

    def seed(self, shot: dict, take: int) -> int:
        return int(shot.get("seed", self.show.seed)) + take - 1

    # ---- names ------------------------------------------------------------
    def key_owner(self, shot: dict) -> dict:
        src = shot.get("key_from")
        if not src:
            return shot
        for s in self.episode["shots"]:
            if s["id"] == src:
                return s
        raise SystemExit(f"{shot['id']}: key_from {src!r} is not a shot in this episode")

    def key_name(self, shot: dict) -> str:
        o = self.key_owner(shot)
        return f"{self.ep}_{o['id']}_k{int(o.get('key_take', 1))}"

    def key_file(self, shot: dict) -> str | None:
        return self.latest(KEY_LANE, self.key_name(shot), "png")

    def clip_name(self, shot: dict) -> str:
        return f"{self.ep}_{shot['id']}_t{int(shot.get('take', 1))}"

    def clip_file(self, shot: dict) -> str | None:
        return (self.latest(TALK_LANE, self.clip_name(shot), "mp4")
                or self.latest(S2V_LANE, self.clip_name(shot), "mp4")
                or self.latest(I2V_LANE, self.clip_name(shot), "mp4"))

    def wav_file(self, shot: dict) -> str:
        return os.path.join(self.audio_dir, f"{self.ep}_{shot['id']}.wav")

    def talks(self, shot: dict) -> bool:
        d = shot.get("dialogue")
        return bool(d) and not d.get("vo")

    # ---- stage: assets ----------------------------------------------------
    def stage_assets(self) -> None:
        cfg, show = self.ctx.cfg["lanes"], self.show
        for cid in show.chars:
            if not self.want(cid):
                continue
            master = self.input_path(show.asset(f"face_{cid}"))
            seed = int(show.char(cid).get("seed", show.seed))
            for i, w in enumerate(show.wardrobes(cid)):
                sheet = self.input_path(show.char_sheet(cid, w))
                if os.path.exists(sheet) and not self.force:
                    continue
                if i == 0:
                    prompt = show.face_prompt(cid, w)
                    g = graphs.image(cfg["image_character"], prompt, None, SHEET_W, SHEET_H,
                                     seed, f"{show.name}/assets/face_{cid}_{w}")
                    face = self.submit(g, "image_character", prompt, {"seed": seed},
                                       f"{cid} face ({w})")
                    if face:
                        shutil.copy2(face, master)
                else:
                    if not os.path.exists(master):
                        raise SystemExit(f"{cid}: master face missing, generate the first "
                                         f"wardrobe before {w!r}")
                    prompt = show.face_variant_prompt(cid, w)
                    g = graphs.image_ref(cfg[KEY_LANE], prompt, [show.asset(f"face_{cid}")],
                                         SHEET_W, SHEET_H, seed,
                                         f"{show.name}/assets/face_{cid}_{w}")
                    face = self.submit(g, KEY_LANE, prompt, {"seed": seed}, f"{cid} face ({w})")
                if not face:
                    continue
                shutil.copy2(face, self.input_path(show.asset(f"face_{cid}_{w}")))
                prompt = show.body_prompt(cid, w)
                g = graphs.image_ref(cfg[KEY_LANE], prompt, [show.asset(f"face_{cid}_{w}")],
                                     SHEET_W, SHEET_H, seed, f"{show.name}/assets/body_{cid}_{w}")
                body = self.submit(g, KEY_LANE, prompt, {"seed": seed}, f"{cid} body ({w})")
                if not body:
                    continue
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", face, "-i", body,
                                "-filter_complex", "hstack=inputs=2", sheet], check=True)
                print(f"    sheet -> {os.path.relpath(sheet, self.ctx.root)}")
        for lid in show.locs:
            if not self.want(lid):
                continue
            plate = self.input_path(show.loc_plate(lid))
            if os.path.exists(plate) and not self.force:
                continue
            seed = int(show.loc(lid).get("seed", show.seed))
            prompt = show.plate_prompt(lid)
            g = graphs.image(cfg["image_fast"], prompt, None, 864, 1536, seed,
                             f"{show.name}/assets/loc_{lid}")
            out = self.submit(g, "image_fast", prompt, {"seed": seed}, f"location {lid}")
            if out:
                shutil.copy2(out, plate)
                print(f"    plate -> {os.path.relpath(plate, self.ctx.root)}")

    # ---- stage: keyframes -------------------------------------------------
    def stage_keyframes(self) -> None:
        lane = self.ctx.lane(KEY_LANE)
        for shot in self.shots():
            if shot.get("key_from"):
                continue
            name = self.key_name(shot)
            if self.key_file(shot) and not self.force:
                continue
            prompt, refs = self.show.keyframe(shot)
            missing = [r for r in refs if not os.path.exists(self.input_path(r))]
            if missing:
                raise SystemExit(f"{shot['id']}: missing assets {missing} - run --stage assets")
            seed = self.seed(shot, int(shot.get("key_take", 1)))
            prefix = f"{self.show.name}/{KEY_LANE}/{name}"
            if refs:
                g = graphs.image_ref(lane, prompt, refs, lane["width"], lane["height"], seed,
                                     prefix)
            else:
                g = graphs.image(self.ctx.lane("image_character"), prompt, None, lane["width"],
                                 lane["height"], seed, prefix)
            self.submit(g, KEY_LANE, prompt, {"seed": seed, "refs": refs}, f"{shot['id']} key")

    # ---- stage: sheet -----------------------------------------------------
    def stage_sheet(self) -> None:
        from PIL import Image, ImageDraw
        cells = [(s["id"], self.key_file(s)) for s in self.episode["shots"]]
        cells = [(sid, f) for sid, f in cells if f]
        if not cells:
            print("  no keyframes yet")
            return
        cw, ch, cols = 270, 480, 8
        rows = math.ceil(len(cells) / cols)
        sheet = Image.new("RGB", (cols * cw, rows * (ch + 22)), (18, 18, 18))
        draw = ImageDraw.Draw(sheet)
        for i, (sid, f) in enumerate(cells):
            x, y = (i % cols) * cw, (i // cols) * (ch + 22)
            im = Image.open(f).convert("RGB").resize((cw, ch), Image.LANCZOS)
            sheet.paste(im, (x, y + 22))
            draw.text((x + 6, y + 5), sid, fill=(240, 240, 240))
        out = os.path.join(self.ep_dir, f"{self.ep}_keyframes.jpg")
        sheet.save(out, quality=88)
        print(f"  contact sheet -> {os.path.relpath(out, self.ctx.root)}  ({len(cells)} shots)")

    # ---- stage: voice -----------------------------------------------------
    def stage_voice(self) -> None:
        jobs = []
        for shot in self.shots():
            v = self.show.voice(shot)
            if not v:
                continue
            out = self.wav_file(shot)
            if os.path.exists(out) and not self.force:
                continue
            jobs.append({"text": v[0], "instruct": v[1], "language": "Chinese", "out": out,
                         "id": shot["id"]})
        if not jobs:
            print("  no lines to generate")
            return
        vcfg = self.ctx.cfg["voice"]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8",
                                         dir=os.path.join(self.ctx.root, "tmp")) as fh:
            json.dump(jobs, fh, ensure_ascii=False)
        cmd = [os.path.join(self.ctx.root, vcfg["venv_python"]), "-m", "pipeline.voice",
               "--batch", fh.name, "--model-dir", os.path.join(self.ctx.root, vcfg["model_dir"])]
        print(f"  [voice] {len(jobs)} lines, one model load", flush=True)
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=self.ctx.root, capture_output=True, text=True)
        os.remove(fh.name)
        infos = [json.loads(l) for l in proc.stdout.splitlines() if l.startswith("{")]
        for job, info in zip(jobs, infos):
            self.ctx.manifest.add(lane="voice", prompt=job["text"],
                                  params={"instruct": job["instruct"], "shot": job["id"]},
                                  graph={"voice": True},
                                  files=[os.path.relpath(job["out"], self.ctx.root)],
                                  elapsed=info["gen_s"], extra=info)
            print(f"    {job['id']}: {info['duration_s']}s  {job['text'][:24]}")
        if proc.returncode != 0 or len(infos) != len(jobs):
            print(proc.stderr[-3000:], file=sys.stderr)
            self.failed.append("voice")
        print(f"  voice stage {time.time() - t0:.0f}s")

    # ---- timing -----------------------------------------------------------
    def talk_timing(self, shot: dict) -> tuple[int, float, float]:
        """(frames, total seconds, lead-in seconds) for a lip-sync shot."""
        lane = self.ctx.lane(TALK_LANE)
        lead, tail = float(lane.get("lead_in_s", 0.25)), float(lane.get("tail_s", 0.35))
        dur = asm.duration(self.wav_file(shot))
        frames = int(math.ceil((dur + lead + tail) * lane["fps"] / 8) * 8 + 1)
        return frames, frames / lane["fps"], lead

    def padded_wav(self, shot: dict) -> str:
        frames, total, lead = self.talk_timing(shot)
        rel = f"{self.show.name}/{self.ep}_{shot['id']}_line.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", self.wav_file(shot), "-af",
                        f"adelay={int(lead * 1000)}:all=1,apad", "-t", f"{total:.4f}",
                        "-ar", "48000", self.input_path(rel)], check=True)
        return rel

    def shot_seconds(self, shot: dict) -> float:
        if self.talks(shot) and os.path.exists(self.wav_file(shot)):
            return self.talk_timing(shot)[1]
        return self.plain_frames(shot) / director.FPS

    def plain_frames(self, shot: dict) -> int:
        """Frames for a shot without lip-sync. A voice-over stretches the shot to fit the line."""
        secs = float(shot.get("duration", 4))
        d = shot.get("dialogue")
        if d and d.get("vo") and os.path.exists(self.wav_file(shot)):
            secs = max(secs, asm.duration(self.wav_file(shot)) + 0.6)
        return director.frames_for(secs)

    # ---- stage: animatic --------------------------------------------------
    def stage_animatic(self) -> None:
        work = os.path.join(self.ep_dir, "animatic_parts")
        os.makedirs(work, exist_ok=True)
        parts = []
        for i, shot in enumerate(self.episode["shots"]):
            key = self.key_file(shot)
            if not key:
                print(f"  {shot['id']}: no keyframe, skipped")
                continue
            secs = self.shot_seconds(shot)
            dst = os.path.join(work, f"a_{i:03d}.mp4")
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", f"{secs:.3f}",
                   "-i", key]
            wav = self.wav_file(shot)
            if shot.get("dialogue") and os.path.exists(wav):
                cmd += ["-i", wav, "-af", "adelay=250:all=1,apad"]
            else:
                cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            cmd += ["-t", f"{secs:.3f}", "-vf",
                    "scale=540:960:force_original_aspect_ratio=increase,crop=540:960,fps=24",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt",
                    "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", dst]
            subprocess.run(cmd, check=True)
            parts.append(dst)
        if not parts:
            return
        listing = os.path.join(work, "concat.txt")
        with open(listing, "w", encoding="utf-8") as fh:
            fh.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
        out = os.path.join(self.ep_dir, f"{self.ep}_animatic.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", listing, "-c", "copy", out], check=True)
        shutil.rmtree(work, ignore_errors=True)
        print(f"  animatic -> {os.path.relpath(out, self.ctx.root)}  "
              f"({asm.duration(out):.1f}s, {len(parts)} shots)")

    # ---- stage: video -----------------------------------------------------
    def stage_video(self) -> None:
        neg = self.show.style.get("negative") or self.ctx.default("negative_ltx")
        for shot in self.shots():
            name = self.clip_name(shot)
            if self.clip_file(shot) and not self.force:
                continue
            key = self.key_file(shot)
            if not key:
                raise SystemExit(f"{shot['id']}: no keyframe - run --stage keyframes")
            key_rel = f"{self.show.name}/{self.ep}_{shot['id']}_key.png"
            shutil.copy2(key, self.input_path(key_rel))
            prompt = self.show.video(shot)
            seed = self.seed(shot, int(shot.get("take", 1)))
            if self.talks(shot) and not os.path.exists(self.wav_file(shot)):
                raise SystemExit(f"{shot['id']}: no voice line - run --stage voice")
            if self.talks(shot) and shot.get("talk_lane") == S2V_LANE:
                # Wan S2V fallback (480x832): for a shot LTX keeps spoiling, e.g. by painting
                # captions into the picture. Softer, but it never draws text.
                lane = self.ctx.lane(S2V_LANE)
                audio = self.padded_wav(shot)
                total = self.talk_timing(shot)[1]
                frames = (round(total * lane["fps"]) // 4) * 4 + 1
                g = graphs.s2v(lane, prompt, self.ctx.default("negative_cn"), key_rel, audio,
                               lane["width"], lane["height"], frames, seed,
                               f"{self.show.name}/{S2V_LANE}/{name}")
                self.submit(g, S2V_LANE, prompt,
                            {"seed": seed, "frames": frames, "key": key_rel, "audio": audio},
                            f"{shot['id']} {frames}f (s2v fallback)")
                continue
            if self.talks(shot):
                lane_name, lane = TALK_LANE, self.ctx.lane(TALK_LANE)
                frames = self.talk_timing(shot)[0]
                audio = self.padded_wav(shot)
            else:
                lane_name, lane = I2V_LANE, self.ctx.lane(I2V_LANE)
                if shot.get("dialogue") and not os.path.exists(self.wav_file(shot)):
                    raise SystemExit(f"{shot['id']}: no voice-over line - run --stage voice")
                frames = self.plain_frames(shot)
                audio = None
            g = graphs.ltx_i2v(lane, prompt, neg, key_rel, lane["width"], lane["height"],
                               frames, lane["fps"], seed,
                               f"{self.show.name}/{lane_name}/{name}", audio=audio)
            self.submit(g, lane_name, prompt,
                        {"seed": seed, "frames": frames, "key": key_rel, "audio": audio},
                        f"{shot['id']} {frames}f")

    # ---- stage: assemble --------------------------------------------------
    def stage_assemble(self) -> None:
        entries, missing = [], []
        for shot in self.episode["shots"]:
            clip = self.clip_file(shot)
            if not clip:
                missing.append(shot["id"])
                continue
            e = {"id": shot["id"], "file": clip}
            d = shot.get("dialogue")
            if d:
                e["text"] = d.get("subtitle", d["text"])
                if d.get("vo"):
                    e["voice"] = self.wav_file(shot)
            entries.append(e)
        if missing:
            print(f"  not rendered yet, left out of the cut: {', '.join(missing)}")
        path = os.path.join(self.ep_dir, "shots.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, ensure_ascii=False, indent=1)
        fin = self.show.bible.get("finish", {})
        asm.assemble(entries, os.path.join(self.ep_dir, f"{self.ep}.mp4"), fit="cover",
                     burn_subs=fin.get("burn_subtitles", True),
                     loudnorm=fin.get("loudnorm", True), label=fin.get("label"))

    # ---- status -----------------------------------------------------------
    def status(self) -> None:
        print(f"{self.show.name} / {self.ep}: {self.episode.get('title', '')}")
        total = 0.0
        for shot in self.episode["shots"]:
            d = shot.get("dialogue")
            wav = "-" if not d else ("ok" if os.path.exists(self.wav_file(shot)) else "TODO")
            clip = self.clip_file(shot)
            secs = self.shot_seconds(shot)
            total += secs
            print(f"  {shot['id']:<6} {shot.get('size', ''):<6} {shot.get('move', 'static'):<10} "
                  f"{secs:4.1f}s  key={'ok' if self.key_file(shot) else 'TODO':<4} "
                  f"voice={wav:<4} video={'ok' if clip else 'TODO':<4} "
                  f"{(d or {}).get('text') or shot.get('action') or shot.get('motion', '')}")
        print(f"  {len(self.episode['shots'])} shots, {total:.0f}s planned")


def run(ctx, args) -> int:
    show = director.Show(ctx.root, args.show)
    only = {x for x in (args.only or "").split(",") if x}
    stages = STAGES if args.stage == "all" else args.stage.split(",")
    for s in stages:
        if s not in STAGES + ["status"]:
            raise SystemExit(f"unknown stage {s!r}; choose from {', '.join(STAGES)}, status, all")
    if any(s != "assets" for s in stages) and not args.episode:
        raise SystemExit("--episode is required for every stage except assets")
    r = Run(ctx, show, args.episode, only, args.force)
    for s in stages:
        print(f"== {s}", flush=True)
        r.status() if s == "status" else getattr(r, f"stage_{s}")()
        if r.failed:
            print(f"stopped after {s}: {len(r.failed)} failed ({', '.join(r.failed)})",
                  file=sys.stderr)
            return 1
    return 0
