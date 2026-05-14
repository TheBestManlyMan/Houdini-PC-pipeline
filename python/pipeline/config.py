"""
Pipeline configuration — loads pipeline_config.json.
All other modules import from here; no other module touches the config file directly.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger("pipeline")

# Resolved at import time; callers that monkeypatch these attributes in tests
# must do so before importing any other pipeline submodule.
_PIPELINE_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_PATH = _PIPELINE_ROOT / "pipeline_config.json"
_PROJECTS_PATH = _PIPELINE_ROOT / "projects.json"


def load_config() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        return json.load(f)


def projects_root() -> Path:
    return Path(load_config()["projects_root"])
