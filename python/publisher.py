"""
Houdini FX Pipeline — FX Asset Publisher (PySide6).
Thin UI layer — all path/versioning logic delegated to pipeline.py.
"""

import datetime
import logging
import os
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QPushButton, QScrollArea, QGroupBox,
        QCheckBox, QSpinBox, QComboBox, QPlainTextEdit, QMessageBox,
        QSizePolicy,
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont
except ImportError:
    raise RuntimeError("PySide6 is required. Install it or run from inside Houdini.")

import pipeline
import naming_conventions

logger = logging.getLogger("pipeline")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NODE_TYPE_FORMAT = {
    "rop_geometry":  {"output_parm": "sopoutput"},
    "geometry":      {"output_parm": "sopoutput"},
    "rop_alembic":   {"format": "abc", "output_parm": "filename"},
    "alembic":       {"format": "abc", "output_parm": "filename"},
    "rop_usdoutput": {"format": "usd", "output_parm": "lopoutput"},
    "usdexport":     {"format": "usd", "output_parm": "lopoutput"},
}
EXT_TO_FORMAT = {"bgeo": "bgeo", "bgeo.sc": "bgeo", "vdb": "vdb"}
SUPPORTED_FORMATS = ("usd", "abc", "bgeo", "vdb")
ROP_PREFIX = "OUT_"
FORMAT_COLORS = {
    "usd": "#4a90e2",
    "abc": "#e2a04a",
    "bgeo": "#4ae2a0",
    "vdb": "#a04ae2",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_format(node):
    type_name = node.type().name()
    info = NODE_TYPE_FORMAT.get(type_name, {})
    if "format" in info:
        return info["format"]
    parm = _get_output_parm(node)
    if parm is None:
        return None
    path = parm.eval()
    if not path:
        return None
    lower = path.lower()
    for ext in ("bgeo.sc", "vdb", "abc", "usd"):
        if lower.endswith("." + ext):
            return EXT_TO_FORMAT.get(ext, ext)
    return None


def _scan_publishable_rops():
    try:
        import hou
    except ImportError:
        raise RuntimeError("Must run inside Houdini.")
    results = []
    for node in hou.node("/out").children():
        if node.name().upper().startswith(ROP_PREFIX):
            fmt = _derive_format(node)
            if fmt in SUPPORTED_FORMATS:
                results.append(node)
    return results


def _get_output_parm(node):
    type_name = node.type().name()
    info = NODE_TYPE_FORMAT.get(type_name, {})
    parm_name = info.get("output_parm")
    if parm_name:
        return node.parm(parm_name)
    for name in ("sopoutput", "filename", "lopoutput", "file"):
        p = node.parm(name)
        if p is not None:
            return p
    return None


def _is_animated(node):
    trange = node.parm("trange")
    if trange is None:
        return False
    return trange.eval() > 0


def _list_obj_cameras():
    try:
        import hou
    except ImportError:
        return []
    cams = []
    for node in hou.node("/obj").allSubChildren():
        if node.type().name() in ("cam", "camera"):
            cams.append(node.path())
    return sorted(cams)


def _list_scene_viewers():
    try:
        import hou
    except ImportError:
        return []
    return [p for p in hou.ui.paneTabs() if p.type() == hou.paneTabType.SceneViewer]


# ---------------------------------------------------------------------------
# Context parser
# ---------------------------------------------------------------------------

def _parse_publisher_context() -> dict:
    try:
        import hou
    except ImportError:
        raise RuntimeError("Must run inside Houdini.")

    hip_path = hou.hipFile.path()
    if not hip_path or hip_path.endswith("untitled.hip"):
        raise RuntimeError(
            "No hip file is open.\nPlease save your scene with a proper name first.\n"
            "Expected: {entity}_fx_{task}_v001.hip"
        )

    hip_path = Path(hip_path)
    parsed = pipeline.parse_hip_filename(hip_path.name)
    if parsed is None:
        raise RuntimeError(
            f"Cannot parse hip filename: {hip_path.name!r}\n"
            "Expected pattern: {entity}_fx_{task}_v001.hip\n"
            "           or: {entity}_fx_{task}_{descriptor}_v001.hip"
        )

    entity = parsed["entity"]
    task = parsed["task"]
    descriptor = parsed.get("descriptor", "")
    hip_version = parsed["version"]

    entity_root = pipeline.entity_root_from_hip(hip_path)
    pub_name = descriptor or "main"
    publish_version = pipeline.get_next_publish_version(entity_root, task, pub_name)

    return {
        "hip_path": hip_path,
        "entity_root": entity_root,
        "entity": entity,
        "task": task,
        "descriptor": descriptor,
        "hip_version": hip_version,
        "publish_version": publish_version,
    }


# ---------------------------------------------------------------------------
# _RopRow
# ---------------------------------------------------------------------------

class _RopRow(QWidget):
    toggled = Signal(bool)

    def __init__(self, node, fmt: str, parent=None):
        super().__init__(parent)
        self._node = node
        self._fmt = fmt

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self._check = QCheckBox(node.name())
        font = self._check.font()
        font.setBold(True)
        self._check.setFont(font)
        self._check.setChecked(True)
        self._check.toggled.connect(self.toggled)

        color = FORMAT_COLORS.get(fmt, "#888888")
        self._fmt_label = QLabel(fmt.upper())
        self._fmt_label.setStyleSheet(
            f"color: white; background: {color}; border-radius: 3px; padding: 1px 5px;"
        )
        self._fmt_label.setFixedWidth(48)

        self._path_label = QLabel()
        self._path_label.setStyleSheet("color: #888; font-size: 10px;")
        self._path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._path_label.setWordWrap(False)

        layout.addWidget(self._check)
        layout.addWidget(self._fmt_label)
        layout.addWidget(self._path_label, stretch=1)

    def is_checked(self) -> bool:
        return self._check.isChecked()

    def set_path_preview(self, html: str):
        self._path_label.setText(html)

    @property
    def node(self):
        return self._node

    @property
    def fmt(self) -> str:
        return self._fmt


# ---------------------------------------------------------------------------
# AssetPublisherWindow
# ---------------------------------------------------------------------------

class AssetPublisherWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FX Asset Publisher")
        self.setMinimumSize(680, 620)
        self._ctx = None
        self._rop_rows: list[tuple] = []  # (node, _RopRow)
        self._build_ui()
        self._connect_signals()
        self._init_context()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)

        # 1. Context banner
        self._ctx_banner = QLabel("Initialising…")
        self._ctx_banner.setAlignment(Qt.AlignCenter)
        self._ctx_banner.setStyleSheet(
            "background: #1a2a4a; color: #cce; padding: 8px; border-radius: 4px;"
        )
        self._ctx_banner.setTextFormat(Qt.RichText)
        root.addWidget(self._ctx_banner)

        # 2. Publish Name + Rescan
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Publish Name:"))
        self._pub_name_edit = QLineEdit()
        self._pub_name_edit.setPlaceholderText("e.g. dust-pass  (lowercase-kebab)")
        name_row.addWidget(self._pub_name_edit, stretch=1)
        self._rescan_btn = QPushButton("Rescan Hip")
        self._rescan_btn.setToolTip("Re-scan /out for publishable OUT_ ROPs")
        name_row.addWidget(self._rescan_btn)
        root.addLayout(name_row)

        # 3. Tip label
        tip = QLabel(
            "ROPs must be at /out and named with the OUT_ prefix (e.g. OUT_dust-pass)."
        )
        tip.setStyleSheet("color: #888; font-size: 10px;")
        root.addWidget(tip)

        # 4. ROP list
        rop_header = QLabel("Publishable ROPs")
        font = rop_header.font()
        font.setBold(True)
        rop_header.setFont(font)
        root.addWidget(rop_header)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setMinimumHeight(120)
        self._scroll_area.setMaximumHeight(260)
        scroll_inner = QWidget()
        self._rop_list_layout = QVBoxLayout(scroll_inner)
        self._rop_list_layout.setContentsMargins(2, 2, 2, 2)
        self._rop_list_layout.setSpacing(2)
        self._rop_list_layout.addStretch()
        self._scroll_area.setWidget(scroll_inner)
        root.addWidget(self._scroll_area)

        # 5. Preview group
        self._preview_group = QGroupBox("Generate Preview")
        self._preview_group.setCheckable(True)
        self._preview_group.setChecked(True)
        prev_layout = QVBoxLayout(self._preview_group)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self._static_radio = QCheckBox("Static (single frame)")
        self._animated_check = QCheckBox("Animated")
        self._animated_check.setChecked(True)
        mode_row.addWidget(self._static_radio)
        mode_row.addWidget(self._animated_check)
        mode_row.addStretch()
        prev_layout.addLayout(mode_row)

        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Frame range:"))
        self._frame_start = QSpinBox()
        self._frame_start.setRange(1, 99999)
        self._frame_start.setValue(1)
        self._frame_end = QSpinBox()
        self._frame_end.setRange(1, 99999)
        self._frame_end.setValue(100)
        range_row.addWidget(self._frame_start)
        range_row.addWidget(QLabel("–"))
        range_row.addWidget(self._frame_end)
        range_row.addStretch()
        prev_layout.addLayout(range_row)

        cam_row = QHBoxLayout()
        cam_row.addWidget(QLabel("Camera:"))
        self._cam_combo = QComboBox()
        self._cam_combo.addItem("<Current Viewport>")
        for cam in _list_obj_cameras():
            self._cam_combo.addItem(cam)
        cam_row.addWidget(self._cam_combo, stretch=1)
        prev_layout.addLayout(cam_row)

        root.addWidget(self._preview_group)

        # 6. Description
        root.addWidget(QLabel("Description:"))
        self._desc_edit = QPlainTextEdit()
        self._desc_edit.setMaximumHeight(70)
        self._desc_edit.setPlaceholderText("Optional notes about this publish…")
        root.addWidget(self._desc_edit)

        # 7. Status label
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(
            "padding: 4px; border-radius: 3px; background: transparent;"
        )
        root.addWidget(self._status_label)

        # 8. Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.close)
        self._publish_btn = QPushButton("Publish")
        self._publish_btn.setEnabled(False)
        self._publish_btn.setStyleSheet(
            "QPushButton { background: #2a7a2a; color: white; font-weight: bold;"
            " padding: 6px 24px; border-radius: 4px; }"
            "QPushButton:disabled { background: #444; color: #888; }"
            "QPushButton:hover:enabled { background: #3a9a3a; }"
        )
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._publish_btn)
        root.addLayout(btn_row)

    def _connect_signals(self):
        self._rescan_btn.clicked.connect(self._rescan)
        self._pub_name_edit.textChanged.connect(self._on_pub_name_changed)
        self._publish_btn.clicked.connect(self._on_publish)
        self._animated_check.toggled.connect(self._on_animated_toggled)
        self._static_radio.toggled.connect(self._on_static_toggled)

    def _on_animated_toggled(self, checked: bool):
        if checked:
            self._static_radio.setChecked(False)

    def _on_static_toggled(self, checked: bool):
        if checked:
            self._animated_check.setChecked(False)

    def _on_pub_name_changed(self, _text: str):
        self._refresh_path_previews()
        self._update_publish_button_state()

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    def _init_context(self):
        try:
            ctx = _parse_publisher_context()
        except RuntimeError as e:
            self._fatal_ctx(str(e))
            return

        self._ctx = ctx
        entity = ctx["entity"]
        task = ctx["task"]
        desc = ctx["descriptor"] or "main"
        ver = ctx["publish_version"]

        self.setWindowTitle(f"FX Asset Publisher — {entity} v{ver:03d}")

        self._ctx_banner.setText(
            f"<b>{entity}</b> &nbsp;·&nbsp; task: <b>{task}</b>"
            f" &nbsp;·&nbsp; descriptor: <b>{desc}</b>"
            f" &nbsp;·&nbsp; <span style='color:#8cf;'>Publish v{ver:03d}</span>"
        )

        self._pub_name_edit.setText(task)
        self._rescan()

    def _fatal_ctx(self, msg: str):
        self._ctx_banner.setText(
            f"<span style='color:#f88;'><b>Context Error</b></span><br>"
            + msg.replace("\n", "<br>")
        )
        self._ctx_banner.setStyleSheet(
            "background: #3a1a1a; color: #f88; padding: 8px; border-radius: 4px;"
        )
        self._publish_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # ROP scanning
    # ------------------------------------------------------------------

    def _rescan(self):
        # Clear existing rows (remove all except the trailing stretch)
        while self._rop_list_layout.count() > 1:
            item = self._rop_list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._rop_rows = []

        try:
            rops = _scan_publishable_rops()
        except RuntimeError:
            rops = []

        for rop in rops:
            self._add_rop_row(rop)

        if not rops:
            placeholder = QLabel(
                "No OUT_ ROPs with supported formats found in /out."
            )
            placeholder.setStyleSheet("color: #888; font-style: italic;")
            placeholder.setAlignment(Qt.AlignCenter)
            self._rop_list_layout.insertWidget(0, placeholder)

        self._refresh_path_previews()
        self._update_publish_button_state()

    def _add_rop_row(self, node):
        fmt = _derive_format(node)
        row = _RopRow(node, fmt or "bgeo")
        row.toggled.connect(self._update_publish_button_state)
        self._rop_list_layout.insertWidget(
            self._rop_list_layout.count() - 1, row
        )
        self._rop_rows.append((node, row))

    def _refresh_path_previews(self):
        if self._ctx is None:
            return
        ctx = self._ctx
        pub_name = self._pub_name_edit.text().strip()
        projects_root_str = str(pipeline.projects_root())

        for node, row in self._rop_rows:
            if not pub_name:
                row.set_path_preview("")
                continue
            fmt = row.fmt
            animated = not self._static_radio.isChecked()
            try:
                target = pipeline.build_publish_path(
                    ctx["entity_root"], ctx["entity"], ctx["task"],
                    pub_name, fmt, ctx["publish_version"], animated,
                )
            except ValueError:
                row.set_path_preview(
                    "<span style='color:#f88;'>Unknown format</span>"
                )
                continue

            short = str(target)
            if short.startswith(projects_root_str):
                short = "…" + short[len(projects_root_str):]

            # Check if ROP output parm differs from proposed path
            parm = _get_output_parm(node)
            current_out = parm.eval() if parm else ""
            if current_out and Path(current_out) != target:
                row.set_path_preview(
                    f"<span style='color:#fa8;'>{short}</span>"
                )
            else:
                row.set_path_preview(
                    f"<span style='color:#888;'>{short}</span>"
                )

    def _update_publish_button_state(self):
        if self._ctx is None:
            self._publish_btn.setEnabled(False)
            return
        pub_name = self._pub_name_edit.text().strip()
        has_name = bool(pub_name)
        has_checked = any(row.is_checked() for _, row in self._rop_rows)
        self._publish_btn.setEnabled(has_name and has_checked)

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def _set_status(self, msg: str, color: str = "#ccc"):
        self._status_label.setStyleSheet(
            f"padding: 4px; border-radius: 3px; background: #222; color: {color};"
        )
        self._status_label.setText(msg)
        QApplication.processEvents()

    def _on_publish(self):
        pub_name_raw = self._pub_name_edit.text().strip()
        try:
            pub_name = naming_conventions.validate_task(pub_name_raw)
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Publish Name", str(e))
            return

        to_publish = [
            (node, row.fmt) for node, row in self._rop_rows if row.is_checked()
        ]
        if not to_publish:
            QMessageBox.warning(self, "Nothing selected", "Check at least one ROP to publish.")
            return

        description = self._desc_edit.toPlainText().strip()

        self._publish_btn.setEnabled(False)
        self._rescan_btn.setEnabled(False)

        try:
            self._do_publish(pub_name, to_publish, description)
        except Exception as e:
            self._set_status(f"Publish failed: {e}", "#f88")
            logger.error("Publish failed: %s", e)
            QMessageBox.critical(self, "Publish Failed", str(e))
        finally:
            self._publish_btn.setEnabled(True)
            self._rescan_btn.setEnabled(True)

    def _do_publish(self, publish_name: str, to_publish: list, description: str):
        ctx = self._ctx
        entity_root = ctx["entity_root"]
        entity = ctx["entity"]
        task = ctx["task"]
        version = ctx["publish_version"]
        hip_path = ctx["hip_path"]
        hip_version = ctx["hip_version"]
        descriptor = ctx["descriptor"]

        published_paths = []

        for i, (node, fmt) in enumerate(to_publish):
            self._set_status(
                f"Cooking {node.name()} ({i + 1}/{len(to_publish)})…", "#8cf"
            )

            animated = _is_animated(node)
            target = pipeline.build_publish_path(
                entity_root, entity, task, publish_name, fmt, version, animated
            )
            target.parent.mkdir(parents=True, exist_ok=True)

            parm = _get_output_parm(node)
            if parm is None:
                raise RuntimeError(f"Cannot find output parameter on {node.name()}")
            parm.set(str(target))

            # Cook
            exec_parm = node.parm("execute")
            if exec_parm is not None:
                exec_parm.pressButton()
            else:
                node.render()

            # Verify output
            if "$F" in str(target):
                frame_start = self._frame_start.value()
                check_path = Path(str(target).replace("$F4", f"{frame_start:04d}"))
                if not check_path.exists():
                    raise RuntimeError(
                        f"Output not found after cook:\n{check_path}\n"
                        "Check your ROP settings and frame range."
                    )

            logger.info("Written: %s", target)
            published_paths.append((node, fmt, animated, target))

        # Preview
        self._set_status("Generating preview…", "#8cf")
        preview_result = self._maybe_generate_preview(publish_name)
        mp4_path = preview_result.get("mp4_path") if preview_result else None
        snapshot_path = None

        # Hip snapshot
        self._set_status("Saving hip snapshot…", "#8cf")
        try:
            snapshot_path, next_work = pipeline.snapshot_and_increment_hip(
                entity_root, hip_path, task, descriptor, hip_version
            )
            logger.info("Next work hip: %s", next_work)
        except RuntimeError as e:
            logger.warning("Hip snapshot skipped: %s", e)

        # Metadata
        for node, fmt, animated, target in published_paths:
            pub_dir = target.parent
            metadata = {
                "schema_version": 1,
                "entity": entity,
                "task": task,
                "publish_name": publish_name,
                "fmt": fmt,
                "version": version,
                "animated": animated,
                "published_by": os.getenv("USER", "unknown"),
                "published_at": datetime.datetime.now().isoformat(),
                "description": description,
                "hip_snapshot": str(snapshot_path) if snapshot_path else None,
                "preview_mp4": str(mp4_path) if mp4_path else None,
            }
            pipeline.write_publish_metadata(pub_dir, metadata)

        self._set_status(
            f"Published v{version:03d} — {len(published_paths)} ROP(s) done.", "#4e4"
        )

    def _maybe_generate_preview(self, publish_name: str) -> dict | None:
        if not self._preview_group.isChecked():
            return None

        ctx = self._ctx
        entity_root = ctx["entity_root"]
        entity = ctx["entity"]
        task = ctx["task"]
        version = ctx["publish_version"]

        animated = not self._static_radio.isChecked()
        start = self._frame_start.value()
        end = self._frame_end.value()

        cam_text = self._cam_combo.currentText()
        camera = None if cam_text == "<Current Viewport>" else cam_text

        jpg_path_obj = pipeline.build_preview_jpg_path(
            entity_root, entity, task, publish_name, version, animated
        )
        jpg_path_obj.parent.mkdir(parents=True, exist_ok=True)
        jpg_seq_path = str(jpg_path_obj)

        mp4_path = None

        try:
            frame_range = (start, end) if animated else (start, start)
            pipeline.flipbook_viewport(
                jpg_seq_path, frame_range, camera, resolution=(1280, 720)
            )

            if animated:
                mp4_obj = pipeline.build_mp4_path(
                    entity_root, entity, task, publish_name, version
                )
                mp4_obj.parent.mkdir(parents=True, exist_ok=True)
                pipeline.encode_mp4(jpg_seq_path, str(mp4_obj), frame_start=start)
                mp4_path = mp4_obj

        except Exception as e:
            QMessageBox.warning(
                self, "Preview Warning",
                f"Preview generation failed (publish will continue):\n{e}"
            )
            return None

        return {
            "mp4_path": mp4_path,
            "jpg_path": jpg_seq_path,
            "first_frame": start,
            "last_frame": end,
        }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_instance = None


def show():
    global _instance
    if _instance is not None:
        try:
            _instance.close()
        except RuntimeError:
            pass
        _instance = None

    parent = None
    try:
        import hou
        parent = hou.qt.mainWindow()
    except (ImportError, AttributeError):
        pass

    app = QApplication.instance()
    if app is None:
        import sys
        app = QApplication(sys.argv)

    win = AssetPublisherWindow(parent=parent)
    win.setAttribute(Qt.WA_DeleteOnClose)
    win.show()
    _instance = win
