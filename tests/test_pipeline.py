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
    import pipeline.config
    # Patch the canonical locations in the config module — all submodules read from there.
    monkeypatch.setattr(pipeline.config, "_CONFIG_PATH", config_path)
    monkeypatch.setattr(pipeline.config, "_PROJECTS_PATH", projects_path)
    # Keep the __init__ re-exports in sync for any code that reads them directly.
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
    assert result == {"entity": "SQ010_0010", "task": "falling-ice", "descriptor": "", "version": 3, "version_str": "v003"}


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
    assert str(p).endswith("shows/my-project/SQ010/0010/FX/work/houdini")


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


# ---------------------------------------------------------------------------
# entity_root_from_hip
# ---------------------------------------------------------------------------

def test_entity_root_from_hip_shot(tmp_path):
    import pipeline
    hip = tmp_path / "shows" / "proj" / "SQ010" / "0010" / "FX" / "work" / "houdini" / "shot_fx_sim_v001.hip"
    result = pipeline.entity_root_from_hip(hip)
    assert result == tmp_path / "shows" / "proj" / "SQ010" / "0010" / "FX"


def test_entity_root_from_hip_asset(tmp_path):
    import pipeline
    hip = tmp_path / "shows" / "proj" / "assets" / "char" / "hero" / "FX" / "work" / "houdini" / "hero_fx_sim_v001.hip"
    result = pipeline.entity_root_from_hip(hip)
    assert result == tmp_path / "shows" / "proj" / "assets" / "char" / "hero" / "FX"


# ---------------------------------------------------------------------------
# Validation (Phase 3)
# ---------------------------------------------------------------------------

def test_validate_entity_name_valid():
    import pipeline
    assert pipeline.validate_entity_name("SQ010_0010") == "SQ010_0010"
    assert pipeline.validate_entity_name("hero") == "hero"


def test_validate_entity_name_invalid():
    import pipeline
    with pytest.raises(ValueError):
        pipeline.validate_entity_name("")
    with pytest.raises(ValueError):
        pipeline.validate_entity_name("my/entity")


def test_validate_task_name_normalises():
    import pipeline
    assert pipeline.validate_task_name("Falling Ice") == "falling-ice"
    assert pipeline.validate_task_name("dust-sim") == "dust-sim"


def test_validate_task_name_invalid():
    import pipeline
    with pytest.raises(ValueError):
        pipeline.validate_task_name("")
    with pytest.raises(ValueError):
        pipeline.validate_task_name("---")


def test_validate_publish_type_valid():
    import pipeline
    for t in ("cache", "flipbook", "render", "usd", "hip"):
        assert pipeline.validate_publish_type(t) == t


def test_validate_publish_type_invalid():
    import pipeline
    with pytest.raises(ValueError):
        pipeline.validate_publish_type("nope")


def test_validate_version_int():
    import pipeline
    assert pipeline.validate_version(1) == 1
    assert pipeline.validate_version(42) == 42


def test_validate_version_str():
    import pipeline
    assert pipeline.validate_version("v003") == 3
    assert pipeline.validate_version("v042") == 42


def test_validate_version_invalid():
    import pipeline
    with pytest.raises(ValueError):
        pipeline.validate_version(0)
    with pytest.raises(ValueError):
        pipeline.validate_version("v99")  # not 3-digit zero-padded


def test_validate_context_shot():
    import pipeline
    ctx = {"type": "shot", "sequence": "SQ010", "shot": "0010"}
    assert pipeline.validate_context(ctx) == ctx


def test_validate_context_asset():
    import pipeline
    ctx = {"type": "asset", "asset_type": "character", "asset": "hero"}
    assert pipeline.validate_context(ctx) == ctx


def test_validate_context_invalid():
    import pipeline
    with pytest.raises(ValueError):
        pipeline.validate_context({"type": "unknown"})
    with pytest.raises(ValueError):
        pipeline.validate_context({"type": "shot", "sequence": "SQ010"})  # missing shot


# ---------------------------------------------------------------------------
# Metadata (Phase 2)
# ---------------------------------------------------------------------------

def test_build_metadata_structure():
    import pipeline
    meta = pipeline.build_metadata(
        project="TestShow",
        context={"type": "shot", "sequence": "SQ010", "shot": "0010"},
        entity="SQ010_0010",
        task="dust-sim",
        publish_type="cache",
        version=1,
    )
    assert meta["schema_version"] == 2
    assert meta["uuid"].startswith("pub_")
    assert meta["entity"] == "SQ010_0010"
    assert meta["task"] == "dust-sim"
    assert meta["publish_type"] == "cache"
    assert meta["version"] == 1
    assert isinstance(meta["dependencies"], list)
    assert isinstance(meta["tags"], list)
    assert isinstance(meta["notes"], list)


def test_build_metadata_wedge():
    import pipeline
    meta = pipeline.build_metadata(
        project="P",
        context={"type": "asset", "asset_type": "prop", "asset": "rock"},
        entity="rock",
        task="sim",
        publish_type="cache",
        version=2,
        wedge={"parameter": "density", "value": 0.6},
    )
    assert meta["wedge"]["parameter"] == "density"
    assert meta["wedge"]["value"] == 0.6


def test_write_and_read_metadata(tmp_path):
    import pipeline
    pub_dir = tmp_path / "pub" / "v001"
    pub_dir.mkdir(parents=True)
    meta = pipeline.build_metadata(
        project="P",
        context={"type": "shot", "sequence": "SQ010", "shot": "0010"},
        entity="SQ010_0010",
        task="dust-sim",
        publish_type="cache",
        version=1,
    )
    pipeline.write_metadata(pub_dir, meta)
    assert (pub_dir / "metadata.json").exists()
    loaded = pipeline.read_metadata(pub_dir)
    assert loaded["uuid"] == meta["uuid"]


def test_write_publish_metadata_upgrades_legacy(tmp_path):
    """write_publish_metadata must upgrade flat v1 dicts to v2 schema."""
    import pipeline
    pub_dir = tmp_path / "legacy" / "v001"
    pub_dir.mkdir(parents=True)
    legacy = {
        "schema_version": 1,
        "entity": "hero",
        "task": "sim",
        "version": 3,
        "published_by": "maxborg",
        "published_at": "2025-01-01T00:00:00",
    }
    pipeline.write_publish_metadata(pub_dir, legacy)
    loaded = pipeline.read_metadata(pub_dir)
    assert loaded["schema_version"] == 2
    assert "uuid" in loaded


# ---------------------------------------------------------------------------
# Standard outputs (Phase 6)
# ---------------------------------------------------------------------------

def test_build_standard_output_paths(tmp_path):
    import pipeline
    paths = pipeline.build_standard_output_paths(tmp_path / "v001")
    assert "thumbnail" in paths
    assert "mp4" in paths
    assert "contactsheet" in paths
    assert "metadata" in paths
    assert paths["thumbnail"].endswith("thumbnail.jpg")


# ---------------------------------------------------------------------------
# Indexer (Phase 4)
# ---------------------------------------------------------------------------

def test_build_project_index_empty(temp_env):
    import pipeline
    import pipeline.config
    root = pipeline.config._CONFIG_PATH.parent / "shows"
    root.mkdir(exist_ok=True)
    pipeline.add_project("Index Test", "idx-test")
    (root / "idx-test").mkdir(exist_ok=True)
    idx = pipeline.build_project_index("idx-test")
    assert idx["folder"] == "idx-test"
    assert idx["publishes"] == []


def test_build_project_index_with_metadata(temp_env, tmp_path):
    import pipeline
    import pipeline.config
    root = pipeline.config._CONFIG_PATH.parent / "shows"
    root.mkdir(exist_ok=True)
    pipeline.add_project("Scan Test", "scan-test")

    # Create a fake publish folder with metadata.json
    pub_dir = (root / "scan-test" / "SQ010" / "0010" / "FX" /
               "publish" / "geo" / "dust-sim" / "main" / "v001")
    pub_dir.mkdir(parents=True)
    meta = pipeline.build_metadata(
        project="Scan Test",
        context={"type": "shot", "sequence": "SQ010", "shot": "0010"},
        entity="SQ010_0010",
        task="dust-sim",
        publish_type="cache",
        version=1,
    )
    pipeline.write_metadata(pub_dir, meta)

    idx = pipeline.build_project_index("scan-test")
    assert idx["publish_count"] == 1
    assert idx["publishes"][0]["entity"] == "SQ010_0010"
