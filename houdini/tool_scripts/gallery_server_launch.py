# Shelf tool: Gallery Server
# Starts the pipeline API server and web gallery, then opens the browser.
# Prints local and Tailscale URLs to the Houdini console.

import os
import subprocess
import sys
import webbrowser

import hou

_root = hou.getenv("HOUDINI_PIPELINE_ROOT") or os.environ.get("HOUDINI_PIPELINE_ROOT")
if not _root:
    hou.ui.displayMessage(
        "HOUDINI_PIPELINE_ROOT is not set.\nAdd it to houdini.env and restart Houdini.",
        severity=hou.severityType.Error,
    )
    raise EnvironmentError("HOUDINI_PIPELINE_ROOT not set")

_api_server = os.path.join(_root, "python", "api_server.py")
_web_dir = os.path.join(_root, "web")

LOCAL_API  = "http://localhost:8765"
LOCAL_WEB  = "http://localhost:5173"
WEB_PORT   = 5173

# ── Get Tailscale IP (best-effort) ──────────────────────────────────────────
def _tailscale_ip():
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True, text=True, timeout=3
        )
        ip = result.stdout.strip()
        if ip and not ip.startswith("no "):
            return ip
    except Exception:
        pass
    return None

ts_ip = _tailscale_ip()
ts_url = f"http://{ts_ip}:{WEB_PORT}" if ts_ip else None

# ── Start API server ─────────────────────────────────────────────────────────
try:
    subprocess.Popen(
        [sys.executable, _api_server, "--host", "0.0.0.0"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"[Pipeline] API server starting at {LOCAL_API}/api")
except Exception as e:
    print(f"[Pipeline] WARNING: Could not start API server: {e}")

# ── Start Vite dev server ────────────────────────────────────────────────────
try:
    subprocess.Popen(
        ["npm", "run", "dev", "--", "--host"],
        cwd=_web_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"[Pipeline] Web gallery starting at {LOCAL_WEB}")
except Exception as e:
    print(f"[Pipeline] WARNING: Could not start web gallery: {e}")

# ── Log URLs ─────────────────────────────────────────────────────────────────
print(f"[Pipeline] Local:     {LOCAL_WEB}")
if ts_url:
    print(f"[Pipeline] Tailscale: {ts_url}")
else:
    print("[Pipeline] Tailscale: not connected (run 'sudo tailscale up')")

# ── Open browser (give servers a moment to start) ────────────────────────────
import threading
def _open():
    import time
    time.sleep(2)
    webbrowser.open(LOCAL_WEB)
threading.Thread(target=_open, daemon=True).start()

# ── Summary popup ─────────────────────────────────────────────────────────────
lines = [f"Gallery started.\n\nLocal:  {LOCAL_WEB}"]
if ts_url:
    lines.append(f"Tailscale: {ts_url}")
else:
    lines.append("Tailscale: not connected")
hou.ui.displayMessage("\n".join(lines), title="Pipeline Gallery")
