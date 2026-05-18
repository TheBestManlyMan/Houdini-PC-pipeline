"""
Houdini FX Pipeline — package root.

Backward-compatible re-export of every public symbol from the pipeline submodules.
Existing callers using ``import pipeline; pipeline.some_fn()`` continue to work
without modification.
"""

# Config
from .config import (
    load_config,
    projects_root,
    _CONFIG_PATH,
    _PROJECTS_PATH,
    _PIPELINE_ROOT,
)

# Project registry
from .entities import (
    load_projects,
    get_project,
    save_projects,
    add_project,
    add_sequence,
)

# Path builders — private helpers (used by tests + publisher internals)
from .paths import (
    _shot_fx_root,
    _asset_fx_root,
    _work_houdini,
    _cache_root,
    _publish_root,
    # Public shot context
    shot_fx_root,
    shot_work_houdini,
    shot_cache_root,
    shot_publish_root,
    # Public asset context
    asset_fx_root,
    asset_work_houdini,
    asset_cache_root,
    asset_publish_root,
    # Derived
    entity_root_from_hip,
)

# Versioning
from .versioning import (
    get_versions,
    get_latest_version,
    get_next_version,
    version_str,
    get_next_publish_version,
    get_next_render_version,
)

# Hip file + publish path helpers
from .publish import (
    hip_filename,
    parse_hip_filename,
    find_hip_files,
    latest_hip,
    next_hip_path,
    prepare_hip_version_dir,
    task_from_rop,
    build_publish_path,
    build_hip_publish_path,
    build_preview_jpg_path,
    build_mp4_path,
    build_exr_path,
    build_usd_cache_path,
    hip_snapshot_paths,
    snapshot_and_increment_hip,
    build_standard_output_paths,
    resolve_thumbnail,
)

# Cache + directory creation
from .cache import (
    cache_filename,
    flipbook_filename,
    mp4_filename,
    make_shot_work_dirs,
    make_asset_work_dirs,
    make_cache_version_dirs,
    make_publish_version_dir,
)

# ffmpeg
from .ffmpeg import (
    build_ffmpeg_cmd,
    encode_mp4,
    encode_mp4_from_exr,
)

# Flipbook
from .flipbook import flipbook_viewport

# Metadata (write_publish_metadata kept for backward compat)
from .metadata import (
    build_metadata,
    build_metadata_from_legacy,
    write_metadata,
    read_metadata,
    update_metadata_outputs,
    write_publish_metadata,
)

# Validation
from .validation import (
    validate_entity_name,
    validate_task_name,
    validate_publish_type,
    validate_context,
    validate_version,
    validate_publish,
    validate_publish_folder,
)

# Indexer
from .indexer import (
    build_project_index,
    write_project_index,
    read_project_index,
    scan_all_projects,
    rebuild,
    get_publish_dependencies,
    get_downstream_dependents,
    detect_stale_dependencies,
)


__all__ = [
    # config
    "load_config", "projects_root",
    # entities
    "load_projects", "get_project", "save_projects", "add_project", "add_sequence",
    # paths
    "shot_fx_root", "shot_work_houdini", "shot_cache_root", "shot_publish_root",
    "asset_fx_root", "asset_work_houdini", "asset_cache_root", "asset_publish_root",
    "entity_root_from_hip",
    # versioning
    "get_versions", "get_latest_version", "get_next_version", "version_str",
    "get_next_publish_version", "get_next_render_version",
    # hip + publish
    "hip_filename", "parse_hip_filename", "find_hip_files", "latest_hip",
    "next_hip_path", "prepare_hip_version_dir", "task_from_rop",
    "build_publish_path", "build_hip_publish_path", "build_preview_jpg_path",
    "build_mp4_path", "build_exr_path", "build_usd_cache_path",
    "hip_snapshot_paths", "snapshot_and_increment_hip",
    # cache + dirs
    "cache_filename", "flipbook_filename", "mp4_filename",
    "make_shot_work_dirs", "make_asset_work_dirs",
    "make_cache_version_dirs", "make_publish_version_dir",
    # ffmpeg
    "build_ffmpeg_cmd", "encode_mp4", "encode_mp4_from_exr",
    # flipbook
    "flipbook_viewport",
    # metadata
    "build_metadata", "write_metadata", "read_metadata",
    "update_metadata_outputs", "write_publish_metadata",
    # validation
    "validate_entity_name", "validate_task_name", "validate_publish_type",
    "validate_context", "validate_version", "validate_publish",
    "validate_publish_folder",
    # indexer
    "build_project_index", "write_project_index", "read_project_index",
    "scan_all_projects", "rebuild",
    "get_publish_dependencies", "get_downstream_dependents", "detect_stale_dependencies",

]
