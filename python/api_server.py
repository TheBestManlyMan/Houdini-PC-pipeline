"""
Pipeline API server — serves publish data to the web gallery.

Run from the repo root:
    python3 python/api_server.py

Endpoints:
    GET /api/projects           — list of registered projects
    GET /api/publishes          — all publishes across all projects (live scan)
    GET /api/publishes/{folder} — publishes for a single project folder
    GET /api/index/{folder}     — full index dict for one project
    POST /api/reindex           — rebuild all project indexes
    POST /api/reindex/{folder}  — rebuild index for one project
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import logging
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import pipeline
from pipeline.indexer import (
    build_project_index,
    read_project_index,
    write_project_index,
    scan_all_projects,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("api_server")

app = FastAPI(title="Houdini Pipeline API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/projects")
def get_projects():
    return pipeline.load_projects()


@app.get("/api/publishes")
def get_all_publishes(project: Optional[str] = None):
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

    return all_publishes


@app.get("/api/publishes/{folder}")
def get_project_publishes(folder: str):
    """Return publish records for a single project (live scan)."""
    try:
        idx = build_project_index(folder)
        return idx.get("publishes", [])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/index/{folder}")
def get_project_index(folder: str, cached: bool = False):
    """Return the full index dict for a project. cached=true reads the JSON file."""
    if cached:
        idx = read_project_index(folder)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"No cached index for '{folder}'. POST /api/reindex/{folder} first.")
        return idx
    try:
        return build_project_index(folder)
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
        return {"folder": folder, "publish_count": idx.get("publish_count", 0), "index_path": str(path)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
