"""Generation manifest: every take is recorded so a shot can be reproduced exactly."""
from __future__ import annotations

import hashlib
import json
import os
import time


class Manifest:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    @staticmethod
    def prompt_hash(graph: dict) -> str:
        blob = json.dumps(graph, sort_keys=True, ensure_ascii=False).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def add(self, *, lane: str, prompt: str, params: dict, graph: dict,
            files: list[str], elapsed: float, extra: dict | None = None) -> dict:
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "lane": lane,
            "prompt": prompt,
            "params": params,
            "graph_hash": self.prompt_hash(graph),
            "files": files,
            "elapsed_s": round(elapsed, 1),
        }
        if extra:
            rec.update(extra)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def records(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
