"""
Hero keyframes -> Kimodo full-body constraints.

The animator poses the Mixamo soldier on a few frames, types those frame
numbers, and Kimodo generates the motion between them.  This module owns
everything about that except the two ends: sampling poses out of Houdini
(:mod:`pipeline.kimodo.scene`) and the torch-side conversion into Kimodo's own
constraint format (``scripts/build_constraints.py``, run in the Kimodo venv).

Frame numbers matter here. Houdini frames are 1-based by convention but the
start frame is whatever the scene says; Kimodo frame indices are 0-based from
the start of the generated clip::

    kimodo_frame = houdini_frame - start_frame

Nothing in this module imports hou, Qt, kimodo or torch.

Interchange file (written here, read by the venv script)::

    {stem}_guide_poses.json   SOMA poses at the guide frames, standard-T-pose
                              local rotations straight off the Houdini skeleton
    {stem}_constraints.json   Kimodo's own format, written by the venv script
"""

import json
from pathlib import Path

MIN_GUIDE_FRAMES = 2
_SCHEMA_VERSION = 1


class GuideFrameError(ValueError):
    """The typed guide frames cannot be used."""


def parse_guide_frames(text, start_frame=None, end_frame=None) -> list:
    """``"1, 12, 26, 40"`` -> ``[1, 12, 26, 40]``.

    Whitespace is ignored, duplicates collapse, the result is sorted. Raises
    :class:`GuideFrameError` on a non-integer token, on fewer than two distinct
    frames, or on anything outside ``[start_frame, end_frame]`` when a range is
    given.
    """
    if text is None:
        raise GuideFrameError("No guide frames given.")

    tokens = [t.strip() for t in str(text).replace(";", ",").split(",")]
    tokens = [t for t in tokens if t]
    if not tokens:
        raise GuideFrameError("No guide frames given.")

    frames = []
    for token in tokens:
        try:
            value = int(token)
        except ValueError:
            raise GuideFrameError("Not a frame number: %r" % token)
        frames.append(value)

    frames = sorted(set(frames))
    if len(frames) < MIN_GUIDE_FRAMES:
        raise GuideFrameError(
            "Need at least %d distinct guide frames, got %d."
            % (MIN_GUIDE_FRAMES, len(frames)))

    if start_frame is not None or end_frame is not None:
        lo = int(start_frame) if start_frame is not None else frames[0]
        hi = int(end_frame) if end_frame is not None else frames[-1]
        outside = [f for f in frames if f < lo or f > hi]
        if outside:
            raise GuideFrameError(
                "Outside the frame range %d-%d: %s"
                % (lo, hi, ", ".join(str(f) for f in outside)))
    return frames


def to_kimodo_frame(houdini_frame: int, start_frame: int) -> int:
    """Houdini frame -> 0-based Kimodo frame index."""
    return int(houdini_frame) - int(start_frame)


def to_kimodo_frames(frames, start_frame: int) -> list:
    return [to_kimodo_frame(f, start_frame) for f in frames]


def duration_for_range(start_frame: int, end_frame: int, fps: float) -> float:
    """Clip duration in seconds covering ``[start_frame, end_frame]`` inclusive.

    Deriving the duration from the frame range keeps it in sync with the guide
    frames — a duration that stops short of the last hero pose would silently
    drop that constraint.
    """
    frames = int(end_frame) - int(start_frame) + 1
    if frames < 1:
        raise GuideFrameError("Frame range %s-%s is empty." % (start_frame, end_frame))
    return frames / float(fps)


def covers_frames(guide_frames, start_frame: int, duration: float, fps: float) -> bool:
    """Does a clip of ``duration`` starting at ``start_frame`` reach every guide frame?"""
    generated = int(round(float(duration) * float(fps)))
    last = to_kimodo_frame(max(guide_frames), start_frame)
    return 0 <= min(to_kimodo_frames(guide_frames, start_frame)) and last < generated


class GuidePose:
    """One sampled SOMA pose destined for a Kimodo constraint.

    ``local_rot`` holds one flat row-major 3x3 rotation per SOMA joint, in the
    model's joint order (77 for SOMA), column-vector convention — the same
    numbers a standard-T-pose SOMA BVH carries, which is exactly what Kimodo
    stores as ``local_rot_mats``. ``root_position`` is the world position of
    ``Hips`` in metres. ``positions`` (optional) is the world position of every
    joint, kept only so the constraint can be checked against the pose it came
    from.
    """

    __slots__ = ("houdini_frame", "kimodo_frame", "root_position", "local_rot",
                 "positions")

    def __init__(self, houdini_frame, kimodo_frame, root_position, local_rot,
                 positions=None):
        self.houdini_frame = int(houdini_frame)
        self.kimodo_frame = int(kimodo_frame)
        self.root_position = [float(v) for v in root_position]
        self.local_rot = [[float(v) for v in row] for row in local_rot]
        self.positions = ([[float(v) for v in p] for p in positions]
                          if positions is not None else None)

    def as_dict(self) -> dict:
        data = {
            "houdini_frame": self.houdini_frame,
            "kimodo_frame": self.kimodo_frame,
            "root_position": self.root_position,
            "local_rot": self.local_rot,
        }
        if self.positions is not None:
            data["positions"] = self.positions
        return data

    def __repr__(self):
        return "GuidePose(houdini_frame=%d, kimodo_frame=%d, joints=%d)" % (
            self.houdini_frame, self.kimodo_frame, len(self.local_rot))


def guide_poses_path(stem: str, root=None) -> Path:
    """``{clips_root}/{stem}_guide_poses.json`` — the interchange file."""
    from . import clips
    return clips.clip_path(stem + "_guide_poses", ".json", root)


def constraints_json_path(stem: str, root=None) -> Path:
    """``{clips_root}/{stem}_constraints.json`` — Kimodo's own format."""
    from . import clips
    return clips.clip_path(stem + "_constraints", ".json", root)


def write_guide_poses(path, poses, joint_names, fps: float, **meta) -> Path:
    """Write the interchange file the venv-side constraint builder reads."""
    if len(poses) < MIN_GUIDE_FRAMES:
        raise GuideFrameError("Need at least %d guide poses." % MIN_GUIDE_FRAMES)
    seen = set()
    for pose in poses:
        if len(pose.local_rot) != len(joint_names):
            raise GuideFrameError(
                "Pose on frame %d has %d joints, skeleton has %d."
                % (pose.houdini_frame, len(pose.local_rot), len(joint_names)))
        if pose.kimodo_frame in seen:
            raise GuideFrameError("Duplicate Kimodo frame %d." % pose.kimodo_frame)
        if pose.kimodo_frame < 0:
            raise GuideFrameError(
                "Guide frame %d is before the clip start." % pose.houdini_frame)
        seen.add(pose.kimodo_frame)

    payload = {
        "version": _SCHEMA_VERSION,
        "fps": float(fps),
        "rest": "standard_tpose",
        "joint_names": list(joint_names),
        "frames": [p.as_dict() for p in sorted(poses, key=lambda p: p.kimodo_frame)],
    }
    payload.update(meta)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return path


def read_guide_poses(path) -> dict:
    return json.loads(Path(path).read_text())


# ------------------------------------------------------- Kimodo constraint file
# Schema, verified against Kimodo's own
# assets/demo/examples/kimodo-soma-rp/03_full_body_keyframes/constraints.json and
# FullBodyConstraintSet.from_dict:
#
#   [{"type": "fullbody",
#     "frame_indices":    [F]        0-based frame index per pose
#     "local_joints_rot": [F][J][3]  axis-angle, model joint order
#     "root_positions":   [F][3]     Hips world position, metres
#   }]
#
# smooth_root_2d is optional — omitted, so Kimodo derives it from the root itself.

CONSTRAINT_TYPE = "fullbody"


def matrix_to_axis_angle(rot) -> list:
    """Row-major 3x3 (column-vector convention) -> axis-angle vector.

    Matches Kimodo's ``matrix_to_axis_angle``: the returned vector is the
    rotation axis scaled by the angle in radians.
    """
    import math

    m = list(rot)
    if len(m) == 3 and all(isinstance(r, (list, tuple)) for r in m):
        m = [v for row in m for v in row]
    if len(m) != 9:
        raise ValueError("Expected a 3x3 rotation, got %d values" % len(m))

    trace = m[0] + m[4] + m[8]
    cos = max(-1.0, min(1.0, (trace - 1.0) / 2.0))
    angle = math.acos(cos)

    if angle < 1e-8:
        return [0.0, 0.0, 0.0]

    if math.pi - angle > 1e-5:
        scale = angle / (2.0 * math.sin(angle))
        return [scale * (m[7] - m[5]), scale * (m[2] - m[6]), scale * (m[3] - m[1])]

    # Near pi the skew part vanishes; recover the axis from the diagonal.
    axis = [math.sqrt(max(0.0, (m[0] + 1.0) / 2.0)),
            math.sqrt(max(0.0, (m[4] + 1.0) / 2.0)),
            math.sqrt(max(0.0, (m[8] + 1.0) / 2.0))]
    largest = axis.index(max(axis))
    if largest == 0:
        axis[1] = math.copysign(axis[1], m[1] + m[3])
        axis[2] = math.copysign(axis[2], m[2] + m[6])
    elif largest == 1:
        axis[0] = math.copysign(axis[0], m[1] + m[3])
        axis[2] = math.copysign(axis[2], m[5] + m[7])
    else:
        axis[0] = math.copysign(axis[0], m[2] + m[6])
        axis[1] = math.copysign(axis[1], m[5] + m[7])
    norm = math.sqrt(sum(v * v for v in axis)) or 1.0
    return [angle * v / norm for v in axis]


def build_constraint_payload(poses, joint_count=None) -> list:
    """The list of constraint dicts Kimodo's ``--constraints`` file holds."""
    poses = sorted(poses, key=lambda p: p.kimodo_frame)
    if len(poses) < MIN_GUIDE_FRAMES:
        raise GuideFrameError("Need at least %d guide poses." % MIN_GUIDE_FRAMES)
    counts = {len(p.local_rot) for p in poses}
    if len(counts) != 1:
        raise GuideFrameError("Guide poses disagree on joint count: %s" % sorted(counts))
    if joint_count is not None and counts != {int(joint_count)}:
        raise GuideFrameError(
            "Guide poses have %d joints, the skeleton has %d."
            % (counts.pop(), int(joint_count)))

    return [{
        "type": CONSTRAINT_TYPE,
        "frame_indices": [p.kimodo_frame for p in poses],
        "local_joints_rot": [[matrix_to_axis_angle(rot) for rot in p.local_rot]
                             for p in poses],
        "root_positions": [p.root_position for p in poses],
    }]


def write_constraints(path, poses, joint_count=None) -> Path:
    """Write the Kimodo constraints file. Returns the path."""
    payload = build_constraint_payload(poses, joint_count=joint_count)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return path
