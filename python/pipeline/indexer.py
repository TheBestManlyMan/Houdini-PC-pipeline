"""
Project indexer — scans the filesystem for publishes and builds cached indexes.

Index files live at:
    {projects_root}/{project}/.pipeline/publishes.json

The index is always rebuilt from disk. Version numbers are never stored as state.
"""

import json
import logging
import time
from pathlib import Path
from typing import Iterator

from .config import load_config, projects_root
from .entities import load_projects
from .metadata import read_metadata, METADATA_FILENAME, _LEGACY_FILENAME
from .versioning import get_versions

logger = logging.getLogger("pipeline")

_INDEX_SUBDIR = ".pipeline"
_INDEX_FILENAME = "publishes.json"


# ---------------------------------------------------------------------------
# Entity root discovery
# ---------------------------------------------------------------------------

def _iter_entity_roots(project_dir: Path, project_meta: dict) -> Iterator[dict]:
    """
    Yield dicts describing every entity FX root in the project directory.

    Shot:  {project}/{SEQ}/{SHOT}/FX/
    Asset: {project}/assets/{asset_type}/{asset}/FX/
    """
    proj_name = project_meta.get("name", project_dir.name)

    # Shots
    for seq_dir in project_dir.iterdir():
        if not seq_dir.is_dir() or seq_dir.name in ("assets", _INDEX_SUBDIR):
            continue
        for shot_dir in seq_dir.iterdir():
            if not shot_dir.is_dir():
                continue
            fx = shot_dir / "FX"
            if fx.is_dir():
                yield {
                    "project": proj_name,
                    "entity_type": "shot",
                    "sequence": seq_dir.name,
                    "shot": shot_dir.name,
                    "entity_root": fx,
                }

    # Assets
    assets_dir = project_dir / "assets"
    if assets_dir.is_dir():
        for type_dir in assets_dir.iterdir():
            if not type_dir.is_dir():
                continue
            for asset_dir in type_dir.iterdir():
                if not asset_dir.is_dir():
                    continue
                fx = asset_dir / "FX"
                if fx.is_dir():
                    yield {
                        "project": proj_name,
                        "entity_type": "asset",
                        "asset_type": type_dir.name,
                        "asset": asset_dir.name,
                        "entity_root": fx,
                    }


# ---------------------------------------------------------------------------
# Publish discovery
# ---------------------------------------------------------------------------

def _iter_publish_dirs(entity_root: Path) -> Iterator[Path]:
    """Yield every versioned publish directory under an entity root."""
    for top in (entity_root / "publish", entity_root / "preview"):
        if not top.is_dir():
            continue
        for fmt_dir in top.iterdir():
            if not fmt_dir.is_dir():
                continue
            for task_dir in fmt_dir.iterdir():
                if not task_dir.is_dir():
                    continue
                for pub_name_dir in task_dir.iterdir():
                    if not pub_name_dir.is_dir():
                        continue
                    for ver_dir in pub_name_dir.iterdir():
                        if ver_dir.is_dir() and ver_dir.name.startswith("v"):
                            yield ver_dir


def _read_publish_record(ver_dir: Path, entity_entry: dict) -> dict | None:
    """
    Read (or synthesise) a publish record for a versioned directory.
    Returns None if the directory is empty or unreadable.
    """
    try:
        meta = read_metadata(ver_dir)
        if meta is not None:
            meta["_index_path"] = str(ver_dir)
            return meta
        # Synthesise minimal record from folder structure
        parts = ver_dir.parts
        # …/publish/{fmt}/{task}/{pub_name}/{ver}
        record = _synthesise_record(ver_dir, entity_entry)
        return record
    except Exception as e:
        logger.warning("Could not read publish at %s: %s", ver_dir, e)
        return None


def _synthesise_record(ver_dir: Path, entity_entry: dict) -> dict:
    """Build a minimal index entry from folder path when no metadata.json exists."""
    parts = ver_dir.parts
    # Typical layout: .../publish/{fmt}/{task}/{pub_name}/{ver}
    ver_name = ver_dir.name
    pub_name = ver_dir.parent.name
    task = ver_dir.parent.parent.name
    fmt = ver_dir.parent.parent.parent.name

    entity_root = entity_entry["entity_root"]
    proj = entity_entry["project"]

    return {
        "schema_version": 0,
        "uuid": None,
        "project": proj,
        "entity": "",
        "task": task,
        "publish_type": fmt,
        "version": int(ver_name[1:]) if ver_name[1:].isdigit() else 0,
        "created_at": "",
        "created_by": "",
        "source": {},
        "outputs": {},
        "stats": {"disk_mb": 0.0},
        "dependencies": [],
        "tags": [],
        "notes": [],
        "_index_path": str(ver_dir),
        "_synthesised": True,
    }


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _check_missing_outputs(record: dict) -> list[str]:
    """Return list of warning strings for missing expected output files."""
    warnings = []
    path = Path(record.get("_index_path", ""))
    if not path.is_dir():
        return warnings

    outputs = record.get("outputs", {})

    # Check thumbnail
    thumb = outputs.get("thumbnail", "")
    if not thumb or not Path(thumb).exists():
        jpgs = list(path.glob("*.jpg"))
        if not jpgs:
            warnings.append("missing_thumbnail")

    # Check mp4
    mp4 = outputs.get("mp4", "")
    if not mp4 or not Path(mp4).exists():
        mp4s = list(path.glob("*.mp4"))
        if not mp4s:
            warnings.append("missing_preview_mp4")

    # Check metadata
    if not (path / METADATA_FILENAME).exists() and not (path / _LEGACY_FILENAME).exists():
        warnings.append("missing_metadata")

    return warnings


def _check_orphaned(record: dict) -> bool:
    """An orphaned publish has no output files of any kind."""
    path = Path(record.get("_index_path", ""))
    if not path.is_dir():
        return True
    files = [f for f in path.iterdir() if f.is_file()]
    return len(files) == 0


# ---------------------------------------------------------------------------
# Index builder
# ---------------------------------------------------------------------------

def build_project_index(project_folder: str) -> dict:
    """
    Scan a single project directory and return its full index as a dict.

    The index is a flat list of publish records, each annotated with:
    - _index_path: the versioned publish folder
    - _warnings: list of validation issues
    - _orphaned: True if the folder contains no files
    """
    root = projects_root()
    project_dir = root / project_folder
    if not project_dir.is_dir():
        raise ValueError(f"Project directory not found: {project_dir}")

    # Find project metadata
    all_projects = load_projects()
    project_meta = next(
        (p for p in all_projects if p.get("folder") == project_folder),
        {"name": project_folder, "folder": project_folder},
    )

    publishes = []
    seen_paths: set[str] = set()

    for entity_entry in _iter_entity_roots(project_dir, project_meta):
        entity_root = entity_entry["entity_root"]
        for ver_dir in _iter_publish_dirs(entity_root):
            key = str(ver_dir)
            if key in seen_paths:
                continue
            seen_paths.add(key)

            record = _read_publish_record(ver_dir, entity_entry)
            if record is None:
                continue

            # Annotate with context if missing
            if not record.get("context"):
                if entity_entry["entity_type"] == "shot":
                    record["context"] = {
                        "type": "shot",
                        "sequence": entity_entry.get("sequence", ""),
                        "shot": entity_entry.get("shot", ""),
                    }
                else:
                    record["context"] = {
                        "type": "asset",
                        "asset_type": entity_entry.get("asset_type", ""),
                        "asset": entity_entry.get("asset", ""),
                    }

            record["_warnings"] = _check_missing_outputs(record)
            record["_orphaned"] = _check_orphaned(record)
            publishes.append(record)

    return {
        "project": project_meta.get("name", project_folder),
        "folder": project_folder,
        "indexed_at": _utc_now(),
        "publish_count": len(publishes),
        "publishes": publishes,
    }


def write_project_index(project_folder: str) -> Path:
    """Build and write .pipeline/publishes.json for a project. Returns the index path."""
    root = projects_root()
    index_data = build_project_index(project_folder)

    index_dir = root / project_folder / _INDEX_SUBDIR
    index_dir.mkdir(parents=True, exist_ok=True)
    index_path = index_dir / _INDEX_FILENAME

    with open(index_path, "w") as f:
        json.dump(index_data, f, indent=2, default=str)

    logger.info("Index written: %s  (%d publishes)", index_path, index_data["publish_count"])
    return index_path


def read_project_index(project_folder: str) -> dict | None:
    """Read the cached .pipeline/publishes.json for a project, if it exists."""
    root = projects_root()
    index_path = root / project_folder / _INDEX_SUBDIR / _INDEX_FILENAME
    if not index_path.exists():
        return None
    with open(index_path, "r") as f:
        return json.load(f)


def scan_all_projects() -> dict[str, dict]:
    """Build and write indexes for every registered project. Returns {folder: index}."""
    results = {}
    for project in load_projects():
        folder = project.get("folder", "")
        if not folder:
            continue
        try:
            write_project_index(folder)
            results[folder] = read_project_index(folder)
            logger.info("Indexed project: %s", folder)
        except Exception as e:
            logger.error("Failed to index project %s: %s", folder, e)
    return results


# ---------------------------------------------------------------------------
# Dependency helpers (Phase 7)
# ---------------------------------------------------------------------------

def get_publish_dependencies(publish_uuid: str, project_folder: str) -> list[dict]:
    """Return all dependency records for a publish UUID from the project index."""
    index = read_project_index(project_folder)
    if not index:
        return []
    for record in index.get("publishes", []):
        if record.get("uuid") == publish_uuid:
            return record.get("dependencies", [])
    return []


def get_downstream_dependents(publish_uuid: str, project_folder: str) -> list[dict]:
    """Return all publishes that list this UUID as a dependency."""
    index = read_project_index(project_folder)
    if not index:
        return []
    dependents = []
    for record in index.get("publishes", []):
        for dep in record.get("dependencies", []):
            if dep.get("publish_uuid") == publish_uuid:
                dependents.append(record)
                break
    return dependents


def detect_stale_dependencies(publish_uuid: str, project_folder: str) -> list[dict]:
    """
    Return dependencies whose source publish has been superseded by a newer version.
    A dependency is considered stale if there exists a newer version of the same
    entity/task/publish_type in the index.
    """
    index = read_project_index(project_folder)
    if not index:
        return []

    all_publishes = index.get("publishes", [])
    deps = get_publish_dependencies(publish_uuid, project_folder)
    stale = []

    for dep in deps:
        dep_uuid = dep.get("publish_uuid")
        if not dep_uuid:
            continue
        dep_record = next((r for r in all_publishes if r.get("uuid") == dep_uuid), None)
        if dep_record is None:
            stale.append({**dep, "_reason": "dependency_not_found"})
            continue

        # Check whether a newer version of the same entity+task+publish_type exists
        dep_entity = dep_record.get("entity", "")
        dep_task = dep_record.get("task", "")
        dep_type = dep_record.get("publish_type", "")
        dep_version = dep_record.get("version", 0)

        newer = [
            r for r in all_publishes
            if r.get("entity") == dep_entity
            and r.get("task") == dep_task
            and r.get("publish_type") == dep_type
            and r.get("version", 0) > dep_version
        ]
        if newer:
            stale.append({**dep, "_reason": "newer_version_exists",
                          "_latest_version": max(r["version"] for r in newer)})

    return stale


# ---------------------------------------------------------------------------
# Private
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"
