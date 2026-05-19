# Houdini runs this when a new (empty) scene is created.
# Clear pipeline vars so a fresh scene doesn't inherit context from the previous session.

import logging

_log = logging.getLogger("pipeline")

try:
    from pipeline import context as _ctx
    _ctx.apply_to_houdini(None)
    _log.info("pipeline vars cleared (new scene)")
    print("pipeline vars cleared (new scene)")
except Exception as _e:
    _log.exception("pipeline vars: clear-on-new-scene failed")
    print("pipeline vars: clear-on-new-scene failed: %s" % _e)
