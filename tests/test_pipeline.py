"""Unit tests for pipeline.py — run with: python -m pytest tests/"""

import json
import tempfile
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

# Patch config before importing pipeline so paths point at temp dirs
_orig_config = None


@pytest.fixture(autouse=True)
def temp_env(tmp_path, monkeypatch):
    config = {
        "projects_root": str(tmp_path / "shows"),
        "ffmpeg": "ffmpeg",
        "default_fps": 24,
        "default_resolution": "1920x1080",
    }
    config_path = tmp_path / "pipeline_config.json"
    config_path.write_text(json.dumps(config))

    projects_path = tmp_path / "projects.json"
    projects_path.write_text(json.dumps({"projects": []}))

    import pipeline
    monkeypatch.setattr(pipeline, "_CONFIG_PATH", config_path)
    monkeypatch.setattr(pipeline, "_PROJECTS_PATH", projects_path)
    (tmp_path / "shows").mkdir()
    yield tmp_path


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

def test_get_next_version_empty(tmp_path):
    import pipeline
    assert pipeline.get_next_version(tmp_path / "nonexistent") == 1


def test_get_next_version_with_existing(tmp_path):
    import pipeline
    folder = tmp_path / "cache"
    folder.mkdir()
    (folder / "v001").mkdir()
    (folder / "v003").mkdir()
    assert pipeline.get_next_version(folder) == 4


def test_get_latest_version(tmp_path):
    import pipeline
    folder = tmp_path / "cache"
    folder.mkdir()
    (folder / "v002").mkdir()
    (folder / "v005").mkdir()
    assert pipeline.get_latest_version(folder) == 5


def test_version_str():
    import pipeline
    assert pipeline.version_str(1) == "v001"
    assert pipeline.version_str(42) == "v042"
    assert pipeline.version_str(999) == "v999"


# ---------------------------------------------------------------------------
# Hip filename
# ---------------------------------------------------------------------------

def test_hip_filename():
    import pipeline
    assert pipeline.hip_filename("SQ010_0010", "falling-ice", 1) == "SQ010_0010_fx_falling-ice_v001.hip"


def test_parse_hip_filename_valid():
    import pipeline
    result = pipeline.parse_hip_filename("SQ010_0010_fx_falling-ice_v003.hip")
    assert result == {"entity": "SQ010_0010", "task": "falling-ice", "version": 3, "version_str": "v003"}


def test_parse_hip_filename_invalid():
    import pipeline
    assert pipeline.parse_hip_filename("random_file.hip") is None


# ---------------------------------------------------------------------------
# Cache filenames
# ---------------------------------------------------------------------------

def test_cache_filename_geo():
    import pipeline
    assert pipeline.cache_filename("hero", "dust-sim", 2, "bgeo.sc") == "hero_fx_dust-sim_v002.$F4.bgeo.sc"


def test_cache_filename_vdb():
    import pipeline
    assert pipeline.cache_filename("hero", "dust-sim", 2, "vdb") == "hero_fx_dust-sim_v002.$F4.vdb"


def test_cache_filename_abc():
    import pipeline
    assert pipeline.cache_filename("hero", "cloth", 1, "abc") == "hero_fx_cloth_v001.abc"


def test_flipbook_filename():
    import pipeline
    assert pipeline.flipbook_filename("SQ010_0010", 1) == "SQ010_0010_fx_flipbook_v001.$F4.jpg"


def test_mp4_filename():
    import pipeline
    assert pipeline.mp4_filename("SQ010_0010", "smoke", 4) == "SQ010_0010_fx_smoke_v004.mp4"


# ---------------------------------------------------------------------------
# Path builders
# ---------------------------------------------------------------------------

def test_shot_work_houdini(temp_env):
    import pipeline
    p = pipeline.shot_work_houdini("my-project", "SQ010", "0010")
    assert str(p).endswith("shows/my-project/sequences/SQ010/0010/FX/work/houdini")


def test_asset_work_houdini(temp_env):
    import pipeline
    p = pipeline.asset_work_houdini("my-project", "character", "hero")
    assert str(p).endswith("shows/my-project/assets/character/hero/FX/work/houdini")


# ---------------------------------------------------------------------------
# Project registry
# ---------------------------------------------------------------------------

def test_add_and_load_project(temp_env):
    import pipeline
    project = pipeline.add_project("Test Show", "test-show", sequences=["SQ010"])
    projects = pipeline.load_projects()
    assert len(projects) == 1
    assert projects[0]["folder"] == "test-show"
    assert projects[0]["fps"] == 24


def test_add_duplicate_project_raises(temp_env):
    import pipeline
    pipeline.add_project("Test Show", "test-show")
    with pytest.raises(ValueError):
        pipeline.add_project("Test Show 2", "test-show")


def test_get_project(temp_env):
    import pipeline
    pipeline.add_project("My Show", "my-show")
    assert pipeline.get_project("my-show") is not None
    assert pipeline.get_project("nonexistent") is None


# ---------------------------------------------------------------------------
# ROP / task
# ---------------------------------------------------------------------------

def test_task_from_rop():
    import pipeline
    assert pipeline.task_from_rop("OUT_falling-ice") == "falling-ice"
    assert pipeline.task_from_rop("OUT_SMOKE") == "smoke"
    assert pipeline.task_from_rop("dust_sim") == "dust_sim"


# ---------------------------------------------------------------------------
# Directory creation
# ---------------------------------------------------------------------------

def test_make_shot_work_dirs(temp_env):
    import pipeline
    pipeline.make_shot_work_dirs("my-project", "SQ010", "0010")
    d = pipeline.shot_work_houdini("my-project", "SQ010", "0010")
    assert d.exists()


def test_make_cache_version_dirs(tmp_path):
    import pipeline
    result = pipeline.make_cache_version_dirs(tmp_path / "cache", 1)
    assert result["geo"].exists()
    assert result["vdb"].exists()
