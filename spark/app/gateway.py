#!/usr/bin/env python3
"""Manju Studio Control Plane & Auth Gateway for DGX Spark.

    Windows Client ──(Bearer token)──▶ gateway :8000 ──▶ ComfyUI :8188

Features:
- Mandatory Bearer token authentication (FREEFIELD_TOKEN; no open bypass).
- Persistent SQLite job queue at $AIGC/app/queue.db with lane-batched scheduling (A3).
- Rule 2 & Rule 5 gate: validates models against $AIGC/models/MANIFEST.json and enforces
  shot-level `territory` (cn | global | both) before enqueuing.
- Rule 1 provenance: computes output SHA-256 and appends an entry to
  $AIGC/provenance/<episode>/MODEL_PROVENANCE.json for every completed job.
- Reverse-proxies native ComfyUI routes without deleting work outputs or provenance.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import importlib.metadata
import json
import logging
import os
import re
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, ClientTimeout, web

AIGC = Path(os.environ["AIGC"]).resolve()
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
TOKEN = os.environ.get("FREEFIELD_TOKEN", "")
GATEWAY_PORT = int(os.environ.get("GATEWAY_PORT", "8000"))

QUEUE_DB = AIGC / "app" / "queue.db"
MANIFEST_PATH = AIGC / "models" / "MANIFEST.json"
OUTPUT_DIR = AIGC / "work" / "output"
PROVENANCE_DIR = AIGC / "provenance"
COMFY_DIR = AIGC / "app" / "ComfyUI"

HOP_HEADERS = {
    "host",
    "authorization",
    "content-length",
    "transfer-encoding",
    "connection",
    "keep-alive",
}
SAFE_SLUG = re.compile(r"^[A-Za-z0-9_.-]+$")
VALID_TERRITORIES = {"cn", "global", "both"}

log = logging.getLogger("gateway")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_engine_version() -> dict[str, str]:
    comfy_rev = "unknown"
    try:
        comfy_rev = subprocess.check_output(
            ["git", "-C", str(COMFY_DIR), "rev-parse", "--short", "HEAD"],
            text=True,
            timeout=5,
        ).strip()
    except Exception:
        pass
    pkgs = {}
    for pkg in ("torch", "sageattention"):
        try:
            pkgs[pkg] = importlib.metadata.version(pkg)
        except Exception:
            pkgs[pkg] = "unknown"
    return {"comfyui": comfy_rev, **pkgs}


def load_manifest() -> tuple[dict[str, dict[str, Any]], set[str]]:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"missing {MANIFEST_PATH}")
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    approved = set(data.get("approved_spdx", ["Apache-2.0", "MIT", "BSD-3-Clause", "BSD-2-Clause", "OpenRAIL++"]))
    by_id = {m["id"]: m for m in data.get("models", [])}
    return by_id, approved


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            episode TEXT NOT NULL,
            shot_id TEXT NOT NULL,
            lane TEXT NOT NULL,
            territory TEXT NOT NULL,
            status TEXT NOT NULL,
            prompt_id TEXT,
            models_json TEXT NOT NULL,
            workflow_json TEXT NOT NULL,
            workflow_sha256 TEXT NOT NULL,
            meta_json TEXT NOT NULL,
            output_files_json TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT
        )
        """
    )
    conn.execute(
        "UPDATE jobs SET status='failed', error='interrupted by gateway restart', finished_at=? WHERE status='running'",
        (utc_now(),),
    )
    conn.commit()
    return conn


def resolve_output_file(subfolder: str, filename: str) -> Path:
    base = OUTPUT_DIR.resolve()
    candidate = (base / subfolder / filename).resolve() if subfolder else (base / filename).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError(f"unsafe output path: {subfolder}/{filename}")
    return candidate


class ControlPlane:
    def __init__(self, session: ClientSession, conn: sqlite3.Connection):
        self.session = session
        self.conn = conn
        self.db_lock = asyncio.Lock()
        self.prov_lock = asyncio.Lock()
        self.gpu_lock = asyncio.Lock()
        self.current_lane: str | None = None
        self.current_models: str | None = None
        self.frees = 0
        self.engine_version = detect_engine_version()
        self._worker_task: asyncio.Task | None = None
        self._wake = asyncio.Event()

    def start(self) -> None:
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def free_vram(self) -> None:
        async with self.session.post(
            f"{COMFYUI_URL}/free",
            json={"unload_models": True, "free_memory": True},
            timeout=ClientTimeout(total=30),
        ) as r:
            r.raise_for_status()
        self.frees += 1

    async def prepare(self, app_name: str, models: str) -> dict[str, Any]:
        async with self.gpu_lock:
            freed = False
            prev = self.current_lane
            if self.current_models is not None and models != self.current_models:
                await self.free_vram()
                freed = True
            self.current_lane = app_name
            self.current_models = models
            return {"freed": freed, "previous": prev, "current": app_name}

    async def scrub(self, unload_vram: bool = True) -> dict[str, Any]:
        async with self.gpu_lock:
            if unload_vram:
                try:
                    await self.free_vram()
                except Exception as e:
                    log.warning("VRAM free warning: %s", e)
                self.current_lane = None
                self.current_models = None
            try:
                async with self.session.post(
                    f"{COMFYUI_URL}/history",
                    json={"clear": True},
                    timeout=ClientTimeout(total=5),
                ) as _:
                    pass
            except Exception as e:
                log.warning("History clear warning: %s", e)
            return {"unloaded_vram": unload_vram}

    async def enqueue_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        episode = payload.get("episode", "")
        shot_id = payload.get("shot_id", "")
        lane = payload.get("lane", "")
        territory = payload.get("territory", "both")
        model_ids = payload.get("models")
        workflow = payload.get("workflow")
        meta = payload.get("meta") or {}

        if not isinstance(episode, str) or not SAFE_SLUG.match(episode):
            raise web.HTTPBadRequest(text=json.dumps({"error": "invalid episode slug"}), content_type="application/json")
        if not isinstance(shot_id, str) or not SAFE_SLUG.match(shot_id):
            raise web.HTTPBadRequest(text=json.dumps({"error": "invalid shot_id"}), content_type="application/json")
        if not isinstance(lane, str) or not lane.strip():
            raise web.HTTPBadRequest(text=json.dumps({"error": "lane is required"}), content_type="application/json")
        if territory not in VALID_TERRITORIES:
            raise web.HTTPBadRequest(
                text=json.dumps({"error": f"territory must be one of {sorted(VALID_TERRITORIES)}"}),
                content_type="application/json",
            )
        if not isinstance(model_ids, list) or not model_ids or not all(isinstance(x, str) for x in model_ids):
            raise web.HTTPBadRequest(text=json.dumps({"error": "models must be a non-empty list of manifest ids"}), content_type="application/json")
        if not isinstance(workflow, dict) or not workflow:
            raise web.HTTPBadRequest(text=json.dumps({"error": "workflow must be a non-empty ComfyUI API prompt dict"}), content_type="application/json")

        by_id, approved_spdx = load_manifest()
        resolved_models: list[dict[str, Any]] = []
        for mid in model_ids:
            entry = by_id.get(mid)
            if entry is None:
                raise web.HTTPBadRequest(
                    text=json.dumps({"error": f"Rule 2: model {mid!r} not declared in models/MANIFEST.json"}),
                    content_type="application/json",
                )
            spdx = entry.get("spdx", "")
            if spdx not in approved_spdx or not entry.get("license_url") or not entry.get("sha256"):
                raise web.HTTPForbidden(
                    text=json.dumps({"error": f"Rule 2: model {mid!r} fails licence gate (spdx={spdx!r})"}),
                    content_type="application/json",
                )
            exclusions = entry.get("territory_exclusions") or []
            if territory in ("global", "both") and exclusions:
                raise web.HTTPForbidden(
                    text=json.dumps({"error": f"Rule 5: model {mid!r} has territory exclusions {exclusions} for territory={territory!r}"}),
                    content_type="application/json",
                )
            weight_path = AIGC / "models" / entry["dir"] / entry["name"]
            if not weight_path.is_file():
                raise web.HTTPBadRequest(
                    text=json.dumps({"error": f"missing weight on disk: {entry['dir']}/{entry['name']} (run bin/restore.sh)"}),
                    content_type="application/json",
                )
            resolved_models.append({
                "id": entry["id"],
                "name": entry["name"],
                "spdx": entry["spdx"],
                "license_url": entry["license_url"],
                "quantisation": entry.get("quantisation", "unknown"),
                "sha256": entry["sha256"],
            })

        canonical_wf = json.dumps(workflow, sort_keys=True, separators=(",", ":")).encode("utf-8")
        wf_sha = sha256_bytes(canonical_wf)
        job_id = uuid.uuid4().hex[:16]
        now = utc_now()

        async with self.db_lock:
            self.conn.execute(
                """
                INSERT INTO jobs (
                    job_id, episode, shot_id, lane, territory, status,
                    models_json, workflow_json, workflow_sha256, meta_json, created_at
                ) VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    episode,
                    shot_id,
                    lane,
                    territory,
                    json.dumps(resolved_models),
                    json.dumps(workflow),
                    wf_sha,
                    json.dumps(meta),
                    now,
                ),
            )
            self.conn.commit()

        self._wake.set()
        return {"job_id": job_id, "status": "queued", "workflow_sha256": wf_sha, "created_at": now}

    async def _next_job(self) -> sqlite3.Row | None:
        async with self.db_lock:
            row = None
            if self.current_lane:
                row = self.conn.execute(
                    "SELECT * FROM jobs WHERE status='queued' AND lane=? ORDER BY created_at ASC LIMIT 1",
                    (self.current_lane,),
                ).fetchone()
            if row is None:
                row = self.conn.execute(
                    "SELECT * FROM jobs WHERE status='queued' ORDER BY created_at ASC LIMIT 1"
                ).fetchone()
            return row

    async def _worker_loop(self) -> None:
        while True:
            try:
                job = await self._next_job()
                if job is None:
                    self._wake.clear()
                    try:
                        await asyncio.wait_for(self._wake.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        pass
                    continue
                await self._run_job(job)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.exception("Worker loop error: %s", e)
                await asyncio.sleep(2.0)

    async def _run_job(self, job: sqlite3.Row) -> None:
        job_id = job["job_id"]
        lane = job["lane"]
        workflow = json.loads(job["workflow_json"])
        models = json.loads(job["models_json"])
        meta = json.loads(job["meta_json"])

        async with self.db_lock:
            self.conn.execute(
                "UPDATE jobs SET status='running', started_at=? WHERE job_id=?",
                (utc_now(), job_id),
            )
            self.conn.commit()

        try:
            async with self.gpu_lock:
                if self.current_lane is not None and self.current_lane != lane:
                    log.info("Lane switch %s -> %s: unloading ComfyUI models", self.current_lane, lane)
                    await self.free_vram()
                self.current_lane = lane
                self.current_models = ",".join(m["id"] for m in models)

                async with self.session.post(
                    f"{COMFYUI_URL}/prompt",
                    json={"prompt": workflow, "client_id": "manju-gateway"},
                    timeout=ClientTimeout(total=30),
                ) as r:
                    body_txt = await r.text()
                    if r.status != 200:
                        raise RuntimeError(f"ComfyUI /prompt HTTP {r.status}: {body_txt}")
                    prompt_resp = json.loads(body_txt)
                    prompt_id = prompt_resp["prompt_id"]

                async with self.db_lock:
                    self.conn.execute("UPDATE jobs SET prompt_id=? WHERE job_id=?", (prompt_id, job_id))
                    self.conn.commit()

                history_entry = await self._wait_for_prompt(prompt_id)

            status_info = history_entry.get("status", {})
            if status_info.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI execution error: {status_info.get('messages')}")

            outputs = []
            for node_id, node_out in (history_entry.get("outputs") or {}).items():
                for kind in ("images", "videos", "gifs", "audio"):
                    for item in node_out.get(kind) or []:
                        fn = item.get("filename")
                        sub = item.get("subfolder", "")
                        if not fn:
                            continue
                        fpath = resolve_output_file(sub, fn)
                        if not fpath.is_file():
                            raise FileNotFoundError(f"ComfyUI reported output {fpath}, but file missing")
                        outputs.append({
                            "node_id": node_id,
                            "kind": kind,
                            "filename": fn,
                            "subfolder": sub,
                            "type": item.get("type", "output"),
                            "sha256": sha256_file(fpath),
                            "bytes": fpath.stat().st_size,
                        })

            if not outputs:
                raise RuntimeError(f"ComfyUI prompt {prompt_id} completed with no output files")

            await self._record_provenance(job, prompt_id, models, meta, outputs)

            async with self.db_lock:
                self.conn.execute(
                    "UPDATE jobs SET status='done', output_files_json=?, finished_at=? WHERE job_id=?",
                    (json.dumps(outputs), utc_now(), job_id),
                )
                self.conn.commit()
            log.info("Job %s (%s/%s) done: %d output(s)", job_id, job["episode"], job["shot_id"], len(outputs))
        except Exception as e:
            log.exception("Job %s failed: %s", job_id, e)
            async with self.db_lock:
                self.conn.execute(
                    "UPDATE jobs SET status='failed', error=?, finished_at=? WHERE job_id=?",
                    (str(e), utc_now(), job_id),
                )
                self.conn.commit()

    async def _wait_for_prompt(self, prompt_id: str) -> dict[str, Any]:
        while True:
            async with self.session.get(
                f"{COMFYUI_URL}/history/{prompt_id}",
                timeout=ClientTimeout(total=10),
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    if prompt_id in data:
                        entry = data[prompt_id]
                        if entry.get("status", {}).get("completed") or entry.get("status", {}).get("status_str") == "error":
                            return entry
            await asyncio.sleep(0.5)

    async def _record_provenance(
        self,
        job: sqlite3.Row,
        prompt_id: str,
        models: list[dict[str, Any]],
        meta: dict[str, Any],
        outputs: list[dict[str, Any]],
    ) -> None:
        ep_dir = PROVENANCE_DIR / job["episode"]
        ep_dir.mkdir(parents=True, exist_ok=True)
        prov_path = ep_dir / "MODEL_PROVENANCE.json"
        record = {
            "job_id": job["job_id"],
            "episode": job["episode"],
            "shot_id": job["shot_id"],
            "lane": job["lane"],
            "territory": job["territory"],
            "prompt_id": prompt_id,
            "models": models,
            "sampler": meta.get("sampler"),
            "steps": meta.get("steps"),
            "cfg": meta.get("cfg"),
            "seed": meta.get("seed"),
            "workflow_sha256": job["workflow_sha256"],
            "blender_sha256": meta.get("blender_sha256"),
            "engine_version": self.engine_version,
            "outputs": outputs,
            "timestamp": utc_now(),
        }
        async with self.prov_lock:
            if prov_path.is_file():
                doc = json.loads(prov_path.read_text(encoding="utf-8"))
            else:
                doc = {"episode": job["episode"], "schema": 1, "entries": []}
            doc["entries"].append(record)
            tmp_path = ep_dir / f".MODEL_PROVENANCE.{job['job_id']}.tmp"
            tmp_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
            tmp_path.replace(prov_path)


def authorized(request: web.Request) -> bool:
    header = request.headers.get("Authorization", "")
    return bool(TOKEN) and hmac.compare_digest(header, f"Bearer {TOKEN}")


@web.middleware
async def auth_mw(request: web.Request, handler):
    if request.path == "/health" or authorized(request):
        return await handler(request)
    return web.json_response({"error": "missing or wrong token"}, status=401)


async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "manju-gateway"})


async def prepare(request: web.Request) -> web.Response:
    body = await request.json()
    if not isinstance(body.get("models"), str) or not isinstance(body.get("app"), str):
        return web.json_response({"error": "expected {app, models}"}, status=400)
    res = await request.app["cp"].prepare(body["app"], body["models"])
    return web.json_response(res)


async def scrub(request: web.Request) -> web.Response:
    unload = True
    if request.can_read_body:
        try:
            body = await request.json()
            unload = bool(body.get("unload_vram", True))
        except Exception:
            pass
    res = await request.app["cp"].scrub(unload_vram=unload)
    return web.json_response(res)


async def status(request: web.Request) -> web.Response:
    cp: ControlPlane = request.app["cp"]
    try:
        async with cp.session.get(f"{COMFYUI_URL}/system_stats", timeout=ClientTimeout(total=5)) as r:
            comfy_stats = await r.json()
    except Exception as e:
        comfy_stats = {"error": str(e)}
    async with cp.db_lock:
        rows = cp.conn.execute("SELECT status, count(*) AS n FROM jobs GROUP BY status").fetchall()
        counts = {r["status"]: r["n"] for r in rows}
    return web.json_response({
        "lane": cp.current_lane,
        "models": cp.current_models,
        "frees": cp.frees,
        "queue": counts,
        "engine_version": cp.engine_version,
        "comfyui": comfy_stats,
    })


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "job_id": row["job_id"],
        "episode": row["episode"],
        "shot_id": row["shot_id"],
        "lane": row["lane"],
        "territory": row["territory"],
        "status": row["status"],
        "prompt_id": row["prompt_id"],
        "models": json.loads(row["models_json"]),
        "workflow_sha256": row["workflow_sha256"],
        "meta": json.loads(row["meta_json"]),
        "output_files": json.loads(row["output_files_json"]) if row["output_files_json"] else [],
        "error": row["error"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


async def submit_job(request: web.Request) -> web.Response:
    body = await request.json()
    res = await request.app["cp"].enqueue_job(body)
    return web.json_response(res, status=202)


async def list_jobs(request: web.Request) -> web.Response:
    cp: ControlPlane = request.app["cp"]
    async with cp.db_lock:
        rows = cp.conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100").fetchall()
    return web.json_response({"jobs": [row_to_dict(r) for r in rows]})


async def get_job(request: web.Request) -> web.Response:
    cp: ControlPlane = request.app["cp"]
    job_id = request.match_info["job_id"]
    async with cp.db_lock:
        row = cp.conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if row is None:
        return web.json_response({"error": "job not found"}, status=404)
    return web.json_response(row_to_dict(row))


async def get_job_file(request: web.Request) -> web.Response:
    cp: ControlPlane = request.app["cp"]
    job_id = request.match_info["job_id"]
    idx = int(request.match_info["idx"])
    async with cp.db_lock:
        row = cp.conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if row is None:
        return web.json_response({"error": "job not found"}, status=404)
    files = json.loads(row["output_files_json"]) if row["output_files_json"] else []
    if idx < 0 or idx >= len(files):
        return web.json_response({"error": "file index out of range"}, status=404)
    item = files[idx]
    fpath = resolve_output_file(item.get("subfolder", ""), item["filename"])
    if not fpath.is_file():
        return web.json_response({"error": "file missing on disk"}, status=404)
    resp = web.FileResponse(fpath)
    resp.headers["X-Output-Sha256"] = item["sha256"]
    return resp


async def forward(request: web.Request) -> web.StreamResponse:
    session: ClientSession = request.app["session"]
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_HEADERS}

    async def body():
        async for chunk in request.content.iter_chunked(1 << 16):
            yield chunk

    data = body() if request.can_read_body else None
    async with session.request(
        request.method,
        f"{COMFYUI_URL}{request.rel_url}",
        headers=headers,
        data=data,
        allow_redirects=False,
    ) as upstream:
        passthrough = {
            k: v for k, v in upstream.headers.items() if k.lower() not in HOP_HEADERS | {"content-encoding"}
        }
        resp = web.StreamResponse(status=upstream.status)
        for k, v in passthrough.items():
            resp.headers[k] = v
        await resp.prepare(request)
        async for chunk in upstream.content.iter_any():
            await resp.write(chunk)
        await resp.write_eof()
        return resp


async def on_startup(app: web.Application) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
    app["session"] = ClientSession(timeout=ClientTimeout(total=None, sock_connect=30), auto_decompress=False)
    app["conn"] = init_db(QUEUE_DB)
    app["cp"] = ControlPlane(app["session"], app["conn"])
    app["cp"].start()


async def on_cleanup(app: web.Application) -> None:
    await app["cp"].stop()
    app["conn"].close()
    await app["session"].close()


def make_app() -> web.Application:
    if not TOKEN:
        raise SystemExit("FREEFIELD_TOKEN is not set; refusing to start an open gateway")
    app = web.Application(middlewares=[auth_mw], client_max_size=1024 ** 3)
    app.router.add_get("/health", health)
    app.router.add_post("/freefield/prepare", prepare)
    app.router.add_post("/freefield/scrub", scrub)
    app.router.add_get("/freefield/status", status)
    app.router.add_post("/jobs", submit_job)
    app.router.add_get("/jobs", list_jobs)
    app.router.add_get("/jobs/{job_id}", get_job)
    app.router.add_get("/jobs/{job_id}/file/{idx}", get_job_file)
    app.router.add_route("*", "/{tail:.*}", forward)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    web.run_app(make_app(), host="0.0.0.0", port=GATEWAY_PORT)
