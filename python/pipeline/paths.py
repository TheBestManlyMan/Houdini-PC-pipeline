"""
Path builders for shot and asset contexts.
All path construction is centralised here — no other module builds paths inline.
"""

from pathlib import Path

from .config import projects_root


# ---------------------------------------------------------------------------
# Private shared helpers — everything below FX/ is identical for shots/assets
# ---------------------------------------------------------------------------

def _shot_fx_root(project_folder: str, seq: str, shot: str) -> Path:
    return projects_root() / project_folder / seq / shot / "FX"


def _asset_fx_root(project_folder: str, asset_type: str, asset: str) -> Path:
    return projects_root() / project_folder / "assets" / asset_type / asset / "FX"


def _work_houdini(fx_root: Path) -> Path:
    return fx_root / "work" / "houdini"


def _cache_root(fx_root: Path, task: str) -> Path:
    return _work_houdini(fx_root) / "cache" / task


def _publish_root(fx_root: Path, fmt: str, task: str) -> Path:
    return fx_root / "publish" / fmt / task


# ---------------------------------------------------------------------------
# Shot context — public API
# ---------------------------------------------------------------------------

def shot_fx_root(project_folder: str, seq: str, shot: str) -> Path:
    return _shot_fx_root(project_folder, seq, shot)


def shot_work_houdini(project_folder: str, seq: str, shot: str) -> Path:
    return _work_houdini(_shot_fx_root(project_folder, seq, shot))


def shot_cache_root(project_folder: str, seq: str, shot: str, task: str) -> Path:
    return _cache_root(_shot_fx_root(project_folder, seq, shot), task)


def shot_publish_root(project_folder: str, seq: str, shot: str, fmt: str, task: str) -> Path:
    return _publish_root(_shot_fx_root(project_folder, seq, shot), fmt, task)


# ---------------------------------------------------------------------------
# Asset context — public API
# ---------------------------------------------------------------------------

def asset_fx_root(project_folder: str, asset_type: str, asset: str) -> Path:
    return _asset_fx_root(project_folder, asset_type, asset)


def asset_work_houdini(project_folder: str, asset_type: str, asset: str) -> Path:
    return _work_houdini(_asset_fx_root(project_folder, asset_type, asset))


def asset_cache_root(project_folder: str, asset_type: str, asset: str, task: str) -> Path:
    return _cache_root(_asset_fx_root(project_folder, asset_type, asset), task)


def asset_publish_root(project_folder: str, asset_type: str, asset: str, fmt: str, task: str) -> Path:
    return _publish_root(_asset_fx_root(project_folder, asset_type, asset), fmt, task)


# ---------------------------------------------------------------------------
# Derived roots
# ---------------------------------------------------------------------------

def entity_root_from_hip(hip_path) -> Path:
    """Resolve entity root (FX/) from a hip file anywhere in .../FX/work/houdini/."""
    hip_path = Path(hip_path)
    parent = hip_path.parent
    if parent.name == "houdini" and parent.parent.name == "work":
        return parent.parent.parent
    return parent.parent
