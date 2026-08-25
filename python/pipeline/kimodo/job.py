"""
Non-blocking Kimodo generation for Houdini's UI thread.

Sequences ``kimodo_gen`` then ``kimodo_convert`` through QProcess so Houdini
stays responsive while the model runs (a 4 s clip is minutes of GPU work).
Commands, environment and clip paths all come from the sibling modules — this
file only owns the state machine.

Qt is imported here and nowhere else in the package, so hython/pytest can use
:mod:`pipeline.kimodo.runner` without a Qt binding.
"""

import time

try:
    from PySide6 import QtCore
except ImportError:  # older builds
    from PySide2 import QtCore

from . import clips, config, runner


class KimodoJob(QtCore.QObject):
    """One prompt -> one BVH, asynchronously.

    Signals:
        log(str)                 a line of subprocess output, or a status note
        stage(str)               "generate" / "convert" / "done" / "failed"
        finished(bool, str)      (ok, bvh path or error message)
    """

    log = QtCore.Signal(str)
    stage = QtCore.Signal(str)
    finished = QtCore.Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._stage = None
        self._t0 = None
        self._cancelled = False
        self.stem = None
        self.npz = None
        self.bvh = None

    # -------------------------------------------------------------- lifecycle
    def is_running(self) -> bool:
        return (self._proc is not None
                and self._proc.state() != QtCore.QProcess.NotRunning)

    def start(self, prompt: str, duration: float = 4.0, steps: int = 30,
              seed=None, name: str = "", model: str = ""):
        """Kick off generation. Returns False if it could not start."""
        if self.is_running():
            self._emit("Already generating.")
            return False

        problems = config.problems()
        if problems:
            self._fail("; ".join(problems))
            return False

        prompt = (prompt or "").strip()
        if not prompt:
            self._fail("No prompt.")
            return False

        root = clips.ensure_clips_root()
        self.stem = clips.unique_stem(name or prompt, root)
        self.npz = clips.npz_path(self.stem, root)
        self.bvh = clips.bvh_path(self.stem, root)
        self._prompt = prompt
        self._duration = float(duration)
        self._steps = int(steps)
        self._seed = seed
        self._model = model
        self._cancelled = False
        self._t0 = time.time()

        self._emit('Generating "%s"  (%.1fs, %d steps, seed %s)'
                   % (prompt, self._duration, self._steps,
                      "random" if seed is None or int(seed) < 0 else seed))
        self._emit("-> %s" % self.bvh)
        self._run("generate", runner.gen_command(
            prompt, self.npz.with_suffix(""), duration=self._duration,
            steps=self._steps, seed=seed, model=model))
        return True

    def cancel(self):
        self._cancelled = True
        if self.is_running():
            self._proc.kill()

    # ---------------------------------------------------------------- process
    def _run(self, stage, cmd):
        self._stage = stage
        self.stage.emit(stage)

        proc = QtCore.QProcess(self)
        env = QtCore.QProcessEnvironment()
        for key, value in config.child_env().items():
            env.insert(key, value)
        proc.setProcessEnvironment(env)
        proc.setWorkingDirectory(str(config.install_root()))
        proc.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_output)
        proc.finished.connect(self._on_finished)
        self._proc = proc
        proc.start(str(cmd[0]), [str(c) for c in cmd[1:]])

    def _on_output(self):
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        for line in data.splitlines():
            line = line.strip()
            if line:
                self.log.emit("    " + line)

    def _on_finished(self, code, status):
        stage = self._stage
        if self._cancelled:
            self._fail("Cancelled after %s." % self._elapsed())
            return
        if code != 0:
            self._fail("%s failed (exit %s) — see log above." % (stage, code))
            return

        if stage == "generate":
            if not self.npz.is_file():
                self._fail("kimodo_gen finished but %s was not written" % self.npz)
                return
            self._emit("NPZ written (%s). Converting to SOMA BVH..." % self._elapsed())
            self._run("convert", runner.convert_command(self.npz, self.bvh))
            return

        if not self.bvh.is_file():
            self._fail("kimodo_convert finished but %s was not written" % self.bvh)
            return

        frames = clips.bvh_frame_count(self.bvh)
        clips.write_meta(self.stem, self._prompt, self._duration, self._steps,
                         seed=self._seed, model=self._model, frames=frames)
        self._emit("Done in %s — %s frames @ %g fps."
                   % (self._elapsed(), frames, clips.bvh_fps(self.bvh)))
        self.stage.emit("done")
        self.finished.emit(True, str(self.bvh))

    # ------------------------------------------------------------------ utils
    def _elapsed(self):
        return "%.0fs" % (time.time() - self._t0) if self._t0 else "0s"

    def _emit(self, text):
        self.log.emit(time.strftime("[%H:%M:%S] ") + text)

    def _fail(self, message):
        self._emit(message)
        self.stage.emit("failed")
        self.finished.emit(False, message)
