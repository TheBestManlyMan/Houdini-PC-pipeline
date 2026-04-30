# Claude Code — Houdini-PC-Pipeline

## What this is

A personal Houdini FX pipeline for managing projects, versioning hip files, writing caches, and publishing outputs. No ShotGrid, no render farm — disk + JSON only.

Launched from: `/home/maxborg/projects/Houdini-PC-Pipeline/`

## Repo structure

```
Houdini-PC-Pipeline/
  pipeline_config.json       # Settings: projects_root, ffmpeg path, defaults
  projects.json              # Project list (gitignored — local only)
  projects.json.example      # Template for projects.json
  CLAUDE.md                  # This file
  python/
    pipeline.py              # Core utility — ALL shared logic lives here
    file_manager.py          # PySide6 File Manager dialog
  houdini/
    otls/                    # Compiled HDAs
    toolbar/                 # Shelf files
  docs/
    pipeline_api.md          # pipeline.py function reference
  tests/
    test_pipeline.py         # Unit tests for pipeline.py
  .gitignore
```

## Rules — read before writing any code

1. **Check `python/pipeline.py` first.** If a function exists for the task, use it. Never duplicate logic. Never build paths inline in other scripts.

2. **`pipeline.py` owns all logic.** UI files (file_manager.py, future tools) are thin — they call pipeline.py functions and display results. No path building or versioning logic in UI files.

3. **No hardcoded paths.** Always load `projects_root` from `pipeline_config.json`. `pipeline.py` loads config relative to its own location — no absolute paths in code.

4. **Both contexts always.** Every function touching paths must handle:
   - Shot: `{projects_root}/{project}/sequences/{SEQ}/{SHOT}/FX/`
   - Asset: `{projects_root}/{project}/assets/{ASSET_TYPE}/{ASSET}/FX/`

5. **Versioning from disk only.** Scan the folder. Never track version numbers in config or state. `get_next_version()` is the single source of truth.

6. **Hip filename is the version source of truth.** Pattern: `{entity}_fx_{task}_v{VER}.hip`

7. **ROP node name = task name.** Strip `OUT_` prefix. No hardcoded task list.

8. **Full file replacement** when more than ~2 spots change in a script.

9. **After editing pipeline.py** — check if `tests/test_pipeline.py` needs updating.

10. **After meaningful API changes** — update `docs/pipeline_api.md`.

## Naming conventions

| File type      | Pattern                               |
|----------------|---------------------------------------|
| Hip file       | `{entity}_fx_{task}_v001.hip`         |
| Cache geo      | `{entity}_fx_{task}_v001.$F4.bgeo.sc` |
| Cache vdb      | `{entity}_fx_{task}_v001.$F4.vdb`     |
| Cache abc      | `{entity}_fx_{task}_v001.abc`         |
| USD publish    | `{entity}_fx_{task}_v001.usd`         |
| Flipbook frame | `{entity}_fx_flipbook_v001.$F4.jpg`   |
| MP4 preview    | `{entity}_fx_{task}_v001.mp4`         |

- Version: always 3-digit zero-padded (`v001`, `v002`…)
- Task: lowercase, hyphen-separated (e.g. `falling-ice`, `dust-sim`)
- Entity: shot code or asset name (e.g. `SQ010_0010`, `hero`)

## Folder layouts

**Shot:**
```
{projects_root}/{project}/sequences/{SEQ}/{SHOT}/FX/
  work/houdini/
    {shot}_fx_{task}_v001.hip
    cache/{task}/geo/v001/
    cache/{task}/vdb/v001/
  publish/render/{task}/v001/
  publish/{fmt}/{task}/v001/
```

**Asset:**
```
{projects_root}/{project}/assets/{ASSET_TYPE}/{ASSET}/FX/
  work/houdini/
    {asset}_fx_{task}_v001.hip
    cache/...
  publish/...
```

## Houdini environment wiring

In `~/houdini21.0/houdini.env`:
```
HOUDINI_PIPELINE_ROOT = /home/maxborg/projects/Houdini-PC-Pipeline
PYTHONPATH = $HOUDINI_PIPELINE_ROOT/python;&
HOUDINI_PATH = $HOUDINI_PIPELINE_ROOT/houdini;&
```
