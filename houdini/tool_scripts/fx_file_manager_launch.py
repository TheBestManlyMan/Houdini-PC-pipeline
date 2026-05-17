# Shelf tool: FX File Manager (browser UI)
# Starts the pipeline server if needed and opens the FX File Manager in your browser.

import os
import sys
import webbrowser

import hou

_root = hou.getenv("HOUDINI_PIPELINE_ROOT") or os.environ.get("HOUDINI_PIPELINE_ROOT")
if not _root:
    raise EnvironmentError("HOUDINI_PIPELINE_ROOT is not set.")

_py = os.path.join(_root, "python")
if _py not in sys.path:
    sys.path.insert(0, _py)
if _root not in sys.path:
    sys.path.insert(0, _root)

import server

server.start_server(host="127.0.0.1", port=8765, open_browser=False)

ui_path = os.path.join(_root, "ui", "fx-file-manager.html")
webbrowser.open("file://" + ui_path)
hou.ui.setStatusMessage("FX File Manager open — pipeline server running at http://127.0.0.1:8765")
