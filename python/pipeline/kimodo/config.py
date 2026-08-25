"""
Kimodo integration settings — where the external Kimodo install lives, and how
Houdini must launch a child process against it.

Kimodo (NVIDIA text-to-motion) is an EXTERNAL application with its own Python
environment.  Nothing in this package imports kimodo, torch or transformers —
Houdini only ever talks to it over subprocess.  This module is the single place
that knows the install layout; every other kimodo module asks here.

Settings come from the ``kimodo`` block of pipeline_config.json (loaded through
pipeline.config, never read directly).  Missing keys fall back to DEFAULTS.
"""

import os
from pathlib import Path

from ..config import load_config, projects_root

DEFAULTS = {
    # Root of the external Kimodo checkout (contains .venv/, kimodo/).
    "install_root": "~/Projects/kimodo",
    # Virtualenv directory name inside install_root.
    "venv": ".venv",
    # Where generated clips are written. Empty -> {projects_root}/_library/motion/kimodo
    "clips_root": "",
    # Kimodo resamples every generated motion to 30 Hz.
    "fps": 30.0,
    # SOMA BVH is authored in centimetres; Houdini works in metres.
    "bvh_scale": 0.01,
    # 12 GB card: keeping the Llama-3 text encoder off the GPU leaves room for
    # the diffusion model.
    "text_encoder_device": "cpu",
    # Empty -> kimodo_gen's own default model.
    "model": "",
    # Houdini leaks its own interpreter into children; these must not survive
    # into the venv's python (see PYTHONHOME leak note in docs/kimodo_setup.md).
    "strip_env": ["PYTHONHOME", "PYTHONPATH"],
}


def settings() -> dict:
    """DEFAULTS merged with the ``kimodo`` block of pipeline_config.json."""
    merged = dict(DEFAULTS)
    merged.update(load_config().get("kimodo", {}))
    return merged


def _expand(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(str(value))))


def install_root() -> Path:
    """Kimodo checkout. $KIMODO_ROOT wins over the config file."""
    return _expand(os.environ.get("KIMODO_ROOT") or settings()["install_root"])


def venv_root() -> Path:
    return install_root() / settings()["venv"]


def venv_bin(name: str) -> Path:
    """Path to an executable inside the Kimodo venv (kimodo_gen, python, ...)."""
    return venv_root() / "bin" / name


def gen_executable() -> Path:
    return venv_bin("kimodo_gen")


def convert_executable() -> Path:
    return venv_bin("kimodo_convert")


def clips_root() -> Path:
    """Motion library root — generated NPZ/BVH clips land here."""
    configured = settings()["clips_root"]
    if configured:
        return _expand(configured)
    return projects_root() / "_library" / "motion" / "kimodo"


def fps() -> float:
    return float(settings()["fps"])


def bvh_scale() -> float:
    return float(settings()["bvh_scale"])


def model() -> str:
    return str(settings()["model"] or "")


def child_env(extra: dict | None = None) -> dict:
    """Environment for a Kimodo child process launched from Houdini.

    Houdini's PYTHONHOME/PYTHONPATH point at $HFS/python (3.13); inheriting them
    makes the venv's python 3.10 fail on import.  Strip them, then pin the text
    encoder device.
    """
    env = dict(os.environ)
    for key in settings()["strip_env"]:
        env.pop(key, None)
    env["TEXT_ENCODER_DEVICE"] = str(settings()["text_encoder_device"])
    if extra:
        env.update({str(k): str(v) for k, v in extra.items()})
    return env


def problems() -> list:
    """Human-readable reasons Kimodo could not run right now. Empty == ready."""
    issues = []
    root = install_root()
    if not root.is_dir():
        issues.append("Kimodo install not found: %s" % root)
        return issues
    for exe in (gen_executable(), convert_executable()):
        if not exe.is_file():
            issues.append("Missing executable: %s" % exe)
        elif not os.access(exe, os.X_OK):
            issues.append("Not executable: %s" % exe)
    return issues
