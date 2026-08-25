# pipeline — API Reference

All shared logic lives in `python/pipeline/` (package). UI scripts and HDAs
`import pipeline` and call these functions. Never build paths, version numbers,
or metadata outside this package.

The package is split into focused submodules; every public symbol is re-exported
from `pipeline/__init__.py` for backward compatibility.

---

## Submodule map

| Module | Responsibility |
|---|---|
| `config.py` | Load `pipeline_config.json` |
| `entities.py` | projects.json registry |
| `paths.py` | Shot + asset path builders |
| `versioning.py` | Disk-based version scanning |
| `publish.py` | Hip naming + publish path builders |
| `cache.py` | Cache naming + directory creation |
| `ffmpeg.py` | MP4 encoding wrappers |
| `flipbook.py` | Houdini viewport capture |
| `metadata.py` | Publish metadata schema + I/O |
| `validation.py` | Centralised validators |
| `indexer.py` | Project publish index builder |
| `context.py` | Parse current HIP path → Houdini env vars (`$SHOT` etc.) |
| `kimodo/` | Kimodo text-to-motion bridge (subpackage — see below) |

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

### `add_sequence(project_folder: str, seq: str) -> None`
Append a sequence to a project in the registry.

---

## Path builders — shot context

All return `Path` objects.

### `shot_fx_root(project_folder, seq, shot) -> Path`
`{projects_root}/{project}/{SEQ}/{SHOT}/FX/`

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
### `asset_cache_root(project_folder, asset_type, asset, task) -> Path`
### `asset_publish_root(project_folder, asset_type, asset, fmt, task) -> Path`

---

## Versioning

All version numbers come from scanning disk. Never track them in config or state.

### `get_versions(folder: Path) -> list[int]`
Sorted list of `v###` subfolder numbers.

### `get_latest_version(folder: Path) -> int | None`
Highest version, or `None`.

### `get_next_version(folder: Path) -> int`
Next version (`1` if none exist).

### `version_str(n: int) -> str`
`version_str(3)` → `"v003"`.

### `get_next_publish_version(entity_root, task, publish_name) -> int`
Scan `publish/{geo,usd,houdini}/{task}/{pub_name}` and `preview/{task}/{pub_name}`.

### `get_next_render_version(entity_root, task) -> int`
Scan `publish/render/{task}/` across all ROP subdirs.

---

## Hip file naming

### `hip_filename(entity, task, version, descriptor="") -> str`
`{entity}_fx_{task}_v{VER}.hip` or `{entity}_fx_{task}_{descriptor}_v{VER}.hip`.

### `parse_hip_filename(filename) -> dict | None`
Parse `entity`, `task`, `descriptor`, `version`, `version_str`. Returns `None` on no match.

### `find_hip_files(work_houdini: Path) -> list[Path]`
Glob `*_fx_*_v???.hip`, sorted.

### `latest_hip(work_houdini: Path) -> Path | None`
Most recent hip by filename sort.

### `next_hip_path(work_houdini, entity, task, descriptor="") -> Path`
Next versioned hip path for the task+descriptor combination.

---

## Cache file naming

### `cache_filename(entity, task, version, ext) -> str`
Ext: `"bgeo.sc"`, `"vdb"`, `"abc"`.

### `flipbook_filename(entity, version) -> str`
`{entity}_fx_flipbook_v{VER}.$F4.jpg`

### `mp4_filename(entity, task, version) -> str`
`{entity}_fx_{task}_v{VER}.mp4`

---

## Directory creation

### `make_shot_work_dirs(project_folder, seq, shot)`
### `make_asset_work_dirs(project_folder, asset_type, asset)`
### `make_cache_version_dirs(cache_root: Path, version: int) -> dict`
Returns `{"geo": Path, "vdb": Path}`.

### `make_publish_version_dir(publish_root: Path, version: int) -> Path`

---

## ROP / task helpers

### `task_from_rop(rop_name: str) -> str`
Strip `OUT_` prefix and lowercase.

---

## Publisher — path builders

### `entity_root_from_hip(hip_path) -> Path`
Determine entity root (`FX/`) from a hip file at `…/FX/work/houdini/{hip}`.

### `build_publish_path(entity_root, entity, task, publish_name, fmt, version, animated=True) -> Path`
Full published file path. Supported `fmt`: `"usd"`, `"abc"`, `"bgeo"`, `"vdb"`.

### `build_hip_publish_path(entity_root, entity, task, descriptor, version) -> Path`
Hip snapshot publish path under `publish/houdini/`.

### `build_preview_jpg_path(entity_root, entity, task, publish_name, version, animated=True) -> Path`
JPG sequence path under `preview/{task}/{publish_name}/v{VER}/`.

### `build_mp4_path(entity_root, entity, task, publish_name, version) -> Path`
MP4 preview path.

### `build_exr_path(entity_root, entity, task, descriptor, rop_name, version) -> Path`
EXR render path under `publish/render/`.

### `build_usd_cache_path(entity_root, entity, task, descriptor, version) -> Path`
USD cache path.

### `build_standard_output_paths(publish_dir) -> dict[str, str]`
Return the conventional gallery output paths for a versioned publish directory.
Keys: `thumbnail`, `mp4`, `contactsheet`, `metadata`.
These are expected by the gallery; the indexer flags missing ones as warnings.

### `resolve_thumbnail(publish_dir) -> str | None`
Return the best available thumbnail path (`thumbnail.jpg` → `contactsheet.jpg` → first JPG).

### `get_next_publish_version(entity_root, task, publish_name) -> int`
### `hip_snapshot_paths(entity_root, current_hip, task, descriptor, version) -> tuple`
Pure path calculation. Returns `(snapshot_path, next_work_path)`.

### `snapshot_and_increment_hip(entity_root, current_hip_path, task, descriptor, version) -> tuple`
Save + copy snapshot + increment work hip. Requires Houdini.

---

## ffmpeg

### `build_ffmpeg_cmd(image_seq_path, output_mp4, fps) -> list[str]`
### `encode_mp4(jpg_seq_path, output_mp4, fps=None, frame_start=1) -> None`
### `encode_mp4_from_exr(exr_seq_path, output_mp4, fps=None, frame_start=1) -> None`
Tonemap (reinhard) then encode to H.264.

---

## Flipbook

### `flipbook_viewport(jpg_seq_path, frame_range, camera=None, resolution=(1280,720), scene_viewer=None) -> None`
Requires Houdini. Captures viewport frames.

---

## Metadata (Phase 2)

Publish metadata is written as `metadata.json` inside each versioned publish folder.

### Schema (version 2)

```json
{
  "schema_version": 2,
  "uuid": "pub_<12 hex chars>",
  "project": "Reel",
  "context": {
    "type": "shot",
    "sequence": "SQ010",
    "shot": "0010"
  },
  "entity": "SQ010_0010",
  "task": "dust-sim",
  "publish_type": "cache",
  "version": 3,
  "created_at": "2025-01-15T10:30:00Z",
  "created_by": "maxborg",
  "source": {
    "hip": "/path/to/snapshot.hip",
    "houdini_version": "21.0.506",
    "rop": "OUT_dust-sim",
    "git_commit": "abc1234"
  },
  "outputs": {
    "thumbnail": "/path/thumbnail.jpg",
    "mp4": "/path/preview.mp4",
    "frames": "/path/frames.$F4.jpg",
    "usd": "",
    "cache": ""
  },
  "stats": {
    "frame_start": 1,
    "frame_end": 120,
    "disk_mb": 2400.0
  },
  "dependencies": [],
  "tags": [],
  "notes": [],
  "wedge": { "parameter": "density", "value": 0.6 }
}
```

`wedge` is optional and omitted when not relevant.

### `build_metadata(...) -> dict`
Build a structured metadata record. All fields with defaults can be omitted.

| Arg | Type | Required |
|---|---|---|
| `project` | str | yes |
| `context` | dict | yes |
| `entity` | str | yes |
| `task` | str | yes |
| `publish_type` | str | yes |
| `version` | int | yes |
| `source` | dict | no |
| `outputs` | dict | no |
| `stats` | dict | no |
| `dependencies` | list | no |
| `tags` | list | no |
| `notes` | list | no |
| `wedge` | dict | no |

### `write_metadata(publish_dir, metadata: dict) -> Path`
Write `metadata.json`. Creates `publish_dir` if missing.

### `read_metadata(publish_dir) -> dict | None`
Read `metadata.json`. Falls back to legacy `publish_meta.json` and upgrades it.

### `update_metadata_outputs(publish_dir, outputs: dict) -> None`
Merge additional output paths into an existing `metadata.json`.

### `write_publish_metadata(publish_dir, metadata: dict) -> Path`
Backward-compatible shim. Accepts v1 flat dicts and upgrades them to v2 before writing.

---

## Validation (Phase 3)

All validation raises `ValueError` with a clear message on failure.

### `validate_entity_name(name: str) -> str`
Must match `^[A-Za-z0-9][A-Za-z0-9_]*$`. Rejects illegal filesystem chars.

### `validate_task_name(raw: str) -> str`
Normalise (`'Falling Ice'` → `'falling-ice'`) then validate `^[a-z0-9]+(-[a-z0-9]+)*$`.

### `validate_publish_type(publish_type: str) -> str`
Must be one of: `cache`, `flipbook`, `render`, `usd`, `hip`.

### `validate_context(context: dict) -> dict`
Shot context: `type='shot'`, `sequence`, `shot`. Asset: `type='asset'`, `asset_type`, `asset`.

### `validate_version(version) -> int`
Accept `int ≥ 1` or `'v###'` string. Returns integer.

### `validate_publish(publish: dict) -> dict`
Validate a full metadata record — checks all required fields and types.

### `validate_publish_folder(publish_dir) -> Path`
Raise `ValueError` if the directory is missing or has no metadata file.

---

## Indexer (Phase 4)

The indexer scans the filesystem and writes `{project}/.pipeline/publishes.json`.
The gallery consumes this file instead of embedded data.

### `build_project_index(project_folder: str) -> dict`
Scan a project directory. Returns a dict with:
- `project`, `folder`, `indexed_at`, `publish_count`
- `publishes`: list of metadata records, each annotated with `_warnings` and `_orphaned`

### `write_project_index(project_folder: str) -> Path`
Build and write `.pipeline/publishes.json`. Returns the index path.

### `read_project_index(project_folder: str) -> dict | None`
Read the cached index, or `None` if not yet generated.

### `scan_all_projects() -> dict[str, dict]`
Build and write indexes for all registered projects.

---

## Dependency tracking (Phase 7)

All dependency tracking is JSON-only — no database.

A publish's `dependencies` list contains records like:
```json
{ "type": "cache", "publish_uuid": "pub_abc123" }
```

### `get_publish_dependencies(publish_uuid, project_folder) -> list[dict]`
Return the dependency list for a publish UUID from the project index.

### `get_downstream_dependents(publish_uuid, project_folder) -> list[dict]`
Return all publishes that declare this UUID as a dependency.

### `detect_stale_dependencies(publish_uuid, project_folder) -> list[dict]`
Return dependencies that have been superseded by newer versions of the same
entity+task+publish_type. Each stale entry gets `_reason` and optionally
`_latest_version` added.

---

## Wedge support (Phase 8)

Wedge metadata is an optional field on any publish:

```python
pipeline.build_metadata(
    ...,
    wedge={"parameter": "density", "value": 0.6},
)
```

The indexer groups wedges automatically (same entity+task, different wedge values).
The gallery detail panel displays wedge info when present.

---

## Context — HIP path → Houdini variables

A HIP that sits under the pipeline layout already encodes every entity field
in its path. `pipeline.context` parses that path and pushes the fields into
Houdini as environment variables so ROPs and File SOPs can reference
`$SHOT`, `$SEQ`, `$TASK`, etc. instead of hand-typed strings.

Variables applied:

| Var | Source | Notes |
|---|---|---|
| `$PROJECT` | project folder | always set when context resolves |
| `$SEQ` | sequence code | shot context only |
| `$SHOT` | shot code | shot context only |
| `$ASSETTYPE` | asset type | asset context only |
| `$ASSET` | asset name | asset context only |
| `$TASK` | `parse_hip_filename(hip).task` | derived from filename |
| `$VER` | zero-padded version | `"001"`, etc. — use as `v$VER` in paths |

Reserved for a follow-up pass (per-shot `.shot.json`): `$SHOTSTART`,
`$SHOTEND`, `$FPS`, `$SHOTWIDTH`, `$SHOTHEIGHT`. Not set by this module.

### `context_from_hip(hip_path) -> dict | None`
Parse a hip path into `{kind, project, seq, shot, asset_type, asset, task,
version, version_str}`. Returns `None` if the hip is outside `projects_root`,
doesn't sit in `.../FX/work/houdini/`, or has an unparseable filename.
Pure function — no Houdini import — so the parsing logic is unit-testable.

### `apply_to_houdini(ctx: dict | None) -> dict`
Push the context dict into the live Houdini session two ways for every var:
`hou.putenv(NAME, VAL)` (so `hou.getenv` works) **and**
`hou.hscript('set -g NAME = "VAL"')` (so the variable appears in
**Edit → Aliases and Variables**). After applying, runs `hou.hscript("varchange")`
to refresh the Variables window without a manual reopen. Passing `None` clears
every pipeline var so a hip outside the project tree doesn't inherit stale
values from a previous load. Returns the `{var: value}` map that was applied.

### `apply_from_current_hip() -> dict`
Convenience wrapper: reads `hou.hipFile.path()` and applies. Wired into
`houdini/scripts/456.py` (runs on every HIP load) and
`houdini/scripts/123.py` (runs on new scene; clears vars). A shelf tool
`apply_pipeline_vars_launch.py` reapplies on demand and prints the resolved
vars to the status bar.

---

## Kimodo — text-to-motion (`pipeline.kimodo`)

Kimodo (NVIDIA SOMA) runs as an **external process** against its own venv at
`~/Projects/kimodo/.venv`. Nothing in Houdini imports kimodo, torch or
transformers. Full setup notes: [`kimodo_setup.md`](kimodo_setup.md).

Subpackage layout — `job` and `scene` are not re-exported, so `import
pipeline.kimodo` stays safe outside Houdini and outside Qt:

| Module | Responsibility | Imports |
|---|---|---|
| `kimodo/config.py` | Install locations, child-process environment | — |
| `kimodo/clips.py` | Clip library: paths, sidecars, BVH header probing | — |
| `kimodo/runner.py` | Command building + blocking execution | — |
| `kimodo/retarget.py` | SOMA → Mixamo rig map data + validation | — |
| `kimodo/job.py` | QProcess sequencer for the UI | Qt |
| `kimodo/scene.py` | The `/obj/kimodo_import` BVH network | `hou` |

### `config.install_root() -> Path`
Kimodo checkout. `$KIMODO_ROOT` wins over the `kimodo` block of
`pipeline_config.json`. `gen_executable()` / `convert_executable()` /
`venv_bin(name)` resolve inside its venv.

### `config.clips_root() -> Path`
Motion library root. Empty `clips_root` in config →
`{projects_root}/_library/motion/kimodo`.

### `config.child_env(extra=None) -> dict`
Environment for a Kimodo child of Houdini: strips `PYTHONHOME`/`PYTHONPATH`
(Houdini's 3.13 interpreter otherwise breaks the venv's 3.10) and sets
`TEXT_ENCODER_DEVICE=cpu`.

### `config.problems() -> list[str]`
Why Kimodo can't run right now. Empty means ready — the panel calls this on
open and the runner calls it before every launch.

### `runner.gen_command(...)` / `runner.convert_command(...)`
argv builders for `kimodo_gen` and `kimodo_convert`. Generation is two steps so
the NPZ stays the reproducible master and the BVH can be re-exported without
re-generating.

### `runner.run(cmd, on_output=None, timeout=None, check=True) -> int`
Blocking execution with merged stdout/stderr streamed line by line. For hython,
TOPs and tests — **never** Houdini's UI thread. Raises `KimodoError`.

### `runner.generate_clip(prompt, stem, duration, steps, seed, ...) -> Path`
Blocking prompt → BVH: generate NPZ, convert to SOMA BVH, write the sidecar.
Returns the BVH path.

### `clips.unique_stem(name, root=None) -> str`
Free clip stem — appends `_002`, `_003`… rather than overwriting a clip.

### `clips.write_meta(...)` / `clips.read_meta(stem)`
The `{stem}.json` sidecar recording prompt, duration, steps, seed, model and
fps, so a clip can be reproduced.

### `clips.bvh_frame_count / bvh_frame_time / bvh_fps / bvh_joints`
Cheap BVH **header** reads — the motion block is never parsed.

### `scene.import_clip(bvh_path, set_frame_range=True, set_fps=True) -> hou.Node`
Builds or refreshes `/obj/kimodo_import` (`mocap_anim` + `mocap_rest` →
`OUT` / `OUT_REST`) pointing at the clip, and sets the playbar to the clip's
frame count and rate. Returns the `OUT` null.

### `scene.build_retarget(target_skeleton, rig_map="soma_mixamo", ...) -> hou.Node`
Builds `/obj/kimodo_retarget` — the SOMA → Mixamo chain — and returns its
`OUT_RETARGET` null. Self-calibrating: the source size match (leg-length ratio)
and the A-pose → T-pose rotations are solved from the two skeletons in the
scene, not hardcoded. Requires `/obj/kimodo_import` (import a clip first).

### `retarget.load_rig_map(name="soma_mixamo") -> dict`
Reads `config/rig_maps/{name}.json`. `joint_map()` and `fbik_targets()` are the
common accessors; `validate(name, source_joints, target_joints)` returns the
problems with a map — pass the joint names from the live scene to check the map
against the skeletons actually loaded.
