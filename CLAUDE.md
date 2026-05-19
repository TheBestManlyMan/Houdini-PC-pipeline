# Claude Code — Houdini-PC-Pipeline

## What this is

A personal Houdini FX pipeline for managing projects, versioning hip files, writing caches, publishing outputs, and offloading renders/sims to a Deadline render farm. No ShotGrid — disk + JSON for project state, Deadline for compute offload.

## Architecture

The filesystem IS the project database.  Pipeline tools never run a server; Deadline handles compute scheduling only.

```
publisher.py  →  writes deliverable + metadata.json to disk
                 calls pipeline.rebuild() at the end of every publish
indexer.py    →  walks projects_root, collects all metadata.json files,
                 writes a single index.json at projects_root
gallery.html  →  fetch("./index.json"), renders cards,
                 loads MP4s and thumbnails via relative paths
Deadline      →  reads HIPs from work/houdini/, runs ROPs/TOPs on workers,
                 writes outputs to publish/render/ or publish/cache/
                 (single workstation now; ready for Linux render nodes later)
```

Deadline never writes project metadata. Renders land on disk; `publisher.py` (or `indexer.rebuild()`) picks them up the next time it runs — the "disk + JSON" contract is preserved.

Sharing with clients: drag the projects root onto Netlify Drop and paste the URL.  No backend ever.

## Repo structure

```
Houdini-PC-pipeline/
  pipeline_config.json       # Settings: projects_root, ffmpeg path, defaults
  projects.json              # Project list (gitignored — local only)
  projects.json.example      # Template for projects.json
  CLAUDE.md                  # This file
  python/
    pipeline/                # Core package — ALL shared logic lives here
      __init__.py            # Re-exports all public symbols
      config.py              # Load pipeline_config.json
      entities.py            # Project and entity registry
      paths.py               # Path builders (shot + asset contexts)
      versioning.py          # get_next_version, version_str
      publish.py             # Hip, publish, preview path helpers
      cache.py               # Cache filenames + directory creation
      ffmpeg.py              # encode_mp4, encode_mp4_from_exr
      flipbook.py            # flipbook_viewport
      metadata.py            # build_metadata, write_metadata, read_metadata
      validation.py          # validate_* functions
      indexer.py             # Scan publishes → index.json (rebuild())
      context.py             # Parse hip path → $SHOT/$SEQ/$TASK/$VER vars
      naming_conventions.py  # Naming pattern helpers (standalone shim)
    file_manager.py          # PySide6 File Manager dialog
    publisher.py             # PySide6 Publisher dialog
    naming_conventions.py    # Naming helpers (used by publisher.py)
  houdini/
    scripts/                 # Houdini auto-run hooks
      123.py                 # On new scene — clear pipeline vars
      456.py                 # On hip load — apply pipeline vars from hip path
    tool_scripts/            # Shelf tool button scripts
      file_manager_launch.py
      publisher_launch.py
      apply_pipeline_vars_launch.py  # Manual reapply + status message
  docs/
    pipeline_api.md          # pipeline package function reference
    deadline_setup.md        # Deadline render farm integration
  tests/
    test_pipeline.py         # Unit tests for pipeline package
  .gitignore
```

## Opening each tool

| Tool | How to open |
|------|-------------|
| File Manager | Run `file_manager_launch.py` shelf button in Houdini |
| Publisher | Run `publisher_launch.py` shelf button in Houdini |
| Reapply pipeline vars | Run `apply_pipeline_vars_launch.py` shelf button — also auto-fires on every HIP load |
| Submit to Deadline | **Thinkbox** shelf → **Submit to Deadline** (select a ROP first) |
| Deadline Monitor | **Thinkbox** shelf → **Open Monitor**, or run `/opt/Thinkbox/Deadline10/bin/deadlinemonitor` |
| Deadline check | **Thinkbox** shelf → **Check Deadline** — prints connectivity diagnostics to Python Shell |

## Workflow — collaborating with Claude

**Local machine:** `/home/maxborg/projects/Houdini-PC-pipeline/` (Linux Pop_OS!)
**GitHub repo:** `https://github.com/TheBestManlyMan/Houdini-PC-pipeline`

### Direction 1 — Claude makes changes, you pull them down

1. Describe the task in chat.
2. Claude edits files, commits, and pushes to a task branch on GitHub
   (e.g. `claude/some-description`).
3. On your machine, pull the branch and merge into main:

   ```
   git fetch origin
   git checkout main
   git merge origin/<branch-name>
   git push origin main            # sync main back to GitHub
   ```

4. Delete the Claude branch when done (optional):

   ```
   git branch -d <branch-name>
   git push origin --delete <branch-name>
   ```

### Direction 2 — You make changes locally, push to GitHub

1. Edit files on your machine as normal.
2. Commit and push to main (or your own branch):

   ```
   git add <files>
   git commit -m "your message"
   git push origin main
   ```

3. Next Claude session will automatically see your latest changes.

### merge vs squash
- `git merge <branch>` — keeps the full commit history from the Claude branch.
- `git merge --squash <branch> && git commit -m "..."` — collapses it into one clean commit on main.

## Rules — read before writing any code

1. **Check `python/pipeline/` first.** If a function exists for the task, use it. Never duplicate logic. Never build paths inline in other scripts.

2. **The `pipeline` package owns all logic.** UI files (file_manager.py, publisher.py, future tools) are thin — they call pipeline functions and display results. No path building or versioning logic in UI files.

3. **No hardcoded paths.** Always load `projects_root` from `pipeline_config.json`. The package loads config relative to its own location — no absolute paths in code.

4. **Both contexts always.** Every function touching paths must handle:
   - Shot: `{projects_root}/{project}/{SEQ}/{SHOT}/`
   - Asset: `{projects_root}/{project}/assets/{ASSET_TYPE}/{ASSET}/FX/`

5. **Versioning from disk only.** Scan the folder. Never track version numbers in config or state. `get_next_version()` is the single source of truth.

6. **Hip filename is the version source of truth.** Pattern: `{entity}_fx_{task}_v{VER}.hip`

7. **ROP node name = task name.** Strip `OUT_` prefix. No hardcoded task list.

8. **Full file replacement** when more than ~2 spots change in a script.

9. **After editing the pipeline package** — check if `tests/test_pipeline.py` needs updating.

10. **After meaningful API changes** — update `docs/pipeline_api.md`.

11. **No new web gallery surfaces.** The gallery is a single static `gallery.html` that reads `index.json`.  Do not introduce server endpoints, React build steps, or additional HTML files for the gallery.

12. **Deadline reads, never writes project metadata.** A Deadline job's only job is to render or sim — outputs land on disk under `publish/render/{task}/v###/` or `publish/cache/...`. The pipeline picks up new outputs via `indexer.rebuild()` (run automatically by `publisher.py`, or manually). Never write `metadata.json` from inside a job.

13. **ROP output paths set before HIP save.** The ROP's output picture path must point inside `publish/...` before the HIP is saved and submitted. Path building uses `pipeline.publish.*` helpers — never hand-typed paths in a ROP. The render farm renders whatever the HIP says.

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
{projects_root}/{project}/{SEQ}/{SHOT}/FX/
  work/houdini/
    {shot}_fx_{task}_v001.hip
    cache/{task}/geo/v001/
    cache/{task}/vdb/v001/
  publish/render/{task}/v001/
  publish/{fmt}/{task}/v001/
  preview/{task}/...
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
HOUDINI_PIPELINE_ROOT = /home/maxborg/projects/Houdini-PC-pipeline
PYTHONPATH = $HOUDINI_PIPELINE_ROOT/python;&
HOUDINI_PATH = $HOUDINI_PIPELINE_ROOT/houdini;&
```

A separate Houdini package at `~/houdini21.0/packages/deadline.json` wires the Deadline submitter (adds the submitter to `PYTHONPATH` and the Deadline HDA to `HOUDINI_OTLSCAN_PATH`, and a custom shelf at `~/houdini21.0/toolbar/deadline.shelf` registers the Thinkbox tools). The package and `houdini.env` coexist — Houdini merges environment from both. See `docs/deadline_setup.md` for the full integration model.

## Houdini API Reference

See `houdini_api_notes.md` for verified method signatures and gotchas.
Always check this file before writing any `hou.*` call.

## Houdini API — Self-Correction Rule

When any `hou.*` call fails with AttributeError or TypeError:
1. Fix the code.
2. Immediately append the correction to `houdini_api_notes.md` under "What Does NOT Exist":
   Format: `| hou.wrong() | hou.correct() | brief reason |`
3. Do this before moving on — no exceptions.
