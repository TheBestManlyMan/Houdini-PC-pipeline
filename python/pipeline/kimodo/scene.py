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
                   scale_source: bool = True) -> hou.Node:
    """Build (or refresh) the SOMA -> Mixamo retarget network. Returns its OUT null.

    ``target_skeleton`` is the SOP path of the Mixamo *capture pose* (rest)
    skeleton — leaf joints missing from it are never mapped, see the rig map.
    """
    from . import retarget as rigmaps

    data = rigmaps.load_rig_map(rig_map)
    src = import_network(create=False)
    if src is None:
        raise hou.OperationFailed("No %s network — import a clip first." % CONTAINER)
    tgt_node = hou.node(target_skeleton)
    if tgt_node is None:
        raise hou.OperationFailed("Target skeleton not found: %s" % target_skeleton)

    geo = hou.node("/obj").node(container) or hou.node("/obj").createNode("geo", container)

    def node(kind, name):
        return geo.node(name) or geo.createNode(kind, name)

    src_anim = node("object_merge", "SRC_ANIM")
    src_anim.parm("objpath1").set(src.path() + "/" + OUT_NODE)
    src_rest = node("object_merge", "SRC_REST")
    src_rest.parm("objpath1").set(src.path() + "/" + OUT_REST_NODE)
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
