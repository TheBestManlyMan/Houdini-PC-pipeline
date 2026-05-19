"""
Pipeline context — parse the current HIP path into entity context and apply
the result as Houdini environment variables.

Variables exposed in Houdini:
    $PROJECT    project folder       (e.g. "drone")
    $SEQ        sequence code        (shot context only)
    $SHOT       shot code            (shot context only)
    $ASSETTYPE  asset type           (asset context only)
    $ASSET      asset name           (asset context only)
    $TASK       task name            (parsed from hip filename)
    $VER        zero-padded version  (e.g. "001" — use as `v$VER`)

Frame-range / fps / resolution variables ($SHOTSTART, $SHOTEND, $FPS,
$SHOTWIDTH, $SHOTHEIGHT) are reserved for a later pass that reads a per-shot
.shot.json file. This module only handles vars derivable from the HIP path.

When the HIP isn't under projects_root or doesn't follow the layout, the
pipeline vars are cleared so artists don't pick up stale values from a
previous session.
"""

from pathlib import Path
from typing import Optional

from .config import projects_root
from .publish import parse_hip_filename


_PIPELINE_VARS = ("PROJECT", "SEQ", "SHOT", "ASSETTYPE", "ASSET", "TASK", "VER")


def context_from_hip(hip_path) -> Optional[dict]:
    """
    Parse pipeline context from a hip file path.

    Returns dict with keys: kind, project, seq, shot, asset_type, asset, task,
    version, version_str. `kind` is "shot" or "asset". Returns None if the hip
    isn't under projects_root, doesn't sit in .../FX/work/houdini/, or has an
    unrecognised filename.
    """
    if not hip_path:
        return None

    hip = Path(hip_path)
    try:
        hip = hip.resolve()
    except OSError:
        return None

    try:
        rel = hip.relative_to(projects_root().resolve())
    except ValueError:
        return None

    parts = rel.parts
    # Shot layout:  <project>/<SEQ>/<SHOT>/FX/work/houdini/<hipfile>          → 7 parts
    # Asset layout: <project>/assets/<TYPE>/<ASSET>/FX/work/houdini/<hipfile> → 8 parts
    if len(parts) < 7:
        return None
    if parts[-2] != "houdini" or parts[-3] != "work" or parts[-4] != "FX":
        return None

    parsed = parse_hip_filename(parts[-1])
    if not parsed:
        return None

    ctx = {
        "kind": None,
        "project": parts[0],
        "seq": None,
        "shot": None,
        "asset_type": None,
        "asset": None,
        "task": parsed["task"],
        "version": parsed["version"],
        "version_str": f"{parsed['version']:03d}",
    }

    if len(parts) >= 8 and parts[1] == "assets":
        ctx["kind"] = "asset"
        ctx["asset_type"] = parts[2]
        ctx["asset"] = parts[3]
        return ctx

    if len(parts) == 7:
        ctx["kind"] = "shot"
        ctx["seq"] = parts[1]
        ctx["shot"] = parts[2]
        return ctx

    return None


def _vars_from_context(ctx: dict) -> dict:
    return {
        "PROJECT":   ctx.get("project") or "",
        "SEQ":       ctx.get("seq") or "",
        "SHOT":      ctx.get("shot") or "",
        "ASSETTYPE": ctx.get("asset_type") or "",
        "ASSET":     ctx.get("asset") or "",
        "TASK":      ctx.get("task") or "",
        "VER":       ctx.get("version_str") or "",
    }


def apply_to_houdini(ctx: Optional[dict]) -> dict:
    """
    Push pipeline vars into the current Houdini session.

    Each var is set two ways:
      * hou.putenv(NAME, VAL)          — env-table lookup (hou.getenv works)
      * hou.hscript("set -g NAME = …") — global hscript variable, which is what
        Edit → Aliases and Variables lists. Parm expansion accepts either; the
        Variables window only shows the latter.

    ctx=None clears every pipeline var so a hip outside the project tree
    doesn't inherit stale values from a previous load.
    Returns the {var: value} that was applied.
    """
    import hou  # local: parsing functions must stay importable outside Houdini for tests

    vars_ = _vars_from_context(ctx) if ctx else {name: "" for name in _PIPELINE_VARS}
    for name, val in vars_.items():
        hou.putenv(name, val)
        # Quote the value to survive spaces / special chars. Our pipeline values
        # are simple identifiers today, but quoting is cheap insurance.
        escaped = val.replace('"', '\\"')
        hou.hscript('set -g %s = "%s"' % (name, escaped))
    # Notify the variables UI that globals changed so the window updates without
    # a manual refresh. varchange is the canonical hscript command for this.
    hou.hscript("varchange")
    return vars_


def apply_from_current_hip() -> dict:
    """Read hou.hipFile.path() and apply the resolved context."""
    import hou

    ctx = context_from_hip(hou.hipFile.path())
    return apply_to_houdini(ctx)
