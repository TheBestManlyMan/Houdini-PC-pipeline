"""
Project registry — load, save, and mutate projects.json.
"""

import json
import logging
from pathlib import Path

from . import config as _config
from .config import load_config, projects_root

logger = logging.getLogger("pipeline")


def load_projects() -> list[dict]:
    if not _config._PROJECTS_PATH.exists():
        return []
    with open(_config._PROJECTS_PATH, "r") as f:
        return json.load(f).get("projects", [])


def get_project(name: str) -> dict | None:
    for p in load_projects():
        if p["name"] == name or p["folder"] == name:
            return p
    return None


def save_projects(projects: list[dict]) -> None:
    with open(_config._PROJECTS_PATH, "w") as f:
        json.dump({"projects": projects}, f, indent=2)


def add_sequence(project_folder: str, seq: str) -> None:
    projects = load_projects()
    for p in projects:
        if p["folder"] == project_folder:
            if seq in p.get("sequences", []):
                raise ValueError(f"Sequence '{seq}' already exists in project.")
            p.setdefault("sequences", []).append(seq)
            p["sequences"].sort()
            save_projects(projects)
            logger.info("Sequence added: %s/%s", project_folder, seq)
            return
    raise ValueError(f"Project folder '{project_folder}' not found in registry.")


def add_project(name: str, folder: str, fps: int = None, resolution: str = None,
                sequences: list[str] = None, assets: dict = None) -> dict:
    cfg = load_config()
    project = {
        "name": name,
        "folder": folder,
        "fps": fps or cfg.get("default_fps", 24),
        "resolution": resolution or cfg.get("default_resolution", "1920x1080"),
        "sequences": sequences or [],
        "assets": assets or {},
    }
    existing = load_projects()
    if any(p["folder"] == folder for p in existing):
        raise ValueError(f"Project folder '{folder}' already exists in registry.")
    existing.append(project)
    save_projects(existing)
    logger.info("Project created: %s  →  %s", name, projects_root() / folder)
    return project
