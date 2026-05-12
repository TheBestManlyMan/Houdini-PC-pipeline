"""
Houdini FX Pipeline — File Manager dialog (PySide6).
Thin UI layer — all logic delegated to pipeline.py.
"""

import html as html_module
import logging
import re
import sys
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QComboBox, QPushButton, QStatusBar, QGroupBox, QDialog,
        QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox,
        QTreeWidget, QTreeWidgetItem, QSplitter, QTextEdit, QHeaderView,
    )
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QFont, QKeySequence, QDesktopServices, QShortcut
except ImportError:
    raise RuntimeError("PySide6 is required. Install it or run from inside Houdini.")

import pipeline
import naming_conventions


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

class AddProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Project")
        self.setMinimumWidth(300)

        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. My Short Film")
        form.addRow("Name:", self._name)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _accept(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        folder = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
        try:
            pipeline.add_project(name=name, folder=folder)
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
            return
        self._project_name = name
        self.accept()

    def project_name(self) -> str:
        return getattr(self, "_project_name", "")


class AddSequenceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Sequence")
        self.setMinimumWidth(260)

        form = QFormLayout()
        self._seq = QLineEdit()
        self._seq.setPlaceholderText("e.g. SQ010")
        form.addRow("Sequence:", self._seq)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _accept(self):
        if not self._seq.text().strip():
            QMessageBox.warning(self, "Validation", "Sequence code is required.")
            return
        self.accept()

    def seq_code(self) -> str:
        return self._seq.text().strip().upper()


class AddShotDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Shot")
        self.setMinimumWidth(260)

        form = QFormLayout()
        self._shot = QLineEdit()
        self._shot.setPlaceholderText("e.g. 0010")
        form.addRow("Shot:", self._shot)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _accept(self):
        if not self._shot.text().strip():
            QMessageBox.warning(self, "Validation", "Shot code is required.")
            return
        self.accept()

    def shot_code(self) -> str:
        return self._shot.text().strip()


class NewVersionDialog(QDialog):
    def __init__(self, entity: str, work_houdini, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Houdini Version")
        self.setMinimumWidth(380)
        self._entity = entity
        self._work_houdini = work_houdini

        form = QFormLayout()

        self._task_combo = QComboBox()
        self._task_combo.setEditable(True)
        self._task_combo.addItems(naming_conventions.STANDARD_TASKS)
        self._task_combo.setCurrentIndex(0)
        form.addRow("Task:", self._task_combo)

        self._preview = QLabel()
        self._preview.setStyleSheet("color: grey;")
        form.addRow("File:", self._preview)

        self._task_combo.currentTextChanged.connect(self._update_preview)
        self._update_preview(self._task_combo.currentText())

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _update_preview(self, raw: str):
        try:
            task = naming_conventions.validate_task(raw)
            path = pipeline.next_hip_path(self._work_houdini, self._entity, task)
            self._preview.setText(path.name)
            self._preview.setStyleSheet("color: grey;")
        except ValueError:
            self._preview.setText("Invalid task name")
            self._preview.setStyleSheet("color: red;")

    def _accept(self):
        try:
            self._task = naming_conventions.validate_task(self._task_combo.currentText())
        except ValueError as e:
            QMessageBox.warning(self, "Invalid task", str(e))
            return
        self.accept()

    def task(self) -> str:
        return self._task


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class _LogPanelHandler(logging.Handler):
    """Logging handler that appends colored HTML records to a QTextEdit."""

    _COLORS = {
        "CRITICAL": "#ff4444",
        "ERROR":    "#ff5555",
        "WARNING":  "#ffaa00",
        "DEBUG":    "#888888",
    }

    def __init__(self, widget: "QTextEdit"):
        super().__init__()
        self._widget = widget
        self.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))

    def emit(self, record: logging.LogRecord):
        try:
            msg = html_module.escape(self.format(record))
            color = self._COLORS.get(record.levelname)
            if color:
                self._widget.append(f'<span style="color:{color};">{msg}</span>')
            else:
                self._widget.append(msg)
        except RuntimeError:
            pass  # widget deleted
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class FileManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FX File Manager")
        self.setMinimumSize(900, 600)
        self._build_ui()
        self._setup_logging()
        self._populate_projects()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        # Project row
        proj_row = QHBoxLayout()
        self._project_combo = QComboBox()
        self._project_combo.currentIndexChanged.connect(self._on_project_changed)
        self._add_project_btn = QPushButton("+ Project")
        self._add_project_btn.clicked.connect(self._on_add_project)
        proj_row.addWidget(QLabel("Project:"))
        proj_row.addWidget(self._project_combo, stretch=1)
        proj_row.addWidget(self._add_project_btn)
        root_layout.addLayout(proj_row)

        # Context group
        ctx_group = QGroupBox("Context")
        ctx_layout = QHBoxLayout(ctx_group)

        self._seq_combo = QComboBox()
        self._seq_combo.currentIndexChanged.connect(self._on_seq_changed)
        self._add_seq_btn = QPushButton("+ Seq")
        self._add_seq_btn.clicked.connect(self._on_add_sequence)

        self._shot_combo = QComboBox()
        self._shot_combo.currentIndexChanged.connect(self._on_shot_changed)
        self._add_shot_btn = QPushButton("+ Shot")
        self._add_shot_btn.clicked.connect(self._on_add_shot)

        ctx_layout.addWidget(QLabel("Sequence:"))
        ctx_layout.addWidget(self._seq_combo)
        ctx_layout.addWidget(self._add_seq_btn)
        ctx_layout.addSpacing(16)
        ctx_layout.addWidget(QLabel("Shot:"))
        ctx_layout.addWidget(self._shot_combo)
        ctx_layout.addWidget(self._add_shot_btn)
        ctx_layout.addStretch()
        root_layout.addWidget(ctx_group)

        # Splitter: hip tree (top) + log panel (bottom)
        splitter = QSplitter(Qt.Vertical)

        # Hip file tree
        hip_group = QGroupBox("Hip files")
        hip_layout = QVBoxLayout(hip_group)

        self._hip_tree = QTreeWidget()
        self._hip_tree.setColumnCount(3)
        self._hip_tree.setHeaderLabels(["Filename / Task", "Version", "Size"])
        self._hip_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._hip_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._hip_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._hip_tree.setSelectionBehavior(QTreeWidget.SelectRows)
        self._hip_tree.currentItemChanged.connect(self._on_hip_selection_changed)
        self._hip_tree.itemDoubleClicked.connect(self._on_open_hip)
        hip_layout.addWidget(self._hip_tree)

        btn_row = QHBoxLayout()
        self._refresh_btn = QPushButton("Refresh  (F5)")
        self._refresh_btn.setToolTip("Re-scan the shot folder for hip files")
        self._refresh_btn.clicked.connect(self._refresh_hips)

        self._open_btn = QPushButton("Open")
        self._open_btn.setToolTip("Open the selected hip file in Houdini")
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._on_open_hip)

        self._copy_btn = QPushButton("Copy Path")
        self._copy_btn.setToolTip("Copy full file path to clipboard")
        self._copy_btn.setEnabled(False)
        self._copy_btn.clicked.connect(self._on_copy_path)

        self._reveal_btn = QPushButton("Reveal")
        self._reveal_btn.setToolTip("Open the containing folder in the file manager")
        self._reveal_btn.setEnabled(False)
        self._reveal_btn.clicked.connect(self._on_reveal)

        self._new_version_btn = QPushButton("+ Version")
        self._new_version_btn.setToolTip("Create a new versioned hip file for this shot")
        self._new_version_btn.setEnabled(False)
        self._new_version_btn.clicked.connect(self._on_new_version)

        btn_row.addWidget(self._refresh_btn)
        btn_row.addWidget(self._open_btn)
        btn_row.addWidget(self._copy_btn)
        btn_row.addWidget(self._reveal_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._new_version_btn)
        hip_layout.addLayout(btn_row)
        splitter.addWidget(hip_group)

        # Log panel
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)

        log_header = QHBoxLayout()
        log_header.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setMaximumWidth(60)
        clear_btn.setToolTip("Clear the log output")
        clear_btn.clicked.connect(lambda: self._log_panel.clear())
        log_header.addWidget(clear_btn)
        log_layout.addLayout(log_header)

        self._log_panel = QTextEdit()
        self._log_panel.setReadOnly(True)
        self._log_panel.setFont(QFont("Monospace", 9))
        self._log_panel.setPlaceholderText("Pipeline log…")
        log_layout.addWidget(self._log_panel)
        splitter.addWidget(log_group)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter)

        self.setStatusBar(QStatusBar())

        # Keyboard shortcuts
        QShortcut(QKeySequence("F5"), self, self._refresh_hips)
        QShortcut(QKeySequence("Return"), self, self._on_open_hip)

    def _setup_logging(self):
        handler = _LogPanelHandler(self._log_panel)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter("%(levelname)s  %(message)s"))
        for log_name in ("pipeline", "naming_conventions"):
            lg = logging.getLogger(log_name)
            lg.setLevel(logging.DEBUG)
            lg.handlers.clear()
            lg.propagate = False
            lg.addHandler(handler)
            lg.addHandler(stream_handler)

    def closeEvent(self, event):
        for log_name in ("pipeline", "naming_conventions"):
            lg = logging.getLogger(log_name)
            lg.handlers = [h for h in lg.handlers if not isinstance(h, _LogPanelHandler)]
        super().closeEvent(event)

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
        self.setWindowTitle(f"FX File Manager — {project['name']}")
        self._seq_combo.blockSignals(True)
        self._seq_combo.clear()
        for seq in project.get("sequences", []):
            self._seq_combo.addItem(seq)
        self._seq_combo.blockSignals(False)
        self._on_seq_changed(0)

    def _on_seq_changed(self, index: int):
        project = self._project_combo.currentData()
        seq = self._seq_combo.currentText()
        self._shot_combo.clear()
        if not project or not seq:
            return
        seq_dir = pipeline.projects_root() / project["folder"] / seq
        if seq_dir.exists():
            shots = sorted(d.name for d in seq_dir.iterdir() if d.is_dir())
            self._shot_combo.addItems(shots)
        self._refresh_hips()

    def _on_shot_changed(self, index: int):
        has_shot = bool(self._shot_combo.currentText())
        self._new_version_btn.setEnabled(has_shot)
        self._refresh_hips()

    def _refresh_hips(self):
        self._hip_tree.clear()
        project = self._project_combo.currentData()
        seq = self._seq_combo.currentText()
        shot = self._shot_combo.currentText()
        self._new_version_btn.setEnabled(bool(shot))
        if not all([project, seq, shot]):
            return
        work_dir = pipeline.shot_work_houdini(project["folder"], seq, shot)
        hips = pipeline.find_hip_files(work_dir)

        task_groups: dict[str, QTreeWidgetItem] = {}
        for hip in hips:
            parsed = pipeline.parse_hip_filename(hip.name)
            task = parsed["task"] if parsed else "unknown"
            ver_str = parsed["version_str"] if parsed else ""

            if task not in task_groups:
                group = QTreeWidgetItem(self._hip_tree, [task, "", ""])
                font = group.font(0)
                font.setBold(True)
                group.setFont(0, font)
                group.setExpanded(True)
                task_groups[task] = group

            size_str = self._format_size(hip.stat().st_size) if hip.exists() else ""
            child = QTreeWidgetItem(task_groups[task], [hip.name, ver_str, size_str])
            child.setData(0, Qt.UserRole, str(hip))

        # Bold the latest version in each task group
        for group in task_groups.values():
            n = group.childCount()
            if n > 0:
                latest = group.child(n - 1)
                for col in range(3):
                    f = latest.font(col)
                    f.setBold(True)
                    latest.setFont(col, f)

        self.statusBar().showMessage(f"{len(hips)} hip file(s) found in {work_dir}")

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"

    # ------------------------------------------------------------------
    # Hip selection
    # ------------------------------------------------------------------

    def _current_hip_path(self) -> str | None:
        item = self._hip_tree.currentItem()
        if item is None or item.parent() is None:
            return None
        return item.data(0, Qt.UserRole)

    def _on_hip_selection_changed(self, current, _previous):
        path = self._current_hip_path()
        is_hip = path is not None
        self._open_btn.setEnabled(is_hip)
        self._copy_btn.setEnabled(is_hip)
        self._reveal_btn.setEnabled(is_hip)
        if is_hip:
            self.statusBar().showMessage(path)

    # ------------------------------------------------------------------
    # Add actions
    # ------------------------------------------------------------------

    def _on_add_project(self):
        dlg = AddProjectDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        new_name = dlg.project_name()
        self._populate_projects()
        idx = self._project_combo.findText(new_name)
        if idx >= 0:
            self._project_combo.setCurrentIndex(idx)
        self.statusBar().showMessage(f"Project '{new_name}' added.")

    def _on_add_sequence(self):
        project = self._project_combo.currentData()
        if not project:
            QMessageBox.warning(self, "No project", "Select or create a project first.")
            return
        dlg = AddSequenceDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        seq = dlg.seq_code()
        try:
            pipeline.add_sequence(project["folder"], seq)
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
            return
        updated = pipeline.get_project(project["folder"])
        idx = self._project_combo.currentIndex()
        self._project_combo.setItemData(idx, updated)
        self._seq_combo.addItem(seq)
        self._seq_combo.setCurrentText(seq)
        self.statusBar().showMessage(f"Sequence '{seq}' added to {project['name']}.")

    def _on_add_shot(self):
        project = self._project_combo.currentData()
        seq = self._seq_combo.currentText()
        if not project or not seq:
            QMessageBox.warning(self, "No context", "Select a project and sequence first.")
            return
        dlg = AddShotDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        shot = dlg.shot_code()
        work_dir = pipeline.shot_work_houdini(project["folder"], seq, shot)
        if work_dir.exists():
            QMessageBox.warning(self, "Already exists", f"Shot '{shot}' already exists.")
            return
        pipeline.make_shot_work_dirs(project["folder"], seq, shot)
        self._shot_combo.addItem(shot)
        self._shot_combo.setCurrentText(shot)
        self.statusBar().showMessage(f"Shot '{seq}/{shot}' created at {work_dir}")

    # ------------------------------------------------------------------
    # Hip file actions
    # ------------------------------------------------------------------

    def _on_open_hip(self, *_):
        path = self._current_hip_path()
        if not path:
            return
        try:
            import hou
            if hou.hipFile.hasUnsavedChanges():
                reply = QMessageBox.question(
                    self, "Unsaved Changes",
                    "Current scene has unsaved changes. Open anyway?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return
            hou.hipFile.load(path)
            self.statusBar().showMessage(f"Opened: {Path(path).name}")
        except ImportError:
            QMessageBox.information(self, "Standalone", f"Would open: {path}")

    def _on_copy_path(self):
        path = self._current_hip_path()
        if not path:
            return
        QApplication.clipboard().setText(path)
        self.statusBar().showMessage(f"Copied: {path}")

    def _on_reveal(self):
        path = self._current_hip_path()
        if not path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    def _on_new_version(self):
        project = self._project_combo.currentData()
        seq = self._seq_combo.currentText()
        shot = self._shot_combo.currentText()
        if not all([project, seq, shot]):
            return
        entity = f"{seq}_{shot}"
        work_dir = pipeline.shot_work_houdini(project["folder"], seq, shot)
        dlg = NewVersionDialog(entity=entity, work_houdini=work_dir, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        hip_path = pipeline.prepare_hip_version_dir(
            project["folder"], seq, shot, entity, dlg.task()
        )
        try:
            import hou
            hou.hipFile.save(str(hip_path))
        except ImportError:
            pass
        self._refresh_hips()
        self.statusBar().showMessage(f"Saved: {hip_path}")


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    existing = getattr(app, "_fx_file_manager", None)
    if existing is not None:
        try:
            existing.raise_()
            existing.activateWindow()
            return
        except RuntimeError:
            pass
    win = FileManagerWindow()
    win.setAttribute(Qt.WA_DeleteOnClose)
    win.show()
    app._fx_file_manager = win


if __name__ == "__main__":
    main()
