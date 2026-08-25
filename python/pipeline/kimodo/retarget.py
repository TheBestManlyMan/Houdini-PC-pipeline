"""
SOMA -> Mixamo retarget data (Phase 4 foundation).

Only the *data* lives here for now: the joint map in config/rig_maps/ and the
checks that keep it honest.  The KineFX network (Rig Stash Pose -> Rig Match
Pose -> Map Points -> Full Body IK) is built on top of this once the map has
been validated against the canonical soldier.

Pure python — no hou, so a map can be linted outside Houdini.
"""

import json
from pathlib import Path

from ..config import _PIPELINE_ROOT

RIG_MAPS_DIR = Path(_PIPELINE_ROOT) / "config" / "rig_maps"
DEFAULT_MAP = "soma_mixamo"


def rig_map_path(name: str = DEFAULT_MAP) -> Path:
    return RIG_MAPS_DIR / (name + ".json")


def load_rig_map(name: str = DEFAULT_MAP) -> dict:
    path = rig_map_path(name)
    if not path.is_file():
        raise FileNotFoundError("No rig map at %s" % path)
    return json.loads(path.read_text())


def joint_map(name: str = DEFAULT_MAP) -> dict:
    """{soma_joint: mixamo_joint} — body only, fingers excluded by design."""
    return load_rig_map(name)["joint_map"]


def fbik_targets(name: str = DEFAULT_MAP) -> list:
    """The sparse effector set the Full Body IK solve should drive."""
    return load_rig_map(name)["fbik_targets"]


def validate(name: str = DEFAULT_MAP, source_joints=None, target_joints=None) -> list:
    """Problems with a map. Empty == usable.

    ``source_joints``/``target_joints`` let a caller check the map against the
    skeletons actually in the scene (or a BVH) rather than the recorded lists.
    """
    data = load_rig_map(name)
    src = list(source_joints if source_joints is not None else data["source"]["joints"])
    tgt = list(target_joints if target_joints is not None else data["target"]["joints"])
    issues = []

    if not data["joint_map"]:
        issues.append("joint_map is empty")
    if not tgt:
        issues.append("target skeleton has not been inspected yet")

    for s, t in data["joint_map"].items():
        if src and s not in src:
            issues.append("source joint not in skeleton: %s" % s)
        if tgt and t not in tgt:
            issues.append("target joint not in skeleton: %s" % t)

    mapped = set(data["joint_map"].values())
    for t in data.get("fbik_targets", []):
        if t not in mapped:
            issues.append("fbik target is not a mapped joint: %s" % t)

    for pair in data["target"].get("tpose_level_bones", []):
        for joint in pair:
            if tgt and joint not in tgt:
                issues.append("tpose_level_bones joint not in skeleton: %s" % joint)

    scale = data.get("scale", {})
    for joint in scale.get("source_bones", []):
        if src and joint not in src:
            issues.append("scale source bone not in skeleton: %s" % joint)
    for joint in scale.get("target_bones", []):
        if tgt and joint not in tgt:
            issues.append("scale target bone not in skeleton: %s" % joint)

    static = data["source"].get("static_joint")
    if static and static in data["joint_map"]:
        issues.append("static joint %s must not be mapped (locomotion is on %s)"
                      % (static, data["source"].get("locomotion_joint")))
    return issues
