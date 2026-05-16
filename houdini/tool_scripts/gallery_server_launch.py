# Shelf tool: Gallery Server
# Starts the pipeline API server and web gallery, then opens the browser.
# Ensures Tailscale is running, then prints local and Tailscale URLs.

import os
import subprocess
import sys
import threading
import time
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
_web_dir    = os.path.join(_root, "web")

LOCAL_API = "http://localhost:8765"
LOCAL_WEB = "http://localhost:5173"
WEB_PORT  = 5173


# ── Tailscale helpers ────────────────────────────────────────────────────────

def _tailscale_ip():
    """Return current Tailscale IPv4, or None if not connected."""
    try:
        r = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True, text=True, timeout=3,
        )
        ip = r.stdout.strip()
        if ip and not ip.startswith("no ") and r.returncode == 0:
            return ip
    except Exception:
        pass
    return None


def _ensure_tailscale():
    """
    Make sure Tailscale is connected.  Three attempts in order:
      1. Already connected → done.
      2. Daemon running but down → tailscale up (no sudo needed).
      3. Daemon not running → start service with sudo -n (non-interactive,
         fails fast if password required rather than blocking forever).

    Returns (ip_or_None, status_string).
    """
    # 1. Already up?
    ip = _tailscale_ip()
    if ip:
        return ip, "already connected"

    # 2. Daemon running, just not connected.
    print("[Pipeline] Tailscale not connected — running 'tailscale up'…")
    try:
        subprocess.run(
            ["tailscale", "up"],
            capture_output=True, text=True, timeout=15,
        )
        ip = _tailscale_ip()
        if ip:
            return ip, "reconnected"
    except subprocess.TimeoutExpired:
        print("[Pipeline] 'tailscale up' timed out.")
    except Exception as e:
        print(f"[Pipeline] 'tailscale up' failed: {e}")

    # 3. Daemon may not be running — try systemctl (sudo -n = non-interactive).
    print("[Pipeline] Attempting to start tailscaled service…")
    try:
        subprocess.run(
            ["sudo", "-n", "systemctl", "start", "tailscaled"],
            capture_output=True, text=True, timeout=10,
        )
        subprocess.run(
            ["tailscale", "up"],
            capture_output=True, text=True, timeout=15,
        )
        ip = _tailscale_ip()
        if ip:
            return ip, "service started"
    except Exception as e:
        print(f"[Pipeline] Could not start tailscaled: {e}")

    return None, "unavailable"


# ── Ensure Tailscale ─────────────────────────────────────────────────────────
ts_ip, ts_status = _ensure_tailscale()
ts_url = f"http://{ts_ip}:{WEB_PORT}" if ts_ip else None
print(f"[Pipeline] Tailscale: {ts_ip or 'not connected'} ({ts_status})")

# ── Start API server ─────────────────────────────────────────────────────────
_log_file = os.path.join(_root, "logs", "api_server.log")
os.makedirs(os.path.dirname(_log_file), exist_ok=True)

# Build a clean environment for the system Python process.
# Houdini sets PYTHONHOME and PYTHONPATH to its own interpreter, which
# causes system python3 to ignore user site-packages (where uvicorn lives).
_env = os.environ.copy()
_env.pop("PYTHONHOME", None)
_env.pop("PYTHONNOUSERSITE", None)
# Restore PYTHONPATH to only the pipeline package — drop Houdini's entries.
_env["PYTHONPATH"] = os.path.join(_root, "python")

try:
    with open(_log_file, "a") as _lf:
        subprocess.Popen(
            ["/usr/bin/python3", _api_server, "--host", "0.0.0.0"],
            stdout=_lf,
            stderr=_lf,
            env=_env,
        )
    print(f"[Pipeline] API server starting at {LOCAL_API}/api")
    print(f"[Pipeline] Log: {_log_file}")
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
    print("[Pipeline] Tailscale: not available — run: sudo tailscale up")

# ── Open browser ─────────────────────────────────────────────────────────────
def _open_browser():
    time.sleep(2)
    webbrowser.open(LOCAL_WEB)
threading.Thread(target=_open_browser, daemon=True).start()

# ── Summary popup ─────────────────────────────────────────────────────────────
lines = [f"Gallery started.\n\nLocal:  {LOCAL_WEB}"]
if ts_url:
    lines.append(f"Tailscale: {ts_url}")
else:
    lines.append("Tailscale: not available\nRun: sudo tailscale up")
hou.ui.displayMessage("\n".join(lines), title="Pipeline Gallery")
