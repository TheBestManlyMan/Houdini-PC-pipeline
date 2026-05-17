# Configuration Reference

Two JSON files configure the pipeline. Both live at the repo root.

---

## `pipeline_config.json`

Machine-level settings. Checked into git. **Do not put personal paths here** — use `projects_root` as the only machine-specific value and keep the rest as defaults.

```json
{
  "projects_root": "/home/maxborg/projects/shows",
  "ffmpeg": "ffmpeg",
  "default_fps": 24,
  "default_resolution": "1920x1080"
}
```

### Keys

| Key | Required | Type | Description |
|-----|----------|------|-------------|
| `projects_root` | yes | string | Absolute path to the root directory containing all project folders. Must already exist on disk. |
| `ffmpeg` | yes | string | Path to the `ffmpeg` binary, or just `"ffmpeg"` if it is on your `PATH`. Used for MP4 preview encoding. |
| `default_fps` | no | integer | Frame rate used when creating new projects via File Manager. Default: `24`. |
| `default_resolution` | no | string | Resolution string used when creating new projects. Default: `"1920x1080"`. |

### Notes

- The file is read once at import time by `python/pipeline/config.py`.
- `projects_root` is resolved to an absolute path. Relative paths are not supported.
- `ffmpeg` accepts a bare name (`"ffmpeg"`) or full path (`"/usr/local/bin/ffmpeg"`). Verify with `which ffmpeg` before using a bare name.

---

## `projects.json`

Project registry. **Gitignored** — this file is local to your machine and is not committed to the repo.

```json
{
  "projects": [
    {
      "name": "My Short",
      "folder": "my-short",
      "fps": 24,
      "resolution": "1920x1080",
      "sequences": ["SQ010", "SQ020"],
      "assets": {
        "character": ["hero", "villain"],
        "environment": ["forest"],
        "vehicle": []
      }
    }
  ]
}
```

### Top-level structure

| Key | Required | Type | Description |
|-----|----------|------|-------------|
| `projects` | yes | array | List of project objects. |

### Project object

| Key | Required | Type | Description |
|-----|----------|------|-------------|
| `name` | yes | string | Human-readable project name. Shown in the gallery and file manager. |
| `folder` | yes | string | Folder name under `projects_root`. Must exist on disk: `{projects_root}/{folder}/`. Lowercase, hyphen-separated recommended. |
| `fps` | no | integer | Project frame rate. Used as default when creating new hip files. Default: value of `default_fps` from `pipeline_config.json`. |
| `resolution` | no | string | Project resolution (`"WxH"`). Default: value of `default_resolution` from `pipeline_config.json`. |
| `sequences` | no | array of strings | Sequence codes (e.g. `["SQ010", "SQ020"]`). Adding a code here does not create the folder — use the File Manager for that. |
| `assets` | no | object | Asset registry. Keys are asset type names (e.g. `"character"`, `"environment"`), values are arrays of asset names. |

### Setting up `projects.json`

Copy the example:

```bash
cp projects.json.example projects.json
```

Then edit for your project. Create the project directory before running the pipeline:

```bash
mkdir -p /path/to/projects_root/my-project
```

### Multiple projects

```json
{
  "projects": [
    {
      "name": "My Short",
      "folder": "my-short",
      "fps": 24,
      "resolution": "1920x1080",
      "sequences": ["SQ010"],
      "assets": {}
    },
    {
      "name": "Commercial",
      "folder": "commercial-2026",
      "fps": 25,
      "resolution": "3840x2160",
      "sequences": ["SQ010", "SQ020", "SQ030"],
      "assets": {
        "character": ["product"],
        "environment": ["studio"]
      }
    }
  ]
}
```

### Stale projects

If a project folder is deleted or moved, the registry entry becomes stale. `load_projects()` silently skips projects whose folder does not exist on disk (default behaviour). To see the raw list including stale entries: `pipeline.load_projects(filter_missing=False)`.

---

## Environment variables

These are optional and only needed if you want to override the gallery's API endpoint (e.g. for a non-localhost setup).

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE` | `http://localhost:8765/api` | API base URL used by the React frontend. Set before `npm run dev` or in `web/.env`. |
| `VITE_INDEX_BASE` | _(unset)_ | Optional fallback URL for a static `publishes.json` index. Used when the API is unreachable. |

### Houdini environment variables

Set in `~/houdini21.0/houdini.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `HOUDINI_PIPELINE_ROOT` | yes | Absolute path to the repo root. All shelf tool scripts derive their Python import path from this. |
| `PYTHONPATH` | yes | Must include `$HOUDINI_PIPELINE_ROOT/python` so `import pipeline` resolves correctly inside Houdini. |
| `HOUDINI_PATH` | yes | Must include `$HOUDINI_PIPELINE_ROOT/houdini` so Houdini finds the shelf and tool scripts. |
