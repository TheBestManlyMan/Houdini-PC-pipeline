# Troubleshooting

Common problems and their fixes.

---

## Houdini cannot import pipeline

**Symptom:** Shelf tool button throws `ModuleNotFoundError: No module named 'pipeline'`

**Cause:** `PYTHONPATH` is not set correctly in `houdini.env`.

**Fix:**

1. Open `~/houdini21.0/houdini.env`
2. Verify it contains:

```
HOUDINI_PIPELINE_ROOT = /home/yourname/projects/Houdini-PC-pipeline
PYTHONPATH = $HOUDINI_PIPELINE_ROOT/python;&
```

3. The `;` before `&` is required on Linux — it appends to the existing `PYTHONPATH` rather than replacing it.
4. Restart Houdini completely (not just reload shelf).
5. Test in the Houdini Python console: `import pipeline; print(pipeline.projects_root())`

---

## `pipeline_config.json` not found

**Symptom:** `FileNotFoundError` or `KeyError: 'projects_root'` when importing pipeline.

**Cause:** The config file is missing or the working directory is wrong.

**Fix:**

`pipeline_config.json` must exist at the repo root (same directory as `python/`). The package resolves its path relative to `python/pipeline/config.py`, so the working directory does not matter.

Verify:

```bash
ls ~/projects/Houdini-PC-pipeline/pipeline_config.json
```

If missing, create it:

```json
{
  "projects_root": "/home/yourname/projects/shows",
  "ffmpeg": "ffmpeg",
  "default_fps": 24,
  "default_resolution": "1920x1080"
}
```

---

## `projects.json` not found

**Symptom:** `FileNotFoundError: projects.json` or empty project list everywhere.

**Cause:** `projects.json` is gitignored (it is local to your machine). You need to create it.

**Fix:**

```bash
cp ~/projects/Houdini-PC-pipeline/projects.json.example \
   ~/projects/Houdini-PC-pipeline/projects.json
```

Then edit it with your project details. See `docs/configuration.md`.

---

## Indexer finds no publishes

**Symptom:** Gallery shows empty after publishing. `GET /api/publishes` returns `[]`.

**Causes and fixes:**

1. **`metadata.json` not written** — the publish did not complete. Check the Houdini Python console for errors from the Publisher dialog.

2. **`projects_root` wrong** — the API server is looking in the wrong directory. Verify `pipeline_config.json` has the correct `projects_root`.

3. **Project folder does not match** — the `folder` key in `projects.json` must exactly match the directory name under `projects_root`. `"folder": "my-short"` requires `{projects_root}/my-short/` to exist.

4. **Index stale** — the gallery may be showing a cached index. Click **↺** in the toolbar, or: `curl -X POST http://localhost:8765/api/reindex`

5. **Wrong metadata filename** — the indexer looks for files named `metadata.json`. Legacy files named `publish_meta.json` are also scanned and auto-upgraded. If you renamed them to something else, they will be missed.

---

## ffmpeg not found

**Symptom:** Publisher fails with `FileNotFoundError: ffmpeg` or `[Errno 2] No such file or directory: 'ffmpeg'`

**Fix:**

1. Install ffmpeg: `sudo apt install ffmpeg`
2. Verify: `which ffmpeg` → `/usr/bin/ffmpeg`
3. Either set `"ffmpeg": "ffmpeg"` in `pipeline_config.json` (uses `PATH`) or set the full path: `"ffmpeg": "/usr/bin/ffmpeg"`

---

## React gallery cannot connect to API

**Symptom:** Gallery banner says "API unavailable — showing demo data" or shows no publishes despite them existing on disk.

**Causes and fixes:**

1. **API server not running** — `start.sh` must be running. Check: `curl http://localhost:8765/api/health` — should return `{"status": "ok"}`.

2. **Wrong API port** — the gallery defaults to `http://localhost:8765`. If you changed the port in `api_server.py`, set `VITE_API_BASE=http://localhost:<port>/api` before running Vite.

3. **CORS error** — the API has CORS enabled for all origins. If you see CORS errors in the browser console, check that `api_server.py` is not running an old version without `allow_origins=["*"]`.

4. **Firewall blocking port 8765** — check with: `ss -tlnp | grep 8765`. See `docs/remote_access.md` for firewall fix.

---

## Tailscale not reachable

See the full troubleshooting section in `docs/remote_access.md`.

Short checklist:

```bash
tailscale status                      # is the machine connected?
ss -tlnp | grep -E "5173|8765"       # are servers listening on 0.0.0.0?
curl http://localhost:8765/api/health # does the API respond locally?
```

---

## Broken PYTHONPATH inside Houdini

**Symptom:** `import pipeline` works in a terminal but not inside Houdini.

**Cause:** Houdini builds its own Python environment and only extends `PYTHONPATH` from `houdini.env`.

**Fix:**

Check `houdini.env` contains exactly:

```
PYTHONPATH = $HOUDINI_PIPELINE_ROOT/python;&
```

The `;&` means "prepend this path, then append the original PYTHONPATH". Without it, other Houdini Python paths may be lost.

Also verify `HOUDINI_PIPELINE_ROOT` is set in the same file:

```
HOUDINI_PIPELINE_ROOT = /home/yourname/projects/Houdini-PC-pipeline
```

Test inside Houdini Python console:

```python
import sys
[p for p in sys.path if "pipeline" in p]
# should show .../Houdini-PC-pipeline/python
```

---

## Publisher dialog does not open

**Symptom:** Clicking the Publisher shelf button does nothing, or shows a brief flash.

**Cause:** Python error before the dialog is created, or PySide6 not available.

**Fix:**

1. Check the Houdini Python console for a traceback.
2. Verify PySide6 is importable: `import PySide6; print(PySide6.__version__)` in the Houdini console.
3. If PySide6 is missing, Houdini 19.5+ ships with it bundled — you should not need to install it separately. Use the Houdini Python (`hython`) rather than system Python.

---

## Version numbering seems wrong

**Symptom:** Publisher creates `v003` when you expected `v002`.

**Cause:** There are existing version directories on disk that the publisher found.

**Explanation:** Versions are derived by scanning the disk. If `v001/` and `v002/` already exist (from earlier tests, failed publishes, or manual copies), the next version will be `v003`. This is correct behaviour — the disk is authoritative.

To reset: delete or rename the existing version directories, then re-publish.

---

## `metadata.json` has wrong paths after moving the projects folder

**Symptom:** Gallery shows publishes but thumbnails and videos are broken (404 from `/media/...`).

**Cause:** `metadata.json` files contain absolute paths recorded at publish time. Moving `projects_root` makes them invalid.

**Fix:**

1. Update `projects_root` in `pipeline_config.json` to the new location.
2. Rebuild the index: `curl -X POST http://localhost:8765/api/reindex`

The API rewrites absolute paths to `/media/...` URLs at serve time using the current `projects_root`. As long as the relative structure is intact (i.e. you moved the whole folder), paths will resolve correctly after reindexing.

---

## Asset Browser shows stale data

**Symptom:** Asset Browser (in Houdini) shows old entries after new publishes.

**Cause:** The Asset Browser uses a SQLite cache that is not updated automatically.

**Fix:**

In the Asset Browser dialog, click **Rebuild Index**. Or from Python:

```python
import pipeline
db = pipeline.AssetDatabase()
db.rebuild_all()
```

The cache is completely rebuilt from `metadata.json` files on disk.
