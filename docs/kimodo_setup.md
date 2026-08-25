# Kimodo — text-to-motion in Houdini 22

Generate motion clips from a text prompt with NVIDIA **Kimodo** (SOMA model),
import them as BVH through KineFX, and build an offline motion library that
Houdini crowd agents reuse.

The end goal is spear-carrying Mixamo soldiers: Kimodo generates the body
motion offline, Houdini retargets it onto one canonical Mixamo skeleton, and a
deterministic spear rig keeps both hands on the shaft. **Kimodo never runs per
crowd agent.**

## The rule that shapes everything

Kimodo is an **external application** with its own Python 3.10 venv at
`~/Projects/kimodo/.venv`. Houdini 22 ships Python 3.13. Nothing kimodo,
torch or transformers is ever installed into, or imported by, Houdini's Python.
The only channel between them is a subprocess.

```
Houdini 22 (py3.13)
    │  QProcess / subprocess, sanitised env
    ▼
~/Projects/kimodo/.venv/bin/kimodo_gen      prompt  -> NPZ
~/Projects/kimodo/.venv/bin/kimodo_convert  NPZ     -> SOMA BVH
    │
    ▼
kinefx::mocapimport  ->  /obj/kimodo_import/OUT (+ OUT_REST)
```

Houdini exports `PYTHONHOME=$HFS/python` into every child process; the venv's
3.10 interpreter dies on import if it inherits it. `pipeline.kimodo.config.child_env()`
strips `PYTHONHOME` and `PYTHONPATH` and pins `TEXT_ENCODER_DEVICE=cpu` — the
Llama-3-8B text encoder stays on the CPU so the 12 GB card keeps room for the
diffusion model.

## Install layout

| Thing | Where |
|---|---|
| Kimodo checkout | `~/Projects/kimodo` (override with `$KIMODO_ROOT`) |
| Venv | `{install_root}/.venv` |
| Model weights | HF cache — `nvidia/Kimodo-SOMA-RP-v1.1` + `meta-llama/Meta-Llama-3-8B-Instruct` |
| Clip library | `{projects_root}/_library/motion/kimodo` |

Settings live in the `kimodo` block of `pipeline_config.json`:

```json
"kimodo": {
  "install_root": "~/Projects/kimodo",
  "venv": ".venv",
  "clips_root": "",          // empty -> {projects_root}/_library/motion/kimodo
  "fps": 30.0,
  "bvh_scale": 0.01,
  "text_encoder_device": "cpu",
  "model": ""                // empty -> kimodo_gen's default model
}
```

Houdini needs the repo on its paths (`~/houdini22.0/houdini.env`):

```
HOUDINI_PIPELINE_ROOT = /home/maxborg/projects/Houdini-PC-pipeline
PYTHONPATH = $HOUDINI_PIPELINE_ROOT/python;&
HOUDINI_PATH = $HOUDINI_PIPELINE_ROOT/houdini;&
```

`HOUDINI_PATH` is what makes `houdini/python_panels/kimodo.pypanel` discoverable
— the panel lives in the repo, not in the version-specific prefs directory.

## Using the panel

**Pane tab → New Pane Tab Type → Kimodo**, or the Python Panel menu.

```
Prompt     A soldier stands alert with a long spear, subtly shifting his weight...
Duration   4.0 s
Steps      30          (diffusion steps — lower is faster, rougher)
Seed       1234        (-1 = random; a fixed seed reproduces a clip)
Clip name  idle_guard_01   (blank = slug of the prompt)
[x] Import into the scene when finished
[ Generate Animation ]  [ Cancel ]
```

Generation runs through `QProcess`, so Houdini stays responsive; subprocess
output streams into the log. A 4 s clip at 30 steps takes roughly 40–60 s,
most of it loading the text encoder.

Each clip writes three files side by side:

```
idle_guard_01.npz    raw Kimodo motion — the reproducible master
idle_guard_01.bvh    SOMA skeleton, standard T-pose rest
idle_guard_01.json   prompt, duration, steps, seed, model, fps, frames
```

Clip names are never overwritten: a second `idle_guard_01` becomes
`idle_guard_01_002`.

## The import network

`scene.import_clip()` builds one predictable network:

```
/obj/kimodo_import
    mocap_anim   kinefx::mocapimport  BioVision, scale 0.01, 30 fps, Output: Animation
    mocap_rest   same file,                                          Output: Rest Pose
    OUT          null <- mocap_anim   (display + render)
    OUT_REST     null <- mocap_rest
```

`OUT_REST` exists because KineFX retargeting needs the **real** SOMA rest pose
(a T-pose) as its source — never frame 1 of the animation. Retarget setups
object-merge `OUT` and `OUT_REST`, so pointing the network at another clip
swaps the motion with nothing else to rewire.

Verified settings: BioVision `.bvh`, scale `0.01` (SOMA BVH is centimetres),
frame rate pinned to the file's own 30 Hz.

## Batch / headless generation

The blocking path takes no Qt and no `hou`, so it works from hython, a TOPs
Python Script or a plain shell:

```python
from pipeline.kimodo import runner, clips

stem = clips.unique_stem("march_spear_01")
bvh = runner.generate_clip(
    "A disciplined infantry soldier marches forward while carrying a long spear in both hands.",
    stem, duration=4.0, steps=30, seed=1234, on_output=print)
```

## Retarget map (Phase 4, in progress)

`config/rig_maps/soma_mixamo.json` holds the SOMA → canonical-Mixamo data.
Both joint lists were read from real skeletons, not guessed. What it records:

- **22 mapped body joints.** Fingers, jaw and eyes are unmapped: SOMA ends
  finger chains with `*End`, Mixamo with `*4`, and the Phase 5 spear rig drives
  the hands anyway.
- **Leaf joints are never mapped.** `kinefx::fbxcharacterimport`'s capture pose
  (52 joints) omits every `*_End` / finger `*4` that the animated branch (66)
  has, and rest matching runs against the capture pose.
- **`Root` is not the locomotion root.** SOMA's `Root` is static; locomotion
  lives on `Hips`.
- **Rest poses differ** — SOMA rests in a T-pose, the Mixamo soldier in an
  A-pose, so Rig Match Pose has real work to do.
- A **sparse** FBIK effector set (11 targets), not every mapped joint.

`retarget.validate(source_joints=..., target_joints=...)` checks the map
against the skeletons actually loaded in the scene.

## The retarget network (Phase 4)

```python
from pipeline.kimodo import scene
scene.build_retarget("/obj/Soldier_Rig/Capture_Pose")   # -> /obj/kimodo_retarget/OUT_RETARGET
```

```
SRC_ANIM ─ SRC_SCALE_ANIM ─┐
                           ├─ SRC_STASH ─────────────────┐  source rest = SOMA T-pose
SRC_REST ─ SRC_SCALE_REST ─┘                             │
                                                         │
TGT_REST ─ MAP ─ TGT_TPOSE_POSE ─ TGT_TPOSE ─────────────┴─ FBIK ─ OUT_RETARGET
```

Nothing in it is hardcoded: the joint pairs come from the rig map, the source
scale is the measured leg-length ratio, and the A-pose → T-pose rotations are
solved off the rig itself (two samples per joint, local X).

**Why the T-pose step exists.** SOMA rests in a T-pose, the Mixamo soldier in an
A-pose (measured: 50.0° down at the shoulder, 45.8° at the elbow). Handing FBIK
the A-pose rest leaves the arms badly off; levelling them into a T-pose first
and stashing that as the target rest fixes it.

Measured on `idle_guard_01`, mean bone-direction error against the source over
5 frames:

| Setup | Mean error | Hands |
|---|---|---|
| A-pose rest (naive) | 17.9° | ~47° |
| **T-posed rest (built)** | **7.3°** | **8–12°** |
| No FBIK offsets | 85.7° | — |

Bone lengths are preserved exactly, feet stay at the rig's own foot height
(0.096–0.100 m against a 0.096 m rest), and the hips follow the source.

Known gap: the upper arms still read ~30° off, because the SOMA and Mixamo
clavicle/shoulder orientations differ. Hands — what the Phase 5 spear grip needs
— are within ~10°, so this is parked rather than solved.

## Hero keyframes -> Kimodo inbetweening

Pose the Mixamo soldier on a few frames, type those frame numbers, and Kimodo
generates the motion between them.

```
Prompt        A disciplined soldier raises his spear...
Guide Frames  1, 12, 26, 40
[ Generate From Guide Frames ]
```

```
Mixamo hero poses -> /obj/kimodo_guide (reverse retarget) -> SOMA poses
  -> {stem}_constraints.json -> kimodo_gen --constraints -> NPZ -> BVH
  -> /obj/kimodo_import -> /obj/kimodo_retarget -> Mixamo
```

The animator types the frames; keyframes are **not** auto-detected (partially
keyed controls and IK channels make that ambiguous). Parsing lives in
`pipeline.kimodo.constraints`, not in the UI: whitespace is ignored, duplicates
collapse, the list is sorted, non-integers and out-of-range frames are
rejected, and at least two distinct frames are required.

**Frame numbers.** Kimodo indices are 0-based from the start of the clip:
`kimodo_frame = houdini_frame - start_frame`. The start frame is the scene's,
not a hardcoded 1. Duration is derived from the Houdini frame range
(`(end - start + 1) / fps`) rather than typed, so it can never stop short of the
last hero pose — `covers_frames()` re-checks that before launching.

**The constraint format** (verified against Kimodo's own
`assets/demo/examples/kimodo-soma-rp/03_full_body_keyframes/constraints.json`
and `FullBodyConstraintSet.from_dict`):

```json
[{"type": "fullbody",
  "frame_indices":    [0, 11, 25, 39],
  "local_joints_rot": [[[ax, ay, az], ... 77 joints], ...],
  "root_positions":   [[x, y, z], ...]}]
```

`local_joints_rot` is axis-angle per joint in `SOMASkeleton77.bone_order_names`
order (recorded in the rig map as `source.model_joints`). `smooth_root_2d` is
optional and omitted, so Kimodo derives it from the root itself.

**Why no torch is needed to author constraints.** A standard-T-pose SOMA BVH's
local rotations *are* Kimodo's `local_rot_mats` — checked against a generated
clip, max difference 3.5e-6 — so the rotations read off the Houdini skeleton go
straight into the file with no rest conversion. The BVH's `Root` wrapper always
carries an identity rotation and is not a model joint; `root_positions` is the
world position of `Hips` in metres.

Kimodo's own reader is the check on our writer:

```bash
~/Projects/kimodo/.venv/bin/python     python/pipeline/kimodo/scripts/verify_constraints.py     {clip}_constraints.json --poses {clip}_guide_poses.json
```

It runs `load_constraints_lst` (which forward-kinematics the stored rotations)
and compares against the joint positions Houdini recorded.

**Files per guided clip** — the NPZ stays the master:

```
{stem}.npz  {stem}.bvh  {stem}.json  {stem}_constraints.json  {stem}_guide_poses.json
```

The sidecar records prompt, seed, steps, fps, the Houdini frame range, the guide
frames, their Kimodo indices, the source skeleton and the constraints filename.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Panel says "Kimodo not available" | `config.problems()` — install or venv executables missing |
| Child process dies on import | `PYTHONHOME` leaked in; check `config.child_env()` is used |
| CUDA OOM during generation | text encoder landed on the GPU — `TEXT_ENCODER_DEVICE` must be `cpu` |
| Skeleton imports 100× too big | `scale` isn't `0.01`; SOMA BVH is centimetres |
| Retarget explodes | source rest taken from frame 1 instead of `OUT_REST` |
