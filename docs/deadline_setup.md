# Deadline render farm — pipeline integration

How AWS Thinkbox Deadline plugs into this disk + JSON pipeline.

The **full OS-level install record** (MongoDB, Repository, Client, systemd unit, Houdini plugin overrides) lives outside the repo at:

```
~/Documents/deadline-setup/setup-guide.md
```

That guide is the source of truth for "how the workstation got Deadline running." This document is narrower: how the running farm interacts with the pipeline.

---

## Integration model

Deadline does not know about the pipeline. The pipeline does not know about Deadline. They meet on disk through one contract:

> A submitted HIP renders to whatever path its ROP `output_picture` (or equivalent) points to. The pipeline sets those paths before save. The farm honors them.

```
publisher.py / file_manager.py
        │
        │  save HIP at:
        ▼
{projects_root}/{project}/{SEQ}/{SHOT}/FX/work/houdini/{shot}_fx_{task}_v###.hip
        │  ROP output_picture pre-set via pipeline.publish.* helpers
        │
        ▼
"Submit to Deadline" shelf tool  →  Deadline Repository  →  Worker on this box
        │
        │  Worker reads the HIP, renders the ROP,
        │  writes frames to the path baked into the HIP
        ▼
{projects_root}/{project}/{SEQ}/{SHOT}/FX/publish/render/{task}/v###/
        │
        ▼
indexer.rebuild()  →  index.json  →  gallery.html sees the new render
```

**Critical**: Deadline never writes `metadata.json`. The publisher does that after a render is delivered, or `indexer.rebuild()` picks up new files on the next walk. This keeps the disk + JSON contract intact.

---

## Components on this workstation

| Component | Path | Notes |
|---|---|---|
| MongoDB 7.0 | system service `mongod` | Bound to `127.0.0.1`, holds Deadline job state |
| Deadline Repository | `/mnt/deadline/repository/` | Plugins, scripts, jobs/, submitter files |
| Deadline Client | `/opt/Thinkbox/Deadline10/` | `deadlinecommand`, `deadlinemonitor`, `deadlineworker` |
| systemd service | `/etc/systemd/system/deadline10launcher.service` | Boots Launcher → Worker on every startup |
| Worker config | `~/Thinkbox/Deadline10/launcher.ini` | `LaunchSlaveAtStartup=true`, `KeepWorkerRunning=true` |
| Logs | `/var/log/Thinkbox/Deadline10/` | World-readable; `deadlineslave-<host>-<date>-NNNN.log` is the Worker log |
| Houdini plugin override | `/mnt/deadline/repository/custom/plugins/Houdini/` | Adds Houdini 21.0 to a plugin that stock-shipped with H20.5 as the latest |
| Houdini package | `~/houdini21.0/packages/deadline.json` | Wires submitter `PYTHONPATH` + Deadline HDA `HOUDINI_OTLSCAN_PATH` |
| Custom shelf | `~/houdini21.0/toolbar/deadline.shelf` | Defines the Thinkbox shelf (Deadline 10.4 ships no Linux shelf) |

The first six are OS-level (covered in the install guide). The last three are pipeline-adjacent and version-controlled here in spirit, but live in the user's Houdini prefs because Houdini insists.

---

## Path conventions — pipeline ↔ farm

The pipeline's `projects_root` (from `pipeline_config.json`) is the *only* path Deadline jobs care about. Everything inside the HIP is built relative to that root by `pipeline.paths.*`.

| Concern | Value | Why |
|---|---|---|
| `projects_root` | `/home/maxborg/projects/shows` | Set in `pipeline_config.json`. Workers read HIPs and write outputs under this tree. |
| `HOUDINI_TEMP_DIR` | `/mnt/cache/tmp` | Set by `deadline.json` package. Keeps flipbooks/autosaves off `$HOME`. |
| Deadline repo | `/mnt/deadline/repository` | NFS-export target when a second machine joins. |
| PDG working dir | `/mnt/cache/pdg/{hipname}/` | TOPs scheduler temp; identical across all (future) nodes. |

### Single-machine simplification (today)

Both the project tree and the Deadline repo are local directories on the same NVMe. No NFS, no mounts. The `/mnt/...` paths are conventions, not mountpoints — chosen now so they become NFS exports without refactor later.

### Multi-node scaling (future)

When a Linux render node joins:
1. NFS-export `/mnt/deadline/repository` from this workstation.
2. NFS-export the project tree. The cleanest move is to make `/mnt/projects` the real root and update `pipeline_config.json → projects_root`. Until then, NFS-export `/home/maxborg/projects/shows` directly at the same path on the node.
3. Enable Mongo TLS + auth via `deadlinecommand CreateNewCertificates` and rebind to the LAN IP.
4. Install only the Deadline Client on the new node; point it at the mounted repo and LAN Mongo.

Path identity across nodes is non-negotiable. A HIP saved on the workstation must resolve every path the same way on the render node — that's why `projects_root` lives in `pipeline_config.json`, not in env vars per machine.

---

## Workflow — submit a render

1. **Houdini**: open or save a HIP via `file_manager.py` / `publisher.py`. The hip lands at `…/work/houdini/{entity}_fx_{task}_v###.hip`.
2. The pipeline tools set the ROP's output to `…/publish/render/{task}/v###/` (or `publish/cache/...` for sims). Check the ROP node to confirm before submitting.
3. Select the ROP in the network view.
4. **Thinkbox** shelf → **Submit to Deadline**. The submitter dialog opens.
5. Set pool (`houdini`, `sim`, or `render`), frame range, machine limit. Submit.
6. **Thinkbox** shelf → **Open Monitor** to watch progress, or open separately with `deadlinemonitor` from a terminal.
7. When the job completes, the renders are on disk. Run `publisher.py`'s rebuild, or `python -c "from pipeline import indexer; indexer.rebuild()"`, to update `index.json`.
8. `gallery.html` shows the new publish.

---

## Workflow — TOPs/PDG with Deadline

For wedged sims and per-frame parallel cooks:

1. In a TOP Network, drop a **Deadline Scheduler** node (auto-loaded from `Deadline.hda` via the package's `HOUDINI_OTLSCAN_PATH`).
2. Configure:
   - **Deadline Path**: `/opt/Thinkbox/Deadline10/bin`
   - **Working Directory**: `/mnt/cache/pdg/$HIPNAME/$OS`
   - **Local Shared Path** = **Remote Shared Path** = `/mnt/cache/pdg`
   - **Pool**: `sim` (or `houdini` for general work)
3. Set the TOP Network's **Scheduler Override** to the new Deadline scheduler.
4. Cook out-of-process. Wedges appear as separate jobs in the Monitor.

The PDG paths must be identical across all future nodes — `/mnt/cache/pdg` is the planned NFS path. On the single workstation it's just a local directory.

---

## Known integration gaps & TODO

| Item | Status | Fix |
|---|---|---|
| `deadline.json` package sets `JOB=/mnt/projects/$HIPNAME` | wrong root for this pipeline | Either change `projects_root` to `/mnt/projects` or remove the `JOB` env var from the package. Recommend removing — the pipeline's `paths.py` already manages every path; `JOB` is legacy noise. |
| Deadline Limit `gpu0` for ComfyUI co-residency | not yet created | `deadlinecommand -CreateLimitGroup gpu0 1 "Single GPU on workstation" "" ""` — gates Karma XPU / Redshift jobs so they don't fight ComfyUI for the 4070 SUPER's 12 GB VRAM. |
| Pools `houdini`, `sim`, `render` + group `houdini-fx` | not yet created | `deadlinecommand -AddPool` × 3 and `-AddGroup houdini-fx`. Build the structure now even on one Worker so no job-retagging when a node joins. |
| `~/houdini21.0_BACKUP` left over from prior setup | review and clean | Verify no settings need to be salvaged, then remove. |
| Deadline plugin support for Houdini 21 | patched locally via `custom/plugins/Houdini/` | Stock plugin (10.4.1.10) tops out at H20.5. Drop the custom override when Thinkbox ships native H21 support. |

---

## Operational reference

### Verify the farm from inside Houdini

**Thinkbox** shelf → **Check Deadline** — prints version, repo root, registered workers, and confirms `import SubmitHoudiniToDeadline` succeeds. Run this if a submit fails or after any package/env change.

### Verify the farm from the terminal

```bash
systemctl is-active mongod deadline10launcher        # both: active
deadlinecommand GetRepositoryRoot                    # /mnt/deadline/repository
deadlinecommand GetSlaveNames                        # pop-os
mongosh --quiet deadline10db --eval \
  'db.SlaveInfo.findOne({Name:"pop-os"}, {Name:1, Stat:1, _id:0})'
# Stat: 2 = Idle, 1 = Rendering, 8 = Stalled
```

### Worker won't take jobs

1. `tail -40 /var/log/Thinkbox/Deadline10/deadlineslave-pop-os-*.log` — check for plugin errors.
2. In Monitor, right-click the worker → **Modify Worker Properties** → confirm Pools/Groups include the job's pool.
3. If a Houdini job fails with "Could not find Houdini executable" — check `/mnt/deadline/repository/custom/plugins/Houdini/Houdini.param` has the H21 entry and the path points at the real `/opt/hfs21.0.650/bin/hython`.

### Pause Deadline GPU jobs (so ComfyUI gets the GPU)

Once the `gpu0` limit exists:

```bash
deadlinecommand -SetLimitGroupOverage gpu0 -1    # block all jobs tagged with gpu0
deadlinecommand -SetLimitGroupOverage gpu0 0     # re-allow
```

Wire into `comfyui-start.sh` / `comfyui-stop.sh` for automatic toggling.

---

## Why a render farm in a "disk + JSON" pipeline

The pipeline's design tenet was server-less: no database, no daemons, no API server. Deadline does run services (Mongo, Launcher, Worker) — but only for *farm* state (jobs, workers, schedules), never for *project* state. Renders still land on disk; metadata still comes from `publisher.py`; `index.json` is still the only source of truth `gallery.html` reads.

In other words: Deadline is **compute, not state**. The disk + JSON contract is intact.
