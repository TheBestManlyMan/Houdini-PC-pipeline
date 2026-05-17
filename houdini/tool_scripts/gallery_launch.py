# Paste this into the shelf tool button script.
#
# Strategy: start python -m http.server as a daemon thread rooted at
# projects_root, then open http://127.0.0.1:8000/gallery.html in the
# default browser.  http.server is used (rather than a file:// URL) so that
# fetch('./index.json') inside gallery.html is not blocked by browser CORS
# restrictions.

import os
import sys
import threading
import webbrowser

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
import pipeline.config as _cfg

_projects_root = str(pipeline.projects_root())
_gallery_html = os.path.join(_root, "gallery.html")
_index_json = os.path.join(_projects_root, "index.json")

# Rebuild the index if it is missing.
if not os.path.exists(_index_json):
    hou.ui.setStatusMessage("Gallery: building index.json…")
    try:
        pipeline.rebuild()
    except Exception as _e:
        hou.ui.setStatusMessage(f"Gallery: index build failed — {_e}", severity=hou.severityType.Warning)

# Copy gallery.html into projects_root so it is served alongside index.json
# and relative paths in index.json resolve correctly.
import shutil
_dest_html = os.path.join(_projects_root, "gallery.html")
shutil.copy2(_gallery_html, _dest_html)

_PORT = 8000

def _start_server(directory, port):
    import http.server
    import socketserver
    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *a: None  # silence access log
    os.chdir(directory)
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()

_t = threading.Thread(target=_start_server, args=(_projects_root, _PORT), daemon=True)
_t.start()

webbrowser.open(f"http://127.0.0.1:{_PORT}/gallery.html")
hou.ui.setStatusMessage(f"Gallery open at http://127.0.0.1:{_PORT}/gallery.html")
