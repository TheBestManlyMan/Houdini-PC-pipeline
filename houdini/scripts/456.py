# Houdini runs this on every hip-file load (any file under $HOUDINI_PATH/scripts/456.py).
# Pipeline vars ($PROJECT, $SEQ, $SHOT, $ASSETTYPE, $ASSET, $TASK, $VER) are applied
# from the current HIP path, or cleared if the hip is outside the pipeline layout.
#
# Logs to the "pipeline" logger and prints to stdout (Python Shell) — no UI popups
# because this hook fires on every load.

import logging

_log = logging.getLogger("pipeline")

try:
    from pipeline import context as _ctx
    _vars = _ctx.apply_from_current_hip()
    _nonempty = {k: v for k, v in _vars.items() if v}
    if _nonempty:
        _msg = "pipeline vars applied: " + "  ".join(
            "$%s=%s" % (k, v) for k, v in _nonempty.items()
        )
        _log.info(_msg)
        print(_msg)
    else:
        _msg = "pipeline vars cleared (hip outside projects_root or layout mismatch)"
        _log.info(_msg)
        print(_msg)
except Exception as _e:
    _log.exception("pipeline vars: hook failed")
    print("pipeline vars: hook failed: %s" % _e)
