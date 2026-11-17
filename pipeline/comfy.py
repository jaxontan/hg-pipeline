"""Minimal stdlib client for the local ComfyUI API."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Optional


class ComfyError(RuntimeError):
    pass


class Comfy:
    def __init__(self, host: str = "http://127.0.0.1:9090", timeout: int = 120):
        self.host = host.rstrip("/")
        self.timeout = timeout

    # ---- low level -------------------------------------------------------
    def _request(self, path: str, payload: Optional[dict] = None, timeout: Optional[int] = None):
        url = self.host + path
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
            body = resp.read()
        return json.loads(body) if body else None

    # ---- api -------------------------------------------------------------
    def health(self) -> bool:
        try:
            self._request("/system_stats", timeout=10)
            return True
        except Exception:
            return False

    def submit(self, graph: dict, client_id: str = "aigcpp2") -> str:
        try:
            r = self._request("/prompt", {"prompt": graph, "client_id": client_id})
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            raise ComfyError(f"submit failed {e.code}: {detail[:3000]}") from None
        if "prompt_id" not in r:
            raise ComfyError(f"submit returned no prompt_id: {r}")
        return r["prompt_id"]

    def queue(self) -> dict:
        return self._request("/queue", timeout=30)

    def history(self, prompt_id: str) -> Optional[dict]:
        h = self._request(f"/history/{prompt_id}", timeout=60)
        return h.get(prompt_id)

    def wait(self, prompt_id: str, timeout: float = 7200.0,
             on_tick: Optional[Callable[[float, int], None]] = None,
             poll: float = 3.0) -> dict:
        t0 = time.time()
        last_running = -1
        while True:
            entry = self.history(prompt_id)
            if entry is not None:
                return entry
            running = len(self.queue().get("queue_running", []))
            if on_tick and running != last_running:
                on_tick(time.time() - t0, running)
                last_running = running
            if time.time() - t0 > timeout:
                raise ComfyError(f"timeout after {timeout:.0f}s waiting for {prompt_id}")
            time.sleep(poll)

    @staticmethod
    def status(entry: dict) -> str:
        return (entry.get("status") or {}).get("status_str", "unknown")

    @staticmethod
    def error(entry: dict) -> Optional[str]:
        for kind, payload in (entry.get("status") or {}).get("messages") or []:
            if kind in ("execution_error", "execution_interrupted"):
                return f"{kind}: {json.dumps(payload)[:3000]}"
        return None

    @staticmethod
    def files(entry: dict) -> list[dict]:
        """Every produced file, flattened, with its kind (images / gifs / audio / video)."""
        out = []
        for _node, blob in (entry.get("outputs") or {}).items():
            for kind, value in blob.items():
                if not isinstance(value, list):
                    continue
                for item in value:
                    if isinstance(item, dict) and item.get("filename"):
                        item = dict(item)
                        item["kind"] = kind
                        out.append(item)
        return out

    @staticmethod
    def relpath(item: dict) -> str:
        sub = item.get("subfolder") or ""
        return f"{sub}/{item['filename']}".lstrip("/")

    def run(self, graph: dict, timeout: float = 7200.0,
            on_tick: Optional[Callable[[float, int], None]] = None) -> dict:
        pid = self.submit(graph)
        print(f"  queued {pid}", flush=True)
        entry = self.wait(pid, timeout=timeout, on_tick=on_tick)
        status = self.status(entry)
        if status != "success":
            raise ComfyError(self.error(entry) or f"status={status}")
        return entry
