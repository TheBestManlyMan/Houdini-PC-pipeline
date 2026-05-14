"""
Cache file naming and directory creation helpers.
"""

import logging
from pathlib import Path

from .versioning import version_str
from .paths import _shot_fx_root, _asset_fx_root, _work_houdini

logger = logging.getLogger("pipeline")


# ---------------------------------------------------------------------------
# Cache file naming
# ---------------------------------------------------------------------------

def cache_filename(entity: str, task: str, version: int, ext: str) -> str:
    """ext: 'bgeo.sc', 'vdb', or 'abc'"""
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

def _make_work_dirs(fx_root: Path) -> Path:
    path = _work_houdini(fx_root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_shot_work_dirs(project_folder: str, seq: str, shot: str) -> None:
    path = _make_work_dirs(_shot_fx_root(project_folder, seq, shot))
    logger.info("Shot dirs created: %s", path)


def make_asset_work_dirs(project_folder: str, asset_type: str, asset: str) -> None:
    path = _make_work_dirs(_asset_fx_root(project_folder, asset_type, asset))
    logger.info("Asset dirs created: %s", path)


def make_cache_version_dirs(cache_root: Path, version: int) -> dict[str, Path]:
    """Create geo/ and vdb/ subdirs for a versioned cache folder. Returns paths."""
    geo = cache_root / "geo" / version_str(version)
    vdb = cache_root / "vdb" / version_str(version)
    geo.mkdir(parents=True, exist_ok=True)
    vdb.mkdir(parents=True, exist_ok=True)
    return {"geo": geo, "vdb": vdb}


def make_publish_version_dir(publish_root: Path, version: int) -> Path:
    d = publish_root / version_str(version)
    d.mkdir(parents=True, exist_ok=True)
    return d
