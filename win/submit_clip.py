#!/usr/bin/env python3
"""Submit a Wan 2.2 TI2V-5B clip job to the Spark gateway from Windows.

Mirrors submit_keyframe.py: upload the first frame, submit the API-format workflow,
poll, pull the encoded video, verify SHA-256 against the gateway's record.

Graph is the official ComfyUI image_to_video_wan22_5B workflow, expressed for the
gateway's /jobs endpoint.

    UNETLoader(wan2.2_ti2v_5B_fp16) -> ModelSamplingSD3(shift)
    CLIPLoader(umt5_xxl_fp8_e4m3fn_scaled, type=wan)
    VAELoader(wan2.2_vae)
    LoadImage(first frame) -> Wan22ImageToVideoLatent(vae, w, h, length, batch, start_image)
    KSampler(uni_pc/simple, steps, cfg=5.0, denoise=1.0)
    VAEDecode -> CreateVideo(fps) -> SaveVideo(mp4)

Defaults are the ComfyUI template's (shift 8.0, 30 steps). The Wan repo's own
wan_ti2v_5B.py uses shift 5.0 / 50 steps; sweep only if motion disappoints.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

MODELS = [
    "wan2.2_ti2v_5B_fp16",
    "wan_umt5_xxl_fp8_e4m3fn_scaled",
    "wan2.2_vae",
]

# Wardrobe clauses live in work/story/wardrobe.md. A shot prompt without the clause
# for whichever character is legible in frame comes back dressed differently to the
# previous shot — that is how 苏念 ended up in a sleeveless top in s004.
NEGATIVE = (
    "色调艳丽, 过曝, 静态, 细节模糊, 字幕, 画面静止, 最差质量, 低质量, JPEG压缩残留, "
    "丑陋的, 残缺的, 多余的手指, 画得不好的手, 画得不好的脸, 畸形, 手指融合, "
    "杂乱的背景, 三条腿, 背景人很多, 倒着走, "
    "bare shoulders, sleeveless top, tank top, crop top, mismatched outfit"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_image(base_url: str, token: str, image_path: Path) -> str:
    boundary = f"----ManjuBoundary{uuid.uuid4().hex}"
    ctype = mimetypes.guess_type(str(image_path))[0] or "image/png"
    raw = image_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode("utf-8") + raw + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/upload/image",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return resp["name"]


def build_wan22_5b_i2v(
    prompt: str,
    negative: str,
    seed: int,
    width: int,
    height: int,
    length: int,
    steps: int,
    cfg: float,
    shift: float,
    fps: float,
    sampler: str,
    scheduler: str,
    start_image_name: str,
    filename_prefix: str,
    video_format: str,
) -> dict:
    return {
        "37": {"class_type": "UNETLoader",
               "inputs": {"unet_name": "wan2.2_ti2v_5B_fp16.safetensors",
                          "weight_dtype": "default"}},
        "48": {"class_type": "ModelSamplingSD3",
               "inputs": {"model": ["37", 0], "shift": shift}},
        "38": {"class_type": "CLIPLoader",
               "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                          "type": "wan", "device": "default"}},
        "39": {"class_type": "VAELoader",
               "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["38", 0], "text": prompt}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["38", 0], "text": negative}},
        "55": {"class_type": "LoadImage",
               "inputs": {"image": start_image_name}},
        "57": {"class_type": "Wan22ImageToVideoLatent",
               "inputs": {"vae": ["39", 0], "width": width, "height": height,
                          "length": length, "batch_size": 1,
                          "start_image": ["55", 0]}},
        "3": {"class_type": "KSampler",
              "inputs": {"model": ["48", 0], "positive": ["6", 0], "negative": ["7", 0],
                         "latent_image": ["57", 0], "seed": seed, "steps": steps,
                         "cfg": cfg, "sampler_name": sampler, "scheduler": scheduler,
                         "denoise": 1.0}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["3", 0], "vae": ["39", 0]}},
        "56": {"class_type": "CreateVideo",
               "inputs": {"images": ["8", 0], "fps": fps}},
        "47": {"class_type": "SaveVideo",
               "inputs": {"video": ["56", 0], "filename_prefix": filename_prefix,
                          "format": video_format}},
    }


def api_json(url: str, token: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} on {method} {url}: {e.read().decode('utf-8', 'replace')}") from e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://192.168.1.103:8000")
    ap.add_argument("--token", default=os.environ.get("FREEFIELD_TOKEN", ""))
    ap.add_argument("--episode", default="laotang_ep01")
    ap.add_argument("--shot-id", default="s001")
    ap.add_argument("--territory", default="both", choices=("cn", "global", "both"))
    ap.add_argument("--first-frame", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--negative", default=NEGATIVE)
    ap.add_argument("--width", type=int, default=704)
    ap.add_argument("--height", type=int, default=1280)
    ap.add_argument("--length", type=int, default=121, help="frames; 121 = 5.0 s at 24 fps")
    ap.add_argument("--fps", type=float, default=24.0)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--cfg", type=float, default=5.0)
    ap.add_argument("--shift", type=float, default=8.0)
    ap.add_argument("--sampler", default="uni_pc")
    ap.add_argument("--scheduler", default="simple")
    ap.add_argument("--seed", type=int, default=420261113)
    ap.add_argument("--format", default="mp4", choices=("mp4", "mkv", "webm", "auto"))
    ap.add_argument("--filename-prefix", default="manju_clip")
    ap.add_argument("--lane", default="wan-i2v")
    ap.add_argument("--poll", type=float, default=5.0)
    ap.add_argument("--max-poll-errors", type=int, default=120,
                    help="consecutive poll failures tolerated before giving up (~10 min at 5 s)")
    ap.add_argument("--timeout", type=float, default=3600.0)
    ap.add_argument("--out-dir", default=str(Path(__file__).resolve().parent.parent / "work"))
    args = ap.parse_args()

    if not args.token:
        sys.exit("FREEFIELD_TOKEN env var or --token is required")

    frame_path = Path(args.first_frame)
    if not frame_path.is_file():
        sys.exit(f"first frame not found: {frame_path}")

    # The Wan 2.2 VAE compresses 16x16 spatially and 4x temporally; both dimensions must
    # divide by 16 and length-1 must divide by 4, or the latent silently truncates.
    if args.width % 16 or args.height % 16:
        sys.exit(f"width/height must be divisible by 16 (got {args.width}x{args.height})")
    if (args.length - 1) % 4:
        sys.exit(f"length-1 must be divisible by 4 (got {args.length})")

    frame_sha = sha256_file(frame_path)
    start_name = upload_image(args.url, args.token, frame_path)
    print(f"uploaded first frame {frame_path.name} -> {start_name} sha256={frame_sha[:16]}…")

    wf = build_wan22_5b_i2v(
        prompt=args.prompt, negative=args.negative, seed=args.seed,
        width=args.width, height=args.height, length=args.length,
        steps=args.steps, cfg=args.cfg, shift=args.shift, fps=args.fps,
        sampler=args.sampler, scheduler=args.scheduler,
        start_image_name=start_name, filename_prefix=args.filename_prefix,
        video_format=args.format,
    )
    payload = {
        "episode": args.episode,
        "shot_id": args.shot_id,
        "lane": args.lane,
        "territory": args.territory,
        "models": MODELS,
        "workflow": wf,
        "meta": {
            "model": "wan2.2_ti2v_5B_fp16",
            "sampler": f"{args.sampler}/{args.scheduler}",
            "steps": args.steps,
            "cfg": args.cfg,
            "shift": args.shift,
            "seed": args.seed,
            "width": args.width,
            "height": args.height,
            "length": args.length,
            "fps": args.fps,
            "first_frame": frame_path.name,
            "first_frame_sha256": frame_sha,
            "format": args.format,
        },
    }

    t0 = time.perf_counter()
    sub = api_json(f"{args.url}/jobs", args.token, method="POST", body=payload)
    job_id = sub["job_id"]
    print(f"submitted job_id={job_id} wf_sha256={sub['workflow_sha256']} "
          f"{args.width}x{args.height}x{args.length}@ {args.fps}fps")

    last = None
    poll_errors = 0
    while True:
        try:
            job = api_json(f"{args.url}/jobs/{job_id}", args.token)
        except OSError as e:
            # A transient socket timeout killed a 137 s-old poll on 13 Nov while the job
            # went on to finish server-side: the client lost the result, not the render.
            # The job is the source of truth, so keep polling well past a normal hiccup.
            poll_errors += 1
            if poll_errors == 1 or poll_errors % 10 == 0:
                print(f"  poll error x{poll_errors} ({e.__class__.__name__}); job {job_id} "
                      f"keeps running, retrying", flush=True)
            if poll_errors > args.max_poll_errors:
                sys.exit(f"FAIL: no answer from {args.url} after {poll_errors} polls. "
                         f"job {job_id} may still be running and renderable — check "
                         f"{args.url}/jobs/{job_id} before resubmitting")
            time.sleep(args.poll)
            continue
        poll_errors = 0
        status = job["status"]
        if status != last:
            print(f"  status={status} t={time.perf_counter() - t0:.0f}s")
            last = status
        if status == "done":
            break
        if status == "failed":
            sys.exit(f"FAIL: job {job_id} failed: {job.get('error')}")
        if time.perf_counter() - t0 > args.timeout:
            sys.exit(f"FAIL: job {job_id} exceeded {args.timeout:.0f}s, still {status}")
        time.sleep(args.poll)

    dt = time.perf_counter() - t0
    outputs = job.get("output_files") or []
    if not outputs:
        sys.exit(f"FAIL: job {job_id} returned no outputs")

    dest_dir = Path(args.out_dir) / args.episode
    dest_dir.mkdir(parents=True, exist_ok=True)
    for idx, item in enumerate(outputs):
        req = urllib.request.Request(
            f"{args.url}/jobs/{job_id}/file/{idx}",
            headers={"Authorization": f"Bearer {args.token}"},
        )
        dest = dest_dir / f"{args.shot_id}_{item['filename']}"
        hdr_sha = ""
        for attempt in (1, 2, 3):
            try:
                with urllib.request.urlopen(req, timeout=600) as r:
                    hdr_sha = r.headers.get("X-Output-Sha256", "")
                    dest.write_bytes(r.read())
                break
            except OSError as e:
                if attempt == 3:
                    sys.exit(f"FAIL: could not download {item['filename']} after 3 attempts: {e}")
                print(f"  download error ({e.__class__.__name__}), retrying", flush=True)
                time.sleep(5)
        local_sha = sha256_file(dest)
        expected = item["sha256"]
        if local_sha != expected or (hdr_sha and hdr_sha != local_sha):
            sys.exit(f"FAIL: sha256 mismatch for {dest}: local={local_sha} remote={expected}")
        print(f"pulled {dest} ({dest.stat().st_size} bytes) sha256={local_sha} "
              f"VERIFIED in {dt:.0f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
