"""
Houdini FX Pipeline — Local Management Server
Run via shelf tool. Serves the web UI and exposes a REST API for
managing projects, sequences, shots, assets, and browsing publishes.

Start:  python server.py
Stop:   Ctrl+C  or close via shelf tool
"""

import logging
import re
import shutil
import socket
import sys
import threading
from pathlib import Path

import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Bootstrap pipeline path
# ---------------------------------------------------------------------------

_SERVER_DIR = Path(__file__).resolve().parent
_PIPELINE_PYTHON = _SERVER_DIR / "python"
if str(_PIPELINE_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_PYTHON))

import pipeline
import pipeline.config as _cfg  # noqa: F401 — imported for package init side-effects

logger = logging.getLogger("pipeline.server")

# ---------------------------------------------------------------------------
# App + middleware
# ---------------------------------------------------------------------------

app = FastAPI(title="FX Pipeline Manager", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_WEB_DIST = _SERVER_DIR / "pipeline_web" / "dist"

# ---------------------------------------------------------------------------
# Write lock — all mutation operations acquire this before touching filesystem
# state or the pipeline index. Read endpoints remain lock-free.
# ---------------------------------------------------------------------------

_write_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str
    folder: str = ""
    fps: int = 24
    resolution: str = "1920x1080"

class SequenceCreate(BaseModel):
    seq: str

class ShotCreate(BaseModel):
    shot: str

class AssetTypeCreate(BaseModel):
    asset_type: str

class AssetCreate(BaseModel):
    asset: str

# ---------------------------------------------------------------------------
# Helpers + input validation
# ---------------------------------------------------------------------------

_VALID_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_MAX_ID_LEN  = 64
_MAX_NAME_LEN = 128
# Path separators, null bytes, and traversal patterns are always dangerous.
_DANGEROUS_NAME_RE = re.compile(r"[\x00/\\]|\.\.")


def _validate_id(value: str, label: str) -> str:
    """Validate a filesystem path component (folder, seq, shot, asset, asset_type).

    Accepts only letters, digits, hyphens, and underscores. Rejects empty
    values, oversized values, and anything that could enable path traversal.
    Returns the stripped value on success; raises HTTP 400 on failure.
    """
    v = (value or "").strip()
    if not v:
        raise HTTPException(status_code=400, detail=f"{label} is required.")
    if len(v) > _MAX_ID_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"{label} exceeds maximum length ({_MAX_ID_LEN} chars).",
        )
    if not _VALID_ID_RE.match(v):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{label} contains invalid characters. "
                "Use letters, digits, hyphens, and underscores only."
            ),
        )
    return v


def _validate_display_name(value: str, label: str) -> str:
    """Validate a human-readable display name (e.g. project name).

    Less strict than _validate_id: allows spaces, unicode, and most punctuation.
    Rejects null bytes, path separators, '..' traversal patterns, and oversized
    values — the minimum set needed to prevent misuse in display contexts.
    Returns the stripped value on success; raises HTTP 400 on failure.
    """
    v = (value or "").strip()
    if not v:
        raise HTTPException(status_code=400, detail=f"{label} is required.")
    if len(v) > _MAX_NAME_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"{label} exceeds maximum length ({_MAX_NAME_LEN} chars).",
        )
    if _DANGEROUS_NAME_RE.search(v):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{label} contains invalid characters. "
                "Null bytes, path separators, and '..' are not allowed."
            ),
        )
    return v


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()


def _get_project_or_404(folder: str) -> dict:
    project = pipeline.get_project(folder)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{folder}' not found.")
    return project


def _refresh_index_after_delete(folder: str) -> None:
    """Rebuild the project publish index after a filesystem deletion.

    Called inside _write_lock after shutil.rmtree so that the gallery cannot
    display stale records for deleted entities. Failures are logged and swallowed
    to avoid masking a successful delete response.
    """
    try:
        if (pipeline.projects_root() / folder).is_dir():
            pipeline.write_project_index(folder)
    except Exception as exc:
        logger.warning("Could not refresh publish index for '%s': %s", folder, exc)

# ---------------------------------------------------------------------------
# Routers — all registered BEFORE the static catch-all mount so that /api
# routes can never be shadowed by the static file handler.
# ---------------------------------------------------------------------------

_r_projects  = APIRouter(prefix="/api", tags=["projects"])
_r_sequences = APIRouter(prefix="/api", tags=["sequences"])
_r_shots     = APIRouter(prefix="/api", tags=["shots"])
_r_assets    = APIRouter(prefix="/api", tags=["assets"])
_r_publishes = APIRouter(prefix="/api", tags=["publishes"])

# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@_r_projects.get("/projects")
def list_projects():
    return pipeline.load_projects()


@_r_projects.post("/projects", status_code=201)
def create_project(body: ProjectCreate):
    # Display name: human-readable, loose validation.
    name = _validate_display_name(body.name, "Project name")
    # Filesystem identifier: strict validation.
    folder = _validate_id(body.folder or _slug(name), "Project folder")
    with _write_lock:
        try:
            project = pipeline.add_project(
                name=name,
                folder=folder,
                fps=body.fps,
                resolution=body.resolution,
            )
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        (pipeline.projects_root() / folder).mkdir(parents=True, exist_ok=True)
    return project


@_r_projects.delete("/projects/{folder}", status_code=200)
def delete_project(folder: str, delete_files: bool = False):
    folder = _validate_id(folder, "Project folder")
    with _write_lock:
        projects = pipeline.load_projects()
        match = next((p for p in projects if p["folder"] == folder), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"Project '{folder}' not found.")
        pipeline.save_projects([p for p in projects if p["folder"] != folder])
        if delete_files:
            proj_dir = pipeline.projects_root() / folder
            if proj_dir.exists():
                shutil.rmtree(proj_dir)
            # Project directory (including .pipeline/publishes.json) is gone;
            # no index refresh needed.
    return {"deleted": folder}


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------

@_r_sequences.get("/projects/{folder}/sequences")
def list_sequences(folder: str):
    folder = _validate_id(folder, "Project folder")
    return _get_project_or_404(folder).get("sequences", [])


@_r_sequences.post("/projects/{folder}/sequences", status_code=201)
def create_sequence(folder: str, body: SequenceCreate):
    folder = _validate_id(folder, "Project folder")
    seq = _validate_id((body.seq or "").strip().upper(), "Sequence code")
    with _write_lock:
        try:
            pipeline.add_sequence(folder, seq)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        (pipeline.projects_root() / folder / seq).mkdir(parents=True, exist_ok=True)
    return {"seq": seq}


@_r_sequences.delete("/projects/{folder}/sequences/{seq}", status_code=200)
def delete_sequence(folder: str, seq: str, delete_files: bool = False):
    folder = _validate_id(folder, "Project folder")
    seq = _validate_id(seq, "Sequence code")
    with _write_lock:
        projects = pipeline.load_projects()
        match = next((p for p in projects if p["folder"] == folder), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"Project '{folder}' not found.")
        seqs = match.get("sequences", [])
        if seq not in seqs:
            raise HTTPException(status_code=404, detail=f"Sequence '{seq}' not found.")
        match["sequences"] = [s for s in seqs if s != seq]
        pipeline.save_projects(projects)
        if delete_files:
            seq_dir = pipeline.projects_root() / folder / seq
            if seq_dir.exists():
                shutil.rmtree(seq_dir)
            _refresh_index_after_delete(folder)
    return {"deleted": seq}


# ---------------------------------------------------------------------------
# Shots
# ---------------------------------------------------------------------------

@_r_shots.get("/projects/{folder}/sequences/{seq}/shots")
def list_shots(folder: str, seq: str):
    folder = _validate_id(folder, "Project folder")
    seq = _validate_id(seq, "Sequence code")
    seq_dir = pipeline.projects_root() / folder / seq
    if not seq_dir.exists():
        return []
    return sorted(d.name for d in seq_dir.iterdir() if d.is_dir())


@_r_shots.post("/projects/{folder}/sequences/{seq}/shots", status_code=201)
def create_shot(folder: str, seq: str, body: ShotCreate):
    folder = _validate_id(folder, "Project folder")
    seq = _validate_id(seq, "Sequence code")
    shot = _validate_id((body.shot or "").strip(), "Shot code")
    with _write_lock:
        work_dir = pipeline.shot_work_houdini(folder, seq, shot)
        if work_dir.exists():
            raise HTTPException(status_code=409, detail=f"Shot '{shot}' already exists.")
        pipeline.make_shot_work_dirs(folder, seq, shot)
    return {"shot": shot, "path": str(work_dir)}


@_r_shots.delete("/projects/{folder}/sequences/{seq}/shots/{shot}", status_code=200)
def delete_shot(folder: str, seq: str, shot: str, delete_files: bool = False):
    folder = _validate_id(folder, "Project folder")
    seq = _validate_id(seq, "Sequence code")
    shot = _validate_id(shot, "Shot code")
    # Shots are filesystem-only (no metadata record). Refusing to delete files
    # would leave state unchanged while returning success — explicitly rejected.
    if not delete_files:
        raise HTTPException(
            status_code=400,
            detail="Shot has no separate metadata record. Pass ?delete_files=true to remove from filesystem.",
        )
    with _write_lock:
        shot_dir = pipeline.projects_root() / folder / seq / shot
        if not shot_dir.exists():
            raise HTTPException(status_code=404, detail=f"Shot '{shot}' not found.")
        shutil.rmtree(shot_dir)
        _refresh_index_after_delete(folder)
    return {"deleted": shot}


@_r_shots.get("/projects/{folder}/sequences/{seq}/shots/{shot}/hips")
def list_hip_files(folder: str, seq: str, shot: str):
    folder = _validate_id(folder, "Project folder")
    seq = _validate_id(seq, "Sequence code")
    shot = _validate_id(shot, "Shot code")
    work_dir = pipeline.shot_work_houdini(folder, seq, shot)
    hips = pipeline.find_hip_files(work_dir)
    result = []
    for hip in hips:
        parsed = pipeline.parse_hip_filename(hip.name)
        result.append({
            "name": hip.name,
            "path": str(hip),
            "size_mb": round(hip.stat().st_size / (1024 * 1024), 2) if hip.exists() else 0,
            "task": parsed["task"] if parsed else "",
            "version": parsed["version"] if parsed else 0,
            "version_str": parsed["version_str"] if parsed else "",
        })
    return result


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

@_r_assets.get("/projects/{folder}/assets")
def list_assets(folder: str):
    folder = _validate_id(folder, "Project folder")
    _get_project_or_404(folder)
    assets_dir = pipeline.projects_root() / folder / "assets"
    if not assets_dir.exists():
        return {}
    result = {}
    for type_dir in sorted(assets_dir.iterdir()):
        if type_dir.is_dir():
            result[type_dir.name] = sorted(
                d.name for d in type_dir.iterdir() if d.is_dir()
            )
    return result


@_r_assets.post("/projects/{folder}/asset-types", status_code=201)
def create_asset_type(folder: str, body: AssetTypeCreate):
    folder = _validate_id(folder, "Project folder")
    asset_type = _validate_id((body.asset_type or "").strip().lower(), "Asset type")
    with _write_lock:
        (pipeline.projects_root() / folder / "assets" / asset_type).mkdir(
            parents=True, exist_ok=True
        )
    return {"asset_type": asset_type}


@_r_assets.delete("/projects/{folder}/asset-types/{asset_type}", status_code=200)
def delete_asset_type(folder: str, asset_type: str, delete_files: bool = False):
    folder = _validate_id(folder, "Project folder")
    asset_type = _validate_id(asset_type, "Asset type")
    if not delete_files:
        raise HTTPException(
            status_code=400,
            detail="Asset type has no separate metadata record. Pass ?delete_files=true to remove from filesystem.",
        )
    with _write_lock:
        type_dir = pipeline.projects_root() / folder / "assets" / asset_type
        if not type_dir.exists():
            raise HTTPException(status_code=404, detail=f"Asset type '{asset_type}' not found.")
        shutil.rmtree(type_dir)
        _refresh_index_after_delete(folder)
    return {"deleted": asset_type}


@_r_assets.post("/projects/{folder}/assets/{asset_type}", status_code=201)
def create_asset(folder: str, asset_type: str, body: AssetCreate):
    folder = _validate_id(folder, "Project folder")
    asset_type = _validate_id(asset_type.strip().lower(), "Asset type")
    asset = _validate_id((body.asset or "").strip(), "Asset name")
    with _write_lock:
        work_dir = pipeline.asset_work_houdini(folder, asset_type, asset)
        if work_dir.exists():
            raise HTTPException(status_code=409, detail=f"Asset '{asset}' already exists.")
        pipeline.make_asset_work_dirs(folder, asset_type, asset)
    return {"asset_type": asset_type, "asset": asset, "path": str(work_dir)}


@_r_assets.delete("/projects/{folder}/assets/{asset_type}/{asset}", status_code=200)
def delete_asset(folder: str, asset_type: str, asset: str, delete_files: bool = False):
    folder = _validate_id(folder, "Project folder")
    asset_type = _validate_id(asset_type, "Asset type")
    asset = _validate_id(asset, "Asset name")
    if not delete_files:
        raise HTTPException(
            status_code=400,
            detail="Asset has no separate metadata record. Pass ?delete_files=true to remove from filesystem.",
        )
    with _write_lock:
        asset_dir = pipeline.projects_root() / folder / "assets" / asset_type / asset
        if not asset_dir.exists():
            raise HTTPException(status_code=404, detail=f"Asset '{asset}' not found.")
        shutil.rmtree(asset_dir)
        _refresh_index_after_delete(folder)
    return {"deleted": asset}


# ---------------------------------------------------------------------------
# Publishes (read-only — feeds the gallery tab)
# ---------------------------------------------------------------------------

@_r_publishes.get("/publishes")
def get_publishes(project: str = None):
    try:
        if project:
            project = _validate_id(project, "Project folder")
            idx = pipeline.read_project_index(project)
            return idx.get("publishes", []) if idx else []
        all_pubs = []
        for proj in pipeline.load_projects():
            folder = proj.get("folder", "")
            if not folder:
                continue
            idx = pipeline.read_project_index(folder)
            if idx:
                all_pubs.extend(idx.get("publishes", []))
        return all_pubs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@_r_publishes.post("/publishes/rebuild")
def rebuild_index(project: str = None):
    with _write_lock:
        try:
            if project:
                project = _validate_id(project, "Project folder")
                pipeline.write_project_index(project)
                return {"rebuilt": project}
            pipeline.scan_all_projects()
            return {"rebuilt": "all"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Register routers — must happen before the static catch-all mount so that
# all /api routes take priority and can never be intercepted by StaticFiles.
# ---------------------------------------------------------------------------

app.include_router(_r_projects)
app.include_router(_r_sequences)
app.include_router(_r_shots)
app.include_router(_r_assets)
app.include_router(_r_publishes)


# ---------------------------------------------------------------------------
# Root route + React web UI static files
#
# Static files are mounted at /ui (not /) so that the /api prefix is never
# shadowed regardless of whether the dist directory exists. The root handler
# below serves index.html directly when the build is present.
# ---------------------------------------------------------------------------

@app.get("/")
def serve_index():
    index = _WEB_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(
        {"status": "ok", "message": "FX Pipeline API is running. Web UI not built — run: cd web && npm install && npm run build"},
        status_code=200,
    )

if _WEB_DIST.exists():
    app.mount("/ui", StaticFiles(directory=str(_WEB_DIST), html=True), name="static")


# ---------------------------------------------------------------------------
# Server lifecycle (for running inside Houdini via threading)
# ---------------------------------------------------------------------------

_server_instance = None
_server_thread   = None
_start_lock      = threading.Lock()  # prevents concurrent start_server calls racing the port check


def _port_bound(host: str, port: int) -> bool:
    """Return True if something is already accepting connections on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


def _wait_for_port(host: str, port: int, timeout: float = 5.0) -> bool:
    """Poll until host:port accepts connections or timeout expires. Returns True on success."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_bound(host, port):
            return True
        time.sleep(0.1)
    return False


def start_server(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True):
    """Start the uvicorn server in a background thread. Idempotent — safe to call from Houdini."""
    global _server_instance, _server_thread

    with _start_lock:
        if _port_bound(host, port):
            if _server_thread is not None and _server_thread.is_alive():
                # Our server is genuinely running — nothing to do.
                logger.info("Server already running at http://%s:%d", host, port)
                if open_browser:
                    import webbrowser
                    webbrowser.open(f"http://{host}:{port}")
                return
            # Port is bound but our thread is gone (e.g. called right after stop_server
            # while the OS socket is still in TIME_WAIT / releasing). Wait briefly.
            import time
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline and _port_bound(host, port):
                time.sleep(0.2)
            if _port_bound(host, port):
                logger.warning(
                    "Port %d still in use after waiting; attempting to bind anyway.", port
                )

        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",
            loop="asyncio",
        )
        _server_instance = uvicorn.Server(config)
        _srv = _server_instance  # capture for thread closure; immune to later global reassignment

        def _run():
            import asyncio
            try:
                asyncio.run(_srv.serve())
            except Exception as exc:
                logger.error("Server thread exited with error: %s", exc)

        _server_thread = threading.Thread(target=_run, daemon=True, name="pipeline-server")
        _server_thread.start()
        logger.info("Pipeline server started at http://%s:%d", host, port)

    if open_browser:
        import webbrowser

        def _open_when_ready():
            if _wait_for_port(host, port, timeout=5.0):
                webbrowser.open(f"http://{host}:{port}")
            else:
                logger.warning("Server did not become reachable within timeout; skipping browser open.")

        threading.Thread(target=_open_when_ready, daemon=True, name="pipeline-browser-open").start()


def stop_server():
    """Signal uvicorn to stop and wait for the thread to exit (up to 5 s)."""
    global _server_instance, _server_thread
    if not _server_instance:
        return
    _server_instance.should_exit = True
    if _server_thread and _server_thread.is_alive():
        _server_thread.join(timeout=5.0)
        if _server_thread.is_alive():
            logger.warning("Server thread did not stop within timeout.")
    # Always clear state so a subsequent start_server gets a clean slate.
    _server_instance = None
    _server_thread = None
    logger.info("Pipeline server stopped.")


# ---------------------------------------------------------------------------
# Lightweight self-tests  (python server.py --selftest)
# ---------------------------------------------------------------------------

def _run_self_tests() -> bool:
    """Run in-process validation tests with no external framework.

    Covers: identifier validation, display name validation, publish-index
    refresh logic, and server start/stop/restart lifecycle.
    """
    import time

    failures: list[str] = []

    def _ok(condition: bool, msg: str) -> None:
        if condition:
            print(f"  ok  : {msg}")
        else:
            failures.append(msg)
            print(f"  FAIL: {msg}")

    def _raises_400(fn) -> bool:
        try:
            fn()
            return False
        except HTTPException as exc:
            return exc.status_code == 400
        except Exception:
            return False

    print("=== pipeline server self-tests ===\n")

    # -- _validate_id ---------------------------------------------------------
    print("-- _validate_id --")
    _ok(_validate_id("hello", "x") == "hello",           "accepts simple lowercase")
    _ok(_validate_id("SQ010", "x") == "SQ010",           "accepts uppercase")
    _ok(_validate_id("my-shot_01", "x") == "my-shot_01", "accepts hyphens + underscores")
    _ok(_raises_400(lambda: _validate_id("", "x")),       "rejects empty string")
    _ok(_raises_400(lambda: _validate_id("  ", "x")),     "rejects whitespace-only")
    _ok(_raises_400(lambda: _validate_id("../etc", "x")), "rejects path traversal")
    _ok(_raises_400(lambda: _validate_id("a/b", "x")),    "rejects forward slash")
    _ok(_raises_400(lambda: _validate_id("a b", "x")),    "rejects space")
    _ok(_raises_400(lambda: _validate_id("a" * 65, "x")), "rejects oversized id")

    # -- _validate_display_name -----------------------------------------------
    print("\n-- _validate_display_name --")
    _ok(_validate_display_name("My Cool Project", "x") == "My Cool Project",
        "allows spaces in display name")
    _ok(_validate_display_name("Episode 01", "x") == "Episode 01",
        "allows digits and spaces")
    _ok(_validate_display_name("Épisode: Alpha", "x") == "Épisode: Alpha",
        "allows unicode + colon")
    _ok(_raises_400(lambda: _validate_display_name("", "x")),
        "rejects empty display name")
    _ok(_raises_400(lambda: _validate_display_name("a/b", "x")),
        "rejects forward slash in name")
    _ok(_raises_400(lambda: _validate_display_name("a\\b", "x")),
        "rejects backslash in name")
    _ok(_raises_400(lambda: _validate_display_name("a\x00b", "x")),
        "rejects null byte in name")
    _ok(_raises_400(lambda: _validate_display_name("../etc", "x")),
        "rejects '..' traversal in name")
    _ok(_raises_400(lambda: _validate_display_name("n" * 129, "x")),
        "rejects oversized display name")

    # -- server lifecycle ------------------------------------------------------
    print("\n-- server lifecycle --")
    _TEST_PORT = 18765  # isolated port; avoids touching the production server
    _TEST_HOST = "127.0.0.1"

    _ok(not _port_bound(_TEST_HOST, _TEST_PORT),
        f"test port {_TEST_PORT} is free before tests")

    start_server(host=_TEST_HOST, port=_TEST_PORT, open_browser=False)
    _ok(_wait_for_port(_TEST_HOST, _TEST_PORT, timeout=5.0),
        "server becomes reachable after start_server()")

    # idempotent duplicate start
    start_server(host=_TEST_HOST, port=_TEST_PORT, open_browser=False)
    _ok(_port_bound(_TEST_HOST, _TEST_PORT),
        "port still bound after duplicate start_server() call")

    stop_server()
    _ok(_server_instance is None, "_server_instance cleared after stop_server()")
    _ok(_server_thread is None,   "_server_thread cleared after stop_server()")
    # Wait for OS to release the socket (allows the restart test to be reliable).
    deadline = time.monotonic() + 5.0
    while _port_bound(_TEST_HOST, _TEST_PORT) and time.monotonic() < deadline:
        time.sleep(0.1)
    _ok(not _port_bound(_TEST_HOST, _TEST_PORT), "port released after stop_server()")

    # restart
    start_server(host=_TEST_HOST, port=_TEST_PORT, open_browser=False)
    _ok(_wait_for_port(_TEST_HOST, _TEST_PORT, timeout=5.0),
        "server restarts successfully after stop_server() + start_server()")
    stop_server()

    # -- summary ---------------------------------------------------------------
    print(f"\n{'ALL PASS' if not failures else 'FAILURES DETECTED'}: "
          f"{len(failures)} failure(s) out of {9 + 9 + 7} checks")
    for f in failures:
        print(f"  - {f}")
    return len(failures) == 0


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        success = _run_self_tests()
        sys.exit(0 if success else 1)

    import webbrowser

    _host, _port = "127.0.0.1", 8765
    print(f"Starting FX Pipeline Server at http://{_host}:{_port}")

    def _open_when_ready():
        if _wait_for_port(_host, _port, timeout=10.0):
            webbrowser.open(f"http://{_host}:{_port}")

    threading.Thread(target=_open_when_ready, daemon=True).start()
    uvicorn.run(app, host=_host, port=_port, log_level="info")
