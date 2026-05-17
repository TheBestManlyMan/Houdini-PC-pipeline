# Claude Code — Houdini-PC-Pipeline

## What this is

A personal Houdini FX pipeline for managing projects, versioning hip files, writing caches, and publishing outputs. No ShotGrid, no render farm — disk + JSON only.

## Repo structure

```
Houdini-PC-pipeline/
  pipeline_config.json       # Settings: projects_root, ffmpeg path, defaults
  projects.json              # Project list (gitignored — local only)
  projects.json.example      # Template for projects.json
  start.sh                   # Start API server + web gallery
  CLAUDE.md                  # This file
  README.md                  # Setup and usage docs
  python/
    pipeline/                # Core package — ALL shared logic lives here
      __init__.py            # Public API re-exports
      config.py              # Config loading
      entities.py            # Project registry
      paths.py               # Path builders (shot + asset)
      versioning.py          # Version scanning
      publish.py             # Hip/publish/preview path helpers
      cache.py               # Cache directory creation
      metadata.py            # metadata.json read/write (schema v2)
      indexer.py             # Filesystem scanner → publishes.json
      ffmpeg.py              # MP4 encoding wrappers
      flipbook.py            # Houdini viewport capture
      validation.py          # Centralised input validators
      publish_schema.py      # PublishProduct dataclass contract
      publish_product.py     # Builds PublishProduct by scanning publish dir
      database.py            # SQLite cache (Asset Browser only — disk is canonical)
    api_server.py            # FastAPI server (port 8765) for web gallery
    file_manager.py          # PySide6 File Manager dialog
    publisher.py             # PySide6 Publisher dialog
    asset_browser.py         # PySide6 Asset Browser (in-Houdini only)
    naming_conventions.py    # STANDARD_TASKS list + task slug helpers
  houdini/
    tool_scripts/            # Shelf tool button scripts
  web/                       # React gallery frontend (Vite, port 5173)
  docs/
    pipeline_api.md          # python/pipeline/ function reference
    architecture.md          # System overview and data flow diagrams
    configuration.md         # Full config file reference
    workflow.md              # End-to-end artist workflow tutorial
    remote_access.md         # Tailscale setup and troubleshooting
    troubleshooting.md       # Common problems and fixes
    development.md           # Engineering conventions
  tests/
    test_pipeline.py         # Unit tests for the pipeline package
  archive/                   # Superseded code preserved for reference (do not use)
  .gitignore
```

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

1. **Check `python/pipeline/` first.** If a function exists for the task, use it. Never duplicate logic. Never build paths inline in other scripts. Import via `import pipeline` or `from pipeline import ...`.

2. **`python/pipeline/` owns all logic.** UI files (`file_manager.py`, `publisher.py`, `asset_browser.py`, tool scripts) are thin — they call pipeline functions and display results. No path building or versioning logic in UI files.

3. **No hardcoded paths.** Always load `projects_root` from `pipeline_config.json`. The package loads config relative to its own location — no absolute paths in code.

4. **Both contexts always.** Every function touching paths must handle:
   - Shot: `{projects_root}/{project}/{SEQ}/{SHOT}/`
   - Asset: `{projects_root}/{project}/assets/{ASSET_TYPE}/{ASSET}/FX/`

5. **Versioning from disk only.** Scan the folder. Never track version numbers in config or state. `get_next_version()` is the single source of truth.

6. **Hip filename is the version source of truth.** Pattern: `{entity}_fx_{task}_v{VER}.hip`

7. **ROP node name = task name.** Strip `OUT_` prefix. No hardcoded task list.

8. **Full file replacement** when more than ~2 spots change in a script.

9. **After editing `python/pipeline/`** — check if `tests/test_pipeline.py` needs updating.

10. **After meaningful API changes** — update `docs/pipeline_api.md`.

11. **Web gallery backend** lives in `python/api_server.py` (FastAPI, port 8765). Frontend lives in `web/` (React/Vite, port 5173). Start both with `start.sh`.

12. **No new surfaces in the web app.** The gallery has three surfaces: Gallery, 3D Assets, Manager. Do not add more.

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
  publish/
    {fmt}/          # geo | usd | render | houdini
      {task}/
        {publish_name}/
          v001/     ← metadata.json + output files written here
  preview/          # one level shallower than publish/
    {task}/
      {publish_name}/   # e.g. "flipbook"
        v001/       ← metadata.json + mp4 + jpg frames written here
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

## Houdini API Reference

See `houdini_api_notes.md` for verified method signatures and gotchas.
Always check this file before writing any `hou.*` call.

## Houdini API — Self-Correction Rule

When any `hou.*` call fails with AttributeError or TypeError:
1. Fix the code.
2. Immediately append the correction to `houdini_api_notes.md` under "What Does NOT Exist":
   Format: `| hou.wrong() | hou.correct() | brief reason |`
3. Do this before moving on — no exceptions.
