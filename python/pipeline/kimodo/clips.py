"""
Kimodo motion clip library — naming, paths, sidecar metadata, BVH inspection.

A clip is a stem in the clips root with up to three files beside each other::

    {clips_root}/{stem}.npz      raw Kimodo motion (the reproducible source)
    {clips_root}/{stem}.bvh      SOMA skeleton, standard T-pose rest
    {clips_root}/{stem}.json     how it was generated (prompt, seed, steps...)

The NPZ is the master: the BVH can always be regenerated from it with
kimodo_convert, so the sidecar records the generation settings, not the export.
"""

import json
import re
import time
from pathlib import Path

from . import config

_SIDECAR_VERSION = 1


def slugify(text: str, maxlen: int = 40) -> str:
    """Prompt (or clip name) -> filesystem-safe stem."""
    slug = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")
    return slug[:maxlen].rstrip("_") or "clip"


def unique_stem(name: str, root: Path | None = None) -> str:
    """``name`` if free, else ``name_002``, ``name_003``... Never overwrites."""
    root = Path(root) if root is not None else config.clips_root()
    stem = slugify(name)
    if not any((root / (stem + ext)).exists() for ext in (".npz", ".bvh")):
        return stem
    for i in range(2, 1000):
        candidate = "%s_%03d" % (stem, i)
        if not any((root / (candidate + ext)).exists() for ext in (".npz", ".bvh")):
            return candidate
    raise RuntimeError("No free clip name for %r in %s" % (name, root))


def clip_path(stem: str, ext: str, root: Path | None = None) -> Path:
    root = Path(root) if root is not None else config.clips_root()
    if not ext.startswith("."):
        ext = "." + ext
    return root / (stem + ext)


def npz_path(stem, root=None) -> Path:
    return clip_path(stem, ".npz", root)


def bvh_path(stem, root=None) -> Path:
    return clip_path(stem, ".bvh", root)


def meta_path(stem, root=None) -> Path:
    return clip_path(stem, ".json", root)


def ensure_clips_root() -> Path:
    root = config.clips_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_meta(stem: str, prompt: str, duration: float, steps: int,
               seed=None, model: str = "", root=None, **extra) -> Path:
    """Record how a clip was generated so it can be reproduced exactly."""
    data = {
        "version": _SIDECAR_VERSION,
        "stem": stem,
        "prompt": prompt,
        "duration": float(duration),
        "diffusion_steps": int(steps),
        "seed": seed,
        "model": model or config.model(),
        "fps": config.fps(),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    data.update(extra)
    path = meta_path(stem, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path


def read_meta(stem: str, root=None) -> dict:
    path = meta_path(stem, root)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError):
        return {}


def list_clips(root=None) -> list:
    """Clip stems in the library that have a BVH, newest first."""
    root = Path(root) if root is not None else config.clips_root()
    if not root.is_dir():
        return []
    bvhs = sorted(root.glob("*.bvh"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.stem for p in bvhs]


# ------------------------------------------------------------------ BVH probe
# Cheap header reads — no third-party BVH parser, and the motion block is never
# loaded.

def bvh_frame_count(path) -> int | None:
    for line in _bvh_header(path):
        m = re.match(r"\s*Frames:\s*(\d+)", line)
        if m:
            return int(m.group(1))
    return None


def bvh_frame_time(path) -> float | None:
    for line in _bvh_header(path):
        m = re.match(r"\s*Frame Time:\s*([0-9.eE+-]+)", line)
        if m:
            return float(m.group(1))
    return None


def bvh_fps(path) -> float:
    ft = bvh_frame_time(path)
    if ft:
        return round(1.0 / ft, 6)
    return config.fps()


def bvh_joints(path) -> list:
    """Joint names in hierarchy order — ROOT first, then every JOINT."""
    names = []
    for line in _bvh_header(path):
        m = re.match(r"\s*(?:ROOT|JOINT)\s+(\S+)", line)
        if m:
            names.append(m.group(1))
        elif line.strip() == "MOTION":
            break
    return names


def _bvh_header(path):
    """Yield lines until the end of the MOTION header (never the frame data)."""
    with open(path, "r") as f:
        for line in f:
            yield line
            if line.startswith("Frame Time:"):
                return
