"""Unit tests for pipeline.kimodo — run with: python -m pytest tests/

Everything here is offline: no Kimodo process is launched, no hou, no Qt.
Only command building, environment sanitising, clip bookkeeping, BVH header
parsing and rig-map validation are covered.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

MINIMAL_BVH = """HIERARCHY
ROOT Root
{
  OFFSET 0.0 0.0 0.0
  CHANNELS 6 Xposition Yposition Zposition Zrotation Yrotation Xrotation
  JOINT Hips
  {
    OFFSET 0.0 100.0 0.0
    CHANNELS 3 Zrotation Yrotation Xrotation
    End Site
    {
      OFFSET 0.0 5.0 0.0
    }
  }
}
MOTION
Frames: 90
Frame Time: 0.0333333333
0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0
"""


@pytest.fixture(autouse=True)
def kimodo_env(tmp_path, monkeypatch):
    """Point the pipeline config at a temp Kimodo install and clip library."""
    install = tmp_path / "kimodo"
    (install / ".venv" / "bin").mkdir(parents=True)
    for exe in ("kimodo_gen", "kimodo_convert"):
        path = install / ".venv" / "bin" / exe
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)

    config = {
        "projects_root": str(tmp_path / "shows"),
        "ffmpeg": "ffmpeg",
        "default_fps": 24,
        "default_resolution": "1920x1080",
        "kimodo": {
            "install_root": str(install),
            "venv": ".venv",
            "clips_root": str(tmp_path / "clips"),
            "fps": 30.0,
            "bvh_scale": 0.01,
            "text_encoder_device": "cpu",
            "model": "",
        },
    }
    config_path = tmp_path / "pipeline_config.json"
    config_path.write_text(json.dumps(config))

    import pipeline.config
    monkeypatch.setattr(pipeline.config, "_CONFIG_PATH", config_path)
    monkeypatch.delenv("KIMODO_ROOT", raising=False)
    yield tmp_path


# --------------------------------------------------------------------- config

def test_install_paths_resolve():
    from pipeline.kimodo import config
    assert config.gen_executable().name == "kimodo_gen"
    assert config.convert_executable().is_file()
    assert config.problems() == []


def test_kimodo_root_env_overrides_config(monkeypatch, tmp_path):
    from pipeline.kimodo import config
    monkeypatch.setenv("KIMODO_ROOT", str(tmp_path / "elsewhere"))
    assert config.install_root() == tmp_path / "elsewhere"


def test_problems_reports_missing_install(monkeypatch, tmp_path):
    from pipeline.kimodo import config
    monkeypatch.setenv("KIMODO_ROOT", str(tmp_path / "gone"))
    assert config.problems()


def test_child_env_strips_houdini_interpreter(monkeypatch):
    from pipeline.kimodo import config
    monkeypatch.setenv("PYTHONHOME", "/opt/hfs22.0/python")
    monkeypatch.setenv("PYTHONPATH", "/opt/hfs22.0/houdini/python3.13libs")
    env = config.child_env()
    assert "PYTHONHOME" not in env
    assert "PYTHONPATH" not in env
    assert env["TEXT_ENCODER_DEVICE"] == "cpu"


def test_clips_root_defaults_under_projects_root(tmp_path):
    """An empty clips_root falls back to the motion library under projects_root."""
    from pipeline.kimodo import config
    config_path = tmp_path / "pipeline_config.json"
    cfg = json.loads(config_path.read_text())
    cfg["kimodo"]["clips_root"] = ""
    config_path.write_text(json.dumps(cfg))
    assert config.clips_root() == tmp_path / "shows" / "_library" / "motion" / "kimodo"


# --------------------------------------------------------------------- runner

def test_gen_command_shape():
    from pipeline.kimodo import runner
    cmd = runner.gen_command("a soldier marches", "/clips/march", duration=4.0,
                             steps=30, seed=1234)
    assert cmd[0].endswith("kimodo_gen")
    assert cmd[1] == "a soldier marches"
    assert cmd[cmd.index("--duration") + 1] == "4.0"
    assert cmd[cmd.index("--diffusion_steps") + 1] == "30"
    assert cmd[cmd.index("--seed") + 1] == "1234"
    assert "--bvh" not in cmd  # BVH comes from the convert step


def test_gen_command_random_seed_omitted():
    from pipeline.kimodo import runner
    assert "--seed" not in runner.gen_command("x", "/clips/x", seed=None)
    assert "--seed" not in runner.gen_command("x", "/clips/x", seed=-1)


def test_convert_command_uses_standard_tpose():
    from pipeline.kimodo import runner
    cmd = runner.convert_command("/clips/x.npz", "/clips/x.bvh")
    assert cmd[0].endswith("kimodo_convert")
    assert cmd[1:3] == ["/clips/x.npz", "/clips/x.bvh"]
    assert "--bvh_standard_tpose" in cmd


def test_run_raises_on_failure(tmp_path):
    from pipeline.kimodo import config, runner
    failing = config.venv_bin("kimodo_gen")
    failing.write_text("#!/bin/sh\necho boom\nexit 3\n")
    failing.chmod(0o755)
    with pytest.raises(runner.KimodoError) as excinfo:
        runner.run([str(failing)])
    assert "exited 3" in str(excinfo.value)


def test_run_streams_output():
    from pipeline.kimodo import config, runner
    script = config.venv_bin("kimodo_gen")
    script.write_text("#!/bin/sh\necho hello\necho world\n")
    script.chmod(0o755)
    seen = []
    assert runner.run([str(script)], on_output=seen.append) == 0
    assert seen == ["hello", "world"]


# ---------------------------------------------------------------------- clips

def test_slugify():
    from pipeline.kimodo import clips
    assert clips.slugify("A soldier marches, spear high!") == "a_soldier_marches_spear_high"
    assert clips.slugify("!!!") == "clip"


def test_unique_stem_never_overwrites():
    from pipeline.kimodo import clips
    root = clips.ensure_clips_root()
    assert clips.unique_stem("idle_guard") == "idle_guard"
    (root / "idle_guard.bvh").write_text(MINIMAL_BVH)
    assert clips.unique_stem("idle_guard") == "idle_guard_002"


def test_meta_roundtrip_and_listing():
    from pipeline.kimodo import clips
    root = clips.ensure_clips_root()
    (root / "march_spear_01.bvh").write_text(MINIMAL_BVH)
    clips.write_meta("march_spear_01", "a soldier marches", 4.0, 30, seed=7)
    meta = clips.read_meta("march_spear_01")
    assert meta["prompt"] == "a soldier marches"
    assert meta["seed"] == 7
    assert meta["fps"] == 30.0
    assert clips.list_clips() == ["march_spear_01"]


def test_bvh_header_probe(tmp_path):
    from pipeline.kimodo import clips
    bvh = tmp_path / "probe.bvh"
    bvh.write_text(MINIMAL_BVH)
    assert clips.bvh_frame_count(bvh) == 90
    assert clips.bvh_fps(bvh) == 30.0
    assert clips.bvh_joints(bvh) == ["Root", "Hips"]


# ------------------------------------------------------------------- retarget

def test_rig_map_is_valid():
    from pipeline.kimodo import retarget
    assert retarget.validate() == []


def test_rig_map_keeps_locomotion_on_hips():
    from pipeline.kimodo import retarget
    data = retarget.load_rig_map()
    assert data["source"]["locomotion_joint"] == "Hips"
    assert "Root" not in data["joint_map"]
    assert retarget.joint_map()["Hips"] == "mixamorig:Hips"


def test_rig_map_validation_catches_bad_joint(tmp_path, monkeypatch):
    from pipeline.kimodo import retarget
    issues = retarget.validate(source_joints=["Hips"], target_joints=["mixamorig:Hips"])
    assert any("not in skeleton" in i for i in issues)


def test_fbik_targets_are_mapped_joints():
    from pipeline.kimodo import retarget
    mapped = set(retarget.joint_map().values())
    assert set(retarget.fbik_targets()) <= mapped


def test_rig_map_tpose_and_scale_reference_real_joints():
    """The T-pose levelling and size-match specs must name joints that exist."""
    from pipeline.kimodo import retarget
    data = retarget.load_rig_map()
    tgt = set(data["target"]["joints"])
    src = set(data["source"]["joints"])
    assert data["target"]["tpose_level_bones"], "no T-pose reference for an A-pose rig"
    for pair in data["target"]["tpose_level_bones"]:
        assert set(pair) <= tgt
    assert set(data["scale"]["source_bones"]) <= src
    assert set(data["scale"]["target_bones"]) <= tgt
    assert retarget.validate() == []


def test_validate_catches_unknown_tpose_joint():
    from pipeline.kimodo import retarget
    issues = retarget.validate(target_joints=["mixamorig:Hips"])
    assert any("tpose_level_bones joint not in skeleton" in i for i in issues)
