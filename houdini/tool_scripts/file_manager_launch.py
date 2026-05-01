# Paste this into the shelf tool button script.

import importlib
import os
import sys

_pipeline_python = os.path.join(os.environ["HOUDINI_PIPELINE_ROOT"], "python")
if _pipeline_python not in sys.path:
    sys.path.insert(0, _pipeline_python)

import file_manager

importlib.reload(file_manager)
file_manager.main()
