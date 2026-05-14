"""
Version scanning utilities.
Version numbers come ONLY from scanning disk — never from config or state.
"""

import re
from pathlib import Path

_VERSION_RE = re.compile(r"v(\d{3})")


def get_versions(folder: Path) -> list[int]:
    """Return sorted list of version numbers found as v### subfolders in folder."""
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


def get_next_publish_version(entity_root, task: str, publish_name: str) -> int:
    entity_root = Path(entity_root)
    found = []
    for folder_fmt in ("geo", "usd", "houdini"):
        scan_dir = entity_root / "publish" / folder_fmt / task / publish_name
        found.extend(get_versions(scan_dir))
    preview_dir = entity_root / "preview" / task / publish_name
    found.extend(get_versions(preview_dir))
    return (max(found) + 1) if found else 1


def get_next_render_version(entity_root, task: str) -> int:
    entity_root = Path(entity_root)
    render_dir = entity_root / "publish" / "render" / task
    found = []
    if render_dir.exists():
        for rop_dir in render_dir.iterdir():
            if rop_dir.is_dir():
                found.extend(get_versions(rop_dir))
    return (max(found) + 1) if found else 1
