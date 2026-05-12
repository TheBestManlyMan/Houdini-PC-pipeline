# Paste this into the shelf tool button script.

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
import naming_conventions
import publisher

importlib.reload(pipeline)
importlib.reload(naming_conventions)
importlib.reload(publisher)
publisher.show()
