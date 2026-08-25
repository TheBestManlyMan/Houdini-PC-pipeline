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

## Troubleshooting

| Symptom | Cause |
|---|---|
| Panel says "Kimodo not available" | `config.problems()` — install or venv executables missing |
| Child process dies on import | `PYTHONHOME` leaked in; check `config.child_env()` is used |
| CUDA OOM during generation | text encoder landed on the GPU — `TEXT_ENCODER_DEVICE` must be `cpu` |
| Skeleton imports 100× too big | `scale` isn't `0.01`; SOMA BVH is centimetres |
| Retarget explodes | source rest taken from frame 1 instead of `OUT_REST` |
