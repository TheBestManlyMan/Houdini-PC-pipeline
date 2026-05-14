"""
Publish metadata schema and I/O.

Every publish writes a metadata.json with a structured, immutable record.
The schema version field allows future migrations.
"""

import datetime
import json
import logging
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("pipeline")

METADATA_FILENAME = "metadata.json"
_LEGACY_FILENAME = "publish_meta.json"
SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_publish_id() -> str:
    return "pub_" + uuid.uuid4().hex[:12]


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _houdini_version() -> str:
    try:
        import hou
        return hou.applicationVersionString()
    except ImportError:
        return ""


def _dir_size_mb(directory: Path) -> float:
    try:
        total = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
        return round(total / (1024 * 1024), 2)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Schema builder
# ---------------------------------------------------------------------------

def build_metadata(
    *,
    project: str,
    context: dict,
    entity: str,
    task: str,
    publish_type: str,
    version: int,
    source: dict = None,
    outputs: dict = None,
    stats: dict = None,
    dependencies: list = None,
    tags: list = None,
    notes: list = None,
    wedge: dict = None,
) -> dict:
    """
    Build a complete, structured metadata record.

    Args:
        project:      Project name (from projects.json).
        context:      Dict with 'type' key ('shot' or 'asset') plus relevant fields.
        entity:       Entity name (e.g. 'SQ010_0010' or 'hero').
        task:         Task slug (e.g. 'dust-sim').
        publish_type: One of 'cache', 'flipbook', 'render', 'usd', 'hip'.
        version:      Integer publish version.
        source:       Source info dict (hip, rop, git_commit, houdini_version).
        outputs:      Output paths dict (thumbnail, mp4, frames, usd, cache).
        stats:        Stats dict (frame_start, frame_end, disk_mb).
        dependencies: List of dependency dicts.
        tags:         List of string tags.
        notes:        List of note strings.
        wedge:        Optional wedge info dict {'parameter': str, 'value': any}.
    """
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "uuid": _make_publish_id(),
        "project": project,
        "context": context,
        "entity": entity,
        "task": task,
        "publish_type": publish_type,
        "version": version,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "created_by": os.getenv("USER", "unknown"),
        "source": {
            "hip": source.get("hip", "") if source else "",
            "houdini_version": source.get("houdini_version", _houdini_version()) if source else _houdini_version(),
            "rop": source.get("rop", "") if source else "",
            "git_commit": source.get("git_commit", _git_commit()) if source else _git_commit(),
        },
        "outputs": outputs or {
            "thumbnail": "",
            "mp4": "",
            "frames": "",
            "usd": "",
            "cache": "",
        },
        "stats": stats or {
            "frame_start": 1,
            "frame_end": 1,
            "disk_mb": 0.0,
        },
        "dependencies": dependencies or [],
        "tags": tags or [],
        "notes": notes or [],
    }
    if wedge is not None:
        record["wedge"] = wedge
    return record


def build_metadata_from_legacy(legacy: dict) -> dict:
    """Upgrade a v1 publish_meta.json record to the current schema."""
    pub_type = "flipbook" if legacy.get("publish_name") == "flipbook" else (
        "render" if "rop_name" in legacy else "cache"
    )
    return build_metadata(
        project=legacy.get("project", ""),
        context={"type": "unknown"},
        entity=legacy.get("entity", ""),
        task=legacy.get("task", ""),
        publish_type=pub_type,
        version=legacy.get("version", 0),
        source={
            "hip": legacy.get("hip_snapshot", ""),
            "houdini_version": "",
            "rop": legacy.get("rop_name", ""),
            "git_commit": "",
        },
        outputs={
            "thumbnail": "",
            "mp4": legacy.get("preview_mp4", "") or "",
            "frames": "",
            "usd": legacy.get("usd_path", "") or "",
            "cache": "",
        },
        stats={
            "frame_start": legacy.get("frame_start", 1),
            "frame_end": legacy.get("frame_end", 1),
            "disk_mb": 0.0,
        },
        notes=[legacy.get("description", "")] if legacy.get("description") else [],
    )


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def write_metadata(publish_dir, metadata: dict) -> Path:
    """Write metadata.json into publish_dir. Returns the written path."""
    publish_dir = Path(publish_dir)
    publish_dir.mkdir(parents=True, exist_ok=True)
    meta_path = publish_dir / METADATA_FILENAME
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    logger.debug("Metadata written: %s", meta_path)
    return meta_path


def read_metadata(publish_dir) -> dict | None:
    """Read metadata.json from publish_dir. Falls back to legacy publish_meta.json."""
    publish_dir = Path(publish_dir)
    meta_path = publish_dir / METADATA_FILENAME
    if meta_path.exists():
        with open(meta_path, "r") as f:
            return json.load(f)
    # Transparent legacy fallback
    legacy_path = publish_dir / _LEGACY_FILENAME
    if legacy_path.exists():
        with open(legacy_path, "r") as f:
            try:
                return build_metadata_from_legacy(json.load(f))
            except Exception:
                return None
    return None


def update_metadata_outputs(publish_dir, outputs: dict) -> None:
    """Merge additional output paths into an existing metadata.json."""
    meta = read_metadata(publish_dir)
    if meta is None:
        return
    meta.setdefault("outputs", {}).update(outputs)
    write_metadata(publish_dir, meta)


# ---------------------------------------------------------------------------
# Backward-compatible shim (used by publisher.py)
# ---------------------------------------------------------------------------

def write_publish_metadata(publish_dir, metadata: dict) -> Path:
    """
    Write metadata to publish_dir.

    Accepts both v1 flat dicts (from existing publisher code) and v2 structured
    dicts. If a v1 dict is detected (no 'uuid' key), it is upgraded in-place.
    The file is always written as metadata.json.
    """
    if "uuid" not in metadata:
        # Upgrade legacy flat dict to structured schema
        metadata = build_metadata_from_legacy(metadata)
    return write_metadata(publish_dir, metadata)
