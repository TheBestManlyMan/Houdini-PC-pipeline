# Artist Workflow Tutorial

End-to-end walkthrough of the pipeline for a solo FX artist. Covers a complete cycle from project setup to reviewing results in the gallery.

---

## Prerequisites

- Pipeline installed and configured (see `README.md` Quick Start)
- `start.sh` has been run at least once to verify servers start
- Houdini `houdini.env` is configured and Houdini has been restarted

---

## Step 1 — Create a project

Open Houdini. On the **FX Pipeline** shelf, click **File Manager**.

In the dialog:

1. Click **Add Project**
2. Enter a project name (e.g. `My Short`) and folder (e.g. `my-short`)
3. Click **OK**

The folder `{projects_root}/my-short/` is created on disk. The project is added to `projects.json`.

---

## Step 2 — Create a sequence and shot

Still in File Manager:

1. Select **My Short** in the project list
2. Click **Add Sequence**, enter `SQ010`
3. Click **Add Shot**, select `SQ010`, enter `0010`

This creates the full shot directory tree:

```
{projects_root}/my-short/SQ010/0010/FX/
  work/houdini/
  publish/
  preview/
```

---

## Step 3 — Create and save a hip file

In File Manager, select the shot `SQ010 / 0010` and click **New Hip**. This creates:

```
SQ010_0010_fx_untitled_v001.hip
```

Rename the task in the hip save dialog (e.g. `dust-sim`):

```
SQ010_0010_fx_dust-sim_v001.hip
```

The file is saved to `{projects_root}/my-short/SQ010/0010/FX/work/houdini/`.

> The hip filename is the version source of truth. The version number in the filename determines what `v001` means everywhere else.

---

## Step 4 — Build and cache your sim

Work in Houdini as normal. When ready to write a cache, your output ROP should be named `OUT_dust-sim` (or any `OUT_<task>` pattern). The pipeline strips the `OUT_` prefix to derive the task name.

Cache paths are built by the pipeline. From a shelf script or Python panel:

```python
import pipeline

path = pipeline.make_cache_version_dirs(
    project="my-short",
    seq="SQ010",
    shot="0010",
    task="dust-sim",
    fmt="geo"   # or "vdb"
)
print(path)  # e.g. .../FX/work/houdini/cache/dust-sim/geo/v001/
```

Write your ROP output to this path. The version number is derived from what already exists on disk — no manual tracking.

---

## Step 5 — Publish

Click the **Publisher** shelf button. The dialog opens.

In the Publisher:

1. **Project** — select `My Short`
2. **Context** — `Shot`, then `SQ010 / 0010`
3. **Task** — `dust-sim` (auto-detected from the open hip filename)
4. **Publish type** — `cache`, `flipbook`, `render`, `usd`, or `hip`
5. **ROP** — select `OUT_dust-sim`
6. **Notes** — optional text (stored in `metadata.json`)
7. Click **Publish**

The publisher:
- Increments the publish version by scanning what is already on disk
- Runs the ROP to write output files
- Writes a `metadata.json` alongside the output
- Takes a snapshot of the hip file
- Encodes an MP4 preview if flipbook frames were written

Output lands at:

```
{projects_root}/my-short/SQ010/0010/FX/publish/geo/dust-sim/main/v001/
  metadata.json
  SQ010_0010_fx_dust-sim_v001.0001.bgeo.sc
  SQ010_0010_fx_dust-sim_v001.0002.bgeo.sc
  ...
```

---

## Step 6 — Publish a flipbook

In the Publisher, set publish type to **flipbook**. The publisher:

1. Captures viewport frames using Houdini's flipbook tool
2. Writes JPG frames to `preview/dust-sim/flipbook/v001/`
3. Encodes an MP4 from those frames using ffmpeg
4. Writes `metadata.json` alongside

The MP4 becomes the gallery thumbnail for this publish.

---

## Step 7 — Increment the hip version

After publishing, click **Save & Increment** (or use File Manager → **Increment Hip**). This saves the current scene as `v002.hip` and leaves `v001.hip` as the publish snapshot.

The next publish will automatically create `v002/` directories.

---

## Step 8 — View in the gallery

Start the servers if not running:

```bash
~/projects/Houdini-PC-pipeline/start.sh
```

Open `http://localhost:5173` in your browser.

Your publish appears as a card in the gallery. Click it to open the detail panel showing:
- Preview image / video
- Metadata (version, task, publish type, frame range, disk size)
- Source hip file path
- Notes

To force a refresh of all publish data, click **↺** in the toolbar.

---

## Step 9 — Reindex a project

If you moved or renamed files outside the publisher, or if the gallery is showing stale data, rebuild the project index:

```bash
curl -X POST http://localhost:8765/api/reindex/my-short
```

Or from within Houdini Python:

```python
import pipeline
pipeline.scan_all_projects()
```

The indexer walks the entire project directory, reads every `metadata.json`, and writes a `publishes.json` cache file. The gallery picks this up on the next fetch.

---

## Step 10 — View remotely via Tailscale

```bash
sudo tailscale up
tailscale ip -4   # e.g. 100.107.100.63
```

Open `http://100.107.100.63:5173` on any device on your Tailscale network — laptop, phone, tablet.

The gallery is fully usable in a mobile browser. No native app required.

See `docs/remote_access.md` for full Tailscale setup.

---

## Asset workflow (non-shot)

For assets (characters, props, environments) the workflow is identical except:

1. In File Manager, create an **asset** instead of a shot
   - Asset type: `character`, `environment`, `vehicle`, etc.
   - Asset name: `hero`, `forest`, etc.
2. The directory layout differs:

```
{projects_root}/my-short/assets/character/hero/FX/
  work/houdini/
    hero_fx_groom_v001.hip
  publish/
  preview/
```

3. Everything else (Publisher, gallery, versioning) works identically.

---

## Common task slugs

| Task | Slug |
|------|------|
| Dust simulation | `dust-sim` |
| Smoke simulation | `smoke-sim` |
| Fire simulation | `fire-sim` |
| Destruction | `destruction` |
| Rigid body | `rigid-body` |
| FLIP fluids | `flip-fluids` |
| Ocean | `ocean-sim` |
| Grains | `grains` |
| Cloth | `cloth-sim` |
| Fur | `fur-sim` |

Task slugs must be lowercase, letters and digits, hyphen-separated. The full list is in `python/naming_conventions.py`.
