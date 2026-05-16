"""
Pipeline API server — serves publish data and media files to the web gallery.

Endpoints:
    GET /api/projects           — list of registered projects
    GET /api/publishes          — all publishes across all projects (live scan)
    GET /api/publishes/{folder} — publishes for a single project folder
    GET /api/index/{folder}     — full index dict for one project
    POST /api/reindex           — rebuild all project indexes
    POST /api/reindex/{folder}  — rebuild index for one project
    GET /api/assets             — list all 3D GLB assets
    GET /api/assets/{project}/{name} — get single 3D asset metadata
    GET /media/{path}           — serve media files (thumbnails, mp4s, GLBs) from shows dir
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import logging
import logging.config
import logging.handlers
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import pipeline
from pipeline.indexer import (
    build_project_index,
    read_project_index,
    write_project_index,
    scan_all_projects,
)

# ---------------------------------------------------------------------------
# Logging — console + rotating file so crashes are visible after the fact
# ---------------------------------------------------------------------------
_LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "api_server.log"
_LOG_FILE.parent.mkdir(exist_ok=True)

_fmt = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"

# Explicit per-logger config passed to uvicorn so its access/error logs also
# land in the file.  backupCount=3 keeps at most ~6 MB of history.
_UVICORN_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": _fmt},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": str(_LOG_FILE),
            "maxBytes": 2 * 1024 * 1024,
            "backupCount": 3,
            "encoding": "utf-8",
        },
    },
    "root": {"level": "INFO", "handlers": ["console", "file"]},
    "loggers": {
        "uvicorn":        {"level": "INFO", "handlers": ["console", "file"], "propagate": False},
        "uvicorn.error":  {"level": "INFO", "handlers": ["console", "file"], "propagate": False},
        "uvicorn.access": {"level": "INFO", "handlers": ["console", "file"], "propagate": False},
        "api_server":     {"level": "INFO", "handlers": ["console", "file"], "propagate": False},
        "pipeline":       {"level": "INFO", "handlers": ["console", "file"], "propagate": False},
    },
}

logging.config.dictConfig(_UVICORN_LOG_CONFIG)
log = logging.getLogger("api_server")
log.info("API server starting — log: %s", _LOG_FILE)

app = FastAPI(title="Houdini Pipeline API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the shows directory so the browser can load thumbnails and mp4s.
# Absolute paths like /home/maxborg/projects/shows/reel/.../thumb.jpg
# are rewritten to /media/reel/.../thumb.jpg before being sent to the client.
_shows_root = pipeline.projects_root()
app.mount("/media", StaticFiles(directory=str(_shows_root)), name="media")


# ---------------------------------------------------------------------------
# Path rewriting — absolute filesystem paths → HTTP /media/... URLs
# ---------------------------------------------------------------------------

def _mediafy(obj, root: str, media_base: str):
    """Recursively replace absolute shows-dir paths with /media/... URLs."""
    if isinstance(obj, dict):
        return {k: _mediafy(v, root, media_base) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mediafy(i, root, media_base) for i in obj]
    if isinstance(obj, str) and obj.startswith(root):
        rel = obj[len(root):].lstrip("/")
        return media_base + rel
    return obj


def _rewrite(records, request: Request):
    root = str(_shows_root)
    # Use request.base_url so remote devices get the right host:port
    media_base = str(request.base_url).rstrip("/") + "/media/"
    return [_mediafy(r, root, media_base) for r in records]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/projects")
def get_projects():
    return pipeline.load_projects()


@app.get("/api/publishes")
def get_all_publishes(request: Request, project: Optional[str] = None):
    """Return flat list of all publish records across all projects (live scan)."""
    projects = pipeline.load_projects()
    if project:
        projects = [p for p in projects if p.get("folder") == project or p.get("name") == project]

    all_publishes = []
    for proj in projects:
        folder = proj.get("folder", "")
        if not folder:
            continue
        try:
            idx = build_project_index(folder)
            all_publishes.extend(idx.get("publishes", []))
        except Exception as e:
            log.warning("Skipping project %s: %s", folder, e)

    return _rewrite(all_publishes, request)


@app.get("/api/publishes/{folder}")
def get_project_publishes(folder: str, request: Request):
    """Return publish records for a single project (live scan)."""
    try:
        idx = build_project_index(folder)
        return _rewrite(idx.get("publishes", []), request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/index/{folder}")
def get_project_index(folder: str, request: Request, cached: bool = False):
    """Return the full index dict for a project. cached=true reads the JSON file."""
    if cached:
        idx = read_project_index(folder)
        if idx is None:
            raise HTTPException(
                status_code=404,
                detail=f"No cached index for '{folder}'. POST /api/reindex/{folder} first.",
            )
        idx["publishes"] = _rewrite(idx.get("publishes", []), request)
        return idx
    try:
        idx = build_project_index(folder)
        idx["publishes"] = _rewrite(idx.get("publishes", []), request)
        return idx
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/reindex")
def reindex_all():
    results = scan_all_projects()
    return {folder: idx.get("publish_count", 0) for folder, idx in results.items()}


@app.post("/api/reindex/{folder}")
def reindex_project(folder: str):
    try:
        path = write_project_index(folder)
        idx = read_project_index(folder)
        return {
            "folder": folder,
            "publish_count": idx.get("publish_count", 0),
            "index_path": str(path),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 3D Asset endpoints
# ---------------------------------------------------------------------------

def _discover_assets(request: Request) -> list[dict]:
    """
    Recursively scan {shows_root}/assets/{project}/{name}/
    and return a list of asset dicts enriched with HTTP URLs.
    """
    assets_root = _shows_root / "assets"
    if not assets_root.exists():
        return []

    base_url = str(request.base_url).rstrip("/")
    results = []

    for meta_path in sorted(assets_root.rglob("metadata.json")):
        asset_dir = meta_path.parent
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Bad metadata.json at %s: %s", meta_path, e)
            continue

        # Derive project and asset_name from directory structure
        # Expected: assets/{project}/{asset_name}/
        try:
            rel = asset_dir.relative_to(assets_root)
            parts = rel.parts
            project = parts[0] if len(parts) >= 1 else "unknown"
            asset_name = parts[1] if len(parts) >= 2 else asset_dir.name
        except ValueError:
            project = "unknown"
            asset_name = asset_dir.name

        # Build media URLs using the already-mounted /media/ static route
        rel_to_shows = asset_dir.relative_to(_shows_root)
        media_prefix = f"{base_url}/media/{rel_to_shows.as_posix()}"

        glb_path = asset_dir / "asset.glb"
        thumb_path = asset_dir / "thumbnail.jpg"

        record = {
            **meta,
            "project": meta.get("project") or project,
            "asset_name": meta.get("asset_name") or asset_name,
            "glb_url": f"{media_prefix}/asset.glb" if glb_path.exists() else None,
            "thumbnail_url": f"{media_prefix}/thumbnail.jpg" if thumb_path.exists() else None,
        }
        results.append(record)

    return results


@app.get("/api/assets")
def list_assets(request: Request):
    """Return all discovered 3D GLB assets."""
    return _discover_assets(request)


@app.get("/api/assets/{project}/{name}")
def get_asset(project: str, name: str, request: Request):
    """Return metadata for a single 3D asset."""
    meta_path = _shows_root / "assets" / project / name / "metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail=f"Asset '{project}/{name}' not found")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    asset_dir = meta_path.parent
    rel_to_shows = asset_dir.relative_to(_shows_root)
    base_url = str(request.base_url).rstrip("/")
    media_prefix = f"{base_url}/media/{rel_to_shows.as_posix()}"

    return {
        **meta,
        "project": project,
        "asset_name": name,
        "glb_url": f"{media_prefix}/asset.glb" if (asset_dir / "asset.glb").exists() else None,
        "thumbnail_url": f"{media_prefix}/thumbnail.jpg" if (asset_dir / "thumbnail.jpg").exists() else None,
    }


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_config=_UVICORN_LOG_CONFIG)
