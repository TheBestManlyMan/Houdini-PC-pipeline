"""
Viewport flipbook capture (requires Houdini).
"""

import logging

logger = logging.getLogger("pipeline")


def flipbook_viewport(jpg_seq_path: str, frame_range: tuple,
                       camera: str = None, resolution: tuple = (1280, 720),
                       scene_viewer=None) -> None:
    try:
        import hou
    except ImportError:
        raise RuntimeError("Must run inside Houdini.")

    if scene_viewer is None:
        for pane in hou.ui.paneTabs():
            if pane.type() == hou.paneTabType.SceneViewer:
                scene_viewer = pane
                break
    if scene_viewer is None:
        raise RuntimeError("No SceneViewer tab found.")

    sv = scene_viewer
    settings = sv.flipbookSettings().stash()
    settings.frameRange(frame_range)
    settings.outputToMPlay(False)
    settings.output(jpg_seq_path)
    settings.resolution(resolution)

    if camera:
        cam_node = hou.node(camera)
        if cam_node:
            viewport = sv.curViewport()
            viewport.setCamera(cam_node)

    sv.flipbook(settings=settings)
    logger.info("Flipbook captured: %s  frames %s–%s", jpg_seq_path, *frame_range)
