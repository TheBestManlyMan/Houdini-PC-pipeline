"""
Centralised validation utilities.
All validation happens here; callers receive either the clean value or a ValueError.
"""

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_ENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_]*$")
_TASK_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_VERSION_STR_RE = re.compile(r"^v(\d{3})$")
_ILLEGAL_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

VALID_PUBLISH_TYPES = frozenset({"cache", "flipbook", "render", "usd", "hip"})
VALID_CONTEXT_TYPES = frozenset({"shot", "asset"})


# ---------------------------------------------------------------------------
# Entity / task
# ---------------------------------------------------------------------------

def validate_entity_name(name: str) -> str:
    """
    Validate and return a clean entity name (shot code or asset name).
    Raises ValueError for empty strings, illegal filesystem characters, or
    patterns that don't match ^[A-Za-z0-9][A-Za-z0-9_]*$.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Entity name must be a non-empty string.")
    name = name.strip()
    if _ILLEGAL_FS_CHARS.search(name):
        raise ValueError(f"Entity name contains illegal filesystem characters: {name!r}")
    if not _ENTITY_RE.fullmatch(name):
        raise ValueError(
            f"Entity name {name!r} is invalid. "
            "Use alphanumerics and underscores only, starting with a letter or digit."
        )
    return name


def _format_task(raw: str) -> str:
    slug = raw.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def validate_task_name(raw: str) -> str:
    """
    Normalise and validate a task slug.
    'Falling Ice' → 'falling-ice'. Raises ValueError if the result is invalid.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Task name must be a non-empty string.")
    result = _format_task(raw)
    if not result or not _TASK_RE.fullmatch(result):
        raise ValueError(
            f"{raw!r} cannot become a valid task name. "
            "Use lowercase letters, digits, and hyphens (e.g. 'dust-sim')."
        )
    return result


def validate_publish_type(publish_type: str) -> str:
    """Validate publish_type is one of the known types."""
    if publish_type not in VALID_PUBLISH_TYPES:
        raise ValueError(
            f"Unknown publish type {publish_type!r}. "
            f"Valid types: {sorted(VALID_PUBLISH_TYPES)}"
        )
    return publish_type


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

def validate_context(context: dict) -> dict:
    """
    Validate a publish context dict.

    Shot context requires: type='shot', sequence, shot.
    Asset context requires: type='asset', asset_type, asset.
    """
    if not isinstance(context, dict):
        raise ValueError("Context must be a dict.")
    ctx_type = context.get("type", "")
    if ctx_type not in VALID_CONTEXT_TYPES:
        raise ValueError(
            f"Context type {ctx_type!r} is invalid. Must be 'shot' or 'asset'."
        )
    if ctx_type == "shot":
        for field in ("sequence", "shot"):
            if not context.get(field):
                raise ValueError(f"Shot context requires '{field}' field.")
    elif ctx_type == "asset":
        for field in ("asset_type", "asset"):
            if not context.get(field):
                raise ValueError(f"Asset context requires '{field}' field.")
    return context


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

def validate_version(version) -> int:
    """
    Accept either an integer ≥ 1 or a 'v###' string.
    Returns the integer version number.
    """
    if isinstance(version, str):
        m = _VERSION_STR_RE.fullmatch(version)
        if m:
            return int(m.group(1))
        try:
            version = int(version)
        except ValueError:
            raise ValueError(
                f"Version {version!r} must be a positive integer or 'v###' string."
            )
    if not isinstance(version, int) or version < 1:
        raise ValueError(f"Version must be a positive integer, got {version!r}.")
    return version


# ---------------------------------------------------------------------------
# Publish record
# ---------------------------------------------------------------------------

def validate_publish(publish: dict) -> dict:
    """
    Validate a publish metadata record.
    Checks required top-level fields and their types.
    Raises ValueError with a descriptive message on the first problem found.
    """
    required = ("uuid", "project", "entity", "task", "publish_type", "version",
                 "created_at", "created_by", "context", "source", "outputs",
                 "stats", "dependencies", "tags", "notes")
    for field in required:
        if field not in publish:
            raise ValueError(f"Publish record missing required field: '{field}'.")

    validate_entity_name(publish["entity"])
    validate_task_name(publish["task"])
    validate_publish_type(publish["publish_type"])
    validate_version(publish["version"])
    validate_context(publish["context"])

    if not isinstance(publish["dependencies"], list):
        raise ValueError("'dependencies' must be a list.")
    if not isinstance(publish["tags"], list):
        raise ValueError("'tags' must be a list.")
    if not isinstance(publish["notes"], list):
        raise ValueError("'notes' must be a list.")

    return publish


# ---------------------------------------------------------------------------
# Publish folder structure
# ---------------------------------------------------------------------------

def validate_publish_folder(publish_dir) -> Path:
    """
    Raise ValueError if the given directory is missing or has no metadata file.
    Returns the resolved Path on success.
    """
    d = Path(publish_dir)
    if not d.exists():
        raise ValueError(f"Publish folder does not exist: {d}")
    if not d.is_dir():
        raise ValueError(f"Publish path is not a directory: {d}")
    meta = d / "metadata.json"
    legacy = d / "publish_meta.json"
    if not meta.exists() and not legacy.exists():
        raise ValueError(
            f"Publish folder has no metadata.json or publish_meta.json: {d}"
        )
    return d
