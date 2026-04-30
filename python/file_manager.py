"""
Houdini FX Pipeline — File Manager dialog (PySide6).
Thin UI layer — all logic delegated to pipeline.py.
"""

import sys
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QComboBox, QPushButton, QListWidget, QListWidgetItem,
        QStatusBar, QGroupBox,
    )
    from PySide6.QtCore import Qt
except ImportError:
    raise RuntimeError("PySide6 is required. Install it or run from inside Houdini.")

import pipeline


class FileManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FX File Manager")
        self.setMinimumSize(700, 500)
        self._build_ui()
        self._populate_projects()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        # Project / context selector row
        selector = QHBoxLayout()
        self._project_combo = QComboBox()
        self._project_combo.currentIndexChanged.connect(self._on_project_changed)
        selector.addWidget(QLabel("Project:"))
        selector.addWidget(self._project_combo)
        selector.addStretch()
        root_layout.addLayout(selector)

        # Context group
        ctx_group = QGroupBox("Context")
        ctx_layout = QHBoxLayout(ctx_group)

        self._seq_combo = QComboBox()
        self._shot_combo = QComboBox()
        self._seq_combo.currentIndexChanged.connect(self._on_seq_changed)
        ctx_layout.addWidget(QLabel("Sequence:"))
        ctx_layout.addWidget(self._seq_combo)
        ctx_layout.addWidget(QLabel("Shot:"))
        ctx_layout.addWidget(self._shot_combo)
        ctx_layout.addStretch()
        root_layout.addWidget(ctx_group)

        # Hip file list
        hip_group = QGroupBox("Hip files")
        hip_layout = QVBoxLayout(hip_group)
        self._hip_list = QListWidget()
        hip_layout.addWidget(self._hip_list)

        btn_row = QHBoxLayout()
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._refresh_hips)
        btn_row.addWidget(self._refresh_btn)
        btn_row.addStretch()
        hip_layout.addLayout(btn_row)
        root_layout.addWidget(hip_group)

        self.setStatusBar(QStatusBar())

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _populate_projects(self):
        self._project_combo.blockSignals(True)
        self._project_combo.clear()
        for p in pipeline.load_projects():
            self._project_combo.addItem(p["name"], userData=p)
        self._project_combo.blockSignals(False)
        if self._project_combo.count():
            self._on_project_changed(0)

    def _on_project_changed(self, index: int):
        project = self._project_combo.itemData(index)
        if not project:
            return
        self._seq_combo.blockSignals(True)
        self._seq_combo.clear()
        for seq in project.get("sequences", []):
            self._seq_combo.addItem(seq)
        self._seq_combo.blockSignals(False)
        self._on_seq_changed(0)

    def _on_seq_changed(self, index: int):
        # Populate shots by scanning disk
        project = self._project_combo.currentData()
        seq = self._seq_combo.currentText()
        self._shot_combo.clear()
        if not project or not seq:
            return
        seq_dir = pipeline.projects_root() / project["folder"] / "sequences" / seq
        if seq_dir.exists():
            shots = sorted(d.name for d in seq_dir.iterdir() if d.is_dir())
            self._shot_combo.addItems(shots)
        self._refresh_hips()

    def _refresh_hips(self):
        self._hip_list.clear()
        project = self._project_combo.currentData()
        seq = self._seq_combo.currentText()
        shot = self._shot_combo.currentText()
        if not all([project, seq, shot]):
            return
        work_dir = pipeline.shot_work_houdini(project["folder"], seq, shot)
        hips = pipeline.find_hip_files(work_dir)
        for hip in hips:
            item = QListWidgetItem(hip.name)
            item.setData(Qt.UserRole, str(hip))
            self._hip_list.addItem(item)
        self.statusBar().showMessage(f"{len(hips)} hip file(s) found in {work_dir}")


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = FileManagerWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
