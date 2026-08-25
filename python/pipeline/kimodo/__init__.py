"""
Kimodo text-to-motion bridge.

Kimodo runs as an external process against its own venv; Houdini never imports
it.  Layout:

    config.py   where the install lives, child-process environment
    clips.py    the motion clip library (paths, sidecars, BVH probing)
    runner.py   command building + blocking execution (hython/TOPs safe)
    retarget.py SOMA -> Mixamo rig map data + validation
    job.py      QProcess sequencer for the UI            (imports Qt)
    scene.py    the /obj/kimodo_import BVH network       (imports hou)

``job`` and ``scene`` are deliberately NOT re-exported here — importing this
package must stay possible outside Houdini and outside a Qt app.
"""

from . import clips, config, retarget, runner
from .runner import KimodoError, generate_clip

__all__ = ["clips", "config", "retarget", "runner",
           "KimodoError", "generate_clip"]
