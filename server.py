"""
Houdini FX Pipeline — Local Management Server
Run via shelf tool. Serves the web UI and exposes a REST API for
managing projects, sequences, shots, assets, and browsing publishes.

Start:  python server.py
Stop:   Ctrl+C  or close via shelf tool
"""

import json
import logging
import os
import shutil
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Bootstrap pipeline path
# ---------------------------------------------------------------------------

import sys

_SERVER_DIR = Path(__file__).resolve().parent
_PIPELINE_PYTHON = _SERVER_DIR / "python"
if str(_PIPELINE_PYTHON) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_PYTHON))

import pipeline
import pipeline.config as _cfg

logger = logging.getLogger("pipeline.server")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="FX Pipeline Manager", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the web UI static files
_WEB_DIST = _SERVER_DIR / "pipeline_web" / "dist"
_WEB_SRC  = _SERVER_DIR / "pipeline_web"

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
# Helper
# ---------------------------------------------------------------------------

def _slug(name: str) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()

# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@app.get("/api/projects")
def list_projects():
    return pipeline.load_projects()


@app.post("/api/projects", status_code=201)
def create_project(body: ProjectCreate):
    folder = body.folder or _slug(body.name)
    try:
        project = pipeline.add_project(
            name=body.name,
            folder=folder,
            fps=body.fps,
            resolution=body.resolution,
        )
        # Create the project directory on disk
        proj_dir = pipeline.projects_root() / folder
        proj_dir.mkdir(parents=True, exist_ok=True)
        return project
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.delete("/api/projects/{folder}", status_code=200)
def delete_project(folder: str, delete_files: bool = False):
    projects = pipeline.load_projects()
    match = next((p for p in projects if p["folder"] == folder), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Project '{folder}' not found.")
    projects = [p for p in projects if p["folder"] != folder]
    pipeline.save_projects(projects)
    if delete_files:
        proj_dir = pipeline.projects_root() / folder
        if proj_dir.exists():
            shutil.rmtree(proj_dir)
    return {"deleted": folder}


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------

@app.get("/api/projects/{folder}/sequences")
def list_sequences(folder: str):
    project = pipeline.get_project(folder)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{folder}' not found.")
    return project.get("sequences", [])


@app.post("/api/projects/{folder}/sequences", status_code=201)
def create_sequence(folder: str, body: SequenceCreate):
    seq = body.seq.strip().upper()
    if not seq:
        raise HTTPException(status_code=400, detail="Sequence code is required.")
    try:
        pipeline.add_sequence(folder, seq)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    # Create the sequence directory
    seq_dir = pipeline.projects_root() / folder / seq
    seq_dir.mkdir(parents=True, exist_ok=True)
    return {"seq": seq}


@app.delete("/api/projects/{folder}/sequences/{seq}", status_code=200)
def delete_sequence(folder: str, seq: str, delete_files: bool = False):
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
    return {"deleted": seq}


# ---------------------------------------------------------------------------
# Shots
# ---------------------------------------------------------------------------

@app.get("/api/projects/{folder}/sequences/{seq}/shots")
def list_shots(folder: str, seq: str):
    seq_dir = pipeline.projects_root() / folder / seq
    if not seq_dir.exists():
        return []
    return sorted(d.name for d in seq_dir.iterdir() if d.is_dir())


@app.post("/api/projects/{folder}/sequences/{seq}/shots", status_code=201)
def create_shot(folder: str, seq: str, body: ShotCreate):
    shot = body.shot.strip()
    if not shot:
        raise HTTPException(status_code=400, detail="Shot code is required.")
    work_dir = pipeline.shot_work_houdini(folder, seq, shot)
    if work_dir.exists():
        raise HTTPException(status_code=409, detail=f"Shot '{shot}' already exists.")
    pipeline.make_shot_work_dirs(folder, seq, shot)
    return {"shot": shot, "path": str(work_dir)}


@app.delete("/api/projects/{folder}/sequences/{seq}/shots/{shot}", status_code=200)
def delete_shot(folder: str, seq: str, shot: str, delete_files: bool = False):
    shot_dir = pipeline.projects_root() / folder / seq / shot
    if not shot_dir.exists():
        raise HTTPException(status_code=404, detail=f"Shot '{shot}' not found.")
    if delete_files:
        shutil.rmtree(shot_dir)
    return {"deleted": shot}


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

@app.get("/api/projects/{folder}/assets")
def list_assets(folder: str):
    project = pipeline.get_project(folder)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{folder}' not found.")
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


@app.post("/api/projects/{folder}/assets/{asset_type}", status_code=201)
def create_asset(folder: str, asset_type: str, body: AssetCreate):
    asset = body.asset.strip()
    if not asset:
        raise HTTPException(status_code=400, detail="Asset name is required.")
    asset_type = asset_type.strip().lower()
    work_dir = pipeline.asset_work_houdini(folder, asset_type, asset)
    if work_dir.exists():
        raise HTTPException(status_code=409, detail=f"Asset '{asset}' already exists.")
    pipeline.make_asset_work_dirs(folder, asset_type, asset)
    return {"asset_type": asset_type, "asset": asset, "path": str(work_dir)}


@app.delete("/api/projects/{folder}/assets/{asset_type}/{asset}", status_code=200)
def delete_asset(folder: str, asset_type: str, asset: str, delete_files: bool = False):
    asset_dir = pipeline.projects_root() / folder / "assets" / asset_type / asset
    if not asset_dir.exists():
        raise HTTPException(status_code=404, detail=f"Asset '{asset}' not found.")
    if delete_files:
        shutil.rmtree(asset_dir)
    return {"deleted": asset}


@app.post("/api/projects/{folder}/asset-types", status_code=201)
def create_asset_type(folder: str, body: AssetTypeCreate):
    asset_type = body.asset_type.strip().lower()
    if not asset_type:
        raise HTTPException(status_code=400, detail="Asset type is required.")
    type_dir = pipeline.projects_root() / folder / "assets" / asset_type
    type_dir.mkdir(parents=True, exist_ok=True)
    return {"asset_type": asset_type}


@app.delete("/api/projects/{folder}/asset-types/{asset_type}", status_code=200)
def delete_asset_type(folder: str, asset_type: str, delete_files: bool = False):
    type_dir = pipeline.projects_root() / folder / "assets" / asset_type
    if not type_dir.exists():
        raise HTTPException(status_code=404, detail=f"Asset type '{asset_type}' not found.")
    if delete_files:
        shutil.rmtree(type_dir)
    return {"deleted": asset_type}


# ---------------------------------------------------------------------------
# Publishes (read-only — feeds the gallery tab)
# ---------------------------------------------------------------------------

@app.get("/api/publishes")
def get_publishes(project: str = None):
    try:
        if project:
            idx = pipeline.read_project_index(project)
            return idx.get("publishes", []) if idx else []
        # All projects
        all_pubs = []
        for proj in pipeline.load_projects():
            folder = proj.get("folder", "")
            if not folder:
                continue
            idx = pipeline.read_project_index(folder)
            if idx:
                all_pubs.extend(idx.get("publishes", []))
        return all_pubs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/publishes/rebuild")
def rebuild_index(project: str = None):
    try:
        if project:
            pipeline.write_project_index(project)
            return {"rebuilt": project}
        pipeline.scan_all_projects()
        return {"rebuilt": "all"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Hip files (read-only listing for file manager tab)
# ---------------------------------------------------------------------------

@app.get("/api/projects/{folder}/sequences/{seq}/shots/{shot}/hips")
def list_hip_files(folder: str, seq: str, shot: str):
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
# Serve the React web UI
# ---------------------------------------------------------------------------

@app.get("/")
def serve_index():
    index = _WEB_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(
        {"message": "Web UI not built yet. Run: cd web && npm install && npm run build"},
        status_code=200,
    )

# Mount static files after route definitions
if _WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_WEB_DIST), html=True), name="static")


# ---------------------------------------------------------------------------
# Server lifecycle (for running inside Houdini via threading)
# ---------------------------------------------------------------------------

_server_instance = None
_server_thread   = None


def _port_bound(host: str, port: int) -> bool:
    """Return True if something is already listening on host:port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


def start_server(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True):
    """Start the uvicorn server in a background thread. Safe to call from Houdini."""
    global _server_instance, _server_thread

    # Socket probe is the authoritative check — works even after a module reload
    # that would have reset _server_thread to None.
    if _port_bound(host, port):
        logger.info("Server already running at http://%s:%d", host, port)
        if open_browser:
            import webbrowser
            webbrowser.open(f"http://{host}:{port}")
        return

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        loop="asyncio",
    )
    _server_instance = uvicorn.Server(config)

    def _run():
        import asyncio
        asyncio.run(_server_instance.serve())

    _server_thread = threading.Thread(target=_run, daemon=True, name="pipeline-server")
    _server_thread.start()
    logger.info("Pipeline server started at http://%s:%d", host, port)

    if open_browser:
        import time, webbrowser
        time.sleep(0.8)  # Give uvicorn a moment to bind
        webbrowser.open(f"http://{host}:{port}")


def stop_server():
    global _server_instance
    if _server_instance:
        _server_instance.should_exit = True
        logger.info("Pipeline server stopped.")


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import webbrowser, time
    print("Starting FX Pipeline Server at http://127.0.0.1:8765")
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:8765")).start()
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
