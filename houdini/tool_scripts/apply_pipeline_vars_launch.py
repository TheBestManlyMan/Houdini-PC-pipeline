# Paste this into a shelf tool button script.
# Reapply pipeline variables from the current HIP and show which were set.

import importlib
import os
import sys

import hou

_root = hou.getenv("HOUDINI_PIPELINE_ROOT") or os.environ.get("HOUDINI_PIPELINE_ROOT")
if not _root:
    raise EnvironmentError(
        "HOUDINI_PIPELINE_ROOT is not set. Add it to houdini.env and restart Houdini."
    )

_pipeline_python = os.path.join(_root, "python")
if _pipeline_python not in sys.path:
    sys.path.insert(0, _pipeline_python)

import pipeline
import pipeline.context as ctx_mod

importlib.reload(pipeline)
importlib.reload(ctx_mod)

vars_ = ctx_mod.apply_from_current_hip()
nonempty = {k: v for k, v in vars_.items() if v}

if nonempty:
    msg = "  ".join("$%s=%s" % (k, v) for k, v in nonempty.items())
    hou.ui.setStatusMessage("Pipeline vars:  " + msg)
else:
    hou.ui.setStatusMessage(
        "Pipeline vars: no context — HIP is outside projects_root or doesn't follow the layout.",
        severity=hou.severityType.Warning,
    )
