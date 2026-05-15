# Shelf tool: Pipeline Manager Server
# Starts the local FastAPI server and opens the web UI in your browser.
# Run again to open the browser if the server is already running.

import importlib
import os
import sys

import hou

_root = hou.getenv("HOUDINI_PIPELINE_ROOT") or os.environ.get("HOUDINI_PIPELINE_ROOT")
if not _root:
    raise EnvironmentError("HOUDINI_PIPELINE_ROOT is not set.")

# Add pipeline python to path
_py = os.path.join(_root, "python")
if _py not in sys.path:
    sys.path.insert(0, _py)

# Add server location to path
if _root not in sys.path:
    sys.path.insert(0, _root)

import server
importlib.reload(server)

server.start_server(host="127.0.0.1", port=8765, open_browser=True)
hou.ui.setStatusMessage("Pipeline Manager running at http://127.0.0.1:8765")
