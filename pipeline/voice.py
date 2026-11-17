"""Voice lane. Runs inside venv-tts (qwen-tts pins transformers 4.57.3).

Invoked by cli.py as:  venv-tts/bin/python -m pipeline.voice --text ... --out file.wav
or, for a whole episode in one model load:
                       venv-tts/bin/python -m pipeline.voice --batch jobs.json
where jobs.json is [{"text", "instruct", "language"?, "out"}, ...].
Prints one JSON line per finished wav so the caller can log it.
"""
from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

DEFAULT_INSTRUCT = "中年男性，沙哑低沉的嗓音，说话缓慢，情绪克制"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text")
    ap.add_argument("--instruct", default=DEFAULT_INSTRUCT)
    ap.add_argument("--language", default="Chinese")
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out")
    ap.add_argument("--batch", help="JSON list of jobs; replaces --text/--out")
    args = ap.parse_args()

    if args.batch:
        with open(args.batch, encoding="utf-8") as fh:
            jobs = json.load(fh)
    elif args.text and args.out:
        jobs = [{"text": args.text, "instruct": args.instruct, "language": args.language,
                 "out": args.out}]
    else:
        ap.error("give --text and --out, or --batch")

    t0 = time.time()
    model = Qwen3TTSModel.from_pretrained(args.model_dir, device_map="cuda:0",
                                          dtype=torch.bfloat16)
    load_s = time.time() - t0

    for job in jobs:
        t1 = time.time()
        wavs, sr = model.generate_voice_design(
            text=job["text"], instruct=job.get("instruct") or DEFAULT_INSTRUCT,
            language=job.get("language", "Chinese"))
        gen_s = time.time() - t1
        wav = np.asarray(wavs[0], dtype=np.float32).squeeze()
        os.makedirs(os.path.dirname(job["out"]) or ".", exist_ok=True)
        sf.write(job["out"], wav, sr)
        print(json.dumps({
            "file": job["out"],
            "sample_rate": int(sr),
            "duration_s": round(len(wav) / sr, 2),
            "peak": round(float(np.abs(wav).max()), 3),
            "load_s": round(load_s, 1),
            "gen_s": round(gen_s, 1),
        }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
