"""
Launching Kimodo from Houdini — command building and blocking execution.

Kimodo stays an external process: this module builds argv for the venv's
console scripts and runs them with a sanitised environment.  It never imports
kimodo, torch or transformers, and it must not import Qt or hou either — that
keeps it usable from hython, TOPs and plain pytest.

The UI path (non-blocking, QProcess) lives in :mod:`pipeline.kimodo.job` and
reuses the command builders here.

Generation is two steps, so the NPZ stays the reproducible master::

    kimodo_gen  <prompt> --output {stem}          ->  {stem}.npz
    kimodo_convert {stem}.npz {stem}.bvh --bvh_standard_tpose
"""

import subprocess
from pathlib import Path

from . import config


class KimodoError(RuntimeError):
    """Kimodo could not be launched, or exited non-zero."""


def gen_command(prompt: str, output_stem, duration: float = 4.0, steps: int = 30,
                seed=None, num_samples: int = 1, model: str = "",
                bvh: bool = False, standard_tpose: bool = True,
                constraints=None) -> list:
    """argv for ``kimodo_gen``.

    ``output_stem`` is a path without extension; kimodo appends ``.npz`` (and
    ``.bvh`` when ``bvh`` is set).  We normally leave ``bvh`` off and convert in
    a second step so the exported BVH can be re-made without re-generating.

    ``constraints`` is a Kimodo constraints file — hero poses the generated
    motion has to pass through.
    """
    cmd = [
        str(config.gen_executable()),
        str(prompt),
        "--duration", str(float(duration)),
        "--diffusion_steps", str(int(steps)),
        "--output", str(output_stem),
    ]
    if num_samples and int(num_samples) != 1:
        cmd += ["--num_samples", str(int(num_samples))]
    if seed is not None and int(seed) >= 0:
        cmd += ["--seed", str(int(seed))]
    name = model or config.model()
    if name:
        cmd += ["--model", name]
    if constraints:
        # Verified against kimodo_gen --help: --constraints takes a saved
        # constraint list (the JSON pipeline.kimodo.constraints writes).
        cmd += ["--constraints", str(constraints)]
    if bvh:
        cmd += ["--bvh"]
        if standard_tpose:
            cmd += ["--bvh_standard_tpose"]
    return cmd


def convert_command(input_path, output_path, standard_tpose: bool = True,
                    source_fps=None) -> list:
    """argv for ``kimodo_convert`` — NPZ -> SOMA BVH by default."""
    cmd = [
        str(config.convert_executable()),
        str(input_path),
        str(output_path),
    ]
    if standard_tpose:
        cmd += ["--bvh_standard_tpose"]
    if source_fps:
        cmd += ["--source-fps", str(float(source_fps))]
    return cmd


def run(cmd, on_output=None, timeout=None, check: bool = True) -> int:
    """Run a Kimodo command to completion, streaming merged output.

    Blocking — for hython, TOPs and tests.  Houdini's UI must use
    :mod:`pipeline.kimodo.job` instead.  ``on_output`` is called per line.
    Returns the exit code; raises :class:`KimodoError` on failure when
    ``check``.
    """
    problems = config.problems()
    if problems:
        raise KimodoError("; ".join(problems))

    try:
        proc = subprocess.Popen(
            [str(c) for c in cmd],
            cwd=str(config.install_root()),
            env=config.child_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        raise KimodoError("Could not launch %s: %s" % (cmd[0], exc))

    lines = []
    try:
        for line in proc.stdout:
            line = line.rstrip("\n")
            lines.append(line)
            if on_output:
                on_output(line)
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise KimodoError("Timed out after %ss: %s" % (timeout, cmd[0]))
    finally:
        if proc.stdout:
            proc.stdout.close()

    if check and code != 0:
        tail = "\n".join(lines[-15:])
        raise KimodoError("%s exited %s\n%s" % (Path(cmd[0]).name, code, tail))
    return code


def generate_clip(prompt: str, stem: str, duration: float = 4.0, steps: int = 30,
                  seed=None, model: str = "", on_output=None, timeout=None,
                  constraints=None):
    """Blocking prompt -> BVH: generate the NPZ, convert it, write the sidecar.

    Returns the BVH path.  The clip library layout is owned by
    :mod:`pipeline.kimodo.clips`.
    """
    from . import clips

    root = clips.ensure_clips_root()
    npz = clips.npz_path(stem, root)
    bvh = clips.bvh_path(stem, root)

    run(gen_command(prompt, npz.with_suffix(""), duration=duration, steps=steps,
                    seed=seed, model=model, constraints=constraints),
        on_output=on_output, timeout=timeout)
    if not npz.is_file():
        raise KimodoError("kimodo_gen finished but %s was not written" % npz)

    run(convert_command(npz, bvh), on_output=on_output, timeout=timeout)
    if not bvh.is_file():
        raise KimodoError("kimodo_convert finished but %s was not written" % bvh)

    clips.write_meta(stem, prompt, duration, steps, seed=seed, model=model,
                     root=root, frames=clips.bvh_frame_count(bvh),
                     constraints=(Path(constraints).name if constraints else None))
    return bvh
