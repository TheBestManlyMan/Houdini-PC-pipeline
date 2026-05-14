"""
Hip file helpers and publish path builders.
All naming follows the conventions defined in CLAUDE.md.
"""

import logging
import re
import shutil
from pathlib import Path

from .versioning import version_str, get_versions
from .paths import shot_work_houdini, _shot_fx_root, entity_root_from_hip

# ---------------------------------------------------------------------------
# Standard outputs (Phase 6)
# ---------------------------------------------------------------------------

def build_standard_output_paths(publish_dir) -> dict[str, str]:
    """
    Return the conventional paths for standardised publish outputs.
    These paths are expected by the gallery; the indexer flags missing ones.

    Args:
        publish_dir: The versioned publish directory (e.g. .../preview/task/pub/v001/).

    Returns:
        Dict with keys: thumbnail, mp4, contactsheet, metadata.
    """
    d = Path(publish_dir)
    return {
        "thumbnail": str(d / "thumbnail.jpg"),
        "mp4": str(d / "preview.mp4"),
        "contactsheet": str(d / "contactsheet.jpg"),
        "metadata": str(d / "metadata.json"),
    }


def resolve_thumbnail(publish_dir) -> str | None:
    """Return the path to the best available thumbnail in publish_dir, or None."""
    d = Path(publish_dir)
    for name in ("thumbnail.jpg", "contactsheet.jpg"):
        p = d / name
        if p.exists():
            return str(p)
    jpgs = sorted(d.glob("*.jpg"))
    return str(jpgs[0]) if jpgs else None

logger = logging.getLogger("pipeline")

_HIP_4PART_RE = re.compile(
    r"^([A-Za-z0-9_]+)_fx_([a-z0-9][a-z0-9-]*)_([a-z0-9][a-z0-9-]*)_(v\d{3})$"
)
_HIP_3PART_RE = re.compile(r"^(.+)_fx_(.+)_(v\d{3})$")


# ---------------------------------------------------------------------------
# Hip file naming
# ---------------------------------------------------------------------------

def hip_filename(entity: str, task: str, version: int, descriptor: str = "") -> str:
    ver = version_str(version)
    if descriptor:
        return f"{entity}_fx_{task}_{descriptor}_{ver}.hip"
    return f"{entity}_fx_{task}_{ver}.hip"


def parse_hip_filename(filename: str) -> dict | None:
    """Parse entity, task, descriptor, version from a hip filename. Returns None if no match."""
    stem = Path(filename).stem
    m4 = _HIP_4PART_RE.fullmatch(stem)
    if m4:
        return {
            "entity": m4.group(1),
            "task": m4.group(2),
            "descriptor": m4.group(3),
            "version": int(m4.group(4)[1:]),
            "version_str": m4.group(4),
        }
    m3 = _HIP_3PART_RE.fullmatch(stem)
    if m3:
        return {
            "entity": m3.group(1),
            "task": m3.group(2),
            "descriptor": "",
            "version": int(m3.group(3)[1:]),
            "version_str": m3.group(3),
        }
    return None


def find_hip_files(work_houdini: Path) -> list[Path]:
    if not work_houdini.exists():
        return []
    return sorted(work_houdini.glob("*_fx_*_v???.hip"))


def latest_hip(work_houdini: Path) -> Path | None:
    hips = find_hip_files(work_houdini)
    return hips[-1] if hips else None


def next_hip_path(work_houdini: Path, entity: str, task: str, descriptor: str = "") -> Path:
    existing = []
    for h in find_hip_files(work_houdini):
        parsed = parse_hip_filename(h.name)
        if parsed and parsed["task"] == task and parsed["descriptor"] == descriptor:
            existing.append(parsed)
    versions = [e["version"] for e in existing if e]
    next_ver = (max(versions) + 1) if versions else 1
    return work_houdini / hip_filename(entity, task, next_ver, descriptor)


def prepare_hip_version_dir(project_folder: str, seq: str, shot: str,
                             entity: str, task: str, descriptor: str = "") -> Path:
    """Return the next versioned .hip path and ensure its parent directory exists."""
    work = shot_work_houdini(project_folder, seq, shot)
    path = next_hip_path(work, entity, task, descriptor)
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
# Publish path builders
# ---------------------------------------------------------------------------

def build_publish_path(entity_root, entity: str, task: str, publish_name: str,
                        fmt: str, version: int, animated: bool = True) -> Path:
    entity_root = Path(entity_root)
    ver = version_str(version)
    if fmt == "usd":
        folder_fmt = "usd"
        filename = f"{entity}_fx_{task}_{publish_name}_{ver}.usd"
    elif fmt == "abc":
        folder_fmt = "geo"
        filename = f"{entity}_fx_{task}_{publish_name}_{ver}.abc"
    elif fmt == "bgeo":
        folder_fmt = "geo"
        if animated:
            filename = f"{entity}_fx_{task}_{publish_name}_{ver}.$F4.bgeo.sc"
        else:
            filename = f"{entity}_fx_{task}_{publish_name}_{ver}.bgeo.sc"
    elif fmt == "vdb":
        folder_fmt = "geo"
        if animated:
            filename = f"{entity}_fx_{task}_{publish_name}_{ver}.$F4.vdb"
        else:
            filename = f"{entity}_fx_{task}_{publish_name}_{ver}.vdb"
    else:
        raise ValueError(f"Unknown publish format: {fmt!r}")
    directory = entity_root / "publish" / folder_fmt / task / publish_name / ver
    return directory / filename


def build_hip_publish_path(entity_root, entity: str, task: str,
                            descriptor: str, version: int) -> Path:
    entity_root = Path(entity_root)
    ver = version_str(version)
    desc = descriptor or "main"
    filename = f"{entity}_fx_{task}_{desc}_{ver}.hip"
    return entity_root / "publish" / "houdini" / task / desc / ver / filename


def build_preview_jpg_path(entity_root, entity: str, task: str, publish_name: str,
                            version: int, animated: bool = True) -> Path:
    entity_root = Path(entity_root)
    ver = version_str(version)
    directory = entity_root / "preview" / task / publish_name / ver
    if animated:
        filename = f"{entity}_fx_{task}_{publish_name}_{ver}.$F4.jpg"
    else:
        filename = f"{entity}_fx_{task}_{publish_name}_{ver}.jpg"
    return directory / filename


def build_mp4_path(entity_root, entity: str, task: str,
                   publish_name: str, version: int) -> Path:
    entity_root = Path(entity_root)
    ver = version_str(version)
    filename = f"{entity}_fx_{task}_{publish_name}_{ver}.mp4"
    return entity_root / "preview" / task / publish_name / ver / filename


def build_exr_path(entity_root, entity: str, task: str, descriptor: str,
                   rop_name: str, version: int) -> Path:
    entity_root = Path(entity_root)
    ver = version_str(version)
    directory = entity_root / "publish" / "render" / task / rop_name / ver
    filename = f"{entity}_fx_{task}_{descriptor}_{rop_name}_{ver}.$F4.exr"
    return directory / filename


def build_usd_cache_path(entity_root, entity: str, task: str,
                          descriptor: str, version: int) -> Path:
    entity_root = Path(entity_root)
    ver = version_str(version)
    directory = entity_root / "cache" / "usd" / task / descriptor / ver
    filename = f"{entity}_fx_{task}_{descriptor}_{ver}.usd"
    return directory / filename


# ---------------------------------------------------------------------------
# Hip snapshot
# ---------------------------------------------------------------------------

def hip_snapshot_paths(entity_root, current_hip, task: str,
                        descriptor: str, version: int) -> tuple[Path, Path]:
    current_hip = Path(current_hip)
    parsed = parse_hip_filename(current_hip.name)
    entity = parsed["entity"] if parsed else current_hip.stem
    snapshot_path = build_hip_publish_path(entity_root, entity, task, descriptor, version)
    next_ver = version + 1
    work_houdini = current_hip.parent
    next_work_path = work_houdini / hip_filename(entity, task, next_ver, descriptor)
    return snapshot_path, next_work_path


def snapshot_and_increment_hip(entity_root, current_hip_path, task: str,
                                 descriptor: str, version: int) -> tuple[Path, Path]:
    try:
        import hou
    except ImportError:
        raise RuntimeError("Must run inside Houdini.")
    current_hip_path = Path(current_hip_path)
    hou.hipFile.save(str(current_hip_path))
    snapshot_path, next_work_path = hip_snapshot_paths(
        entity_root, current_hip_path, task, descriptor, version
    )
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(current_hip_path), str(snapshot_path))
    logger.info("Hip snapshot: %s", snapshot_path)
    next_work_path.parent.mkdir(parents=True, exist_ok=True)
    hou.hipFile.save(str(next_work_path))
    logger.info("Hip incremented: %s", next_work_path)
    return snapshot_path, next_work_path
