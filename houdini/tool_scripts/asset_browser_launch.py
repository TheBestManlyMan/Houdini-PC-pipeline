# Shelf tool: opens the unified Asset Browser.
import importlib
import os
import sys

import hou

_root = hou.getenv("HOUDINI_PIPELINE_ROOT") or os.environ.get("HOUDINI_PIPELINE_ROOT")
if not _root:
    raise EnvironmentError("HOUDINI_PIPELINE_ROOT is not set.")

_py = os.path.join(_root, "python")
if _py not in sys.path:
    sys.path.insert(0, _py)

import pipeline
import asset_browser

importlib.reload(pipeline)
importlib.reload(asset_browser)

context = {}
try:
    hip = hou.hipFile.path()
    if hip and not hip.endswith("untitled.hip"):
        parsed = pipeline.parse_hip_filename(hou.hipFile.basename())
        if parsed:
            context["entity"] = parsed["entity"]
            context["task"] = parsed["task"]
except Exception:
    pass

asset_browser.show(houdini_context=context)
