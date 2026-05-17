# Architecture Overview

This document explains the system boundaries, data flow, and design decisions of the pipeline.

---

## Core principle

The filesystem is the database. Every publish is a versioned directory containing output files and a `metadata.json`. Everything the gallery and API serve is derived from reading those files. Nothing is computed from an external state store.

```
disk
  metadata.json          ← the record
  output files           ← the data
  publishes.json         ← the cache (rebuild-on-demand from metadata.json files)
```

---

## System map

```
┌─────────────────────────────────────┐
│  Houdini                            │
│                                     │
│  File Manager  ──►  projects.json   │
│  Publisher     ──►  disk            │
│  Asset Browser ◄──  SQLite cache    │
└──────────┬──────────────────────────┘
           │  writes
           ▼
┌──────────────────────────────────────┐
│  Filesystem (projects_root/)         │
│                                      │
│  my-short/                           │
│    SQ010/0010/FX/                    │
│      work/houdini/*.hip              │
│      publish/geo/dust-sim/main/v001/ │
│        metadata.json                 │
│        *.bgeo.sc                     │
│      preview/dust-sim/flipbook/v001/ │
│        metadata.json                 │
│        *.jpg  *.mp4                  │
│    publishes.json  ◄─── indexer      │
└──────────┬───────────────────────────┘
           │  reads
           ▼
┌──────────────────────┐
│  FastAPI server      │
│  port 8765           │
│                      │
│  /api/publishes      │
│  /api/projects       │
│  /api/reindex        │
│  /media/{path}       │
└──────────┬───────────┘
           │  HTTP
           ▼
┌──────────────────────┐
│  React gallery       │
│  port 5173           │
│                      │
│  Gallery surface     │
│  3D Assets surface   │
│  Manager surface     │
└──────────────────────┘
           │
           │  Tailscale
           ▼
┌──────────────────────┐
│  Remote devices      │
│  (any browser)       │
└──────────────────────┘
```

---

## Publish flow

When the artist clicks **Publish** in the Publisher dialog:

```
1. Publisher dialog
   │  collect: project, context, task, ROP, notes, publish type
   ▼
2. pipeline.get_next_publish_version()
   │  scans publish dir on disk → next version number
   ▼
3. pipeline.make_publish_version_dir()
   │  creates versioned output directory
   ▼
4. ROP cook (Houdini renders to the output dir)
   ▼
5. pipeline.snapshot_and_increment_hip()
   │  copies current hip as publish snapshot, saves new version
   ▼
6. pipeline.encode_mp4() / flipbook_viewport()  [if flipbook or render]
   │  ffmpeg encodes MP4 preview
   ▼
7. pipeline.build_metadata()  →  pipeline.write_metadata()
   │  constructs metadata.json and writes it alongside outputs
   ▼
8. Filesystem:  publish/geo/dust-sim/main/v001/
                  metadata.json
                  SQ010_0010_fx_dust-sim_v001.0001.bgeo.sc
                  ...
```

---

## Indexing flow

The indexer converts the raw filesystem into a structured index the API can serve efficiently:

```
1. scan_all_projects()  or  POST /api/reindex
   │
   ▼
2. Walk {projects_root}/{project}/
   │  find every directory containing metadata.json
   ▼
3. read_metadata() for each publish dir
   │  upgrade v1 → v2 schema transparently
   ▼
4. write_project_index()
   │  writes {projects_root}/{project}/publishes.json
   ▼
5. FastAPI reads publishes.json on next request
   │  (or live-scans if publishes.json is absent)
   ▼
6. React gallery displays results
```

The index is a cache. Deleting `publishes.json` and calling `/api/reindex` fully rebuilds it.

---

## API → gallery flow

```
React gallery
   │
   │  on mount: fetch /api/publishes
   │
   ▼
FastAPI /api/publishes
   │
   │  reads publishes.json (cached) or scans disk (live)
   │  rewrites absolute file paths → /media/... URLs
   │
   ▼
React receives publish list
   │
   │  renders PublishCard grid
   │  on card click: opens DetailPanel
   │
   ▼
DetailPanel
   │  shows thumbnail: <img src="/media/...">
   │  shows video:     <video src="/media/...">
   │  FastAPI serves the file via GET /media/{path}
```

---

## Package layer map

```
python/pipeline/           ← business logic (no Houdini, no UI, no HTTP)
  config.py                  load pipeline_config.json
  entities.py                projects.json CRUD
  paths.py                   path builders (shot + asset contexts)
  versioning.py              disk-based version scanning
  publish.py                 hip naming + publish path construction
  cache.py                   cache dir creation + file naming
  metadata.py                metadata.json schema v2 I/O
  indexer.py                 filesystem scanner → publishes.json
  ffmpeg.py                  ffmpeg subprocess wrappers
  flipbook.py                Houdini viewport capture (hou.* calls here only)
  validation.py              centralised input validators
  publish_schema.py          PublishProduct dataclass (data contract)
  publish_product.py         builds PublishProduct by scanning pub dir
  database.py                SQLite cache (Asset Browser only)

python/                    ← thin UI + service layers (import pipeline, no logic)
  api_server.py              FastAPI routes + media serving
  publisher.py               PySide6 Publisher dialog
  file_manager.py            PySide6 File Manager dialog
  asset_browser.py           PySide6 Asset Browser (in-Houdini)
  naming_conventions.py      STANDARD_TASKS list + task slug formatting

houdini/tool_scripts/      ← one-liner shelf buttons (import + show())
web/                       ← React frontend (fetches API, no pipeline imports)
```

The rule: only `python/pipeline/` knows about the filesystem layout and naming conventions. Everything else calls it.

---

## Metadata schema

Every publish directory contains a `metadata.json` at schema version 2:

```json
{
  "schema_version": 2,
  "uuid": "pub_abc123",
  "project": "my-short",
  "context": {
    "type": "shot",
    "sequence": "SQ010",
    "shot": "0010"
  },
  "entity": "SQ010_0010",
  "task": "dust-sim",
  "publish_type": "cache",
  "version": 1,
  "created_at": "2026-05-17T14:30:00Z",
  "created_by": "maxborg",
  "source": {
    "hip": "/path/to/snapshot.hip",
    "houdini_version": "21.0.1234",
    "rop": "OUT_dust-sim",
    "git_commit": "abc1234"
  },
  "outputs": {
    "thumbnail": "/path/to/thumb.jpg",
    "mp4": "/path/to/preview.mp4",
    "frames": "",
    "usd": "",
    "cache": ""
  },
  "stats": {
    "frame_start": 1,
    "frame_end": 240,
    "disk_mb": 125.5
  },
  "dependencies": [],
  "tags": [],
  "notes": []
}
```

Legacy `publish_meta.json` (schema v1) is auto-upgraded to v2 on read via `build_metadata_from_legacy()`. No migration scripts needed.

---

## Version numbering

Versions are always derived from the filesystem. The pipeline never stores "current version" in config or state.

```
get_next_version(path)
  → lists directory
  → finds highest v### folder or file
  → returns that number + 1
```

This means version numbers are correct even if you manually move, copy, or delete version folders. The disk is always authoritative.

---

## SQLite cache (Asset Browser)

`python/pipeline/database.py` maintains a SQLite file at `.pipeline/asset_browser.db`. This is a pure read cache populated by reading `publishes.json` files. It exists only to make the in-Houdini Asset Browser fast to filter and search.

**Disk is always canonical.** Delete `asset_browser.db` and call `AssetDatabase().rebuild_all()` to rebuild it from scratch. The gallery and API do not use this database.

---

## Tailscale topology

```
Your machine (Linux)
  ├── Houdini
  ├── FastAPI  :8765   (binds 0.0.0.0)
  ├── Vite     :5173   (binds 0.0.0.0)
  └── Tailscale daemon

Tailscale network (100.x.x.x)
  ├── Your machine    100.107.100.63
  ├── Laptop          100.x.x.x
  └── Phone           100.x.x.x

Phone browser → http://100.107.100.63:5173  → Vite dev server
                http://100.107.100.63:8765  → FastAPI
```

No port forwarding on your router is needed. Tailscale handles the encrypted peer-to-peer connection.
