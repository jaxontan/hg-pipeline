#!/usr/bin/env python3
"""Stateless Zero-Residue Freefield Gateway for DGX Spark.

    Windows Client (SDK) ──▶ gateway :8000 ──▶ comfy-api-proxy :8189 ──▶ ComfyUI :8188

Guarantees:
1. Bearer $FREEFIELD_TOKEN authentication on all routes except /health.
2. POST /freefield/prepare {"app", "models"} unloads previous GPU models when switching apps
   and scrubs ephemeral_io.
3. POST /freefield/scrub immediately unloads GPU models, clears ComfyUI in-memory history,
   and wipes ephemeral_io/{input,output,temp}.
4. Automatic Zero-Residue Scrubbing: whenever an output asset/view stream completes, a
   debounced task waits for ComfyUI's queue to be idle and automatically wipes all files in
   ephemeral_io/{input,output,temp} and clears ComfyUI /history so zero user inputs or
   generated media remain on the DGX Spark.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import os
import shutil
import time
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, web

COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
PROXY_URL = os.environ.get("PROXY_URL", "http://127.0.0.1:8189")
TOKEN = os.environ.get("FREEFIELD_TOKEN", "")
ALLOW_OPEN = os.environ.get("FREEFIELD_ALLOW_OPEN") == "1"
EPHEMERAL_DIR = Path(os.environ.get("EPHEMERAL_DIR", "/home/tdadmin/Desktop/AIGC-Model/ephemeral_io"))
HOP_HEADERS = {"host", "authorization", "content-length", "transfer-encoding", "connection", "keep-alive"}
LOCAL_HOSTS = ("127.0.0.1", "localhost", "0.0.0.0", "[::1]")

log = logging.getLogger("gateway")


def wipe_ephemeral_dirs() -> int:
    """Delete all transient files inside ephemeral_io/{input,output,temp}. Returns removed count."""
    removed = 0
    for sub in ("input", "output", "temp"):
        d = EPHEMERAL_DIR / sub
        d.mkdir(parents=True, exist_ok=True)
        for item in list(d.iterdir()):
            try:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
                removed += 1
            except Exception:
                pass
    return removed


async def is_comfy_idle(session: ClientSession) -> bool:
    try:
        async with session.get(f"{COMFYUI_URL}/queue", timeout=ClientTimeout(total=3)) as r:
            if r.status != 200:
                return False
            q = await r.json()
            return not q.get("queue_running") and not q.get("queue_pending")
    except Exception:
        return False


async def clear_comfy_history_and_ephemeral(session: ClientSession, unload_vram: bool = False) -> dict:
    if unload_vram:
        try:
            async with session.post(
                f"{COMFYUI_URL}/free",
                json={"unload_models": True, "free_memory": True},
                timeout=ClientTimeout(total=15),
            ) as r:
                pass
        except Exception as e:
            log.warning("VRAM free warning: %s", e)
    try:
        async with session.post(
            f"{COMFYUI_URL}/history",
            json={"clear": True},
            timeout=ClientTimeout(total=5),
        ) as r:
            pass
    except Exception as e:
        log.warning("History clear warning: %s", e)
    removed = wipe_ephemeral_dirs()
    log.info("Zero-residue scrub complete (removed=%d, unload_vram=%s)", removed, unload_vram)
    return {"scrubbed_files": removed, "unloaded_vram": unload_vram}


class Pantry:
    """Tracks loaded models on the GPU and manages debounced zero-residue scrubbing."""

    def __init__(self, session: ClientSession):
        self.session = session
        self.models: str | None = None
        self.app: str | None = None
        self.lock = asyncio.Lock()
        self.frees = 0
        self.scrubs = 0
        self._scrub_task: asyncio.Task | None = None

    def schedule_auto_scrub(self, delay_s: float = 4.0) -> None:
        if self._scrub_task and not self._scrub_task.done():
            self._scrub_task.cancel()
        self._scrub_task = asyncio.create_task(self._delayed_scrub(delay_s))

    async def _delayed_scrub(self, delay_s: float) -> None:
        try:
            await asyncio.sleep(delay_s)
            async with self.lock:
                if await is_comfy_idle(self.session):
                    await clear_comfy_history_and_ephemeral(self.session, unload_vram=False)
                    self.scrubs += 1
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning("Auto-scrub error: %s", e)

    async def prepare(self, app: str, models: str) -> dict:
        async with self.lock:
            freed = False
            previous = self.app
            if self.models is not None and models != self.models:
                async with self.session.post(
                    f"{COMFYUI_URL}/free",
                    json={"unload_models": True, "free_memory": True},
                ) as r:
                    r.raise_for_status()
                freed = True
                self.frees += 1
            if await is_comfy_idle(self.session):
                await clear_comfy_history_and_ephemeral(self.session, unload_vram=False)
            self.models, self.app = models, app
            return {"freed": freed, "previous": previous, "current": app}

    async def scrub_now(self, unload_vram: bool = True) -> dict:
        async with self.lock:
            res = await clear_comfy_history_and_ephemeral(self.session, unload_vram=unload_vram)
            if unload_vram:
                self.models = None
                self.app = None
                self.frees += 1
            self.scrubs += 1
            return res


def authorized(request: web.Request) -> bool:
    if ALLOW_OPEN:
        return True
    header = request.headers.get("Authorization", "")
    return bool(TOKEN) and hmac.compare_digest(header, f"Bearer {TOKEN}")


@web.middleware
async def auth_mw(request: web.Request, handler):
    if request.path == "/health" or authorized(request):
        return await handler(request)
    return web.json_response({"error": "missing or wrong token"}, status=401)


async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def prepare(request: web.Request) -> web.Response:
    body = await request.json()
    if not isinstance(body.get("models"), str) or not isinstance(body.get("app"), str):
        return web.json_response({"error": "expected {app, models}"}, status=400)
    result = await request.app["pantry"].prepare(body["app"], body["models"])
    log.info("prepare %s -> %s", body["app"], result)
    return web.json_response(result)


async def scrub(request: web.Request) -> web.Response:
    unload = True
    if request.can_read_body:
        try:
            body = await request.json()
            unload = bool(body.get("unload_vram", True))
        except Exception:
            pass
    result = await request.app["pantry"].scrub_now(unload_vram=unload)
    return web.json_response(result)


async def status(request: web.Request) -> web.Response:
    pantry: Pantry = request.app["pantry"]
    stats = None
    try:
        async with pantry.session.get(f"{COMFYUI_URL}/system_stats") as r:
            stats = await r.json()
    except Exception as e:
        stats = {"error": str(e)}
    ephemeral_files = sum(
        len(list((EPHEMERAL_DIR / sub).glob("*")))
        for sub in ("input", "output", "temp")
        if (EPHEMERAL_DIR / sub).exists()
    )
    return web.json_response({
        "app": pantry.app,
        "models": pantry.models,
        "frees": pantry.frees,
        "scrubs": pantry.scrubs,
        "ephemeral_files": ephemeral_files,
        "comfyui": stats,
    })


def external_base(request: web.Request) -> str:
    forwarded = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip()
    host = request.host
    name = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
    private = name in LOCAL_HOSTS or name.startswith(
        ("10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2", "172.30.", "172.31.")
    )
    scheme = forwarded or (request.scheme if private else "https")
    return f"{scheme}://{host}"


def relink(body: bytes, request: web.Request) -> bytes:
    return body.replace(PROXY_URL.encode(), external_base(request).encode())


async def forward(request: web.Request) -> web.StreamResponse:
    session: ClientSession = request.app["session"]
    pantry: Pantry = request.app["pantry"]
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_HEADERS}

    async def body():
        async for chunk in request.content.iter_chunked(1 << 16):
            yield chunk

    data = body() if request.can_read_body else None
    async with session.request(
        request.method,
        f"{PROXY_URL}{request.rel_url}",
        headers=headers,
        data=data,
        allow_redirects=False,
    ) as upstream:
        passthrough = {
            k: v for k, v in upstream.headers.items() if k.lower() not in HOP_HEADERS | {"content-encoding"}
        }
        if upstream.content_type == "application/json":
            raw = relink(await upstream.read(), request)
            passthrough.pop("Content-Length", None)
            return web.Response(status=upstream.status, body=raw, headers=passthrough)
        resp = web.StreamResponse(status=upstream.status)
        for k, v in passthrough.items():
            resp.headers[k] = v
        await resp.prepare(request)
        async for chunk in upstream.content.iter_any():
            await resp.write(chunk)
        await resp.write_eof()

        # Trigger debounced zero-residue scrub after streaming output files/views back to client
        path_lower = request.path.lower()
        if request.method == "GET" and (
            "/view" in path_lower or "/outputs/" in path_lower or "/assets/" in path_lower
        ):
            pantry.schedule_auto_scrub(delay_s=4.0)
        return resp


async def on_startup(app: web.Application) -> None:
    wipe_ephemeral_dirs()
    app["session"] = ClientSession(timeout=ClientTimeout(total=None, sock_connect=30), auto_decompress=False)
    app["pantry"] = Pantry(app["session"])


async def on_cleanup(app: web.Application) -> None:
    wipe_ephemeral_dirs()
    await app["session"].close()


def make_app() -> web.Application:
    if not TOKEN and not ALLOW_OPEN:
        raise SystemExit("FREEFIELD_TOKEN is not set; refusing to start an open gateway")
    app = web.Application(middlewares=[auth_mw], client_max_size=1024 ** 3)
    app.router.add_get("/health", health)
    app.router.add_post("/freefield/prepare", prepare)
    app.router.add_post("/freefield/scrub", scrub)
    app.router.add_get("/freefield/status", status)
    app.router.add_route("*", "/{tail:.*}", forward)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    web.run_app(make_app(), host="0.0.0.0", port=int(os.environ.get("GATEWAY_PORT", "8000")))
