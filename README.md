# Houdini FX Pipeline

Personal Houdini FX pipeline for managing projects, versioning hip files, writing caches, and publishing outputs. No ShotGrid, no render farm — disk + JSON only.

## Philosophy

This is intentionally simple:

- **Single-user** — one artist, one machine, one projects folder
- **Filesystem-first** — folders and files are the database
- **JSON metadata** — every publish writes a `metadata.json`; nothing is computed, everything is readable
- **No external dependencies** — no ShotGrid, no FTrack, no render farm, no message queues
- **No ORM or SQL** — the SQLite in `asset_browser.py` is a rebuild-on-demand cache; disk is always canonical
- **Tailscale for remote** — access gallery from any device on your Tailscale network without port-forwarding

Non-goals: multi-user locking, distributed rendering, cloud sync, enterprise auth.

---

## Quick Start

Assumes a fresh Linux machine. Takes about 10 minutes.

### 1. Clone the repo

```bash
git clone https://github.com/TheBestManlyMan/Houdini-PC-pipeline.git ~/projects/Houdini-PC-pipeline
cd ~/projects/Houdini-PC-pipeline
```

### 2. Install Python dependencies

```bash
pip3 install fastapi uvicorn
```

### 3. Install Node dependencies

```bash
cd web && npm install && cd ..
```

### 4. Configure `pipeline_config.json`

Edit the file at the repo root:

```json
{
  "projects_root": "/home/yourname/projects/shows",
  "ffmpeg": "ffmpeg",
  "default_fps": 24,
  "default_resolution": "1920x1080"
}
```

`projects_root` must be an existing directory. `ffmpeg` can be a full path or just `"ffmpeg"` if it is on your `PATH`.

### 5. Create `projects.json`

Copy the example and edit:

```bash
cp projects.json.example projects.json
```

```json
{
  "projects": [
    {
      "name": "My Short",
      "folder": "my-short",
      "fps": 24,
      "resolution": "1920x1080",
      "sequences": ["SQ010"],
      "assets": {
        "character": ["hero"]
      }
    }
  ]
}
```

The `folder` value must exist under `projects_root`:

```bash
mkdir -p /home/yourname/projects/shows/my-short
```

### 6. Wire up Houdini

In `~/houdini21.0/houdini.env` (create if missing):

```
HOUDINI_PIPELINE_ROOT = /home/yourname/projects/Houdini-PC-pipeline
PYTHONPATH = $HOUDINI_PIPELINE_ROOT/python;&
HOUDINI_PATH = $HOUDINI_PIPELINE_ROOT/houdini;&
```

Restart Houdini after editing. The pipeline shelf tools will appear.

### 7. Start the servers

```bash
~/projects/Houdini-PC-pipeline/start.sh
```

This starts:
- **API server** at `http://localhost:8765` — serves live publish data from disk
- **Web gallery** at `http://localhost:5173` — React UI

### 8. Open the gallery

Navigate to `http://localhost:5173` in your browser.

If no publishes exist yet the gallery will show empty. That is expected.

### 9. Publish a test asset

Inside Houdini, click the **Publisher** shelf button. Select a project and shot, choose a ROP, and publish. The gallery will show the result after a browser refresh (or click the ↺ button in the toolbar).

---

## Repo structure

```
Houdini-PC-pipeline/
  pipeline_config.json       # projects_root, ffmpeg path, defaults
  projects.json              # Project list (gitignored — local only)
  projects.json.example      # Template for projects.json
  start.sh                   # Start API server + web gallery in one command
  python/
    pipeline/                # Core package — all shared logic lives here
      __init__.py            # Public API re-exports (import pipeline)
      config.py              # Config loading
      entities.py            # Project registry (projects.json)
      paths.py               # Path builders for shot and asset contexts
      versioning.py          # Disk-based version scanning
      publish.py             # Hip naming + publish/preview path helpers
      cache.py               # Cache dir creation + file naming
      metadata.py            # metadata.json schema v2 read/write
      indexer.py             # Filesystem scanner → publishes.json
      ffmpeg.py              # MP4 encoding via ffmpeg subprocess
      flipbook.py            # Houdini viewport flipbook capture
      validation.py          # Centralised input validation
      publish_schema.py      # PublishProduct dataclass contract
      publish_product.py     # Builds PublishProduct by scanning pub dir
      database.py            # SQLite cache layer (Asset Browser only)
    api_server.py            # FastAPI server (port 8765)
    file_manager.py          # PySide6 file/project/shot navigator
    publisher.py             # PySide6 FX publisher dialog
    asset_browser.py         # PySide6 asset browser (in-Houdini)
    naming_conventions.py    # STANDARD_TASKS list + task slug helpers
  houdini/
    tool_scripts/            # Shelf tool button scripts
  web/                       # React gallery frontend (Vite, port 5173)
  docs/
    pipeline_api.md          # Python API reference
    architecture.md          # System overview and data flow diagrams
    configuration.md         # Full config reference
    workflow.md              # End-to-end artist workflow tutorial
    remote_access.md         # Tailscale remote access setup
    troubleshooting.md       # Common problems and fixes
    development.md           # Engineering conventions
  tests/
    test_pipeline.py         # Unit tests for the pipeline package
  archive/                   # Superseded code (do not use)
```

---

## Requirements

| Component | Version |
|---|---|
| Python | 3.10+ |
| Houdini | 19.5 – 21.5 |
| Node.js | 18+ |
| OS | Linux (developed on Pop!_OS 22.04) |
| Tailscale | Any recent version (optional) |

Python packages: `fastapi`, `uvicorn`  
Node packages: managed by `web/package.json`

---

## Houdini shelf tools

| Tool | What it does |
|---|---|
| **File Manager** | Create and navigate projects, sequences, shots |
| **Publisher** | Export caches, flipbooks, renders; write metadata |
| **Asset Browser** | Browse all published outputs from inside Houdini |
| **Gallery Server** | Start the API + web gallery and open it in your browser |

---

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /api/projects` | All registered projects |
| `GET /api/publishes` | All publishes, live scan |
| `GET /api/publishes/{folder}` | One project's publishes |
| `GET /api/index/{folder}` | Full index dict for a project |
| `POST /api/reindex` | Rebuild all project indexes |
| `POST /api/reindex/{folder}` | Rebuild one project's index |
| `GET /api/assets` | All 3D GLB assets |
| `GET /api/health` | Server health check |
| `GET /media/{path}` | Serve thumbnails, MP4s, GLBs from shows dir |

Example calls:

```bash
curl http://localhost:8765/api/projects
curl http://localhost:8765/api/publishes/my-short
curl http://localhost:8765/api/health
```

Example `/api/health` response:

```json
{"status": "ok"}
```

Example `/api/projects` response:

```json
[
  {
    "name": "My Short",
    "folder": "my-short",
    "fps": 24,
    "resolution": "1920x1080",
    "sequences": ["SQ010"],
    "assets": {"character": ["hero"]}
  }
]
```

---

## Remote access via Tailscale

```bash
sudo tailscale up
tailscale ip -4           # e.g. 100.107.100.63
```

Open `http://100.107.100.63:5173` on any device joined to your Tailscale network.

Both servers bind to `0.0.0.0`, so no extra firewall rules are needed.

See `docs/remote_access.md` for full setup and troubleshooting.

---

## Running tests

```bash
python3 -m pytest tests/
```
