"""
Houdini side of the Kimodo bridge — the SOMA BVH import network.

Builds (or refreshes) one predictable network per scene::

    /obj/kimodo_import
        mocap_anim   kinefx::mocapimport, BioVision, scale 0.01, Output: Animation
        mocap_rest   same file, Output: Rest Pose   (the SOMA rest — never frame 1)
        OUT          null <- mocap_anim   (display/render)
        OUT_REST     null <- mocap_rest

Downstream retargeting object-merges ``OUT`` and ``OUT_REST``, so pointing the
network at a new clip is enough to swap the motion.  The rest branch exists
because KineFX retargeting needs the real rest pose as its source, not the
first animated frame.

This is the only module in the package that imports ``hou``.
"""

import os

import hou

from . import clips, config

CONTAINER = "kimodo_import"
ANIM_NODE = "mocap_anim"
REST_NODE = "mocap_rest"
OUT_NODE = "OUT"
OUT_REST_NODE = "OUT_REST"

_FILETYPE_BIOVISION = 1  # kinefx::mocapimport filetype menu: acclaim/biovision/motanal
_OUTPUT_ANIMATION = 0    # output menu: animation/rest
_OUTPUT_REST = 1


def import_network(create: bool = True) -> hou.Node:
    """The /obj container holding the import network."""
    obj = hou.node("/obj")
    geo = obj.node(CONTAINER)
    if geo is None and create:
        geo = obj.createNode("geo", CONTAINER)
    return geo


def import_clip(bvh_path, set_frame_range: bool = True, set_fps: bool = True) -> hou.Node:
    """Point the import network at ``bvh_path``, building it if needed.

    Returns the OUT null.  Raises hou.OperationFailed if the file is missing.
    """
    path = str(bvh_path)
    if not os.path.isfile(path):
        raise hou.OperationFailed("BVH not found: %s" % path)

    geo = import_network()
    fps = clips.bvh_fps(path)

    anim = _mocap_node(geo, ANIM_NODE, _OUTPUT_ANIMATION, path, fps)
    rest = _mocap_node(geo, REST_NODE, _OUTPUT_REST, path, fps)

    out = _null(geo, OUT_NODE, anim)
    _null(geo, OUT_REST_NODE, rest)
    out.setDisplayFlag(True)
    out.setRenderFlag(True)
    geo.layoutChildren()

    if set_fps and abs(hou.fps() - fps) > 1e-6:
        hou.setFps(fps)
    if set_frame_range:
        frames = clips.bvh_frame_count(path) or int(hou.playbar.frameRange()[1])
        hou.playbar.setFrameRange(1, frames)
        hou.playbar.setPlaybackRange(1, frames)
        hou.setFrame(1)
    return out


def _mocap_node(geo, name, output, path, fps):
    node = geo.node(name)
    if node is None:
        node = geo.createNode("kinefx::mocapimport", name)
    node.parm("filetype").set(_FILETYPE_BIOVISION)
    node.parm("bvhfile").set(path)
    node.parm("scale").set(config.bvh_scale())
    node.parm("output").set(output)
    # Kimodo writes 30 Hz; pin it rather than inheriting the scene rate.
    node.parm("useframerate").set(1)
    node.parm("framerate").set(fps)
    node.parm("reload").pressButton()
    return node


def _null(geo, name, source):
    node = geo.node(name)
    if node is None:
        node = geo.createNode("null", name)
    node.setInput(0, source)
    return node


# --------------------------------------------------------------------- retarget
# SOMA -> canonical Mixamo. The whole network is derived from the rig map plus
# measurements taken off the two skeletons in the scene, so it self-calibrates
# for any Mixamo-named target rig.
#
#   SRC_ANIM ─ SRC_SCALE_ANIM ─┐
#                              ├─ SRC_STASH ──────────────┐   (source rest = SOMA T-pose)
#   SRC_REST ─ SRC_SCALE_REST ─┘                          │
#                                                         │
#   TGT_REST ─ MAP ─ TGT_TPOSE_POSE ─ TGT_TPOSE ──────────┴─ FBIK ─ OUT_RETARGET
#
# Two rest-pose facts drive the design (both measured, see the rig map):
#   * The Mixamo rig rests in an A-pose and SOMA in a T-pose. Feeding FBIK the
#     A-pose rest leaves the arms ~47 deg off; levelling the arms into a T-pose
#     first brings the mean bone error from 17.9 deg to 7.3 deg.
#   * Size matching goes on the source (leg-length ratio), never on the target:
#     Rig Match Pose's bbox match resizes the Mixamo rig to the SOMA bounds.

RETARGET_CONTAINER = "kimodo_retarget"
RETARGET_OUT = "OUT_RETARGET"
DEFAULT_TARGET_SKELETON = "/obj/Soldier_Rig/Capture_Pose"


def build_retarget(target_skeleton: str = DEFAULT_TARGET_SKELETON,
                   rig_map: str = "soma_mixamo",
                   container: str = RETARGET_CONTAINER,
                   scale_source: bool = True,
                   source_anim: str = None,
                   source_rest: str = None) -> hou.Node:
    """Build (or refresh) the SOMA -> Mixamo retarget network. Returns its OUT null.

    ``target_skeleton`` is the SOP path of the Mixamo *capture pose* (rest)
    skeleton — leaf joints missing from it are never mapped, see the rig map.
    ``source_anim``/``source_rest`` default to the import network, and are worth
    overriding to retarget something other than the current clip — a SOMA pose
    coming back out of the guide-pose network, say.
    """
    from . import retarget as rigmaps

    data = rigmaps.load_rig_map(rig_map)
    if source_anim is None or source_rest is None:
        src = import_network(create=False)
        if src is None:
            raise hou.OperationFailed("No %s network — import a clip first." % CONTAINER)
        source_anim = source_anim or (src.path() + "/" + OUT_NODE)
        source_rest = source_rest or (src.path() + "/" + OUT_REST_NODE)
    tgt_node = hou.node(target_skeleton)
    if tgt_node is None:
        raise hou.OperationFailed("Target skeleton not found: %s" % target_skeleton)

    geo = hou.node("/obj").node(container) or hou.node("/obj").createNode("geo", container)

    def node(kind, name):
        return geo.node(name) or geo.createNode(kind, name)

    src_anim = node("object_merge", "SRC_ANIM")
    src_anim.parm("objpath1").set(source_anim)
    src_rest = node("object_merge", "SRC_REST")
    src_rest.parm("objpath1").set(source_rest)
    tgt_rest = node("object_merge", "TGT_REST")
    tgt_rest.parm("objpath1").set(target_skeleton)

    # --- size match on the source, by leg length
    scale = 1.0
    if scale_source:
        scale = _leg_ratio(src_rest, tgt_rest, data["scale"])
    scale_anim = node("xform", "SRC_SCALE_ANIM"); scale_anim.setInput(0, src_anim)
    scale_rest = node("xform", "SRC_SCALE_REST"); scale_rest.setInput(0, src_rest)
    for n in (scale_anim, scale_rest):
        n.parmTuple("s").set((scale, scale, scale))

    # --- the source's rest pose is the SOMA T-pose, never frame 1
    stash = node("kinefx::rigstashpose", "SRC_STASH")
    stash.setInput(0, scale_anim); stash.setInput(1, scale_rest)
    stash.parm("mode").set("store")
    stash.parm("attrib_name").set("rest_transform")

    # --- joint correspondence (selection strings, target <- source)
    mapping = node("kinefx::mappoints", "MAP")
    mapping.setInput(0, tgt_rest); mapping.setInput(1, stash)
    mapping.parm("reftype").set("attribvalue")
    mapping.parm("referenceattrib").set("name")
    pairs = sorted(data["joint_map"].items())
    mapping.parm("mappings").set(len(pairs))
    for i, (soma, mixamo) in enumerate(pairs):
        mapping.parm("from%d" % i).set('@name="%s"' % mixamo)
        mapping.parm("to%d" % i).set('@name="%s"' % soma)

    # --- A-pose -> T-pose, so both rests agree
    pose = node("kinefx::rigpose", "TGT_TPOSE_POSE")
    pose.setInput(0, mapping)
    pose.parm("worldspace").set(0)   # world space is a no-op on this node
    _level_bones(pose, mapping, data["target"]["tpose_level_bones"])

    tpose = node("kinefx::rigstashpose", "TGT_TPOSE")
    tpose.setInput(0, mapping); tpose.setInput(1, pose)
    tpose.parm("mode").set("store")
    tpose.parm("attrib_name").set("rest_transform")

    # --- solve
    fbik = node("kinefx::fullbodyik", "FBIK")
    fbik.setInput(0, tpose); fbik.setInput(1, stash)
    fbik.parm("mapusing").set("mappingattrib")
    fbik.parm("computeoffsets").set(1)   # absorbs the remaining rest difference
    fbik.parm("userestpose").set(1)
    fbik.parm("restposeattrib").set("rest_transform")

    out = node("null", RETARGET_OUT)
    out.setInput(0, fbik)
    out.setDisplayFlag(True)
    out.setRenderFlag(True)
    geo.layoutChildren()
    return out


def _leg_ratio(src_rest, tgt_rest, spec) -> float:
    """target leg length / source leg length, measured off the two rest poses."""
    def length(node, joints):
        pts = {p.attribValue("name"): p.position() for p in node.geometry().points()}
        return sum((pts[b] - pts[a]).length() for a, b in zip(joints, joints[1:]))
    src = length(src_rest, spec["source_bones"])
    tgt = length(tgt_rest, spec["target_bones"])
    return tgt / src if src else 1.0


def _level_bones(pose, mapping, bones):
    """Solve each joint's local X rotation so its bone is horizontal (a T-pose).

    Rig Pose only takes point numbers, and the rotation axis that matters is
    local X for a Mixamo arm — so the angle is solved from the rig itself with
    two samples rather than assumed.
    """
    import math

    numbers = {p.attribValue("name"): p.number() for p in mapping.geometry().points()}
    pose.parm("transformations").set(len(bones))
    for i, (joint, child) in enumerate(bones):
        pose.parm("enable%d" % i).set(1)
        pose.parm("group%d" % i).set(str(numbers[joint]))
        pose.parmTuple("r%d" % i).set((0.0, 0.0, 0.0))

    def elevation(a, b):
        pts = {p.attribValue("name"): p.position() for p in pose.geometry().points()}
        v = pts[b] - pts[a]
        return math.degrees(math.asin(max(-1.0, min(1.0, v[1] / v.length()))))

    for i, (joint, child) in enumerate(bones):
        base = elevation(joint, child)
        pose.parm("r%dx" % i).set(-20.0)
        slope = (elevation(joint, child) - base) / -20.0
        pose.parm("r%dx" % i).set(-base / slope if abs(slope) > 1e-6 else 0.0)


# ------------------------------------------------- reverse retarget (guide poses)
# Mixamo hero poses -> SOMA, so a few keyed frames can be handed to Kimodo as
# full-body constraints.  Mirror image of build_retarget(): there the Mixamo rig
# is the target and needs a T-posed rest; here it is the *source*, so the T-pose
# goes on the source side and SOMA (already a T-pose) is the target.
#
#   SRC_MIXAMO ─ SRC_SCALE ─────────────┐
#                                       ├─ SRC_STASH ─┐
#   SRC_REST ─ SRC_TPOSE ─ SRC_SCALE_REST┘             │
#                                                      │
#   TGT_SOMA_REST ─ TGT_STASH ─ MAP ──────────────────┴─ FBIK ─ OUT_GUIDE

GUIDE_CONTAINER = "kimodo_guide"
GUIDE_OUT = "OUT_GUIDE"
SOLDIER_CONTAINER = "/obj/Soldier_Rig"
DEFAULT_GUIDE_SOURCE = SOLDIER_CONTAINER + "/Animated_Pose"


def guide_source_default(container: str = SOLDIER_CONTAINER) -> str:
    """Where the hero poses are read from when the caller doesn't say.

    A Rig Pose SOP in the soldier container is where blocking gets authored, so
    the last one wins; then whatever is flagged for display, if it is a Mixamo
    skeleton; then the FBX's animated branch. Guessing is only ever a
    convenience — pass an explicit path when it matters.
    """
    geo = hou.node(container)
    if geo is None:
        return DEFAULT_GUIDE_SOURCE
    poses = [c for c in geo.children() if c.type().name().startswith("kinefx::rigpose")]
    if poses:
        return poses[-1].path()
    display = geo.displayNode() if hasattr(geo, "displayNode") else None
    if display is not None and _is_mixamo_skeleton(display):
        return display.path()
    return DEFAULT_GUIDE_SOURCE


def _is_mixamo_skeleton(node) -> bool:
    try:
        geo = node.geometry()
    except hou.Error:
        return False
    if geo is None or geo.findPointAttrib("name") is None:
        return False
    return any(p.attribValue("name").startswith("mixamorig:") for p in geo.points())


def build_reverse_retarget(source_skeleton: str = None,
                           source_rest: str = DEFAULT_TARGET_SKELETON,
                           rig_map: str = "soma_mixamo",
                           container: str = GUIDE_CONTAINER,
                           scale_source: bool = True) -> hou.Node:
    """Build (or refresh) the Mixamo -> SOMA network. Returns its OUT null.

    ``source_skeleton`` is the *animated* Mixamo skeleton the animator poses;
    ``source_rest`` its capture pose.  The SOMA side comes from the import
    network's rest branch, so a clip must have been imported first.
    """
    from . import retarget as rigmaps

    source_skeleton = source_skeleton or guide_source_default()
    data = rigmaps.load_rig_map(rig_map)
    imported = import_network(create=False)
    if imported is None:
        raise hou.OperationFailed(
            "No %s network — import a clip first, the SOMA rest comes from it." % CONTAINER)
    for path in (source_skeleton, source_rest):
        if hou.node(path) is None:
            raise hou.OperationFailed("Skeleton not found: %s" % path)

    geo = hou.node("/obj").node(container) or hou.node("/obj").createNode("geo", container)

    def node(kind, name):
        return geo.node(name) or geo.createNode(kind, name)

    src_anim = node("object_merge", "SRC_MIXAMO")
    src_anim.parm("objpath1").set(source_skeleton)
    src_rest = node("object_merge", "SRC_REST")
    src_rest.parm("objpath1").set(source_rest)
    tgt_rest = node("object_merge", "TGT_SOMA_REST")
    tgt_rest.parm("objpath1").set(imported.path() + "/" + OUT_REST_NODE)

    # --- Mixamo A-pose -> T-pose, so it agrees with SOMA's rest
    pose = node("kinefx::rigpose", "SRC_TPOSE")
    pose.setInput(0, src_rest)
    pose.parm("worldspace").set(0)
    _level_bones(pose, src_rest, data["target"]["tpose_level_bones"])

    # --- size match: shrink the Mixamo rig to SOMA's proportions (inverse of forward)
    scale = 1.0
    if scale_source:
        scale = 1.0 / _leg_ratio(tgt_rest, src_rest, data["scale"])
    scale_anim = node("xform", "SRC_SCALE"); scale_anim.setInput(0, src_anim)
    scale_rest = node("xform", "SRC_SCALE_REST"); scale_rest.setInput(0, pose)
    for n in (scale_anim, scale_rest):
        n.parmTuple("s").set((scale, scale, scale))

    stash = node("kinefx::rigstashpose", "SRC_STASH")
    stash.setInput(0, scale_anim); stash.setInput(1, scale_rest)
    stash.parm("mode").set("store")
    stash.parm("attrib_name").set("rest_transform")
    stash.parm("matchbyattribute").set(1)
    stash.parm("attributetomatch").set("name")

    # --- SOMA is its own rest (the standard T-pose out of the BVH)
    tgt_stash = node("kinefx::rigstashpose", "TGT_STASH")
    tgt_stash.setInput(0, tgt_rest); tgt_stash.setInput(1, tgt_rest)
    tgt_stash.parm("mode").set("store")
    tgt_stash.parm("attrib_name").set("rest_transform")

    # --- correspondence, target(SOMA) <- source(Mixamo): the same map, read the other way
    mapping = node("kinefx::mappoints", "MAP")
    mapping.setInput(0, tgt_stash); mapping.setInput(1, stash)
    mapping.parm("reftype").set("attribvalue")
    mapping.parm("referenceattrib").set("name")
    pairs = sorted(data["joint_map"].items())
    mapping.parm("mappings").set(len(pairs))
    for i, (soma, mixamo) in enumerate(pairs):
        mapping.parm("from%d" % i).set('@name="%s"' % soma)
        mapping.parm("to%d" % i).set('@name="%s"' % mixamo)

    fbik = node("kinefx::fullbodyik", "FBIK")
    fbik.setInput(0, mapping); fbik.setInput(1, stash)
    fbik.parm("mapusing").set("mappingattrib")
    fbik.parm("computeoffsets").set(1)
    fbik.parm("userestpose").set(1)
    fbik.parm("restposeattrib").set("rest_transform")

    out = node("null", GUIDE_OUT)
    out.setInput(0, fbik)
    out.setDisplayFlag(True)
    out.setRenderFlag(True)
    geo.layoutChildren()
    return out


# --------------------------------------------------------------- pose sampling

def soma_pose(node, frame, model_joints, model_parents):
    """Read one SOMA pose off a KineFX skeleton.

    Returns ``(local_rot, root_position, positions)`` where ``local_rot`` holds a
    flat row-major 3x3 per joint in *column-vector* convention — the same numbers
    a standard-T-pose SOMA BVH carries, which is what Kimodo stores as
    ``local_rot_mats``.  Houdini's point ``transform`` is row-vector and carries
    the import scale, so it is transposed and orthonormalised first.

    The model has no equivalent of the BVH's ``Root`` wrapper — ``Hips`` is the
    root — so Hips' local rotation is its world rotation. Reading it relative to
    the Root joint instead silently drops whatever rotation Root has picked up
    (Full Body IK leaves ~2.5 deg on it), which tilts the whole body: invisible
    at the hips, 32 mm out at the fingertips.
    """
    geo = node.geometryAtFrame(frame)
    points = {p.attribValue("name"): p for p in geo.points()}

    missing = [j for j in model_joints if j not in points]
    if missing:
        raise hou.OperationFailed(
            "Skeleton is missing %d SOMA joints (%s...)" % (len(missing), missing[0]))

    world = {}
    for name in model_joints:
        m = hou.Matrix3(points[name].attribValue("transform")).transposed()
        cols = [hou.Vector3(m.at(0, c), m.at(1, c), m.at(2, c)).normalized() for c in range(3)]
        world[name] = [[cols[c][r] for c in range(3)] for r in range(3)]

    positions = [list(points[name].position()) for name in model_joints]

    identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    local_rot = []
    for i, name in enumerate(model_joints):
        parent = model_parents[i]
        R = world[name]
        P = identity if parent < 0 else world[model_joints[parent]]
        # local = parent^T * world, column-vector convention
        loc = [[sum(P[k][r] * R[k][c] for k in range(3)) for c in range(3)] for r in range(3)]
        local_rot.append([v for row in loc for v in row])

    root = list(points[model_joints[0]].position())
    return local_rot, root, positions


def sample_guide_poses(frames, node=None, rig_map: str = "soma_mixamo",
                       start_frame=None, source_skeleton=None):
    """Sample the SOMA guide poses for ``frames`` (Houdini frame numbers).

    Returns a list of :class:`pipeline.kimodo.constraints.GuidePose`.  ``node``
    defaults to the reverse-retarget output, built if it does not exist yet.
    """
    from . import constraints as guides
    from . import retarget as rigmaps

    data = rigmaps.load_rig_map(rig_map)
    model_joints = data["source"]["model_joints"]
    model_parents = data["source"]["model_parents"]

    if node is None:
        geo = hou.node("/obj").node(GUIDE_CONTAINER)
        node = geo.node(GUIDE_OUT) if geo else None
        if node is None:
            node = build_reverse_retarget(rig_map=rig_map,
                                          source_skeleton=source_skeleton)

    if start_frame is None:
        start_frame = int(hou.playbar.frameRange()[0])

    poses = []
    for frame in frames:
        local_rot, root, positions = soma_pose(node, frame, model_joints, model_parents)
        poses.append(guides.GuidePose(
            houdini_frame=int(frame),
            kimodo_frame=guides.to_kimodo_frame(frame, start_frame),
            root_position=root,
            local_rot=local_rot,
            positions=positions))
    return poses


def prepare_guide_constraints(stem: str, frames, rig_map: str = "soma_mixamo",
                              source_skeleton: str = None,
                              start_frame=None, end_frame=None, node=None) -> dict:
    """Hero frames -> a Kimodo constraints file, ready to generate against.

    ``frames`` is either the raw text the animator typed or a list of frame
    numbers.  The clip duration is derived from the Houdini frame range rather
    than asked for, so it can never stop short of the last hero pose.

    Returns everything the caller needs to launch and to record the run.
    """
    from . import clips as cliplib
    from . import constraints as guides
    from . import retarget as rigmaps

    source_skeleton = source_skeleton or guide_source_default()
    scene_start, scene_end = (int(round(v)) for v in hou.playbar.frameRange())
    if start_frame is None:
        start_frame = scene_start
    start_frame = int(start_frame)

    # Guide frames must exist in the scene, but the clip only has to run from the
    # start frame to the last hero pose — deriving the end from the scene range
    # would make a 12 s clip out of a 40-frame blocking.
    if isinstance(frames, str):
        frames = guides.parse_guide_frames(frames, scene_start, scene_end)
    else:
        frames = guides.parse_guide_frames(
            ",".join(str(int(f)) for f in frames), scene_start, scene_end)
    if end_frame is None:
        end_frame = max(frames)
    end_frame = int(end_frame)
    if end_frame < max(frames):
        raise hou.OperationFailed(
            "Clip ends on frame %d, before guide frame %d." % (end_frame, max(frames)))

    fps = float(hou.fps())
    duration = guides.duration_for_range(start_frame, end_frame, fps)
    if not guides.covers_frames(frames, start_frame, duration, fps):
        raise hou.OperationFailed(
            "A %.2fs clip at %g fps does not reach guide frame %d."
            % (duration, fps, max(frames)))

    poses = sample_guide_poses(frames, node=node, rig_map=rig_map,
                               start_frame=start_frame,
                               source_skeleton=source_skeleton)

    data = rigmaps.load_rig_map(rig_map)
    joint_names = data["source"]["model_joints"]
    root = cliplib.ensure_clips_root()
    guide_path = guides.write_guide_poses(
        guides.guide_poses_path(stem, root), poses, joint_names, fps,
        houdini_start_frame=start_frame, houdini_end_frame=end_frame,
        source_skeleton=source_skeleton, rig_map=rig_map)
    constraints_path = guides.write_constraints(
        guides.constraints_json_path(stem, root), poses,
        joint_count=len(joint_names))

    return {
        "stem": stem,
        "guide_frames": frames,
        "kimodo_frames": [p.kimodo_frame for p in poses],
        "constraints": constraints_path,
        "guide_poses": guide_path,
        "duration": duration,
        "fps": fps,
        "houdini_start_frame": start_frame,
        "houdini_end_frame": end_frame,
        "source_skeleton": source_skeleton,
        "rig_map": rig_map,
    }
