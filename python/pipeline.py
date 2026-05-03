"""
Houdini FX Pipeline — core utility module.
All path logic, versioning, and project registry access lives here.
UI scripts call these functions; they never build paths themselves.
"""

import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger("pipeline")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PIPELINE_ROOT / "pipeline_config.json"
_PROJECTS_PATH = _PIPELINE_ROOT / "projects.json"


def load_config() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        return json.load(f)


def projects_root() -> Path:
    return Path(load_config()["projects_root"])


# ---------------------------------------------------------------------------
# Project registry
# ---------------------------------------------------------------------------

def load_projects() -> list[dict]:
    if not _PROJECTS_PATH.exists():
        return []
    with open(_PROJECTS_PATH, "r") as f:
        return json.load(f).get("projects", [])


def get_project(name: str) -> dict | None:
    for p in load_projects():
        if p["name"] == name or p["folder"] == name:
            return p
    return None


def save_projects(projects: list[dict]) -> None:
    with open(_PROJECTS_PATH, "w") as f:
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
    projects = load_projects()
    if any(p["folder"] == folder for p in projects):
        raise ValueError(f"Project folder '{folder}' already exists in registry.")
    projects.append(project)
    save_projects(projects)
    logger.info("Project created: %s  →  %s", name, projects_root() / folder)
    return project


# ---------------------------------------------------------------------------
# Path builders — shot context
# ---------------------------------------------------------------------------

def shot_fx_root(project_folder: str, seq: str, shot: str) -> Path:
    return projects_root() / project_folder / seq / shot / "FX"


def shot_work_houdini(project_folder: str, seq: str, shot: str) -> Path:
    return projects_root() / project_folder / seq / shot / "houdini"


def shot_cache_root(project_folder: str, seq: str, shot: str, task: str) -> Path:
    return shot_work_houdini(project_folder, seq, shot) / "cache" / task


def shot_publish_root(project_folder: str, seq: str, shot: str, fmt: str, task: str) -> Path:
    return shot_fx_root(project_folder, seq, shot) / "publish" / fmt / task


# ---------------------------------------------------------------------------
# Path builders — asset context
# ---------------------------------------------------------------------------

def asset_fx_root(project_folder: str, asset_type: str, asset: str) -> Path:
    return projects_root() / project_folder / "assets" / asset_type / asset / "FX"


def asset_work_houdini(project_folder: str, asset_type: str, asset: str) -> Path:
    return asset_fx_root(project_folder, asset_type, asset) / "work" / "houdini"


def asset_cache_root(project_folder: str, asset_type: str, asset: str, task: str) -> Path:
    return asset_work_houdini(project_folder, asset_type, asset) / "cache" / task


def asset_publish_root(project_folder: str, asset_type: str, asset: str, fmt: str, task: str) -> Path:
    return asset_fx_root(project_folder, asset_type, asset) / "publish" / fmt / task


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"v(\d{3})")


def get_versions(folder: Path) -> list[int]:
    """Return sorted list of version numbers found as subfolders in folder."""
    if not folder.exists():
        return []
    versions = []
    for entry in folder.iterdir():
        if entry.is_dir():
            m = _VERSION_RE.fullmatch(entry.name)
            if m:
                versions.append(int(m.group(1)))
    return sorted(versions)


def get_latest_version(folder: Path) -> int | None:
    versions = get_versions(folder)
    return versions[-1] if versions else None


def get_next_version(folder: Path) -> int:
    latest = get_latest_version(folder)
    return 1 if latest is None else latest + 1


def version_str(n: int) -> str:
    return f"v{n:03d}"


# ---------------------------------------------------------------------------
# Hip file naming
# ---------------------------------------------------------------------------

def hip_filename(entity: str, task: str, version: int) -> str:
    return f"{entity}_fx_{task}_{version_str(version)}.hip"


def parse_hip_filename(filename: str) -> dict | None:
    """Parse entity, task, version from a hip filename. Returns None if no match."""
    stem = Path(filename).stem
    m = re.fullmatch(r"(.+)_fx_(.+)_(v\d{3})", stem)
    if not m:
        return None
    return {
        "entity": m.group(1),
        "task": m.group(2),
        "version": int(m.group(3)[1:]),
        "version_str": m.group(3),
    }


# ---------------------------------------------------------------------------
# Cache file naming
# ---------------------------------------------------------------------------

def cache_filename(entity: str, task: str, version: int, ext: str) -> str:
    """ext examples: 'bgeo.sc', 'vdb', 'abc'"""
    base = f"{entity}_fx_{task}_{version_str(version)}"
    if ext == "abc":
        return f"{base}.abc"
    return f"{base}.$F4.{ext}"


def flipbook_filename(entity: str, version: int) -> str:
    return f"{entity}_fx_flipbook_{version_str(version)}.$F4.jpg"


def mp4_filename(entity: str, task: str, version: int) -> str:
    return f"{entity}_fx_{task}_{version_str(version)}.mp4"


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------

def make_shot_work_dirs(project_folder: str, seq: str, shot: str) -> None:
    path = shot_work_houdini(project_folder, seq, shot)
    path.mkdir(parents=True, exist_ok=True)
    logger.info("Shot dirs created: %s", path)


def make_asset_work_dirs(project_folder: str, asset_type: str, asset: str) -> None:
    path = asset_work_houdini(project_folder, asset_type, asset)
    path.mkdir(parents=True, exist_ok=True)
    logger.info("Asset dirs created: %s", path)


def make_cache_version_dirs(cache_root: Path, version: int) -> dict[str, Path]:
    """Create geo and vdb subdirs for a versioned cache folder. Returns paths."""
    geo = cache_root / "geo" / version_str(version)
    vdb = cache_root / "vdb" / version_str(version)
    geo.mkdir(parents=True, exist_ok=True)
    vdb.mkdir(parents=True, exist_ok=True)
    return {"geo": geo, "vdb": vdb}


def make_publish_version_dir(publish_root: Path, version: int) -> Path:
    d = publish_root / version_str(version)
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Hip file helpers
# ---------------------------------------------------------------------------

def find_hip_files(work_houdini: Path) -> list[Path]:
    if not work_houdini.exists():
        return []
    return sorted(work_houdini.glob("*_fx_*_v???.hip"))


def latest_hip(work_houdini: Path) -> Path | None:
    hips = find_hip_files(work_houdini)
    return hips[-1] if hips else None


def next_hip_path(work_houdini: Path, entity: str, task: str) -> Path:
    existing = [
        parse_hip_filename(h.name)
        for h in find_hip_files(work_houdini)
        if parse_hip_filename(h.name) and parse_hip_filename(h.name)["task"] == task
    ]
    versions = [e["version"] for e in existing if e]
    next_ver = (max(versions) + 1) if versions else 1
    return work_houdini / hip_filename(entity, task, next_ver)


# ---------------------------------------------------------------------------
# Hip version preparation
# ---------------------------------------------------------------------------

def prepare_hip_version_dir(project_folder: str, seq: str, shot: str,
                             entity: str, task: str) -> Path:
    """Return the next versioned .hip path and ensure its parent directory exists."""
    work = shot_work_houdini(project_folder, seq, shot)
    path = next_hip_path(work, entity, task)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Hip version ready: %s", path)
    return path


# ---------------------------------------------------------------------------
# ROP / task helpers
# ---------------------------------------------------------------------------

def task_from_rop(rop_name: str) -> str:
    """Strip OUT_ prefix, lowercase."""
    name = rop_name.strip()
    if name.upper().startswith("OUT_"):
        name = name[4:]
    return name.lower()


# ---------------------------------------------------------------------------
# ffmpeg preview
# ---------------------------------------------------------------------------

def build_ffmpeg_cmd(image_seq_path: str, output_mp4: str, fps: int = None) -> list[str]:
    cfg = load_config()
    ffmpeg = cfg.get("ffmpeg", "ffmpeg")
    frame_rate = fps or cfg.get("default_fps", 24)
    return [
        ffmpeg,
        "-framerate", str(frame_rate),
        "-i", image_seq_path,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        output_mp4,
    ]
