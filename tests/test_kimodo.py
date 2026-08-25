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


# ----------------------------------------------------------------- constraints

def _rot(axis, radians):
    """Column-vector rotation matrix, flat row-major — the constraint convention."""
    import math
    c, s = math.cos(radians), math.sin(radians)
    if axis == "x":
        return [1, 0, 0, 0, c, -s, 0, s, c]
    if axis == "y":
        return [c, 0, s, 0, 1, 0, -s, 0, c]
    return [c, -s, 0, s, c, 0, 0, 0, 1]


def _pose(houdini_frame, kimodo_frame, joints=77, angle=0.3):
    from pipeline.kimodo.constraints import GuidePose
    return GuidePose(houdini_frame, kimodo_frame, [0.0, 0.95, 0.0],
                     [_rot("y", angle)] * joints)


def test_parse_guide_frames_basic():
    from pipeline.kimodo.constraints import parse_guide_frames
    assert parse_guide_frames("1, 12, 26, 40") == [1, 12, 26, 40]


def test_parse_guide_frames_normalises():
    from pipeline.kimodo.constraints import parse_guide_frames
    assert parse_guide_frames("  40,1,12 ,26, 12  ") == [1, 12, 26, 40]
    assert parse_guide_frames("1;12;26") == [1, 12, 26]


def test_parse_guide_frames_rejects_junk():
    from pipeline.kimodo.constraints import GuideFrameError, parse_guide_frames
    for bad in ("", None, "   ", "1, x, 3", "1.5, 3", "1"):
        with pytest.raises(GuideFrameError):
            parse_guide_frames(bad)


def test_parse_guide_frames_enforces_range():
    from pipeline.kimodo.constraints import GuideFrameError, parse_guide_frames
    assert parse_guide_frames("1, 40", 1, 40) == [1, 40]
    with pytest.raises(GuideFrameError) as exc:
        parse_guide_frames("1, 41", 1, 40)
    assert "41" in str(exc.value)
    with pytest.raises(GuideFrameError):
        parse_guide_frames("0, 20", 1, 40)


def test_frame_conversion_is_relative_to_start():
    from pipeline.kimodo import constraints as C
    assert C.to_kimodo_frames([1, 12, 26, 40], 1) == [0, 11, 25, 39]
    assert C.to_kimodo_frames([101, 112], 101) == [0, 11]   # not hardcoded to 1
    assert C.to_kimodo_frame(0, 0) == 0


def test_duration_covers_the_whole_range():
    from pipeline.kimodo import constraints as C
    assert C.duration_for_range(1, 40, 30) == pytest.approx(40 / 30.0)
    assert C.duration_for_range(1, 1, 30) == pytest.approx(1 / 30.0)
    with pytest.raises(C.GuideFrameError):
        C.duration_for_range(10, 1, 30)


def test_covers_frames_catches_a_short_clip():
    from pipeline.kimodo import constraints as C
    assert C.covers_frames([1, 40], 1, C.duration_for_range(1, 40, 30), 30)
    assert not C.covers_frames([1, 40], 1, 1.0, 30)    # 30 frames < guide frame 40


def test_axis_angle_matches_rotation():
    import math
    from pipeline.kimodo.constraints import matrix_to_axis_angle
    assert matrix_to_axis_angle([1, 0, 0, 0, 1, 0, 0, 0, 1]) == [0.0, 0.0, 0.0]
    aa = matrix_to_axis_angle(_rot("y", 0.7))
    assert aa == pytest.approx([0.0, 0.7, 0.0], abs=1e-9)
    aa = matrix_to_axis_angle(_rot("z", -1.2))
    assert aa == pytest.approx([0.0, 0.0, -1.2], abs=1e-9)
    aa = matrix_to_axis_angle(_rot("x", math.pi))     # the degenerate case
    assert abs(aa[0]) == pytest.approx(math.pi, abs=1e-6)


def test_constraint_payload_shape():
    from pipeline.kimodo import constraints as C
    poses = [_pose(1, 0), _pose(26, 25), _pose(12, 11)]
    payload = C.build_constraint_payload(poses, joint_count=77)
    assert len(payload) == 1
    entry = payload[0]
    assert entry["type"] == "fullbody"
    assert entry["frame_indices"] == [0, 11, 25]           # sorted by kimodo frame
    assert len(entry["local_joints_rot"]) == 3
    assert len(entry["local_joints_rot"][0]) == 77
    assert len(entry["local_joints_rot"][0][0]) == 3       # axis-angle
    assert len(entry["root_positions"]) == 3


def test_constraint_payload_rejects_bad_input():
    from pipeline.kimodo import constraints as C
    with pytest.raises(C.GuideFrameError):
        C.build_constraint_payload([_pose(1, 0)])                      # one pose
    with pytest.raises(C.GuideFrameError):
        C.build_constraint_payload([_pose(1, 0), _pose(12, 11, joints=30)])
    with pytest.raises(C.GuideFrameError):
        C.build_constraint_payload([_pose(1, 0), _pose(12, 11)], joint_count=30)


def test_write_constraints_matches_kimodos_schema(tmp_path):
    """Same keys and shapes as kimodo's own full-body keyframe example."""
    from pipeline.kimodo import constraints as C
    path = C.write_constraints(tmp_path / "clip_constraints.json",
                               [_pose(1, 0), _pose(40, 39)], joint_count=77)
    data = json.loads(path.read_text())
    assert isinstance(data, list)
    assert set(data[0]) == {"type", "frame_indices", "local_joints_rot", "root_positions"}
    assert data[0]["frame_indices"] == [0, 39]


def test_guide_pose_interchange_roundtrip(tmp_path):
    from pipeline.kimodo import constraints as C
    names = ["J%d" % i for i in range(77)]
    poses = [_pose(1, 0), _pose(40, 39)]
    path = C.write_guide_poses(tmp_path / "clip_guide_poses.json", poses, names, 30.0,
                               houdini_start_frame=1, houdini_end_frame=40)
    data = C.read_guide_poses(path)
    assert data["rest"] == "standard_tpose"
    assert data["fps"] == 30.0
    assert data["houdini_start_frame"] == 1
    assert [f["kimodo_frame"] for f in data["frames"]] == [0, 39]
    assert len(data["frames"][0]["local_rot"]) == 77


def test_write_guide_poses_validates(tmp_path):
    from pipeline.kimodo import constraints as C
    names = ["J%d" % i for i in range(77)]
    with pytest.raises(C.GuideFrameError):        # joint count mismatch
        C.write_guide_poses(tmp_path / "a.json", [_pose(1, 0), _pose(2, 1, joints=30)],
                            names, 30.0)
    with pytest.raises(C.GuideFrameError):        # duplicate kimodo frame
        C.write_guide_poses(tmp_path / "b.json", [_pose(1, 0), _pose(2, 0)], names, 30.0)
    with pytest.raises(C.GuideFrameError):        # guide frame before the clip start
        C.write_guide_poses(tmp_path / "c.json", [_pose(1, -1), _pose(2, 1)], names, 30.0)


def test_gen_command_passes_constraints():
    from pipeline.kimodo import runner
    cmd = runner.gen_command("a soldier raises his spear", "/clips/spear",
                             constraints="/clips/spear_constraints.json")
    assert cmd[cmd.index("--constraints") + 1] == "/clips/spear_constraints.json"
    assert "--constraints" not in runner.gen_command("x", "/clips/x")


def test_rig_map_carries_the_model_joint_order():
    """Constraint files are indexed by kimodo's SOMASkeleton77 order."""
    from pipeline.kimodo import retarget
    data = retarget.load_rig_map()
    model = data["source"]["model_joints"]
    assert len(model) == 77
    assert model[0] == "Hips"
    assert data["source"]["joints"] == ["Root"] + model   # BVH = Root + model joints
    assert len(data["source"]["model_parents"]) == 77
    assert data["source"]["model_parents"][0] == -1
