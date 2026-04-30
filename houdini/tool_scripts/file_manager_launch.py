# Paste this into the shelf tool button script.
# Requires HOUDINI_PIPELINE_ROOT and PYTHONPATH set in houdini.env.

import importlib
import file_manager

importlib.reload(file_manager)
file_manager.main()
