#!/usr/bin/env python3
"""Submit a Z-Image Turbo INT8 keyframe job to the Spark gateway from Windows,
wait for completion, pull the output PNG to ./work/, and verify SHA-256 + provenance.
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
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return resp["name"]


def build_zimage_turbo_workflow(
    prompt: str,
    seed: int,
    width: int,
    height: int,
    steps: int,
    control_image_name: str | None = None,
    control_strength: float = 0.85,
    handoff: bool = False,
    handoff_split: int = 4,
) -> dict:
    wf = {
        "28": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "z_image_turbo_int8_convrot.safetensors",
                "weight_dtype": "default",
            },
        },
        "30": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_4b_fp8_mixed.safetensors",
                "type": "lumina2",
                "device": "default",
            },
        },
        "29": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"},
        },
        "27": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["30", 0], "text": prompt},
        },
        "33": {
            "class_type": "ConditioningZeroOut",
            "inputs": {"conditioning": ["27", 0]},
        },
        "13": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "11": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["28", 0], "shift": 3.0},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["11", 0],
                "positive": ["27", 0],
                "negative": ["33", 0],
                "latent_image": ["13", 0],
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "res_multistep",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["29", 0]},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": "manju_keyframe"},
        },
    }
    if control_image_name:
        wf["58"] = {
            "class_type": "LoadImage",
            "inputs": {"image": control_image_name},
        }
        wf["64"] = {
            "class_type": "ModelPatchLoader",
            "inputs": {
                "name": "Z-Image-Turbo-Fun-Controlnet-Union-2.1-lite-2602-8steps.safetensors"
            },
        }
        wf["60"] = {
            "class_type": "QwenImageDiffsynthControlnet",
            "inputs": {
                "model": ["28", 0],
                "model_patch": ["64", 0],
                "vae": ["29", 0],
                "image": ["58", 0],
                "strength": control_strength,
            },
        }
        wf["69"] = {
            "class_type": "GetImageSize",
            "inputs": {"image": ["58", 0]},
        }
        wf["13"]["inputs"]["width"] = ["69", 0]
        wf["13"]["inputs"]["height"] = ["69", 1]
        wf["11"]["inputs"]["model"] = ["60", 0]

    if handoff:
        # Step-handoff: the control patch shapes structure for the first
        # `handoff_split` steps, then the *unpatched* model finishes the rest,
        # so the ControlNet stops constraining skin and surface detail.
        # Both arms get the same AuraFlow shift, or the comparison is invalid.
        wf["70"] = {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["60" if control_image_name else "28", 0], "shift": 3.0},
        }
        wf["71"] = {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["28", 0], "shift": 3.0},
        }
        wf["3"] = {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["70", 0],
                "positive": ["27", 0],
                "negative": ["33", 0],
                "latent_image": ["13", 0],
                "add_noise": "enable",
                "noise_seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "res_multistep",
                "scheduler": "simple",
                "start_at_step": 0,
                "end_at_step": handoff_split,
                "return_with_leftover_noise": "enable",
            },
        }
        wf["72"] = {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["71", 0],
                "positive": ["27", 0],
                "negative": ["33", 0],
                "latent_image": ["3", 0],
                "add_noise": "disable",
                "noise_seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "res_multistep",
                "scheduler": "simple",
                "start_at_step": handoff_split,
                "end_at_step": 10000,
                "return_with_leftover_noise": "disable",
            },
        }
        wf["8"]["inputs"]["samples"] = ["72", 0]
    return wf


def api_json(url: str, token: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} on {method} {url}: {e.read().decode('utf-8', 'replace')}") from e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://192.168.1.103:8000")
    ap.add_argument("--token", default=os.environ.get("FREEFIELD_TOKEN", ""))
    ap.add_argument("--episode", default="ep00_p2_smoke")
    ap.add_argument("--shot-id", default="s001")
    ap.add_argument("--territory", default="both", choices=("cn", "global", "both"))
    ap.add_argument("--prompt", default="Cinematic 3D CG vertical keyframe, young woman in tailored navy coat standing under warm streetlamp rain in Shanghai alley, crisp rim lighting, shallow depth of field")
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--height", type=int, default=1344)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--seed", type=int, default=420261113)
    ap.add_argument("--depth-image", default="", help="Optional local Blender depth/canny PNG to upload and condition with Fun ControlNet 2.1 Lite")
    ap.add_argument("--control-strength", type=float, default=0.85)
    ap.add_argument("--handoff", action="store_true",
                    help="Two-sampler step-handoff: ControlNet shapes steps 0..split, plain model finishes")
    ap.add_argument("--handoff-split", type=int, default=4)
    ap.add_argument("--blend-file", default="", help="Optional .blend file path to record blender_sha256 in provenance")
    ap.add_argument("--out-dir", default=str(Path(__file__).resolve().parent.parent / "work"))
    args = ap.parse_args()

    if not args.token:
        sys.exit("FREEFIELD_TOKEN env var or --token is required")

    control_name = None
    models = ["z_image_turbo_int8_convrot", "qwen_3_4b_fp8_mixed", "ae"]
    if args.depth_image:
        depth_path = Path(args.depth_image)
        if not depth_path.is_file():
            sys.exit(f"depth image not found: {depth_path}")
        control_name = upload_image(args.url, args.token, depth_path)
        models.append("z_image_turbo_fun_controlnet_2_1_lite")
        print(f"uploaded control pass {depth_path.name} -> {control_name}")

    blender_sha = None
    if args.blend_file:
        bp = Path(args.blend_file)
        if not bp.is_file():
            sys.exit(f"blend file not found: {bp}")
        blender_sha = sha256_file(bp)

    wf = build_zimage_turbo_workflow(
        args.prompt,
        args.seed,
        args.width,
        args.height,
        args.steps,
        control_image_name=control_name,
        control_strength=args.control_strength,
        handoff=args.handoff,
        handoff_split=args.handoff_split,
    )
    payload = {
        "episode": args.episode,
        "shot_id": args.shot_id,
        "lane": "zimage-turbo",
        "territory": args.territory,
        "models": models,
        "workflow": wf,
        "meta": {
            "sampler": "res_multistep/simple",
            "steps": args.steps,
            "cfg": 1.0,
            "seed": args.seed,
            "width": args.width,
            "height": args.height,
            "blender_sha256": blender_sha,
            "control_strength": args.control_strength if control_name else None,
            "handoff": args.handoff,
            "handoff_split": args.handoff_split if args.handoff else None,
        },
    }

    t0 = time.perf_counter()
    sub = api_json(f"{args.url}/jobs", args.token, method="POST", body=payload)
    job_id = sub["job_id"]
    print(f"submitted job_id={job_id} wf_sha256={sub['workflow_sha256']}")

    while True:
        job = api_json(f"{args.url}/jobs/{job_id}", args.token)
        status = job["status"]
        if status == "done":
            break
        if status == "failed":
            sys.exit(f"FAIL: job {job_id} failed: {job.get('error')}")
        time.sleep(1.0)

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
        with urllib.request.urlopen(req, timeout=60) as r:
            hdr_sha = r.headers.get("X-Output-Sha256", "")
            dest.write_bytes(r.read())
        local_sha = sha256_file(dest)
        expected_sha = item["sha256"]
        if local_sha != expected_sha or (hdr_sha and hdr_sha != local_sha):
            sys.exit(f"FAIL: sha256 mismatch for {dest}: local={local_sha} remote={expected_sha}")
        print(f"pulled {dest} ({dest.stat().st_size} bytes) sha256={local_sha} VERIFIED in {dt:.1f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
