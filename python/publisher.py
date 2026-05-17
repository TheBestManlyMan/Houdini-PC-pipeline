"""
Houdini FX Pipeline — FX Publisher (PySide6).
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
        QSizePolicy, QTabWidget,
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

_USD_ROP_TYPES = {"usd_rop", "usdrender_rop", "usd", "rop_usdrender"}
_KARMA_RS_TYPES = {"karmarendersettings", "karmarendersettings::2.0"}
_GLTF_ROP_TYPES = {"rop_gltf", "gltf", "rop_gltfchar"}

# ---------------------------------------------------------------------------
# Helpers — asset publish
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
# Helpers — render publish
# ---------------------------------------------------------------------------

def _scan_usd_rops() -> list:
    try:
        import hou
    except ImportError:
        raise RuntimeError("Must run inside Houdini.")
    results = []
    for node in hou.node("/out").children():
        if node.name().upper().startswith(ROP_PREFIX):
            if node.type().name() in _USD_ROP_TYPES:
                rop_name = node.name()[4:].lower()
                results.append({"node": node, "name": node.name(), "rop_name": rop_name})
    return results


def _find_karma_rs(usd_rop_node, max_depth=6):
    from collections import deque
    visited = set()
    queue = deque([(usd_rop_node, 0)])
    while queue:
        current, depth = queue.popleft()
        if depth > max_depth:
            continue
        node_id = current.path()
        if node_id in visited:
            continue
        visited.add(node_id)
        if current.type().name() in _KARMA_RS_TYPES:
            return current
        for inp in current.inputs():
            if inp is not None:
                queue.append((inp, depth + 1))
    return None


def _rop_frame_range(node) -> tuple:
    f1 = node.parm("f1")
    f2 = node.parm("f2")
    try:
        start = int(f1.eval()) if f1 else 1001
        end = int(f2.eval()) if f2 else 1100
        return (start, end)
    except Exception:
        return (1001, 1100)


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

    return {
        "hip_path": hip_path,
        "entity_root": entity_root,
        "entity": entity,
        "task": task,
        "descriptor": descriptor,
        "hip_version": hip_version,
    }


# ---------------------------------------------------------------------------
# _RopRow (asset publish)
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
# _RenderRopRow
# ---------------------------------------------------------------------------

class _RenderRopRow(QWidget):
    changed = Signal()

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self._entry = entry
        node = entry["node"]
        rop_name = entry["rop_name"]

        frame_start, frame_end = _rop_frame_range(node)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 2)
        layout.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self._check = QCheckBox(node.name())
        font = self._check.font()
        font.setBold(True)
        self._check.setFont(font)
        self._check.setChecked(True)
        self._check.toggled.connect(self.changed)

        usd_tag = QLabel("USD")
        usd_tag.setStyleSheet(
            "color: white; background: #4a90e2; border-radius: 3px; padding: 1px 5px;"
        )
        usd_tag.setFixedWidth(36)

        top_row.addWidget(self._check)
        top_row.addWidget(usd_tag)
        top_row.addWidget(QLabel("Frames:"))

        self._frame_start = QSpinBox()
        self._frame_start.setRange(1, 99999)
        self._frame_start.setValue(frame_start)
        self._frame_start.setFixedWidth(72)
        self._frame_start.valueChanged.connect(self.changed)

        self._frame_end = QSpinBox()
        self._frame_end.setRange(1, 99999)
        self._frame_end.setValue(frame_end)
        self._frame_end.setFixedWidth(72)
        self._frame_end.valueChanged.connect(self.changed)

        dash = QLabel("–")
        top_row.addWidget(self._frame_start)
        top_row.addWidget(dash)
        top_row.addWidget(self._frame_end)
        top_row.addStretch()

        self._rescan_btn = QPushButton("↺")
        self._rescan_btn.setFixedWidth(28)
        self._rescan_btn.setToolTip("Reset frame range from ROP")
        self._rescan_btn.clicked.connect(self._reset_frame_range)
        top_row.addWidget(self._rescan_btn)

        layout.addLayout(top_row)

        self._path_label = QLabel()
        self._path_label.setStyleSheet("color: #888; font-size: 10px; margin-left: 20px;")
        self._path_label.setWordWrap(False)
        layout.addWidget(self._path_label)

    def _reset_frame_range(self):
        start, end = _rop_frame_range(self._entry["node"])
        self._frame_start.setValue(start)
        self._frame_end.setValue(end)
        self.changed.emit()

    def is_checked(self) -> bool:
        return self._check.isChecked()

    def frame_range(self) -> tuple:
        return (self._frame_start.value(), self._frame_end.value())

    def set_path_preview(self, html: str):
        self._path_label.setText(html)

    @property
    def entry(self) -> dict:
        return self._entry


# ---------------------------------------------------------------------------
# _AssetTab
# ---------------------------------------------------------------------------

class _AssetTab(QWidget):
    def __init__(self, ctx: dict, publish_version: int, parent=None):
        super().__init__(parent)
        self._ctx = ctx
        self._publish_version = publish_version
        self._rop_rows: list[tuple] = []
        self._build_ui()
        self._connect_signals()
        self._rescan()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # Publish Name + Rescan
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Publish Name:"))
        self._pub_name_edit = QLineEdit()
        self._pub_name_edit.setPlaceholderText("e.g. dust-pass  (lowercase-kebab)")
        name_row.addWidget(self._pub_name_edit, stretch=1)
        self._rescan_btn = QPushButton("Rescan Hip")
        self._rescan_btn.setToolTip("Re-scan /out for publishable OUT_ ROPs")
        name_row.addWidget(self._rescan_btn)
        root.addLayout(name_row)

        tip = QLabel(
            "ROPs must be at /out and named with the OUT_ prefix (e.g. OUT_dust-pass)."
        )
        tip.setStyleSheet("color: #888; font-size: 10px;")
        root.addWidget(tip)

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

        # Preview group
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

        root.addWidget(QLabel("Description:"))
        self._desc_edit = QPlainTextEdit()
        self._desc_edit.setMaximumHeight(70)
        self._desc_edit.setPlaceholderText("Optional notes about this publish…")
        root.addWidget(self._desc_edit)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(
            "padding: 4px; border-radius: 3px; background: transparent;"
        )
        root.addWidget(self._status_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._publish_btn = QPushButton("Publish")
        self._publish_btn.setEnabled(False)
        self._publish_btn.setStyleSheet(
            "QPushButton { background: #2a7a2a; color: white; font-weight: bold;"
            " padding: 6px 24px; border-radius: 4px; }"
            "QPushButton:disabled { background: #444; color: #888; }"
            "QPushButton:hover:enabled { background: #3a9a3a; }"
        )
        btn_row.addWidget(self._publish_btn)
        root.addLayout(btn_row)

        ctx = self._ctx
        self._pub_name_edit.setText(ctx["task"])

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

    def _rescan(self):
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
                    pub_name, fmt, self._publish_version, animated,
                )
            except ValueError:
                row.set_path_preview(
                    "<span style='color:#f88;'>Unknown format</span>"
                )
                continue

            short = str(target)
            if short.startswith(projects_root_str):
                short = "…" + short[len(projects_root_str):]

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
        pub_name = self._pub_name_edit.text().strip()
        has_name = bool(pub_name)
        has_checked = any(row.is_checked() for _, row in self._rop_rows)
        self._publish_btn.setEnabled(has_name and has_checked)

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
        version = self._publish_version
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

            exec_parm = node.parm("execute")
            if exec_parm is not None:
                exec_parm.pressButton()
            else:
                node.render()

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

        self._set_status("Generating preview…", "#8cf")
        preview_result = self._maybe_generate_preview(publish_name)
        mp4_path = preview_result.get("mp4_path") if preview_result else None
        snapshot_path = None

        self._set_status("Saving hip snapshot…", "#8cf")
        try:
            snapshot_path, next_work = pipeline.snapshot_and_increment_hip(
                entity_root, hip_path, task, descriptor, hip_version
            )
            logger.info("Next work hip: %s", next_work)
        except RuntimeError as e:
            logger.warning("Hip snapshot skipped: %s", e)

        published_by = os.getenv("USER", "unknown")
        published_at = datetime.datetime.now().isoformat()

        # Determine preview dir (shared across all ROPs in this publish)
        preview_dir = Path(preview_result["jpg_path"]).parent if preview_result else None
        preview_frame_start = preview_result["first_frame"] if preview_result else None
        preview_frame_end   = preview_result["last_frame"]  if preview_result else None

        for node, fmt, animated, target in published_paths:
            pub_dir = target.parent

            # Get ROP frame range for animated geo sequences
            fs = fe = None
            if animated:
                fs, fe = _rop_frame_range(node)

            ctx = {
                "entity": entity,
                "task": task,
                "publish_name": publish_name,
                "version": version,
                "product_type": "asset",
                "animated": animated,
                "frame_start": fs,
                "frame_end": fe,
                "published_by": published_by,
                "published_at": published_at,
                "hip_snapshot": str(snapshot_path) if snapshot_path else None,
                "preview_dir": preview_dir,
                "expect_mp4": preview_result is not None and animated,
            }

            try:
                product = pipeline.build_publish_product(pub_dir, ctx)
            except ValueError as exc:
                raise RuntimeError(
                    f"Publish validation failed for {node.name()}:\n{exc}"
                ) from exc

            pipeline.write_metadata(pub_dir, product.to_dict())

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
        version = self._publish_version

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
# _FlipbookTab
# ---------------------------------------------------------------------------

class _FlipbookTab(QWidget):
    def __init__(self, ctx: dict, flipbook_version: int, parent=None):
        super().__init__(parent)
        self._ctx = ctx
        self._flipbook_version = flipbook_version
        self._build_ui()

    def _build_ui(self):
        ctx = self._ctx
        task = ctx["task"]
        ver = self._flipbook_version

        root = QVBoxLayout(self)
        root.setSpacing(8)

        info = QLabel(
            f"Publishes to: preview/flipbook/{task}/v{ver:03d}/"
        )
        info.setStyleSheet("color: #888; font-size: 10px;")
        root.addWidget(info)

        # Frame range
        frame_start_default = 1
        frame_end_default = 100
        try:
            import hou
            fr = hou.playbar.frameRange()
            frame_start_default = int(fr[0])
            frame_end_default = int(fr[1])
        except Exception:
            pass

        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Frame range:"))
        self._frame_start = QSpinBox()
        self._frame_start.setRange(1, 99999)
        self._frame_start.setValue(frame_start_default)
        self._frame_end = QSpinBox()
        self._frame_end.setRange(1, 99999)
        self._frame_end.setValue(frame_end_default)
        range_row.addWidget(self._frame_start)
        range_row.addWidget(QLabel("–"))
        range_row.addWidget(self._frame_end)
        range_row.addStretch()
        root.addLayout(range_row)

        # Resolution
        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("Resolution:"))
        self._res_w = QSpinBox()
        self._res_w.setRange(1, 7680)
        self._res_w.setValue(1280)
        self._res_h = QSpinBox()
        self._res_h.setRange(1, 4320)
        self._res_h.setValue(720)
        res_row.addWidget(self._res_w)
        res_row.addWidget(QLabel("×"))
        res_row.addWidget(self._res_h)
        res_row.addStretch()
        root.addLayout(res_row)

        # Camera
        cam_row = QHBoxLayout()
        cam_row.addWidget(QLabel("Camera:"))
        self._cam_combo = QComboBox()
        self._cam_combo.addItem("<Current Viewport>")
        for cam in _list_obj_cameras():
            self._cam_combo.addItem(cam)
        cam_row.addWidget(self._cam_combo, stretch=1)
        root.addLayout(cam_row)

        root.addWidget(QLabel("Description:"))
        self._desc_edit = QPlainTextEdit()
        self._desc_edit.setMaximumHeight(60)
        self._desc_edit.setPlaceholderText("Optional notes about this flipbook…")
        root.addWidget(self._desc_edit)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(
            "padding: 4px; border-radius: 3px; background: transparent;"
        )
        root.addWidget(self._status_label)

        root.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._publish_btn = QPushButton("Publish Flipbook")
        self._publish_btn.setStyleSheet(
            "QPushButton { background: #2a7a2a; color: white; font-weight: bold;"
            " padding: 6px 24px; border-radius: 4px; }"
            "QPushButton:hover { background: #3a9a3a; }"
        )
        self._publish_btn.clicked.connect(self._on_publish)
        btn_row.addWidget(self._publish_btn)
        root.addLayout(btn_row)

    def _set_status(self, msg: str, color: str = "#ccc"):
        self._status_label.setStyleSheet(
            f"padding: 4px; border-radius: 3px; background: #222; color: {color};"
        )
        self._status_label.setText(msg)
        QApplication.processEvents()

    def _on_publish(self):
        start = self._frame_start.value()
        end = self._frame_end.value()
        if end < start:
            QMessageBox.warning(self, "Invalid Frame Range", "End frame must be >= start frame.")
            return

        ctx = self._ctx
        entity_root = ctx["entity_root"]
        entity = ctx["entity"]
        task = ctx["task"]
        descriptor = ctx["descriptor"]
        hip_path = ctx["hip_path"]
        hip_version = ctx["hip_version"]
        ver = self._flipbook_version

        w = self._res_w.value()
        h = self._res_h.value()
        cam_text = self._cam_combo.currentText()
        camera = None if cam_text == "<Current Viewport>" else cam_text
        description = self._desc_edit.toPlainText().strip()

        self._publish_btn.setEnabled(False)
        try:
            self._do_publish(entity_root, entity, task, descriptor, hip_path,
                             hip_version, ver, start, end, w, h, camera, description)
        except Exception as e:
            self._set_status(f"Flipbook failed: {e}", "#f88")
            logger.error("Flipbook publish failed: %s", e)
            QMessageBox.critical(self, "Flipbook Failed", str(e))
        finally:
            self._publish_btn.setEnabled(True)

    def _do_publish(self, entity_root, entity, task, descriptor, hip_path,
                    hip_version, ver, start, end, w, h, camera, description):
        self._set_status("Capturing flipbook…", "#8cf")

        jpg_path_obj = pipeline.build_preview_jpg_path(
            entity_root, entity, task, "flipbook", ver, animated=True
        )
        jpg_path_obj.parent.mkdir(parents=True, exist_ok=True)

        pipeline.flipbook_viewport(
            str(jpg_path_obj), (start, end), camera, resolution=(w, h)
        )

        self._set_status("Encoding MP4…", "#8cf")
        mp4_path = pipeline.build_mp4_path(entity_root, entity, task, "flipbook", ver)
        mp4_path.parent.mkdir(parents=True, exist_ok=True)
        pipeline.encode_mp4(str(jpg_path_obj), str(mp4_path), frame_start=start)

        snapshot_path = None
        self._set_status("Saving hip snapshot…", "#8cf")
        try:
            snapshot_path, _next_work = pipeline.snapshot_and_increment_hip(
                entity_root, hip_path, task, descriptor, hip_version
            )
        except Exception as e:
            logger.warning("Hip snapshot skipped: %s", e)

        ctx = {
            "entity": entity,
            "task": task,
            "publish_name": "flipbook",
            "version": ver,
            "product_type": "flipbook",
            "animated": True,
            "frame_start": start,
            "frame_end": end,
            "expect_mp4": True,
            "published_by": os.getenv("USER", "unknown"),
            "published_at": datetime.datetime.now().isoformat(),
            "hip_snapshot": str(snapshot_path) if snapshot_path else None,
        }

        try:
            product = pipeline.build_publish_product(mp4_path.parent, ctx)
        except ValueError as exc:
            raise RuntimeError(f"Flipbook validation failed:\n{exc}") from exc

        pipeline.write_metadata(mp4_path.parent, product.to_dict())

        self._set_status(f"Flipbook v{ver:03d} published.", "#4e4")


# ---------------------------------------------------------------------------
# _RenderTab
# ---------------------------------------------------------------------------

class _RenderTab(QWidget):
    def __init__(self, ctx: dict, render_version: int, parent=None):
        super().__init__(parent)
        self._ctx = ctx
        self._render_version = render_version
        self._rop_rows: list[_RenderRopRow] = []
        self._validated = False
        self._validated_entries: list[dict] = []
        self._build_ui()
        self._rescan()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        tip = QLabel(
            "Scans /out for OUT_* nodes with USD ROP types "
            f"({', '.join(sorted(_USD_ROP_TYPES))}). "
            "Validate wires Karma RS picture parm and USD output path before rendering."
        )
        tip.setStyleSheet("color: #888; font-size: 10px;")
        tip.setWordWrap(True)
        root.addWidget(tip)

        header_row = QHBoxLayout()
        rop_header = QLabel("USD ROPs to render")
        font = rop_header.font()
        font.setBold(True)
        rop_header.setFont(font)
        header_row.addWidget(rop_header)
        header_row.addStretch()
        self._rescan_btn = QPushButton("Rescan")
        self._rescan_btn.clicked.connect(self._on_rescan)
        header_row.addWidget(self._rescan_btn)
        root.addLayout(header_row)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setMinimumHeight(150)
        self._scroll_area.setMaximumHeight(300)
        scroll_inner = QWidget()
        self._rop_list_layout = QVBoxLayout(scroll_inner)
        self._rop_list_layout.setContentsMargins(2, 2, 2, 2)
        self._rop_list_layout.setSpacing(2)
        self._rop_list_layout.addStretch()
        self._scroll_area.setWidget(scroll_inner)
        root.addWidget(self._scroll_area)

        root.addWidget(QLabel("Description:"))
        self._desc_edit = QPlainTextEdit()
        self._desc_edit.setMaximumHeight(60)
        self._desc_edit.setPlaceholderText("Optional notes about this render publish…")
        root.addWidget(self._desc_edit)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(
            "padding: 4px; border-radius: 3px; background: transparent;"
        )
        root.addWidget(self._status_label)

        root.addStretch()

        btn_row = QHBoxLayout()
        self._validate_btn = QPushButton("Validate")
        self._validate_btn.setStyleSheet(
            "QPushButton { background: #1a4a8a; color: white; font-weight: bold;"
            " padding: 6px 18px; border-radius: 4px; }"
            "QPushButton:hover { background: #2a5aaa; }"
        )
        self._validate_btn.clicked.connect(self._on_validate)
        btn_row.addWidget(self._validate_btn)
        btn_row.addStretch()

        self._render_btn = QPushButton("Render Locally")
        self._render_btn.setEnabled(False)
        self._render_btn.setStyleSheet(
            "QPushButton { background: #2a7a2a; color: white; font-weight: bold;"
            " padding: 6px 24px; border-radius: 4px; }"
            "QPushButton:disabled { background: #444; color: #888; }"
            "QPushButton:hover:enabled { background: #3a9a3a; }"
        )
        self._render_btn.clicked.connect(self._on_render)
        btn_row.addWidget(self._render_btn)
        root.addLayout(btn_row)

    def _invalidate(self):
        self._validated = False
        self._validated_entries = []
        self._render_btn.setEnabled(False)

    def _on_rescan(self):
        self._rescan()
        self._invalidate()

    def _rescan(self):
        while self._rop_list_layout.count() > 1:
            item = self._rop_list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._rop_rows = []

        try:
            entries = _scan_usd_rops()
        except RuntimeError:
            entries = []

        for entry in entries:
            row = _RenderRopRow(entry)
            row.changed.connect(self._invalidate)
            self._rop_list_layout.insertWidget(
                self._rop_list_layout.count() - 1, row
            )
            self._rop_rows.append(row)

        if not entries:
            placeholder = QLabel(
                "No OUT_* USD ROPs found in /out."
            )
            placeholder.setStyleSheet("color: #888; font-style: italic;")
            placeholder.setAlignment(Qt.AlignCenter)
            self._rop_list_layout.insertWidget(0, placeholder)

    def _set_status(self, msg: str, color: str = "#ccc"):
        self._status_label.setStyleSheet(
            f"padding: 4px; border-radius: 3px; background: #222; color: {color};"
        )
        self._status_label.setText(msg)
        QApplication.processEvents()

    def _on_validate(self):
        ctx = self._ctx
        entity_root = ctx["entity_root"]
        entity = ctx["entity"]
        task = ctx["task"]
        descriptor = ctx["descriptor"]
        ver = self._render_version

        checked_rows = [r for r in self._rop_rows if r.is_checked()]
        if not checked_rows:
            self._set_status("No ROPs selected.", "#f88")
            return

        projects_root_str = str(pipeline.projects_root())
        validated = []

        for row in checked_rows:
            entry = row.entry
            node = entry["node"]
            rop_name = entry["rop_name"]
            frame_start, frame_end = row.frame_range()

            karma_rs = _find_karma_rs(node)
            if karma_rs is None:
                self._set_status(
                    f"No Karma Render Settings found upstream of {node.name()}.", "#f88"
                )
                self._invalidate()
                return

            picture_parm = karma_rs.parm("picture")
            if picture_parm is None:
                self._set_status(
                    f"'picture' parm not found on {karma_rs.name()}.", "#f88"
                )
                self._invalidate()
                return

            exr_path = pipeline.build_exr_path(
                entity_root, entity, task, descriptor, rop_name, ver
            )
            usd_path = pipeline.build_usd_cache_path(
                entity_root, entity, task, descriptor, ver
            )

            exr_path.parent.mkdir(parents=True, exist_ok=True)
            usd_path.parent.mkdir(parents=True, exist_ok=True)

            picture_parm.set(str(exr_path))

            # Set USD output parm
            usd_out_parm = None
            for pname in ("lopoutput", "usdfile", "output"):
                p = node.parm(pname)
                if p is not None:
                    usd_out_parm = p
                    break

            if usd_out_parm is None:
                self._set_status(
                    f"Cannot find USD output parm on {node.name()}.", "#f88"
                )
                self._invalidate()
                return

            usd_out_parm.set(str(usd_path))

            trange = node.parm("trange")
            if trange is not None:
                trange.set(1)

            f1_parm = node.parm("f1")
            f2_parm = node.parm("f2")
            if f1_parm is not None:
                f1_parm.deleteAllKeyframes()
                f1_parm.set(frame_start)
            if f2_parm is not None:
                f2_parm.deleteAllKeyframes()
                f2_parm.set(frame_end)

            short = str(exr_path)
            if short.startswith(projects_root_str):
                short = "…/" + short[len(projects_root_str):].lstrip("/")
            row.set_path_preview(f"<span style='color:#8cf;'>{short}</span>")

            validated.append({
                "node": node,
                "rop_name": rop_name,
                "exr_path": exr_path,
                "usd_path": usd_path,
                "frame_start": frame_start,
                "frame_end": frame_end,
            })

        self._validated = True
        self._validated_entries = validated
        self._render_btn.setEnabled(True)
        self._set_status(
            f"Validated — {len(validated)} ROP(s) ready. Click Render Locally.", "#8cf"
        )

    def _on_render(self):
        if not self._validated:
            QMessageBox.warning(self, "Not Validated", "Please run Validate first.")
            return

        ctx = self._ctx
        entity_root = ctx["entity_root"]
        entity = ctx["entity"]
        task = ctx["task"]
        descriptor = ctx["descriptor"]
        hip_path = ctx["hip_path"]
        hip_version = ctx["hip_version"]
        ver = self._render_version
        description = self._desc_edit.toPlainText().strip()

        self._render_btn.setEnabled(False)
        self._validate_btn.setEnabled(False)

        try:
            self._do_render(entity_root, entity, task, descriptor, hip_path,
                            hip_version, ver, description)
        except Exception as e:
            self._set_status(f"Render failed: {e}", "#f88")
            logger.error("Render failed: %s", e)
            QMessageBox.critical(self, "Render Failed", str(e))
        finally:
            self._render_btn.setEnabled(self._validated)
            self._validate_btn.setEnabled(True)

    def _do_render(self, entity_root, entity, task, descriptor, hip_path,
                   hip_version, ver, description):
        entries = self._validated_entries
        published_by = os.getenv("USER", "unknown")
        published_at = datetime.datetime.now().isoformat()

        for i, entry in enumerate(entries):
            node = entry["node"]
            rop_name = entry["rop_name"]
            exr_path = entry["exr_path"]
            usd_path = entry["usd_path"]
            frame_start = entry["frame_start"]
            frame_end = entry["frame_end"]

            self._set_status(
                f"Cooking {node.name()} ({i + 1}/{len(entries)})…", "#8cf"
            )

            # usdrender_rop renders; usd_rop only exports — artist renders from Houdini manually
            exec_parm = node.parm("execute")
            if exec_parm is not None:
                exec_parm.pressButton()
            else:
                node.render()

            if not usd_path.exists():
                logger.warning("USD file not found after cook: %s", usd_path)

            # Non-fatal preview encode
            self._set_status(f"Encoding preview for {rop_name}…", "#8cf")
            try:
                mp4_path = pipeline.build_mp4_path(
                    entity_root, entity, task, rop_name, ver
                )
                mp4_path.parent.mkdir(parents=True, exist_ok=True)
                pipeline.encode_mp4_from_exr(
                    str(exr_path), str(mp4_path), frame_start=frame_start
                )
            except Exception as e:
                QMessageBox.warning(
                    self, "Preview Warning",
                    f"MP4 preview failed for {rop_name} (render continues):\n{e}"
                )
                mp4_path = None

            entry["mp4_path"] = mp4_path

        # Hip snapshot (non-fatal)
        snapshot_path = None
        self._set_status("Saving hip snapshot…", "#8cf")
        try:
            snapshot_path, _next_work = pipeline.snapshot_and_increment_hip(
                entity_root, hip_path, task, descriptor, hip_version
            )
        except Exception as e:
            logger.warning("Hip snapshot skipped: %s", e)

        for entry in entries:
            rop_name      = entry["rop_name"]
            exr_path      = entry["exr_path"]
            exr_pub_dir   = exr_path.parent
            mp4_path      = entry.get("mp4_path")
            frame_start_e = entry["frame_start"]
            frame_end_e   = entry["frame_end"]

            ctx = {
                "entity": entity,
                "task": task,
                "publish_name": rop_name,
                "version": ver,
                "product_type": "render",
                "animated": True,
                "frame_start": frame_start_e,
                "frame_end": frame_end_e,
                "published_by": published_by,
                "published_at": published_at,
                "hip_snapshot": str(snapshot_path) if snapshot_path else None,
                "usd_path": str(entry["usd_path"]),
                "preview_dir": mp4_path.parent if mp4_path else None,
                "expect_mp4": mp4_path is not None,
            }

            try:
                product = pipeline.build_publish_product(exr_pub_dir, ctx)
            except ValueError as exc:
                raise RuntimeError(
                    f"Render validation failed for {rop_name}:\n{exc}"
                ) from exc

            pipeline.write_metadata(exr_pub_dir, product.to_dict())

        self._set_status(
            f"Rendered v{ver:03d} — {len(entries)} ROP(s) done.", "#4e4"
        )


# ---------------------------------------------------------------------------
# Helpers — GLB publish
# ---------------------------------------------------------------------------

def _scan_gltf_rops() -> list:
    """
    Search the whole scene for GLTF ROP nodes.
    Covers /obj/**/* (e.g. /obj/SIM/OUT_SNOWMAN_GLTF) and /out/* as fallback.
    """
    try:
        import hou
    except ImportError:
        raise RuntimeError("Must run inside Houdini.")
    results = []
    seen = set()

    def _collect(node):
        for child in node.allSubChildren():
            if child.path() in seen:
                continue
            seen.add(child.path())
            if child.type().name() in _GLTF_ROP_TYPES:
                results.append(child)

    obj_root = hou.node("/obj")
    if obj_root:
        _collect(obj_root)

    # Also check /out in case someone put one there
    out_root = hou.node("/out")
    if out_root:
        for child in out_root.children():
            if child.path() not in seen and child.type().name() in _GLTF_ROP_TYPES:
                results.append(child)

    return results


def _capture_viewport_thumbnail(out_path: Path):
    """Snapshot the first SceneViewer pane into out_path (JPEG)."""
    try:
        import hou
        viewers = _list_scene_viewers()
        if not viewers:
            return False
        viewers[0].curViewport().snapshot(str(out_path))
        return out_path.exists()
    except Exception as e:
        logger.warning("Thumbnail capture failed: %s", e)
        return False


def _export_glb_from_rop(node, out_path: Path, frame_range: tuple, animated: bool):
    """Tell a GLTF ROP to render into out_path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    file_parm = node.parm("file") or node.parm("sopoutput") or node.parm("filename")
    if file_parm is None:
        raise RuntimeError(f"Cannot find output path parm on {node.name()}")
    file_parm.set(str(out_path))
    if animated:
        trange = node.parm("trange")
        if trange is not None:
            trange.set(1)
        f1, f2 = node.parm("f1"), node.parm("f2")
        if f1 is not None:
            f1.deleteAllKeyframes(); f1.set(frame_range[0])
        if f2 is not None:
            f2.deleteAllKeyframes(); f2.set(frame_range[1])
    exec_parm = node.parm("execute")
    if exec_parm is not None:
        exec_parm.pressButton()
    else:
        node.render()
    if not out_path.exists():
        raise RuntimeError(f"GLB not found after cook: {out_path}")


def _export_glb_from_sop(sop_path: str, out_path: Path, frame_range: tuple, animated: bool):
    """
    Create a temporary GLTF ROP in /out, point it at sop_path, render, then destroy it.
    Falls back with a clear error if rop_gltf is not available.
    """
    try:
        import hou
    except ImportError:
        raise RuntimeError("Must run inside Houdini.")

    rop_parent = hou.node("/out")
    available_types = {t.name() for t in hou.ropNodeTypeCategory().nodeTypes().values()}
    gltf_type = next((t for t in _GLTF_ROP_TYPES if t in available_types), None)
    if gltf_type is None:
        raise RuntimeError(
            "No GLTF ROP type found in this Houdini build.\n"
            "Create an OUT_* GLTF ROP in /out to use ROP mode instead."
        )

    tmp = rop_parent.createNode(gltf_type, "__glb_publisher_tmp__")
    try:
        _export_glb_from_rop(tmp, out_path, frame_range, animated)
        # Point at the user's SOP after creation (parm name varies by version)
        for pname in ("soppath", "sop", "inputnode"):
            p = tmp.parm(pname)
            if p is not None:
                p.set(sop_path)
                break
        exec_parm = tmp.parm("execute")
        if exec_parm is not None:
            exec_parm.pressButton()
        else:
            tmp.render()
    finally:
        tmp.destroy()

    if not out_path.exists():
        raise RuntimeError(f"GLB not found after cook: {out_path}")


# ---------------------------------------------------------------------------
# Topology detection + VAT / frame-sequence export helpers
# ---------------------------------------------------------------------------

def _detect_topology_change(sop_node, frame_start: int, frame_end: int) -> tuple:
    """
    Cook the SOP at frame_start and frame_end and compare point counts.
    Returns (is_dynamic, pts_start, pts_end).
    """
    try:
        import hou
        geo_s = sop_node.geometryAtFrame(frame_start)
        geo_e = sop_node.geometryAtFrame(frame_end)
        pts_s = geo_s.intrinsicValue("pointcount") if geo_s else 0
        pts_e = geo_e.intrinsicValue("pointcount") if geo_e else 0
        return pts_s != pts_e, pts_s, pts_e
    except Exception as exc:
        logger.warning("Topology detection failed: %s", exc)
        return False, 0, 0


def _get_source_sop(gltf_rop_node):
    """Return the SOP node that feeds a GLTF ROP, or None."""
    try:
        import hou
    except ImportError:
        return None
    for pname in ("soppath", "sop", "inputnode"):
        p = gltf_rop_node.parm(pname)
        if p is not None:
            path = p.evalAsString()
            if path:
                node = hou.node(path)
                if node is not None:
                    return node
    return None


def _export_vat(sop_node, out_dir: Path, frame_start: int, frame_end: int,
                fps: int = 24, rop_node=None) -> dict:
    """
    Bake a Vertex Animation Texture set for a fixed-topology deforming sim.
    Writes: mesh.glb, vat_pos.bin, vat.json
    Returns the vat metadata dict.

    Layout of vat_pos.bin: Float32 RGBA per vertex per frame.
    Row = frame index (0..frame_count-1), col = vertex index (0..vertex_count-1).
    Total floats = frame_count × vertex_count × 4.
    """
    import struct
    import json as _json

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    vertex_count = None
    all_floats: list[float] = []
    bmin = [1e9, 1e9, 1e9]
    bmax = [-1e9, -1e9, -1e9]

    for f in range(frame_start, frame_end + 1):
        geo = sop_node.geometryAtFrame(f)
        pts = geo.intrinsicValue("pointcount")
        if vertex_count is None:
            vertex_count = pts
        elif pts != vertex_count:
            raise RuntimeError(
                f"Topology changed at frame {f} ({pts} pts vs {vertex_count}). "
                "Use Frame Sequence mode instead."
            )

        try:
            pos_flat = geo.pointFloatAttribValues("P")
        except Exception:
            pos_flat = []
            for pt in geo.points():
                p = pt.position()
                pos_flat.extend([float(p[0]), float(p[1]), float(p[2])])

        for i in range(0, len(pos_flat), 3):
            x, y, z = float(pos_flat[i]), float(pos_flat[i + 1]), float(pos_flat[i + 2])
            all_floats.extend([x, y, z, 1.0])
            if x < bmin[0]: bmin[0] = x
            if y < bmin[1]: bmin[1] = y
            if z < bmin[2]: bmin[2] = z
            if x > bmax[0]: bmax[0] = x
            if y > bmax[1]: bmax[1] = y
            if z > bmax[2]: bmax[2] = z

        logger.debug("VAT: baked frame %d (%d pts)", f, pts)

    vertex_count = vertex_count or 0
    frame_count = frame_end - frame_start + 1

    bin_path = out_dir / "vat_pos.bin"
    bin_path.write_bytes(struct.pack(f"<{len(all_floats)}f", *all_floats))
    logger.info("VAT: %s (%.1f MB)", bin_path, bin_path.stat().st_size / 1e6)

    # Rest-pose mesh at frame_start
    mesh_path = out_dir / "mesh.glb"
    try:
        import hou
        hou.setFrame(frame_start)
    except Exception:
        pass
    if rop_node is not None:
        _export_glb_from_rop(rop_node, mesh_path, (frame_start, frame_start), animated=False)
    elif sop_node is not None:
        _export_glb_from_sop(sop_node.path(), mesh_path, (frame_start, frame_start), animated=False)
    else:
        raise RuntimeError("VAT export needs a ROP or SOP node for the rest mesh.")

    vat_meta = {
        "vertex_count": vertex_count,
        "frame_count": frame_count,
        "fps": fps,
        "frame_start": frame_start,
        "frame_end": frame_end,
        "bounds": {"min": bmin, "max": bmax},
    }
    (out_dir / "vat.json").write_text(_json.dumps(vat_meta, indent=2))
    logger.info("VAT export complete: %d verts × %d frames", vertex_count, frame_count)
    return vat_meta


def _export_frame_sequence(out_dir: Path, frame_start: int, frame_end: int,
                           rop_node=None, sop_path: str = None) -> dict:
    """
    Export one static GLB per frame for topology-changing simulations.
    Writes: frames/frame_NNNN.glb, frame_sequence.json
    Returns the frame_sequence metadata dict.
    """
    import json as _json

    out_dir = Path(out_dir)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    frame_count = frame_end - frame_start + 1
    logger.info("Frame sequence: exporting %d frames", frame_count)

    for f in range(frame_start, frame_end + 1):
        glb_path = frames_dir / f"frame_{f:04d}.glb"
        try:
            import hou
            hou.setFrame(f)
        except Exception:
            pass
        if rop_node is not None:
            _export_glb_from_rop(rop_node, glb_path, (f, f), animated=False)
        elif sop_path:
            _export_glb_from_sop(sop_path, glb_path, (f, f), animated=False)
        else:
            raise RuntimeError("Frame sequence export needs a ROP or SOP path.")
        logger.debug("Frame sequence: frame %d done", f)

    seq_meta = {
        "frame_start": frame_start,
        "frame_end": frame_end,
        "frame_count": frame_count,
    }
    (out_dir / "frame_sequence.json").write_text(_json.dumps(seq_meta, indent=2))
    return seq_meta


# ---------------------------------------------------------------------------
# _GlbRopRow  (mirrors _RopRow for GLTF ROPs)
# ---------------------------------------------------------------------------

class _GlbRopRow(QWidget):
    toggled = Signal(bool)

    def __init__(self, node, parent=None):
        super().__init__(parent)
        self._node = node
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        # Show full path so identically-named nodes in different subnets are distinguishable
        self._check = QCheckBox(node.path())
        font = self._check.font()
        font.setBold(True)
        self._check.setFont(font)
        self._check.setChecked(True)
        self._check.toggled.connect(self.toggled)

        tag = QLabel("GLB")
        tag.setStyleSheet(
            "color: white; background: #7a4ae2; border-radius: 3px; padding: 1px 5px;"
        )
        tag.setFixedWidth(36)

        self._anim_check = QCheckBox("Animated")
        f1, f2 = _rop_frame_range(node)
        self._frame_start = QSpinBox()
        self._frame_start.setRange(1, 99999)
        self._frame_start.setValue(f1)
        self._frame_start.setFixedWidth(64)
        self._frame_end = QSpinBox()
        self._frame_end.setRange(1, 99999)
        self._frame_end.setValue(f2)
        self._frame_end.setFixedWidth(64)

        self._export_mode = QComboBox()
        self._export_mode.addItems(["Auto-detect", "GLTF", "VAT (fixed topo)", "Frame Sequence"])
        self._export_mode.setFixedWidth(150)
        self._export_mode.setVisible(False)
        self._export_mode.setToolTip(
            "Auto-detect: checks point count — routes to GLTF or Frame Sequence.\n"
            "VAT: bakes positions into a texture (fixed topology only).\n"
            "Frame Sequence: exports one GLB per frame (works for any topology)."
        )
        self._anim_check.toggled.connect(self._export_mode.setVisible)

        layout.addWidget(self._check)
        layout.addWidget(tag)
        layout.addWidget(self._anim_check)
        layout.addWidget(QLabel("Frames:"))
        layout.addWidget(self._frame_start)
        layout.addWidget(QLabel("–"))
        layout.addWidget(self._frame_end)
        layout.addWidget(self._export_mode)
        layout.addStretch()

    def is_checked(self) -> bool:
        return self._check.isChecked()

    def is_animated(self) -> bool:
        return self._anim_check.isChecked()

    def frame_range(self) -> tuple:
        return (self._frame_start.value(), self._frame_end.value())

    def export_mode(self) -> str:
        """Returns 'auto', 'gltf', 'vat', or 'frames'."""
        return ["auto", "gltf", "vat", "frames"][self._export_mode.currentIndex()]

    @property
    def node(self):
        return self._node


# ---------------------------------------------------------------------------
# _GlbTab
# ---------------------------------------------------------------------------

class _GlbTab(QWidget):
    def __init__(self, ctx: dict, parent=None):
        super().__init__(parent)
        self._ctx = ctx
        self._rop_rows: list[_GlbRopRow] = []
        self._build_ui()
        self._connect_signals()
        self._rescan()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ---- Publish target ----
        target_group = QGroupBox("Publish Target")
        target_layout = QVBoxLayout(target_group)

        proj_row = QHBoxLayout()
        proj_row.addWidget(QLabel("Project:"))
        self._project_combo = QComboBox()
        try:
            for proj in pipeline.load_projects():
                self._project_combo.addItem(proj.get("name", ""), proj.get("folder", ""))
        except Exception:
            pass
        if self._project_combo.count() == 0:
            self._project_combo.addItem("test", "test")
        proj_row.addWidget(self._project_combo, stretch=1)
        target_layout.addLayout(proj_row)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Asset name:"))
        self._asset_name_edit = QLineEdit()
        self._asset_name_edit.setPlaceholderText("lowercase-kebab or snake_case")
        ctx = self._ctx
        self._asset_name_edit.setText(ctx["entity"].lower().replace(" ", "_"))
        name_row.addWidget(self._asset_name_edit, stretch=1)
        target_layout.addLayout(name_row)

        tip = QLabel(
            "Publishes to: {shows_root}/assets/{project}/{asset_name}/\n"
            "  GLTF → asset.glb   |   VAT → mesh.glb + vat_pos.bin + vat.json\n"
            "  Frame Seq → frames/frame_NNNN.glb"
        )
        tip.setStyleSheet("color: #888; font-size: 10px;")
        target_layout.addWidget(tip)

        self._overwrite_check = QCheckBox("Overwrite existing asset")
        self._overwrite_check.setChecked(True)
        target_layout.addWidget(self._overwrite_check)

        root.addWidget(target_group)

        # ---- GLB source ----
        source_group = QGroupBox("GLB Source")
        source_layout = QVBoxLayout(source_group)

        mode_row = QHBoxLayout()
        self._rop_mode_check = QCheckBox("Use GLTF ROP  (scans all of /obj and /out)")
        self._rop_mode_check.setChecked(True)
        self._sop_mode_check = QCheckBox("Manual SOP path")
        mode_row.addWidget(self._rop_mode_check)
        mode_row.addWidget(self._sop_mode_check)
        mode_row.addStretch()
        source_layout.addLayout(mode_row)

        # ROP list
        rescan_row = QHBoxLayout()
        rescan_row.addWidget(QLabel("GLTF ROPs found in /out:"))
        rescan_row.addStretch()
        self._rescan_btn = QPushButton("Rescan")
        self._rescan_btn.setFixedWidth(72)
        rescan_row.addWidget(self._rescan_btn)
        source_layout.addLayout(rescan_row)

        self._rop_scroll = QScrollArea()
        self._rop_scroll.setWidgetResizable(True)
        self._rop_scroll.setMaximumHeight(140)
        scroll_inner = QWidget()
        self._rop_list_layout = QVBoxLayout(scroll_inner)
        self._rop_list_layout.setContentsMargins(2, 2, 2, 2)
        self._rop_list_layout.setSpacing(2)
        self._rop_list_layout.addStretch()
        self._rop_scroll.setWidget(scroll_inner)
        source_layout.addWidget(self._rop_scroll)

        # Manual SOP path (hidden by default)
        self._sop_row_widget = QWidget()
        sop_row = QHBoxLayout(self._sop_row_widget)
        sop_row.setContentsMargins(0, 0, 0, 0)
        sop_row.addWidget(QLabel("SOP path:"))
        self._sop_path_edit = QLineEdit()
        self._sop_path_edit.setPlaceholderText("/obj/geo1/OUT")
        sop_row.addWidget(self._sop_path_edit, stretch=1)
        self._sop_row_widget.setVisible(False)
        source_layout.addWidget(self._sop_row_widget)

        root.addWidget(source_group)

        # ---- Options ----
        opts_group = QGroupBox("Options")
        opts_layout = QVBoxLayout(opts_group)

        self._thumb_check = QCheckBox("Capture viewport thumbnail")
        self._thumb_check.setChecked(True)
        opts_layout.addWidget(self._thumb_check)

        root.addWidget(opts_group)

        # ---- Description + status ----
        root.addWidget(QLabel("Description:"))
        self._desc_edit = QPlainTextEdit()
        self._desc_edit.setMaximumHeight(60)
        self._desc_edit.setPlaceholderText("Optional notes about this GLB asset…")
        root.addWidget(self._desc_edit)

        root.addWidget(QLabel("Tags (comma-separated):"))
        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("fx, sim, vehicle")
        root.addWidget(self._tags_edit)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("padding: 4px; border-radius: 3px; background: transparent;")
        root.addWidget(self._status_label)

        root.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._publish_btn = QPushButton("Publish GLB")
        self._publish_btn.setStyleSheet(
            "QPushButton { background: #5a2a9a; color: white; font-weight: bold;"
            " padding: 6px 24px; border-radius: 4px; }"
            "QPushButton:disabled { background: #444; color: #888; }"
            "QPushButton:hover:enabled { background: #7a4ac0; }"
        )
        btn_row.addWidget(self._publish_btn)
        root.addLayout(btn_row)

    def _connect_signals(self):
        self._rescan_btn.clicked.connect(self._rescan)
        self._rop_mode_check.toggled.connect(self._on_mode_changed)
        self._sop_mode_check.toggled.connect(self._on_mode_changed)
        self._asset_name_edit.textChanged.connect(self._update_button_state)
        self._publish_btn.clicked.connect(self._on_publish)

    def _on_mode_changed(self):
        rop_mode = self._rop_mode_check.isChecked()
        self._rop_scroll.setVisible(rop_mode)
        self._rescan_btn.setVisible(rop_mode)
        self._sop_row_widget.setVisible(not rop_mode)
        self._update_button_state()

    def _rescan(self):
        while self._rop_list_layout.count() > 1:
            item = self._rop_list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._rop_rows = []

        try:
            rops = _scan_gltf_rops()
        except RuntimeError:
            rops = []

        for rop in rops:
            row = _GlbRopRow(rop)
            row.toggled.connect(self._update_button_state)
            self._rop_list_layout.insertWidget(self._rop_list_layout.count() - 1, row)
            self._rop_rows.append(row)

        if not rops:
            placeholder = QLabel(
                "No GLTF ROP nodes found in /obj or /out.\n"
                "Add a ROP GLTF Output node (e.g. /obj/SIM/OUT_SNOWMAN_GLTF)"
                " or switch to Manual SOP mode."
            )
            placeholder.setStyleSheet("color: #888; font-style: italic;")
            placeholder.setWordWrap(True)
            self._rop_list_layout.insertWidget(0, placeholder)

        self._update_button_state()

    def _update_button_state(self):
        has_name = bool(self._asset_name_edit.text().strip())
        rop_mode = self._rop_mode_check.isChecked()
        if rop_mode:
            has_source = any(row.is_checked() for row in self._rop_rows)
        else:
            has_source = bool(self._sop_path_edit.text().strip())
        self._publish_btn.setEnabled(has_name and has_source)

    def _set_status(self, msg: str, color: str = "#ccc"):
        self._status_label.setStyleSheet(
            f"padding: 4px; border-radius: 3px; background: #222; color: {color};"
        )
        self._status_label.setText(msg)
        QApplication.processEvents()

    def _on_publish(self):
        asset_name_raw = self._asset_name_edit.text().strip()
        if not asset_name_raw:
            QMessageBox.warning(self, "Missing Asset Name", "Enter an asset name.")
            return

        import re
        asset_name = re.sub(r"[^\w\-]+", "_", asset_name_raw).strip("_").lower()
        if not asset_name:
            QMessageBox.warning(self, "Invalid Asset Name", "Asset name is invalid after sanitising.")
            return

        project_folder = self._project_combo.currentData() or self._project_combo.currentText()
        dest_dir = pipeline.projects_root() / "assets" / project_folder / asset_name

        if dest_dir.exists() and not self._overwrite_check.isChecked():
            QMessageBox.warning(
                self, "Already Exists",
                f"Asset already exists at:\n{dest_dir}\n\nEnable 'Overwrite' to replace it."
            )
            return

        self._publish_btn.setEnabled(False)
        try:
            self._do_publish(asset_name, project_folder, dest_dir)
        except Exception as e:
            self._set_status(f"GLB publish failed: {e}", "#f88")
            logger.error("GLB publish failed: %s", e, exc_info=True)
            QMessageBox.critical(self, "Publish Failed", str(e))
        finally:
            self._publish_btn.setEnabled(True)

    def _do_publish(self, asset_name: str, project_folder: str, dest_dir: Path):
        import datetime
        import json as _json

        rop_mode = self._rop_mode_check.isChecked()
        checked_rows = [r for r in self._rop_rows if r.is_checked()]

        dest_dir.mkdir(parents=True, exist_ok=True)

        animated = False
        frame_range = (1, 1)
        format_type = "gltf_static"
        vat_meta = None
        seq_meta = None

        if rop_mode:
            if not checked_rows:
                raise RuntimeError("No GLTF ROP selected.")
            row = checked_rows[0]
            animated = row.is_animated()
            frame_range = row.frame_range()
            mode = row.export_mode() if animated else "gltf"

            if animated:
                if mode == "auto":
                    self._set_status("Detecting topology change…", "#8cf")
                    sop = _get_source_sop(row.node)
                    if sop is not None:
                        is_dyn, pts_s, pts_e = _detect_topology_change(
                            sop, frame_range[0], frame_range[1]
                        )
                        if is_dyn:
                            mode = "frames"
                            self._set_status(
                                f"Topology dynamic ({pts_s}→{pts_e} pts) → Frame Sequence", "#fa4"
                            )
                        else:
                            mode = "gltf"
                            self._set_status(f"Topology stable ({pts_s} pts) → GLTF", "#8cf")
                    else:
                        mode = "gltf"

                if mode == "vat":
                    sop = _get_source_sop(row.node)
                    if sop is None:
                        raise RuntimeError(
                            "Cannot find source SOP for VAT bake.\n"
                            "Set the soppath parm on your GLTF ROP, or use Manual SOP mode."
                        )
                    self._set_status(
                        f"Baking VAT ({frame_range[0]}–{frame_range[1]})…", "#8cf"
                    )
                    vat_meta = _export_vat(
                        sop, dest_dir,
                        frame_range[0], frame_range[1],
                        fps=24, rop_node=row.node,
                    )
                    format_type = "vat"

                elif mode == "frames":
                    self._set_status(
                        f"Exporting frame sequence ({frame_range[0]}–{frame_range[1]})…", "#8cf"
                    )
                    seq_meta = _export_frame_sequence(
                        dest_dir, frame_range[0], frame_range[1],
                        rop_node=row.node,
                    )
                    format_type = "frame_sequence"

                else:
                    glb_path = dest_dir / "asset.glb"
                    self._set_status(f"Exporting GLB via {row.node.name()}…", "#8cf")
                    _export_glb_from_rop(row.node, glb_path, frame_range, animated=True)
                    format_type = "gltf_animated"

            else:
                glb_path = dest_dir / "asset.glb"
                self._set_status(f"Exporting GLB via {row.node.name()}…", "#8cf")
                _export_glb_from_rop(row.node, glb_path, frame_range, animated=False)
                format_type = "gltf_static"

        else:
            sop_path = self._sop_path_edit.text().strip()
            if not sop_path:
                raise RuntimeError("No SOP path provided.")
            glb_path = dest_dir / "asset.glb"
            self._set_status(f"Exporting GLB from {sop_path}…", "#8cf")
            _export_glb_from_sop(sop_path, glb_path, (1, 1), animated=False)
            format_type = "gltf_static"

        if self._thumb_check.isChecked():
            self._set_status("Capturing thumbnail…", "#8cf")
            _capture_viewport_thumbnail(dest_dir / "thumbnail.jpg")

        try:
            import hou
            houdini_version = hou.applicationVersionString()
        except Exception:
            houdini_version = ""

        tags = [t.strip() for t in self._tags_edit.text().split(",") if t.strip()]
        meta = {
            "name": asset_name.replace("_", " ").replace("-", " ").title(),
            "author": os.getenv("USER", "artist"),
            "created": datetime.datetime.utcnow().isoformat() + "Z",
            "houdini_version": houdini_version,
            "format_type": format_type,
            "frame_range": list(frame_range),
            "tags": tags,
            "animations": ["Main"] if format_type == "gltf_animated" else [],
            "polycount": 0,
            "project": project_folder,
            "asset_name": asset_name,
            "description": self._desc_edit.toPlainText().strip(),
            "source_node": checked_rows[0].node.path() if rop_mode and checked_rows else "",
        }
        if vat_meta is not None:
            meta["vat"] = vat_meta
        if seq_meta is not None:
            meta["frame_sequence"] = seq_meta

        (dest_dir / "metadata.json").write_text(
            _json.dumps(meta, indent=2), encoding="utf-8"
        )

        self._set_status(f"Published {format_type} → {dest_dir}", "#4e4")
        logger.info("GLB published: %s (%s)", dest_dir, format_type)


# ---------------------------------------------------------------------------
# PublisherWindow
# ---------------------------------------------------------------------------

class PublisherWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(720, 680)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)

        # Context banner
        self._ctx_banner = QLabel("Initialising…")
        self._ctx_banner.setAlignment(Qt.AlignCenter)
        self._ctx_banner.setStyleSheet(
            "background: #1a2a4a; color: #cce; padding: 8px; border-radius: 4px;"
        )
        self._ctx_banner.setTextFormat(Qt.RichText)
        root.addWidget(self._ctx_banner)

        # Tab widget
        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        # Parse context
        try:
            ctx = _parse_publisher_context()
        except RuntimeError as e:
            self._fatal_ctx(str(e))
            return

        entity = ctx["entity"]
        task = ctx["task"]
        descriptor = ctx["descriptor"] or "main"
        entity_root = ctx["entity_root"]

        self.setWindowTitle(f"FX Publisher — {entity} | {task}")

        # Compute versions for each tab
        asset_version = pipeline.get_next_publish_version(entity_root, task, task)
        flipbook_version = pipeline.get_next_publish_version(entity_root, task, "flipbook")
        render_version = pipeline.get_next_render_version(entity_root, task)

        self._ctx_banner.setText(
            f"<b>{entity}</b> &nbsp;·&nbsp; task: <b>{task}</b>"
            f" &nbsp;·&nbsp; descriptor: <b>{descriptor}</b>"
            f"<br><span style='color:#8ab;'>"
            f"Asset v{asset_version:03d}"
            f" &nbsp;·&nbsp; Flipbook v{flipbook_version:03d}"
            f" &nbsp;·&nbsp; Render v{render_version:03d}"
            f"</span>"
        )

        self._tabs.addTab(_AssetTab(ctx, asset_version), "Asset")
        self._tabs.addTab(_FlipbookTab(ctx, flipbook_version), "Flipbook")
        self._tabs.addTab(_RenderTab(ctx, render_version), "Render")
        self._tabs.addTab(_GlbTab(ctx), "3D Asset (GLB)")

    def _fatal_ctx(self, msg: str):
        self.setWindowTitle("FX Publisher — Context Error")
        self._ctx_banner.setText(
            f"<span style='color:#f88;'><b>Context Error</b></span><br>"
            + msg.replace("\n", "<br>")
        )
        self._ctx_banner.setStyleSheet(
            "background: #3a1a1a; color: #f88; padding: 8px; border-radius: 4px;"
        )
        for label in ("Asset", "Flipbook", "Render", "3D Asset (GLB)"):
            tab = QWidget()
            msg = "Cannot load publisher — fix context error above." if label == "Asset" else ""
            QVBoxLayout(tab).addWidget(QLabel(msg))
            self._tabs.addTab(tab, label)

        for i in range(self._tabs.count()):
            self._tabs.setTabEnabled(i, False)


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

    win = PublisherWindow(parent=parent)
    win.setAttribute(Qt.WA_DeleteOnClose)
    win.show()
    _instance = win
