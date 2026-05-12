"""
Houdini FX Pipeline — core utility module.
All path logic, versioning, and project registry access lives here.
UI scripts call these functions; they never build paths themselves.
"""

import datetime
import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("pipeline")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PIPELINE_ROOT / "pipeline_config.json"
_PROJECTS_PATH = _PIPELINE_ROOT / "projects.json"


def load_config() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        return json.load(f)


def projects_root() -> Path:
    return Path(load_config()["projects_root"])


# ---------------------------------------------------------------------------
# Project registry
# ---------------------------------------------------------------------------

def load_projects() -> list[dict]:
    if not _PROJECTS_PATH.exists():
        return []
    with open(_PROJECTS_PATH, "r") as f:
        return json.load(f).get("projects", [])


def get_project(name: str) -> dict | None:
    for p in load_projects():
        if p["name"] == name or p["folder"] == name:
            return p
    return None


def save_projects(projects: list[dict]) -> None:
    with open(_PROJECTS_PATH, "w") as f:
        json.dump({"projects": projects}, f, indent=2)


def add_sequence(project_folder: str, seq: str) -> None:
    projects = load_projects()
    for p in projects:
        if p["folder"] == project_folder:
            if seq in p.get("sequences", []):
                raise ValueError(f"Sequence '{seq}' already exists in project.")
            p.setdefault("sequences", []).append(seq)
            p["sequences"].sort()
            save_projects(projects)
            logger.info("Sequence added: %s/%s", project_folder, seq)
            return
    raise ValueError(f"Project folder '{project_folder}' not found in registry.")


def add_project(name: str, folder: str, fps: int = None, resolution: str = None,
                sequences: list[str] = None, assets: dict = None) -> dict:
    cfg = load_config()
    project = {
        "name": name,
        "folder": folder,
        "fps": fps or cfg.get("default_fps", 24),
        "resolution": resolution or cfg.get("default_resolution", "1920x1080"),
        "sequences": sequences or [],
        "assets": assets or {},
    }
    projects = load_projects()
    if any(p["folder"] == folder for p in projects):
        raise ValueError(f"Project folder '{folder}' already exists in registry.")
    projects.append(project)
    save_projects(projects)
    logger.info("Project created: %s  →  %s", name, projects_root() / folder)
    return project


# ---------------------------------------------------------------------------
# Path builders — shot context
# ---------------------------------------------------------------------------

def shot_fx_root(project_folder: str, seq: str, shot: str) -> Path:
    return projects_root() / project_folder / seq / shot / "FX"


def shot_work_houdini(project_folder: str, seq: str, shot: str) -> Path:
    return shot_fx_root(project_folder, seq, shot) / "work" / "houdini"


def shot_cache_root(project_folder: str, seq: str, shot: str, task: str) -> Path:
    return shot_work_houdini(project_folder, seq, shot) / "cache" / task


def shot_publish_root(project_folder: str, seq: str, shot: str, fmt: str, task: str) -> Path:
    return shot_fx_root(project_folder, seq, shot) / "publish" / fmt / task


# ---------------------------------------------------------------------------
# Path builders — asset context
# ---------------------------------------------------------------------------

def asset_fx_root(project_folder: str, asset_type: str, asset: str) -> Path:
    return projects_root() / project_folder / "assets" / asset_type / asset / "FX"


def asset_work_houdini(project_folder: str, asset_type: str, asset: str) -> Path:
    return asset_fx_root(project_folder, asset_type, asset) / "work" / "houdini"


def asset_cache_root(project_folder: str, asset_type: str, asset: str, task: str) -> Path:
    return asset_work_houdini(project_folder, asset_type, asset) / "cache" / task


def asset_publish_root(project_folder: str, asset_type: str, asset: str, fmt: str, task: str) -> Path:
    return asset_fx_root(project_folder, asset_type, asset) / "publish" / fmt / task


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"v(\d{3})")


def get_versions(folder: Path) -> list[int]:
    """Return sorted list of version numbers found as subfolders in folder."""
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


# ---------------------------------------------------------------------------
# Hip file naming
# ---------------------------------------------------------------------------

def hip_filename(entity: str, task: str, version: int, descriptor: str = "") -> str:
    ver = version_str(version)
    if descriptor:
        return f"{entity}_fx_{task}_{descriptor}_{ver}.hip"
    return f"{entity}_fx_{task}_{ver}.hip"


_HIP_4PART_RE = re.compile(
    r"^([A-Za-z0-9_]+)_fx_([a-z0-9][a-z0-9-]*)_([a-z0-9][a-z0-9-]*)_(v\d{3})$"
)
_HIP_3PART_RE = re.compile(r"^(.+)_fx_(.+)_(v\d{3})$")


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


# ---------------------------------------------------------------------------
# Cache file naming
# ---------------------------------------------------------------------------

def cache_filename(entity: str, task: str, version: int, ext: str) -> str:
    """ext examples: 'bgeo.sc', 'vdb', 'abc'"""
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

def make_shot_work_dirs(project_folder: str, seq: str, shot: str) -> None:
    path = shot_work_houdini(project_folder, seq, shot)
    path.mkdir(parents=True, exist_ok=True)
    logger.info("Shot dirs created: %s", path)


def make_asset_work_dirs(project_folder: str, asset_type: str, asset: str) -> None:
    path = asset_work_houdini(project_folder, asset_type, asset)
    path.mkdir(parents=True, exist_ok=True)
    logger.info("Asset dirs created: %s", path)


def make_cache_version_dirs(cache_root: Path, version: int) -> dict[str, Path]:
    """Create geo and vdb subdirs for a versioned cache folder. Returns paths."""
    geo = cache_root / "geo" / version_str(version)
    vdb = cache_root / "vdb" / version_str(version)
    geo.mkdir(parents=True, exist_ok=True)
    vdb.mkdir(parents=True, exist_ok=True)
    return {"geo": geo, "vdb": vdb}


def make_publish_version_dir(publish_root: Path, version: int) -> Path:
    d = publish_root / version_str(version)
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Hip file helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Hip version preparation
# ---------------------------------------------------------------------------

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
# ffmpeg preview
# ---------------------------------------------------------------------------

def build_ffmpeg_cmd(image_seq_path: str, output_mp4: str, fps: int = None) -> list[str]:
    cfg = load_config()
    ffmpeg = cfg.get("ffmpeg", "ffmpeg")
    frame_rate = fps or cfg.get("default_fps", 24)
    return [
        ffmpeg,
        "-framerate", str(frame_rate),
        "-i", image_seq_path,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        output_mp4,
    ]


# ---------------------------------------------------------------------------
# Hip context from path
# ---------------------------------------------------------------------------

def entity_root_from_hip(hip_path) -> Path:
    hip_path = Path(hip_path)
    parent = hip_path.parent
    # Both shot and asset hips live at .../FX/work/houdini/{hip} → entity root is FX/
    if parent.name == "houdini" and parent.parent.name == "work":
        return parent.parent.parent
    return parent.parent


# ---------------------------------------------------------------------------
# Publish path builders
# ---------------------------------------------------------------------------

def build_publish_path(entity_root, entity, task, publish_name, fmt, version,
                        animated=True) -> Path:
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


def build_hip_publish_path(entity_root, entity, task, descriptor, version) -> Path:
    entity_root = Path(entity_root)
    ver = version_str(version)
    desc = descriptor or "main"
    filename = f"{entity}_fx_{task}_{desc}_{ver}.hip"
    return entity_root / "publish" / "houdini" / task / desc / ver / filename


def build_preview_jpg_path(entity_root, entity, task, publish_name, version,
                            animated=True) -> Path:
    entity_root = Path(entity_root)
    ver = version_str(version)
    directory = entity_root / "preview" / task / publish_name / ver
    if animated:
        filename = f"{entity}_fx_{task}_{publish_name}_{ver}.$F4.jpg"
    else:
        filename = f"{entity}_fx_{task}_{publish_name}_{ver}.jpg"
    return directory / filename


def build_mp4_path(entity_root, entity, task, publish_name, version) -> Path:
    entity_root = Path(entity_root)
    ver = version_str(version)
    filename = f"{entity}_fx_{task}_{publish_name}_{ver}.mp4"
    return entity_root / "preview" / task / publish_name / ver / filename


# ---------------------------------------------------------------------------
# Publish versioning
# ---------------------------------------------------------------------------

def get_next_publish_version(entity_root, task, publish_name) -> int:
    entity_root = Path(entity_root)
    found = []
    for folder_fmt in ("geo", "usd", "houdini"):
        scan_dir = entity_root / "publish" / folder_fmt / task / publish_name
        found.extend(get_versions(scan_dir))
    preview_dir = entity_root / "preview" / task / publish_name
    found.extend(get_versions(preview_dir))
    return (max(found) + 1) if found else 1


# ---------------------------------------------------------------------------
# Hip snapshot
# ---------------------------------------------------------------------------

def hip_snapshot_paths(entity_root, current_hip, task, descriptor,
                        version) -> tuple[Path, Path]:
    current_hip = Path(current_hip)
    parsed = parse_hip_filename(current_hip.name)
    entity = parsed["entity"] if parsed else current_hip.stem
    snapshot_path = build_hip_publish_path(entity_root, entity, task, descriptor, version)
    next_ver = version + 1
    work_houdini = current_hip.parent
    next_work_path = work_houdini / hip_filename(entity, task, next_ver, descriptor)
    return snapshot_path, next_work_path


def snapshot_and_increment_hip(entity_root, current_hip_path, task, descriptor,
                                 version) -> tuple[Path, Path]:
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


# ---------------------------------------------------------------------------
# Publish metadata
# ---------------------------------------------------------------------------

def write_publish_metadata(publish_dir, metadata: dict) -> Path:
    publish_dir = Path(publish_dir)
    meta_path = publish_dir / "publish_meta.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    return meta_path


# ---------------------------------------------------------------------------
# Media encoding
# ---------------------------------------------------------------------------

def encode_mp4(jpg_seq_path: str, output_mp4: str, fps=None,
                frame_start: int = 1) -> None:
    cfg = load_config()
    ffmpeg = cfg.get("ffmpeg", "ffmpeg")
    frame_rate = fps or cfg.get("default_fps", 24)
    ffmpeg_input = jpg_seq_path.replace("$F4", "%04d")
    cmd = [
        ffmpeg,
        "-framerate", str(frame_rate),
        "-start_number", str(frame_start),
        "-i", ffmpeg_input,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-y",
        output_mp4,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (code {result.returncode}):\n"
            + result.stderr.decode(errors="replace")
        )
    logger.info("Encoded: %s", output_mp4)


def flipbook_viewport(jpg_seq_path: str, frame_range: tuple,
                       camera: str = None, resolution: tuple = (1280, 720),
                       scene_viewer=None) -> None:
    try:
        import hou
    except ImportError:
        raise RuntimeError("Must run inside Houdini.")

    if scene_viewer is None:
        for pane in hou.ui.paneTabs():
            if pane.type() == hou.paneTabType.SceneViewer:
                scene_viewer = pane
                break
    if scene_viewer is None:
        raise RuntimeError("No SceneViewer tab found.")

    sv = scene_viewer
    settings = sv.flipbookSettings().stash()
    settings.frameRange(frame_range)
    settings.outputToMPlay(False)
    settings.output(jpg_seq_path)
    settings.resolution(resolution)

    if camera:
        cam_node = hou.node(camera)
        if cam_node:
            viewport = sv.curViewport()
            viewport.setCamera(cam_node)

    sv.flipbook(settings=settings)
    logger.info("Flipbook captured: %s  frames %s–%s", jpg_seq_path, *frame_range)


def encode_mp4_from_exr(exr_seq_path: str, output_mp4: str, fps=None,
                         frame_start: int = 1) -> None:
    cfg = load_config()
    ffmpeg = cfg.get("ffmpeg", "ffmpeg")
    frame_rate = fps or cfg.get("default_fps", 24)
    ffmpeg_input = exr_seq_path.replace("$F4", "%04d")
    cmd = [
        ffmpeg,
        "-framerate", str(frame_rate),
        "-start_number", str(frame_start),
        "-i", ffmpeg_input,
        "-vf", "tonemap=reinhard:desat=0",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-y",
        output_mp4,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (code {result.returncode}):\n"
            + result.stderr.decode(errors="replace")
        )
    logger.info("Encoded from EXR: %s", output_mp4)


def build_exr_path(entity_root, entity, task, descriptor, rop_name,
                   version) -> Path:
    entity_root = Path(entity_root)
    ver = version_str(version)
    directory = entity_root / "publish" / "render" / task / rop_name / ver
    filename = f"{entity}_fx_{task}_{descriptor}_{rop_name}_{ver}.$F4.exr"
    return directory / filename


def build_usd_cache_path(entity_root, entity, task, descriptor,
                         version) -> Path:
    entity_root = Path(entity_root)
    ver = version_str(version)
    directory = entity_root / "cache" / "usd" / task / descriptor / ver
    filename = f"{entity}_fx_{task}_{descriptor}_{ver}.usd"
    return directory / filename


def get_next_render_version(entity_root, task) -> int:
    entity_root = Path(entity_root)
    render_dir = entity_root / "publish" / "render" / task
    found = []
    if render_dir.exists():
        for rop_dir in render_dir.iterdir():
            if rop_dir.is_dir():
                found.extend(get_versions(rop_dir))
    return (max(found) + 1) if found else 1
