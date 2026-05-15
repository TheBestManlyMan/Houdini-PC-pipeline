"""
Project indexer — scans the filesystem for publishes and builds cached indexes.

Index files live at:
    {projects_root}/{project}/.pipeline/publishes.json

The index is always rebuilt from disk.  Version numbers are never stored as state.
Gallery contract: reads schema only — no filesystem inference, no globbing.
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

# Fields that identify a canonical schema v1 publish product
_CANONICAL_FIELDS = frozenset({"representations", "preview", "paths", "audit"})


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
# Publish directory discovery
# ---------------------------------------------------------------------------

def _iter_publish_dirs(entity_root: Path) -> Iterator[Path]:
    """Yield every versioned publish directory under an entity root.

    publish/ uses 4 levels: publish/{fmt}/{task}/{pub_name}/{ver}/
    preview/ uses 3 levels: preview/{task}/{pub_name}/{ver}/
    """
    pub_top = entity_root / "publish"
    if pub_top.is_dir():
        for fmt_dir in pub_top.iterdir():
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

    preview_top = entity_root / "preview"
    if preview_top.is_dir():
        for task_dir in preview_top.iterdir():
            if not task_dir.is_dir():
                continue
            for pub_name_dir in task_dir.iterdir():
                if not pub_name_dir.is_dir():
                    continue
                for ver_dir in pub_name_dir.iterdir():
                    if ver_dir.is_dir() and ver_dir.name.startswith("v"):
                        yield ver_dir


# ---------------------------------------------------------------------------
# Schema validation (no filesystem access)
# ---------------------------------------------------------------------------

def _is_canonical(record: dict) -> bool:
    """Return True if record follows canonical publish schema v1."""
    return bool(_CANONICAL_FIELDS.issubset(record.keys()))


def _schema_warnings(record: dict) -> list[str]:
    """Derive warnings from schema fields — no filesystem access."""
    if not _is_canonical(record):
        return ["non_canonical_schema"]

    warnings = []
    reps = record.get("representations") or []
    if not reps:
        warnings.append("no_representations")

    preview = record.get("preview") or {}
    if not preview.get("mp4"):
        warnings.append("missing_preview_mp4")
    if not preview.get("thumbnail"):
        warnings.append("missing_thumbnail")

    return warnings


# ---------------------------------------------------------------------------
# Publish record reader
# ---------------------------------------------------------------------------

def _read_publish_record(ver_dir: Path, entity_entry: dict) -> dict | None:
    """
    Read publish metadata for a versioned directory.

    Returns the record annotated with _index_path and _schema_valid.
    Returns None only if the directory is completely unreadable.

    Never synthesises records from folder structure — if no metadata.json
    exists the record is returned with _schema_valid=False so the gallery
    can display "Invalid Publish" rather than guess at content.
    """
    try:
        meta = read_metadata(ver_dir)
    except Exception as e:
        logger.warning("Could not read publish at %s: %s", ver_dir, e)
        return None

    if meta is None:
        # No metadata file — return a minimal invalid record
        return {
            "schema_version": 0,
            "_index_path": str(ver_dir),
            "_schema_valid": False,
            "_invalid_reason": "missing_metadata",
        }

    meta["_index_path"] = str(ver_dir)
    meta["_schema_valid"] = _is_canonical(meta)
    if not meta["_schema_valid"]:
        meta["_invalid_reason"] = "non_canonical_schema"

    return meta


# ---------------------------------------------------------------------------
# Index builder
# ---------------------------------------------------------------------------

def build_project_index(project_folder: str) -> dict:
    """
    Scan a single project directory and return its full index as a dict.

    Each publish record is annotated with:
      _index_path   — the versioned publish folder
      _schema_valid — True only for canonical schema v1 records
      _warnings     — list of schema-derived issues (no filesystem access)
    """
    root = projects_root()
    project_dir = root / project_folder
    if not project_dir.is_dir():
        raise ValueError(f"Project directory not found: {project_dir}")

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

            # Annotate entity context onto canonical records that lack it
            if _is_canonical(record) and not record.get("context"):
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

            if not record.get("project"):
                record["project"] = project_meta.get("name", project_folder)

            record["_warnings"] = _schema_warnings(record)
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
# Dependency helpers
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

        dep_entity  = dep_record.get("entity", "")
        dep_task    = dep_record.get("task", "")
        dep_type    = dep_record.get("product_type") or dep_record.get("publish_type", "")
        dep_version = dep_record.get("version", 0)

        newer = [
            r for r in all_publishes
            if r.get("entity") == dep_entity
            and r.get("task") == dep_task
            and (r.get("product_type") or r.get("publish_type", "")) == dep_type
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
