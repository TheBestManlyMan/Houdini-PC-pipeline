# Houdini FX Pipeline

Personal Houdini FX pipeline for managing projects, versioning hip files, writing caches, and publishing outputs. No ShotGrid, no render farm — disk + JSON only.

## What's in here

```
Houdini-PC-pipeline/
  pipeline_config.json       # projects_root, ffmpeg path, defaults
  projects.json              # Project list (gitignored — local only)
  projects.json.example      # Template for projects.json
  start.sh                   # Start API server + web gallery in one command
  python/
    pipeline/                # Core package — all shared logic lives here
      __init__.py            # Public API re-exports
      config.py              # Config loading
      entities.py            # Project registry
      paths.py               # Path builders (shot + asset)
      versioning.py          # Version scanning
      publish.py             # Hip/publish/preview path helpers
      cache.py               # Cache directory creation
      metadata.py            # publish_meta.json read/write
      indexer.py             # Filesystem scanner → publishes.json
    api_server.py            # FastAPI server for the web gallery
    file_manager.py          # PySide6 file manager (Houdini UI)
    publisher.py             # PySide6 publisher (Houdini UI)
    publish_gallery.py       # Static HTML gallery generator (legacy)
  houdini/
    tool_scripts/            # Shelf tool button scripts
  web/                       # React gallery (Vite)
  docs/
    pipeline_api.md          # Python API reference
  tests/
    test_pipeline.py         # Unit tests
```

## Requirements

- Python 3.10+
- `pip3 install fastapi uvicorn`
- Node.js 18+ (for the web gallery)
- Tailscale (optional — for mobile/remote access)

## Starting the servers

```bash
~/projects/Houdini-PC-pipeline/start.sh
```

This starts:
- **API server** at `http://localhost:8765` — serves live publish data from disk
- **Web gallery** at `http://localhost:5173` — React UI

Press `Ctrl+C` to stop both.

### Access from phone / other devices (Tailscale)

1. Make sure Tailscale is running: `sudo tailscale up`
2. Get your Tailscale IP: `tailscale ip -4` (e.g. `100.107.100.63`)
3. Open on any Tailscale device: `http://100.107.100.63:5173`

Both servers bind to `0.0.0.0` so they're reachable across your Tailscale network.

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /api/projects` | All registered projects |
| `GET /api/publishes` | All publishes, live scan |
| `GET /api/publishes/{folder}` | One project's publishes |
| `GET /api/index/{folder}` | Full index dict for a project |
| `POST /api/reindex` | Rebuild all project indexes |
| `POST /api/reindex/{folder}` | Rebuild one project's index |
| `GET /api/health` | Server health check |

## Adding a project

Edit `projects.json` (copy from `projects.json.example`):

```json
[
  {
    "name": "My Project",
    "folder": "my_project",
    "fps": 24,
    "resolution": "1920x1080",
    "sequences": ["SQ010"],
    "assets": {}
  }
]
```

The `folder` must exist under `projects_root` (set in `pipeline_config.json`).

## Houdini setup

In `~/houdini21.0/houdini.env`:

```
HOUDINI_PIPELINE_ROOT = /home/maxborg/projects/Houdini-PC-pipeline
PYTHONPATH = $HOUDINI_PIPELINE_ROOT/python;&
HOUDINI_PATH = $HOUDINI_PIPELINE_ROOT/houdini;&
```

Shelf tools are in `houdini/tool_scripts/`. The **Gallery Server** shelf tool starts the API + web gallery and opens it in your browser directly from Houdini.

## Running tests

```bash
python3 -m pytest tests/
```
