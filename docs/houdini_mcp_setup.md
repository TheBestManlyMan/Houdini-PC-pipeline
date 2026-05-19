# Houdini MCP — Claude Code integration

How the [capoomgit/houdini-mcp](https://github.com/capoomgit/houdini-mcp) Model Context Protocol bridge is wired up on this workstation so Claude Code can drive Houdini 21.

This is an **experimental tool**, separate from the FX pipeline (publisher, file manager, indexer, gallery). It does not write `metadata.json`, does not touch `projects_root`, and Deadline knows nothing about it. The pipeline's disk + JSON contract is untouched.

---

## Integration model

```
Claude Code (this CLI)
        │  stdio (MCP protocol)
        ▼
houdini_mcp_server.py        ← "bridge" script, launched by uv on demand
        │  TCP localhost:9876
        ▼
houdinimcp Python package    ← runs inside Houdini 21
        │  hou.*  /  PySide6.QtCore.QTimer
        ▼
Houdini session (nodes, /obj, parms, render, etc.)
```

Two halves:

1. **Houdini plugin** (`houdinimcp/`) — a Python package that opens a TCP listener on `localhost:9876` from inside Houdini's main thread (uses a `QtCore.QTimer` to poll).
2. **MCP bridge** (`houdini_mcp_server.py`) — a separate `uv run` process that Claude Code spawns over stdio. Each MCP tool call forwards a JSON command to the TCP listener.

The bridge process is spawned/killed by Claude Code automatically. The TCP listener is started/stopped manually via a Houdini shelf button.

---

## Components on this workstation

| Component | Path | Notes |
|---|---|---|
| Upstream repo clone | `~/houdini-mcp/` | Source of truth for the bridge script; `uv` venv lives here |
| Bridge script | `~/houdini-mcp/houdini_mcp_server.py` | What Claude Code spawns |
| Bridge venv | `~/houdini-mcp/.venv/` | Created by `uv add`; contains `mcp[cli]`, `requests`, `python-dotenv`, `langchain` |
| OPUS config | `~/houdini-mcp/urls.env` | `RAPIDAPI_KEY=disabled` placeholder; see Patches below |
| Houdini plugin package | `~/houdini21.0/scripts/python/houdinimcp/` | What Houdini imports as `houdinimcp` |
| uv binary | `~/.local/bin/uv` | Installed via official installer; `~/.local/bin` already on PATH in `~/.bashrc` |
| Claude Code MCP registration | `~/.claude.json` (user scope) | Added via `claude mcp add -s user houdini …` — available in every project |
| Unused Claude Desktop config | `~/.config/Claude/claude_desktop_config.json` | Created before realizing Claude Desktop isn't on Linux; harmless |

---

## Patches applied to upstream

The upstream repo targets Houdini 19.5 on Windows. Two changes were needed:

1. **PySide2 → PySide6** in `~/houdini21.0/scripts/python/houdinimcp/server.py` line 12. Houdini 21 ships PySide6; only `QtCore.QTimer` is used, which is API-identical.
2. **OPUS RapidAPI bypass** — set `RAPIDAPI_KEY=disabled` in `~/houdini-mcp/urls.env`. Upstream hard-exits at startup if all three RapidAPI vars are unset (line 893 of the bridge), even though OPUS is an optional feature. The placeholder lets the server start; OPUS tools return errors at call time, all other tools work.

Also: the bridge script's hardcoded `.venv/Lib/site-packages` sys.path manipulation is Windows-specific and silently fails on Linux. Harmless — `uv run --project` sets up the correct site-packages itself before invoking the script.

---

## Launching

### Houdini side (manual, once per Houdini session)

Create a shelf tool from the repo README:

- Right-click a shelf → **New Shelf...** → name `MCP`
- Right-click the new shelf → **New Tool...** → Name `Toggle MCP Server`, Label `MCP`
- Under **Script**, paste:

  ```python
  import hou
  import houdinimcp
  import subprocess

  PIPELINE_DIR = "/home/maxborg/projects/Houdini-PC-pipeline"

  if hasattr(hou.session, "houdinimcp_server") and hou.session.houdinimcp_server:
      houdinimcp.stop_server()
      hou.ui.displayMessage("Houdini MCP Server stopped")
  else:
      houdinimcp.start_server()
      # Spawn a gnome-terminal with `claude` running in the pipeline dir.
      # start_new_session detaches it so it survives Houdini quitting.
      subprocess.Popen(
          ["gnome-terminal", "--working-directory", PIPELINE_DIR, "--", "claude"],
          start_new_session=True,
      )
      hou.ui.displayMessage(
          "Houdini MCP Server started on localhost:9876\n"
          "Terminal with Claude Code opened."
      )
  ```

- Click once to start the listener (also spawns the Claude terminal); click again to stop the listener (terminal stays open, close it manually).
- The terminal opens in `/home/maxborg/projects/Houdini-PC-pipeline` so Claude Code starts with the pipeline repo as its working directory.

### Claude Code side (automatic)

Registered at user scope:

```
claude mcp add -s user houdini /home/maxborg/.local/bin/uv -- \
  run --project /home/maxborg/houdini-mcp \
  python /home/maxborg/houdini-mcp/houdini_mcp_server.py
```

Verify:

```
claude mcp list | grep houdini
# houdini: … - ✓ Connected
```

Claude Code spawns the bridge on session start. Tools become available in any new chat.

---

## Verifying end-to-end

1. Start Houdini, click the **MCP** shelf button — should display "Houdini MCP Server started on localhost:9876".
2. In a fresh Claude Code session, ask something like: *"List the nodes under /obj."*
3. Claude calls the `get_scene_info` MCP tool → bridge → TCP → `houdinimcp` plugin → `hou.node("/obj").children()` → response.

If the bridge can't reach Houdini, you'll get a TCP connection error in the tool result — that just means the shelf-button listener isn't running.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `claude mcp list` shows `✗ Failed to connect` for `houdini` | Bridge script crashes at startup | Run `uv run --project ~/houdini-mcp python ~/houdini-mcp/houdini_mcp_server.py` manually and read the traceback |
| `ModuleNotFoundError: No module named 'mcp'` | uv invoked without `--project`, no pyproject in cwd | The MCP registration must include `--project /home/maxborg/houdini-mcp` |
| `ModuleNotFoundError: No module named 'PySide2'` in Houdini | Patch reverted / fresh copy from upstream overwrote `server.py` | Re-apply PySide2→PySide6 in `~/houdini21.0/scripts/python/houdinimcp/server.py` line 12 |
| `Server will not start. RAPIDAPI_*` | `urls.env` is missing the placeholder | Set `RAPIDAPI_KEY=disabled` (or a real key) in `~/houdini-mcp/urls.env` |
| MCP tools error with TCP connection refused | Houdini shelf button not clicked yet, or Houdini not running | Start Houdini and click the **MCP** shelf button |

---

## Updating from upstream

```
cd ~/houdini-mcp
git pull
cp __init__.py server.py houdini_mcp_server.py HoudiniMCPRender.py pyproject.toml \
   ~/houdini21.0/scripts/python/houdinimcp/
# re-apply PySide2 → PySide6 patch in server.py
```

Then restart Houdini and click the shelf button. The bridge venv at `~/houdini-mcp/.venv/` survives `git pull`; rerun `uv add "mcp[cli]" requests python-dotenv langchain` only if `pyproject.toml` declares new deps.
