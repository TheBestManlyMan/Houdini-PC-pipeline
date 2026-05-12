# pipeline.py — API Reference

All shared logic lives here. UI scripts and HDAs call these functions only.

---

## Config

### `load_config() -> dict`
Load `pipeline_config.json`. Keys: `projects_root`, `ffmpeg`, `default_fps`, `default_resolution`.

### `projects_root() -> Path`
Return the configured projects root directory.

---

## Project registry

### `load_projects() -> list[dict]`
Return all projects from `projects.json`.

### `get_project(name: str) -> dict | None`
Look up a project by `name` or `folder`. Returns `None` if not found.

### `add_project(name, folder, fps, resolution, sequences, assets) -> dict`
Add a project to the registry. Raises `ValueError` if `folder` already exists.

### `save_projects(projects: list[dict]) -> None`
Overwrite `projects.json` with the given list.

---

## Path builders — shot context

All return `Path` objects. Never call these from UI files directly — use the result via pipeline functions.

### `shot_fx_root(project_folder, seq, shot) -> Path`
`{projects_root}/{project}/sequences/{SEQ}/{SHOT}/FX/`

### `shot_work_houdini(project_folder, seq, shot) -> Path`
`…/FX/work/houdini/`

### `shot_cache_root(project_folder, seq, shot, task) -> Path`
`…/work/houdini/cache/{task}/`

### `shot_publish_root(project_folder, seq, shot, fmt, task) -> Path`
`…/FX/publish/{fmt}/{task}/`

---

## Path builders — asset context

### `asset_fx_root(project_folder, asset_type, asset) -> Path`
`{projects_root}/{project}/assets/{ASSET_TYPE}/{ASSET}/FX/`

### `asset_work_houdini(project_folder, asset_type, asset) -> Path`
`…/FX/work/houdini/`

### `asset_cache_root(project_folder, asset_type, asset, task) -> Path`
`…/work/houdini/cache/{task}/`

### `asset_publish_root(project_folder, asset_type, asset, fmt, task) -> Path`
`…/FX/publish/{fmt}/{task}/`

---

## Versioning

### `get_versions(folder: Path) -> list[int]`
Return sorted list of version numbers found as `v###` subfolders.

### `get_latest_version(folder: Path) -> int | None`
Highest version number, or `None` if folder is empty/missing.

### `get_next_version(folder: Path) -> int`
Next version number. Returns `1` if no versions exist yet.

### `version_str(n: int) -> str`
Zero-padded version string, e.g. `version_str(3)` → `"v003"`.

---

## Hip file naming

### `hip_filename(entity, task, version, descriptor="") -> str`
`{entity}_fx_{task}_v{VER}.hip` — or `{entity}_fx_{task}_{descriptor}_v{VER}.hip` when `descriptor` is non-empty.

### `parse_hip_filename(filename) -> dict | None`
Parse `entity`, `task`, `descriptor`, `version`, `version_str` from a hip filename. Tries 4-part regex first, falls back to 3-part. Old format gets `"descriptor": ""`. Returns `None` on no match.

### `find_hip_files(work_houdini: Path) -> list[Path]`
Glob all `*_fx_*_v???.hip` files, sorted.

### `latest_hip(work_houdini: Path) -> Path | None`
Most recent hip file by filename sort, or `None`.

### `next_hip_path(work_houdini: Path, entity, task, descriptor="") -> Path`
Full path for the next versioned hip for the given task + descriptor combination.

---

## Cache file naming

### `cache_filename(entity, task, version, ext) -> str`
Ext options: `"bgeo.sc"`, `"vdb"`, `"abc"`.
- `bgeo.sc` / `vdb` → includes `.$F4.` frame token
- `abc` → no frame token

### `flipbook_filename(entity, version) -> str`
`{entity}_fx_flipbook_v{VER}.$F4.jpg`

### `mp4_filename(entity, task, version) -> str`
`{entity}_fx_{task}_v{VER}.mp4`

---

## Directory creation

### `make_shot_work_dirs(project_folder, seq, shot)`
Create `work/houdini/` under the shot FX root.

### `make_asset_work_dirs(project_folder, asset_type, asset)`
Create `work/houdini/` under the asset FX root.

### `make_cache_version_dirs(cache_root: Path, version: int) -> dict`
Create `geo/v###` and `vdb/v###` under `cache_root`. Returns `{"geo": Path, "vdb": Path}`.

### `make_publish_version_dir(publish_root: Path, version: int) -> Path`
Create and return `{publish_root}/v###`.

---

## ROP / task helpers

### `task_from_rop(rop_name: str) -> str`
Strip `OUT_` prefix and lowercase. `"OUT_falling-ice"` → `"falling-ice"`.

---

## ffmpeg preview

### `build_ffmpeg_cmd(image_seq_path, output_mp4, fps) -> list[str]`
Build the ffmpeg command list for an image sequence → MP4 encode. Uses config `ffmpeg` path and `default_fps`.

---

## Publisher — path builders

### `entity_root_from_hip(hip_path) -> Path`
Determine entity root from a hip file path. Asset hips (`…/work/houdini/{hip}`) → 3 levels up; shot hips (`…/houdini/{hip}`) → 2 levels up.

### `build_publish_path(entity_root, entity, task, publish_name, fmt, version, animated=True) -> Path`
Full published file path for geo/usd/abc/vdb output. Directory: `{entity_root}/publish/{folder_fmt}/{task}/{publish_name}/v{VER}/`. Raises `ValueError` for unknown `fmt`.

### `build_hip_publish_path(entity_root, entity, task, descriptor, version) -> Path`
Hip snapshot publish path: `{entity_root}/publish/houdini/{task}/{desc}/v{VER}/{entity}_fx_{task}_{desc}_{ver}.hip`. `desc` defaults to `"main"` when `descriptor` is empty.

### `build_preview_jpg_path(entity_root, entity, task, publish_name, version, animated=True) -> Path`
Preview JPG sequence path under `{entity_root}/preview/{task}/{publish_name}/v{VER}/`. Animated filename includes `$F4`; static is a single `.jpg`.

### `build_mp4_path(entity_root, entity, task, publish_name, version) -> Path`
MP4 preview path: `{entity_root}/preview/{task}/{publish_name}/v{VER}/{entity}_fx_{task}_{publish_name}_{ver}.mp4`.

### `get_next_publish_version(entity_root, task, publish_name) -> int`
Scan `publish/{geo,usd,houdini}/{task}/{publish_name}` and `preview/{task}/{publish_name}` for existing `v###` dirs. Returns `max + 1` (or `1` if none found).

### `hip_snapshot_paths(entity_root, current_hip, task, descriptor, version) -> tuple[Path, Path]`
Pure path calculation — no I/O. Returns `(snapshot_path, next_work_path)`. Entity parsed from `current_hip` filename.

### `snapshot_and_increment_hip(entity_root, current_hip_path, task, descriptor, version) -> tuple[Path, Path]`
Save current hip, copy snapshot to `publish/houdini`, save as `version + 1` in work. Requires Houdini. Returns `(snapshot_path, next_work_path)`.

### `write_publish_metadata(publish_dir, metadata: dict) -> Path`
Write `publish_meta.json` in `publish_dir`. Returns the meta file path.

### `encode_mp4(jpg_seq_path, output_mp4, fps=None, frame_start=1) -> None`
Encode a JPG sequence to MP4 via ffmpeg (path from config). Replaces `$F4` → `%04d`. Raises `RuntimeError` on non-zero ffmpeg exit.

### `flipbook_viewport(jpg_seq_path, frame_range, camera=None, resolution=(1280,720), scene_viewer=None) -> None`
Capture viewport frames using `hou.SceneViewer.flipbook()`. Requires Houdini. Finds first SceneViewer if none provided. If `camera` string given, resolves via `hou.node()` and sets viewport camera.
