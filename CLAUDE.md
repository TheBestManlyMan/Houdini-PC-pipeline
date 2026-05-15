# Claude Code — Houdini-PC-Pipeline

## What this is

A personal Houdini FX pipeline for managing projects, versioning hip files, writing caches, and publishing outputs. No ShotGrid, no render farm — disk + JSON only.

## Repo structure

```
Houdini-PC-pipeline/
  pipeline_config.json       # Settings: projects_root, ffmpeg path, defaults
  projects.json              # Project list (gitignored — local only)
  projects.json.example      # Template for projects.json
  server.py                  # FastAPI server — REST API for pipeline management
  pipeline_manager.html      # Standalone web UI (open directly in browser)
  requirements.txt           # Python dependencies (fastapi, uvicorn)
  CLAUDE.md                  # This file
  python/
    pipeline/                # Core pipeline package — ALL shared logic lives here
    file_manager.py          # PySide6 File Manager dialog
  houdini/
    tool_scripts/            # Shelf tool button scripts
  docs/
    pipeline_api.md          # pipeline.py function reference
  tests/
    test_pipeline.py         # Unit tests for pipeline.py
  .gitignore
```

## Dependencies

Install with:

```bash
pip install -r requirements.txt
```

| Package | Purpose |
|---------|---------|
| `fastapi` | REST API framework for `server.py` |
| `uvicorn[standard]` | ASGI server that runs FastAPI inside Houdini via threading |

These are only needed to run `server.py`. The rest of the pipeline (publisher, file manager, etc.) has no extra dependencies beyond what Houdini ships with.

## Pipeline Manager Server

A local FastAPI server that exposes a REST API for managing projects, sequences, shots, and assets via a browser-based UI.

**Port:** `http://127.0.0.1:8765`

**How to start (from Houdini):**
Run the **Pipeline Manager** shelf tool — script at `houdini/tool_scripts/pipeline_manager_launch.py`.
It starts the server in a background daemon thread and opens the browser automatically.
Running the tool again while the server is already up just re-opens the browser tab.

**How to start (standalone, outside Houdini):**
```bash
python server.py
```

**Web UI:**
`pipeline_manager.html` — a single-file standalone React app. Open it directly in a browser (no build step). It talks to the API at `http://127.0.0.1:8765/api`.

**API routes (all prefixed `/api`):**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects` | List all projects |
| POST | `/projects` | Create project |
| DELETE | `/projects/{folder}` | Delete project (optional `?delete_files=true`) |
| GET | `/projects/{folder}/sequences` | List sequences |
| POST | `/projects/{folder}/sequences` | Add sequence |
| DELETE | `/projects/{folder}/sequences/{seq}` | Delete sequence |
| GET | `/projects/{folder}/sequences/{seq}/shots` | List shots |
| POST | `/projects/{folder}/sequences/{seq}/shots` | Create shot (makes work dirs) |
| DELETE | `/projects/{folder}/sequences/{seq}/shots/{shot}` | Delete shot |
| GET | `/projects/{folder}/assets` | List assets grouped by type |
| POST | `/projects/{folder}/asset-types` | Create asset type directory |
| DELETE | `/projects/{folder}/asset-types/{asset_type}` | Delete asset type |
| POST | `/projects/{folder}/assets/{asset_type}` | Create asset (makes work dirs) |
| DELETE | `/projects/{folder}/assets/{asset_type}/{asset}` | Delete asset |
| GET | `/publishes` | List publishes (optional `?project=name`) |
| POST | `/publishes/rebuild` | Rebuild publish index |

**Note:** `pipeline_web/dist/` does not exist (no React build step). The server's static file mount is guarded by an `if _WEB_DIST.exists()` check, so the server starts cleanly without it. Use `pipeline_manager.html` instead.

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

1. **Check `python/pipeline.py` first.** If a function exists for the task, use it. Never duplicate logic. Never build paths inline in other scripts.

2. **`pipeline.py` owns all logic.** UI files (file_manager.py, future tools) are thin — they call pipeline.py functions and display results. No path building or versioning logic in UI files.

3. **No hardcoded paths.** Always load `projects_root` from `pipeline_config.json`. `pipeline.py` loads config relative to its own location — no absolute paths in code.

4. **Both contexts always.** Every function touching paths must handle:
   - Shot: `{projects_root}/{project}/{SEQ}/{SHOT}/`
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

## Houdini API Reference

See `houdini_api_notes.md` for verified method signatures and gotchas.
Always check this file before writing any `hou.*` call.

## Houdini API — Self-Correction Rule

When any `hou.*` call fails with AttributeError or TypeError:
1. Fix the code.
2. Immediately append the correction to `houdini_api_notes.md` under "What Does NOT Exist":
   Format: `| hou.wrong() | hou.correct() | brief reason |`
3. Do this before moving on — no exceptions.
