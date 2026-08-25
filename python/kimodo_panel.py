"""
Kimodo text-to-motion Python Panel (Houdini 22).

Thin UI: collects prompt/duration/steps/seed, hands them to
``pipeline.kimodo.job.KimodoJob`` (QProcess — Houdini's UI thread never
blocks), then imports the finished SOMA BVH with ``pipeline.kimodo.scene``.
All logic lives in the pipeline package; this file only wires widgets.

Registered through houdini/python_panels/kimodo.pypanel.
"""

try:
    from PySide6 import QtCore, QtWidgets
except ImportError:  # older builds
    from PySide2 import QtCore, QtWidgets

from pipeline.kimodo import clips, config, scene
from pipeline.kimodo.job import KimodoJob


class KimodoPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._job = None
        self._build_ui()
        self._check_install()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        form = QtWidgets.QFormLayout()

        self.prompt = QtWidgets.QPlainTextEdit()
        self.prompt.setPlaceholderText(
            "A soldier stands alert with a long spear, subtly shifting his "
            "weight while watching the area ahead."
        )
        self.prompt.setFixedHeight(56)
        form.addRow("Prompt", self.prompt)

        self.duration = QtWidgets.QDoubleSpinBox()
        self.duration.setRange(0.5, 30.0)
        self.duration.setValue(4.0)
        self.duration.setSuffix(" s")
        form.addRow("Duration", self.duration)

        self.steps = QtWidgets.QSpinBox()
        self.steps.setRange(10, 300)
        self.steps.setValue(30)
        self.steps.setToolTip("Diffusion steps — lower is faster, rougher")
        form.addRow("Steps", self.steps)

        self.seed = QtWidgets.QSpinBox()
        self.seed.setRange(-1, 2 ** 31 - 1)
        self.seed.setValue(1234)
        self.seed.setSpecialValueText("random")
        self.seed.setToolTip("-1 generates a random seed. Fixed seeds reproduce a clip.")
        form.addRow("Seed", self.seed)

        self.clipname = QtWidgets.QLineEdit()
        self.clipname.setPlaceholderText("auto (from prompt)")
        form.addRow("Clip name", self.clipname)

        self.autoimport = QtWidgets.QCheckBox("Import into the scene when finished")
        self.autoimport.setChecked(True)
        form.addRow("", self.autoimport)

        btns = QtWidgets.QHBoxLayout()
        self.gen_btn = QtWidgets.QPushButton("Generate Animation")
        self.gen_btn.clicked.connect(self.generate)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel)
        self.cancel_btn.setEnabled(False)
        btns.addWidget(self.gen_btn)
        btns.addWidget(self.cancel_btn)

        self.status = QtWidgets.QLabel("Idle")
        self.status.setStyleSheet("color: #aaa;")

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("font-family: monospace; font-size: 11px;")

        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(form)
        lay.addLayout(btns)
        lay.addWidget(self.status)
        lay.addWidget(QtWidgets.QLabel("Log:"))
        lay.addWidget(self.log, stretch=1)

    def _check_install(self):
        problems = config.problems()
        if problems:
            self._set_status("Kimodo not available", error=True)
            for line in problems:
                self._log(line)
            self.gen_btn.setEnabled(False)
        else:
            self._log("Kimodo: %s" % config.install_root())
            self._log("Clips:  %s" % config.clips_root())

    def _log(self, text):
        self.log.appendPlainText(text)
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_status(self, text, error=False):
        self.status.setText(text)
        self.status.setStyleSheet("color: %s;" % ("#e06c5c" if error else "#aaa"))

    # ---------------------------------------------------------- generate
    def generate(self):
        if self._job is not None and self._job.is_running():
            return

        job = KimodoJob(self)
        job.log.connect(self._log)
        job.stage.connect(self._on_stage)
        job.finished.connect(self._on_finished)
        self._job = job

        seed = self.seed.value()
        started = job.start(
            self.prompt.toPlainText(),
            duration=self.duration.value(),
            steps=self.steps.value(),
            seed=None if seed < 0 else seed,
            name=self.clipname.text().strip(),
        )
        if started:
            self.gen_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)

    def cancel(self):
        if self._job is not None:
            self._job.cancel()

    def _on_stage(self, stage):
        self._set_status({
            "generate": "Generating motion...",
            "convert": "Converting to SOMA BVH...",
            "done": "Done",
            "failed": "Failed",
        }.get(stage, stage), error=(stage == "failed"))

    def _on_finished(self, ok, payload):
        self.gen_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if not ok:
            return
        if not self.autoimport.isChecked():
            return
        try:
            out = scene.import_clip(payload)
            self._log("Imported into %s (%s frames @ %g fps)." % (
                out.parent().path(),
                clips.bvh_frame_count(payload),
                clips.bvh_fps(payload)))
            self._set_status("Imported %s" % out.parent().path())
        except Exception as exc:  # keep the panel alive on any hou error
            self._log("Import failed: %s" % exc)
            self._set_status("Import failed", error=True)
