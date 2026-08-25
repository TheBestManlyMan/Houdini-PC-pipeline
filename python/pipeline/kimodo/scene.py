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
