"""
Unified Pipeline Asset Browser — PySide6 UI for browsing published assets.
Backed by AssetDatabase (SQLite cache over JSON metadata files).
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

try:
    from PySide6.QtCore import (
        Qt, Signal, QRunnable, QObject, QThreadPool, QTimer, QSize,
        QRect, QPoint,
    )
    from PySide6.QtGui import QPixmap, QColor, QFont, QFontMetrics, QDesktopServices
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QDialog, QFrame, QLabel,
        QPushButton, QComboBox, QLineEdit, QListWidget, QListWidgetItem,
        QCheckBox, QSlider, QSplitter, QScrollArea, QToolBar, QStatusBar,
        QFormLayout, QHBoxLayout, QVBoxLayout, QLayout, QLayoutItem,
        QSizePolicy, QTabWidget, QTableWidget, QTableWidgetItem,
        QHeaderView, QProgressDialog, QAbstractItemView, QSpacerItem,
        QDockWidget, QTextEdit,
    )
    from PySide6.QtCore import QUrl
except ImportError:
    raise ImportError("PySide6 is required for the Asset Browser.")

try:
    from pipeline.database import AssetDatabase, DEFAULT_DB
    from pipeline.entities import load_projects
except ImportError:
    from pipeline import AssetDatabase, DEFAULT_DB, load_projects  # type: ignore

logger = logging.getLogger("asset_browser")

CARD_W_DEFAULT = 200
CARD_W_MIN = 140
CARD_W_MAX = 320

TYPE_COLORS = {
    "cache": "#4ae2a0",
    "flipbook": "#e2c24a",
    "render": "#4a90e2",
    "usd": "#a04ae2",
    "hip": "#e2a04a",
}

_STYLESHEET = """
QMainWindow, QDialog {
    background: #111214;
    color: #d0d4de;
}
QWidget {
    color: #d0d4de;
    font-size: 12px;
}
QFrame {
    background: #1a1c20;
}
QSplitter::handle {
    background: #2e3138;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}
QComboBox {
    background: #1a1c20;
    border: 1px solid #2e3138;
    border-radius: 3px;
    padding: 3px 8px;
    min-height: 22px;
}
QComboBox::drop-down {
    border: none;
    width: 18px;
}
QComboBox QAbstractItemView {
    background: #1a1c20;
    border: 1px solid #2e3138;
    selection-background-color: #2e3138;
}
QLineEdit {
    background: #1a1c20;
    border: 1px solid #2e3138;
    border-radius: 3px;
    padding: 3px 8px;
    min-height: 22px;
}
QLineEdit:focus {
    border-color: #4a90e2;
}
QListWidget {
    background: #1a1c20;
    border: 1px solid #2e3138;
    border-radius: 3px;
}
QListWidget::item {
    padding: 3px 6px;
}
QListWidget::item:selected {
    background: #2e3138;
}
QListWidget::item:hover {
    background: #22252c;
}
QPushButton {
    background: #22252c;
    border: 1px solid #2e3138;
    border-radius: 3px;
    padding: 3px 10px;
    min-height: 22px;
}
QPushButton:hover {
    background: #2e3138;
    border-color: #3e4148;
}
QPushButton:pressed {
    background: #1a1c20;
}
QScrollBar:vertical {
    background: #111214;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #2e3138;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #111214;
    height: 8px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #2e3138;
    border-radius: 4px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QTableWidget {
    background: #1a1c20;
    border: 1px solid #2e3138;
    gridline-color: #2e3138;
    alternate-background-color: #16181c;
}
QTableWidget::item {
    padding: 4px 6px;
}
QTableWidget::item:selected {
    background: #2e3138;
}
QHeaderView::section {
    background: #111214;
    border: none;
    border-bottom: 1px solid #2e3138;
    border-right: 1px solid #2e3138;
    padding: 4px 6px;
    color: #8890a0;
}
QTabWidget::pane {
    border: 1px solid #2e3138;
    background: #1a1c20;
}
QTabBar::tab {
    background: #111214;
    border: 1px solid #2e3138;
    border-bottom: none;
    padding: 4px 12px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #1a1c20;
    color: #d0d4de;
}
QTabBar::tab:hover {
    background: #1a1c20;
}
QToolBar {
    background: #151719;
    border: none;
    spacing: 4px;
    padding: 4px;
}
QStatusBar {
    background: #151719;
    color: #6870808;
}
QDockWidget {
    background: #111214;
    color: #d0d4de;
}
QDockWidget::title {
    background: #151719;
    padding: 4px 8px;
    border-bottom: 1px solid #2e3138;
}
QScrollArea {
    background: #111214;
    border: none;
}
QLabel {
    background: transparent;
}
"""


# ---------------------------------------------------------------------------
# Flow Layout
# ---------------------------------------------------------------------------

class _FlowLayout(QLayout):
    def __init__(self, parent=None, h_spacing=8, v_spacing=8):
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem):
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), dry_run=True)

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._do_layout(rect, dry_run=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            if item.widget() and not item.widget().isVisible():
                continue
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, dry_run: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective.x()
        y = effective.y()
        row_height = 0

        for item in self._items:
            widget = item.widget()
            if widget and not widget.isVisible():
                continue
            item_size = item.sizeHint()
            next_x = x + item_size.width()
            if next_x > effective.right() and row_height > 0:
                x = effective.x()
                y += row_height + self._v_spacing
                next_x = x + item_size.width()
                row_height = 0
            if not dry_run:
                item.setGeometry(QRect(QPoint(x, y), item_size))
            x = next_x + self._h_spacing
            row_height = max(row_height, item_size.height())

        return y + row_height - rect.y() + margins.bottom()


# ---------------------------------------------------------------------------
# Thumbnail loading
# ---------------------------------------------------------------------------

class _ThumbSignals(QObject):
    loaded = Signal(str, QPixmap)


class _ThumbWorker(QRunnable):
    def __init__(self, uuid: str, path: str, signals: _ThumbSignals):
        super().__init__()
        self._uuid = uuid
        self._path = path
        self._signals = signals
        self.setAutoDelete(True)

    def run(self):
        try:
            pixmap = QPixmap(self._path)
            if not pixmap.isNull():
                self._signals.loaded.emit(self._uuid, pixmap)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Asset Card
# ---------------------------------------------------------------------------

class AssetCard(QFrame):
    selected = Signal(dict)
    action = Signal(str, dict)

    def __init__(self, record: dict, card_w: int = CARD_W_DEFAULT, parent=None):
        super().__init__(parent)
        self._record = record
        self._selected = False
        self._card_w = card_w
        self._build_ui()
        self.set_card_width(card_w)

    def _build_ui(self):
        self.setObjectName("AssetCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QFrame#AssetCard { background: #1a1c20; border: 1px solid #2e3138; border-radius: 4px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        r = self._record
        pub_type = r.get("publish_type", "")
        thumb_path = r.get("thumbnail", "")

        # Thumbnail area
        self._thumb_label = QLabel()
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_label.setStyleSheet("background: #1e2028; border: none;")

        if not thumb_path:
            color = TYPE_COLORS.get(pub_type, "#555")
            self._thumb_label.setText(pub_type.upper() or "?")
            self._thumb_label.setStyleSheet(
                f"background: #1e2028; color: {color}; border: none; font-size: 11px; font-weight: bold;"
            )

        layout.addWidget(self._thumb_label)

        # Info area
        info = QWidget()
        info.setStyleSheet("background: transparent;")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(6, 5, 6, 5)
        info_layout.setSpacing(1)

        # Row 1: type badge + version + version count
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        badge_color = TYPE_COLORS.get(pub_type, "#666")
        badge = QLabel(pub_type or "—")
        badge.setStyleSheet(
            f"color: {badge_color}; font-size: 9px; font-weight: bold; "
            f"background: transparent; border: none;"
        )
        row1.addWidget(badge)

        version = r.get("version", 1)
        ver_label = QLabel(f"v{version:03d}")
        ver_label.setStyleSheet("color: #8890a0; font-size: 9px; background: transparent; border: none;")
        row1.addWidget(ver_label)

        ver_count = r.get("version_count", 1)
        if ver_count and int(ver_count) > 1:
            vc_label = QLabel(f"· {ver_count}v")
            vc_label.setStyleSheet("color: #556070; font-size: 9px; background: transparent; border: none;")
            row1.addWidget(vc_label)

        row1.addStretch()
        info_layout.addLayout(row1)

        # Row 2: entity name
        entity = r.get("entity", "")
        entity_label = QLabel(entity or "—")
        entity_label.setStyleSheet("font-weight: bold; font-size: 11px; background: transparent; border: none;")
        entity_label.setMaximumWidth(self._card_w - 12)
        info_layout.addWidget(entity_label)
        self._entity_label = entity_label

        # Row 3: task / publish_name
        task = r.get("task", "")
        pub_name = r.get("publish_name", "")
        task_text = f"{task} / {pub_name}" if pub_name and pub_name != task else task
        task_label = QLabel(task_text or "—")
        task_label.setStyleSheet("color: #8890a0; font-size: 10px; background: transparent; border: none;")
        task_label.setMaximumWidth(self._card_w - 12)
        info_layout.addWidget(task_label)
        self._task_label = task_label

        # Row 4: artist + date
        artist = r.get("created_by", "")
        created = r.get("created_at", "")
        date_short = created[:10] if created else ""
        artist_date = " · ".join(x for x in [artist, date_short] if x)
        if artist_date:
            ad_label = QLabel(artist_date)
            ad_label.setStyleSheet("color: #556070; font-size: 9px; background: transparent; border: none;")
            info_layout.addWidget(ad_label)

        # Row 5: frame range + size
        frame_start = r.get("frame_start", 0)
        frame_end = r.get("frame_end", 0)
        disk_mb = r.get("disk_mb", 0.0)
        parts = []
        if frame_end and frame_end != frame_start:
            parts.append(f"{frame_end - frame_start + 1}fr")
        if disk_mb and float(disk_mb) > 0:
            mb = float(disk_mb)
            if mb >= 1024:
                parts.append(f"{mb/1024:.1f} GB")
            else:
                parts.append(f"{mb:.0f} MB")
        if parts:
            size_label = QLabel(" · ".join(parts))
            size_label.setStyleSheet("color: #556070; font-size: 9px; background: transparent; border: none;")
            info_layout.addWidget(size_label)

        layout.addWidget(info)

        # Overlay (absolute positioned, hidden by default)
        self._overlay = QWidget(self)
        self._overlay.setStyleSheet("background: rgba(17,18,20,210); border: none;")
        self._overlay.hide()

        overlay_layout = QHBoxLayout(self._overlay)
        overlay_layout.setContentsMargins(4, 4, 4, 4)
        overlay_layout.setSpacing(3)

        for label, act in [("▶", "play"), ("Hip", "open_hip"), ("Dir", "reveal"), ("Ver", "versions")]:
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                "QPushButton { background: #22252c; border: 1px solid #3e4148; "
                "border-radius: 3px; font-size: 10px; padding: 0 6px; color: #d0d4de; }"
                "QPushButton:hover { background: #2e3138; }"
            )
            btn.clicked.connect(lambda checked, a=act: self.action.emit(a, self._record))
            overlay_layout.addWidget(btn)

        overlay_layout.addStretch()

    def set_card_width(self, w: int):
        self._card_w = w
        thumb_h = int(w * 9 / 16)
        total_h = thumb_h + 92
        self.setFixedSize(w, total_h)
        self._thumb_label.setFixedSize(w, thumb_h)
        self._overlay.setGeometry(0, thumb_h - 30, w, 30)
        if hasattr(self, "_entity_label"):
            self._entity_label.setMaximumWidth(w - 12)
        if hasattr(self, "_task_label"):
            self._task_label.setMaximumWidth(w - 12)

    def set_thumbnail(self, uuid: str, pixmap: QPixmap):
        if uuid == self._record.get("uuid", ""):
            scaled = pixmap.scaled(
                self._thumb_label.width(),
                self._thumb_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._thumb_label.setPixmap(scaled)
            self._thumb_label.setStyleSheet("background: #1e2028; border: none;")

    def set_selected(self, sel: bool):
        self._selected = sel
        if sel:
            self.setStyleSheet(
                "QFrame#AssetCard { background: #1a1c20; border: 1px solid #4a90e2; border-radius: 4px; }"
            )
        else:
            self.setStyleSheet(
                "QFrame#AssetCard { background: #1a1c20; border: 1px solid #2e3138; border-radius: 4px; }"
            )

    def enterEvent(self, event):
        self._overlay.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._overlay.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._record)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Asset Grid
# ---------------------------------------------------------------------------

class AssetGrid(QScrollArea):
    asset_selected = Signal(dict)
    action = Signal(str, dict)
    versions_requested = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container.setStyleSheet("background: #111214;")
        self._flow = _FlowLayout(self._container, h_spacing=8, v_spacing=8)
        self._flow.setContentsMargins(8, 8, 8, 8)
        self._container.setLayout(self._flow)
        self.setWidget(self._container)

        self._cards: dict[str, AssetCard] = {}
        self._selected_uuid: str | None = None
        self._thumb_signals = _ThumbSignals()
        self._thumb_signals.loaded.connect(self._on_thumb_loaded)

        self._empty_label: QLabel | None = None
        self._card_w = CARD_W_DEFAULT

    def set_records(self, records: list[dict], card_w: int = CARD_W_DEFAULT):
        self._card_w = card_w
        self.clear()

        if not records:
            self._show_empty()
            return

        for rec in records:
            uid = rec.get("uuid", "") or f"nouid_{id(rec)}"
            card = AssetCard(rec, card_w=card_w)
            card.selected.connect(self._on_card_selected)
            card.action.connect(self._on_card_action)
            self._flow.addWidget(card)
            self._cards[uid] = card

            thumb = rec.get("thumbnail", "")
            if thumb and Path(thumb).exists():
                worker = _ThumbWorker(uid, thumb, self._thumb_signals)
                QThreadPool.globalInstance().start(worker)

        self._container.updateGeometry()

    def _show_empty(self):
        if self._empty_label is None:
            self._empty_label = QLabel(
                "No assets found.\nTry rebuilding the index or changing filters."
            )
            self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._empty_label.setStyleSheet("color: #556070; font-size: 13px; background: transparent;")
        self._flow.addWidget(self._empty_label)
        self._empty_label.show()

    def clear(self):
        while self._flow.count():
            item = self._flow.takeAt(0)
            if item and item.widget():
                w = item.widget()
                if w is self._empty_label:
                    w.hide()
                else:
                    w.deleteLater()
        self._cards.clear()
        self._selected_uuid = None

    def deselect_all(self):
        for card in self._cards.values():
            card.set_selected(False)
        self._selected_uuid = None

    def _on_card_selected(self, record: dict):
        uid = record.get("uuid", "")
        for card_uid, card in self._cards.items():
            card.set_selected(card_uid == uid)
        self._selected_uuid = uid
        self.asset_selected.emit(record)

    def _on_card_action(self, action_name: str, record: dict):
        if action_name == "versions":
            self.versions_requested.emit(record)
        else:
            self.action.emit(action_name, record)

    def _on_thumb_loaded(self, uuid: str, pixmap: QPixmap):
        card = self._cards.get(uuid)
        if card:
            card.set_thumbnail(uuid, pixmap)

    def update_card_width(self, w: int):
        self._card_w = w
        for card in self._cards.values():
            card.set_card_width(w)
        self._container.updateGeometry()


# ---------------------------------------------------------------------------
# Context Bar
# ---------------------------------------------------------------------------

class ContextBar(QWidget):
    context_changed = Signal(dict)

    def __init__(self, db: AssetDatabase, parent=None):
        super().__init__(parent)
        self._db = db
        self._updating = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Project:"))
        self._project_cb = QComboBox()
        self._project_cb.setMinimumWidth(120)
        layout.addWidget(self._project_cb)

        layout.addWidget(QLabel("Seq:"))
        self._seq_cb = QComboBox()
        self._seq_cb.setMinimumWidth(80)
        layout.addWidget(self._seq_cb)

        layout.addWidget(QLabel("Shot:"))
        self._shot_cb = QComboBox()
        self._shot_cb.setMinimumWidth(100)
        layout.addWidget(self._shot_cb)

        self._project_cb.currentIndexChanged.connect(self._on_project_changed)
        self._seq_cb.currentIndexChanged.connect(self._on_seq_changed)
        self._shot_cb.currentIndexChanged.connect(self._on_shot_changed)

        self.populate()

    def populate(self):
        self._updating = True
        self._project_cb.clear()
        self._project_cb.addItem("ALL", "")
        try:
            projects = self._db.get_distinct("project")
            for p in projects:
                self._project_cb.addItem(p, p)
        except Exception:
            pass
        self._updating = False
        self._reload_sequences()

    def _reload_sequences(self):
        self._updating = True
        project = self._project_cb.currentData() or ""
        self._seq_cb.clear()
        self._seq_cb.addItem("ALL", "")
        try:
            seqs = self._db.get_distinct("sequence", project)
            for s in seqs:
                if s:
                    self._seq_cb.addItem(s, s)
        except Exception:
            pass
        self._updating = False
        self._reload_shots()

    def _reload_shots(self):
        self._updating = True
        self._shot_cb.clear()
        self._shot_cb.addItem("ALL", "")
        try:
            project = self._project_cb.currentData() or ""
            seq = self._seq_cb.currentData() or ""
            shots = self._db.get_distinct("shot", project)
            for s in shots:
                if s:
                    self._shot_cb.addItem(s, s)
        except Exception:
            pass
        self._updating = False

    def _on_project_changed(self, index: int):
        if self._updating:
            return
        self._reload_sequences()
        self.context_changed.emit(self.get_context())

    def _on_seq_changed(self, index: int):
        if self._updating:
            return
        self._reload_shots()
        self.context_changed.emit(self.get_context())

    def _on_shot_changed(self, index: int):
        if self._updating:
            return
        self.context_changed.emit(self.get_context())

    def get_context(self) -> dict:
        return {
            "project": self._project_cb.currentData() or "",
            "sequence": self._seq_cb.currentData() or "",
            "shot": self._shot_cb.currentData() or "",
        }

    def set_context(self, context: dict):
        project = context.get("project", "")
        if project:
            idx = self._project_cb.findData(project)
            if idx >= 0:
                self._project_cb.setCurrentIndex(idx)


# ---------------------------------------------------------------------------
# Filter Sidebar
# ---------------------------------------------------------------------------

class FilterSidebar(QWidget):
    filters_changed = Signal(dict)

    def __init__(self, db: AssetDatabase, parent=None):
        super().__init__(parent)
        self._db = db
        self._collapsed = False
        self.setMinimumWidth(160)
        self.setMaximumWidth(260)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Toggle button
        self._toggle_btn = QPushButton("◀ Filters")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(False)
        self._toggle_btn.setStyleSheet(
            "QPushButton { text-align: left; padding: 4px 8px; background: #151719; "
            "border: none; border-bottom: 1px solid #2e3138; font-size: 11px; }"
            "QPushButton:checked { color: #8890a0; }"
        )
        self._toggle_btn.clicked.connect(self._toggle_collapse)
        outer.addWidget(self._toggle_btn)

        # Content widget
        self._content = QWidget()
        self._content.setStyleSheet("background: #1a1c20;")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        # Publish Type
        type_lbl = QLabel("Publish Type")
        type_lbl.setStyleSheet("color: #8890a0; font-size: 10px; background: transparent;")
        content_layout.addWidget(type_lbl)

        self._type_list = QListWidget()
        self._type_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._type_list.setMaximumHeight(100)
        for t in ["cache", "flipbook", "render", "usd", "hip"]:
            item = QListWidgetItem(t)
            self._type_list.addItem(item)
        self._type_list.itemSelectionChanged.connect(self._emit)
        content_layout.addWidget(self._type_list)

        # Artist
        artist_lbl = QLabel("Artist")
        artist_lbl.setStyleSheet("color: #8890a0; font-size: 10px; background: transparent;")
        content_layout.addWidget(artist_lbl)
        self._artist_cb = QComboBox()
        self._artist_cb.addItem("ALL", "")
        self._artist_cb.currentIndexChanged.connect(self._emit)
        content_layout.addWidget(self._artist_cb)

        # Date Range
        date_lbl = QLabel("Date Range")
        date_lbl.setStyleSheet("color: #8890a0; font-size: 10px; background: transparent;")
        content_layout.addWidget(date_lbl)
        self._date_cb = QComboBox()
        self._date_cb.addItems(["All Time", "Today", "This Week", "This Month"])
        self._date_cb.currentIndexChanged.connect(self._emit)
        content_layout.addWidget(self._date_cb)

        # Tags
        tag_lbl = QLabel("Tags")
        tag_lbl.setStyleSheet("color: #8890a0; font-size: 10px; background: transparent;")
        content_layout.addWidget(tag_lbl)
        self._tag_edit = QLineEdit()
        self._tag_edit.setPlaceholderText("Filter by tag…")
        self._tag_edit.textChanged.connect(self._emit)
        content_layout.addWidget(self._tag_edit)

        # Checkboxes
        self._hide_orphaned_cb = QCheckBox("Hide orphaned")
        self._hide_orphaned_cb.setStyleSheet("background: transparent;")
        self._hide_orphaned_cb.stateChanged.connect(self._emit)
        content_layout.addWidget(self._hide_orphaned_cb)

        content_layout.addStretch()
        outer.addWidget(self._content)

    def _toggle_collapse(self):
        self._collapsed = self._toggle_btn.isChecked()
        self._content.setVisible(not self._collapsed)
        self._toggle_btn.setText("▶ Filters" if self._collapsed else "◀ Filters")

    def _emit(self):
        self.filters_changed.emit(self.get_filters())

    def get_filters(self) -> dict:
        selected_types = [
            self._type_list.item(i).text()
            for i in range(self._type_list.count())
            if self._type_list.item(i).isSelected()
        ]
        return {
            "publish_type": selected_types[0] if len(selected_types) == 1 else "",
            "publish_types": selected_types,
            "created_by": self._artist_cb.currentData() or "",
            "date_range": self._date_cb.currentText(),
            "tag": self._tag_edit.text().strip(),
            "hide_orphaned": self._hide_orphaned_cb.isChecked(),
        }

    def update_for_context(self, db: AssetDatabase, context: dict):
        project = context.get("project", "")
        current_artist = self._artist_cb.currentData() or ""
        self._artist_cb.blockSignals(True)
        self._artist_cb.clear()
        self._artist_cb.addItem("ALL", "")
        try:
            artists = db.get_distinct("created_by", project)
            for a in artists:
                self._artist_cb.addItem(a, a)
        except Exception:
            pass
        idx = self._artist_cb.findData(current_artist)
        if idx >= 0:
            self._artist_cb.setCurrentIndex(idx)
        self._artist_cb.blockSignals(False)


# ---------------------------------------------------------------------------
# Metadata Panel
# ---------------------------------------------------------------------------

class MetadataPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self._header = QWidget()
        self._header.setStyleSheet("background: #151719; border-bottom: 1px solid #2e3138;")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(8, 4, 8, 4)

        self._header_entity = QLabel("—")
        self._header_entity.setStyleSheet("font-weight: bold; font-size: 13px;")
        header_layout.addWidget(self._header_entity)

        self._header_badge = QLabel("")
        self._header_badge.setStyleSheet("font-size: 10px; font-weight: bold;")
        header_layout.addWidget(self._header_badge)

        self._header_ver = QLabel("")
        self._header_ver.setStyleSheet("color: #8890a0; font-size: 11px;")
        header_layout.addWidget(self._header_ver)
        header_layout.addStretch()

        layout.addWidget(self._header)

        # Tabs
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Info tab
        info_widget = QWidget()
        info_widget.setStyleSheet("background: #1a1c20;")
        self._info_form = QFormLayout(info_widget)
        self._info_form.setContentsMargins(10, 8, 10, 8)
        self._info_form.setSpacing(5)
        self._tabs.addTab(info_widget, "Info")

        # Outputs tab
        self._outputs_text = QTextEdit()
        self._outputs_text.setReadOnly(True)
        self._outputs_text.setStyleSheet("background: #1a1c20; border: none;")
        self._tabs.addTab(self._outputs_text, "Outputs")

        # Notes tab
        self._notes_text = QTextEdit()
        self._notes_text.setReadOnly(True)
        self._notes_text.setStyleSheet("background: #1a1c20; border: none;")
        self._tabs.addTab(self._notes_text, "Notes")

        # Wedge tab (hidden by default)
        self._wedge_text = QTextEdit()
        self._wedge_text.setReadOnly(True)
        self._wedge_text.setStyleSheet("background: #1a1c20; border: none;")
        self._wedge_tab_index = self._tabs.addTab(self._wedge_text, "Wedge")
        self._tabs.setTabVisible(self._wedge_tab_index, False)

        self.clear()

    def _add_field(self, label: str, value: str):
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #8890a0; font-size: 10px;")
        val = QLabel(str(value) if value else "—")
        val.setStyleSheet("font-size: 11px;")
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        val.setWordWrap(True)
        self._info_form.addRow(lbl, val)

    def show_asset(self, record: dict):
        pub_type = record.get("publish_type", "")
        entity = record.get("entity", "—")
        version = record.get("version", 1)

        self._header_entity.setText(entity)
        color = TYPE_COLORS.get(pub_type, "#666")
        self._header_badge.setText(pub_type)
        self._header_badge.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")
        self._header_ver.setText(f"v{version:03d}")

        # Clear info form
        while self._info_form.rowCount():
            self._info_form.removeRow(0)

        self._add_field("Task", record.get("task", ""))
        self._add_field("Publish Name", record.get("publish_name", ""))
        self._add_field("Artist", record.get("created_by", ""))
        self._add_field("Date", record.get("created_at", "")[:19].replace("T", " "))
        self._add_field("Houdini", record.get("houdini_ver", ""))
        self._add_field("Git Commit", record.get("git_commit", ""))
        self._add_field("Hip File", record.get("hip_path", ""))

        fs = record.get("frame_start", 0)
        fe = record.get("frame_end", 0)
        if fs or fe:
            self._add_field("Frames", f"{fs} – {fe}")

        disk = record.get("disk_mb", 0.0)
        if disk:
            mb = float(disk)
            if mb >= 1024:
                self._add_field("Size", f"{mb/1024:.2f} GB")
            else:
                self._add_field("Size", f"{mb:.1f} MB")

        self._add_field("Publish Dir", record.get("publish_dir", ""))

        # Outputs tab
        outputs_lines = []
        for k in ["thumbnail", "mp4", "frames", "usd", "cache"]:
            val = record.get(k, "")
            if val:
                outputs_lines.append(f"{k}: {val}")
        pub_dir = record.get("publish_dir", "")
        if pub_dir:
            outputs_lines.append(f"publish_dir: {pub_dir}")
        self._outputs_text.setPlainText("\n".join(outputs_lines) if outputs_lines else "No outputs recorded.")

        # Notes tab
        try:
            notes = json.loads(record.get("notes_json", "[]")) or []
            tags = json.loads(record.get("tags_json", "[]")) or []
        except Exception:
            notes, tags = [], []
        notes_lines = []
        if tags:
            notes_lines.append("Tags: " + ", ".join(str(t) for t in tags))
        if notes:
            notes_lines.extend(str(n) for n in notes)
        self._notes_text.setPlainText("\n".join(notes_lines) if notes_lines else "No notes.")

        # Wedge tab
        try:
            wedge = json.loads(record.get("wedge_json", "null"))
        except Exception:
            wedge = None
        if wedge:
            self._wedge_text.setPlainText(json.dumps(wedge, indent=2))
            self._tabs.setTabVisible(self._wedge_tab_index, True)
        else:
            self._tabs.setTabVisible(self._wedge_tab_index, False)

    def clear(self):
        while self._info_form.rowCount():
            self._info_form.removeRow(0)
        lbl = QLabel("Select an asset to view metadata.")
        lbl.setStyleSheet("color: #556070; font-size: 12px;")
        self._info_form.addRow(lbl)
        self._header_entity.setText("—")
        self._header_badge.setText("")
        self._header_ver.setText("")
        self._outputs_text.clear()
        self._notes_text.clear()
        self._wedge_text.clear()
        self._tabs.setTabVisible(self._wedge_tab_index, False)


# ---------------------------------------------------------------------------
# Version History Dialog
# ---------------------------------------------------------------------------

class VersionHistoryDialog(QDialog):
    def __init__(self, records: list[dict], parent=None):
        super().__init__(parent)
        self._records = records
        entity = records[0].get("entity", "") if records else ""
        task = records[0].get("task", "") if records else ""
        self.setWindowTitle(f"Versions — {entity} / {task}")
        self.resize(700, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["Version", "Date", "Artist", "Size", "Status", "Actions"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_double_click)

        self._populate()
        layout.addWidget(self._table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _populate(self):
        self._table.setRowCount(len(self._records))
        for row, rec in enumerate(self._records):
            ver = rec.get("version", 0)
            date = rec.get("created_at", "")[:19].replace("T", " ")
            artist = rec.get("created_by", "")
            disk = rec.get("disk_mb", 0.0)
            if disk:
                mb = float(disk)
                size_str = f"{mb/1024:.2f} GB" if mb >= 1024 else f"{mb:.1f} MB"
            else:
                size_str = "—"

            try:
                warnings = json.loads(rec.get("warnings_json", "[]")) or []
            except Exception:
                warnings = []
            status = "⚠ " + ", ".join(warnings) if warnings else "✓"

            self._table.setItem(row, 0, QTableWidgetItem(f"v{ver:03d}"))
            self._table.setItem(row, 1, QTableWidgetItem(date))
            self._table.setItem(row, 2, QTableWidgetItem(artist))
            self._table.setItem(row, 3, QTableWidgetItem(size_str))
            self._table.setItem(row, 4, QTableWidgetItem(status))

            pub_dir = rec.get("publish_dir", "")
            btn = QPushButton("Open Dir")
            btn.setFixedHeight(22)
            btn.setStyleSheet("font-size: 10px;")
            btn.clicked.connect(lambda checked, d=pub_dir: self._open_dir(d))
            self._table.setCellWidget(row, 5, btn)

    def _open_dir(self, pub_dir: str):
        if pub_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(pub_dir))

    def _on_double_click(self, index):
        row = index.row()
        if 0 <= row < len(self._records):
            pub_dir = self._records[row].get("publish_dir", "")
            self._open_dir(pub_dir)


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class AssetBrowserWindow(QMainWindow):
    def __init__(self, db: AssetDatabase, parent=None):
        super().__init__(parent)
        self._db = db
        self._card_w = CARD_W_DEFAULT
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._refresh)

        self.setWindowTitle("Pipeline Asset Browser")
        self.resize(1280, 800)
        self.setStyleSheet(_STYLESHEET)

        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()

        self._context_bar.populate()
        self._sidebar.update_for_context(self._db, {})
        self._refresh()

    def _build_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("QMenuBar { background: #151719; } QMenu { background: #1a1c20; }")

        file_menu = menubar.addMenu("File")
        rebuild_action = file_menu.addAction("Rebuild Index")
        rebuild_action.triggered.connect(self._rebuild_index)
        file_menu.addSeparator()
        close_action = file_menu.addAction("Close")
        close_action.triggered.connect(self.close)

        view_menu = menubar.addMenu("View")
        sidebar_action = view_menu.addAction("Toggle Sidebar")
        sidebar_action.triggered.connect(self._toggle_sidebar)
        meta_action = view_menu.addAction("Toggle Metadata")
        meta_action.triggered.connect(self._toggle_metadata)

    def _build_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)

        self._context_bar = ContextBar(self._db)
        self._context_bar.context_changed.connect(self._on_context_changed)
        toolbar.addWidget(self._context_bar)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search assets…")
        self._search_edit.setFixedWidth(200)
        self._search_edit.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self._search_edit)

        toolbar.addSeparator()

        grid_btn = QPushButton("⊞")
        grid_btn.setFixedWidth(30)
        grid_btn.setToolTip("Grid view")
        grid_btn.clicked.connect(lambda: self._on_view_mode("grid"))
        toolbar.addWidget(grid_btn)

        list_btn = QPushButton("☰")
        list_btn.setFixedWidth(30)
        list_btn.setToolTip("List view (smaller cards)")
        list_btn.clicked.connect(lambda: self._on_view_mode("list"))
        toolbar.addWidget(list_btn)

        toolbar.addSeparator()

        size_lbl = QLabel("Size:")
        toolbar.addWidget(size_lbl)

        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(CARD_W_MIN, CARD_W_MAX)
        self._size_slider.setValue(CARD_W_DEFAULT)
        self._size_slider.setFixedWidth(100)
        self._size_slider.valueChanged.connect(self._on_size_changed)
        toolbar.addWidget(self._size_slider)

        toolbar.addSeparator()

        rebuild_btn = QPushButton("↺ Rebuild")
        rebuild_btn.setToolTip("Rebuild index from disk")
        rebuild_btn.clicked.connect(self._rebuild_index)
        toolbar.addWidget(rebuild_btn)

    def _build_body(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._body_splitter = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(self._body_splitter)

        # Top: sidebar + grid
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._body_splitter.addWidget(self._main_splitter)

        self._sidebar = FilterSidebar(self._db)
        self._sidebar.filters_changed.connect(self._on_filters_changed)
        self._main_splitter.addWidget(self._sidebar)

        self._grid = AssetGrid()
        self._grid.asset_selected.connect(self._on_asset_selected)
        self._grid.action.connect(self._on_action)
        self._grid.versions_requested.connect(self._on_versions_requested)
        self._main_splitter.addWidget(self._grid)

        self._main_splitter.setStretchFactor(0, 0)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setSizes([200, 1000])

        # Bottom: metadata panel
        self._metadata_panel = MetadataPanel()
        self._body_splitter.addWidget(self._metadata_panel)
        self._metadata_panel.hide()

        self._body_splitter.setStretchFactor(0, 1)
        self._body_splitter.setStretchFactor(1, 0)
        self._body_splitter.setSizes([600, 200])

    def _build_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready")

    def _toggle_sidebar(self):
        self._sidebar.setVisible(not self._sidebar.isVisible())

    def _toggle_metadata(self):
        self._metadata_panel.setVisible(not self._metadata_panel.isVisible())

    def _on_context_changed(self, context: dict):
        self._sidebar.update_for_context(self._db, context)
        self._refresh()

    def _on_search_changed(self, text: str):
        self._search_timer.start(300)

    def _on_filters_changed(self, filters: dict):
        self._refresh()

    def _on_asset_selected(self, record: dict):
        self._metadata_panel.show_asset(record)
        if not self._metadata_panel.isVisible():
            self._metadata_panel.show()

    def _on_action(self, action_name: str, record: dict):
        if action_name == "play":
            mp4 = record.get("mp4", "")
            if mp4 and Path(mp4).exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(mp4))
            else:
                self._statusbar.showMessage("No MP4 preview available.", 3000)

        elif action_name == "open_hip":
            hip = record.get("hip_path", "")
            if hip and Path(hip).exists():
                try:
                    import hou
                    hou.hipFile.load(hip)
                    self._statusbar.showMessage(f"Loaded: {hip}", 3000)
                except ImportError:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(hip))
            else:
                self._statusbar.showMessage("Hip file not available.", 3000)

        elif action_name == "reveal":
            pub_dir = record.get("publish_dir", "")
            if pub_dir:
                target = str(Path(pub_dir).parent)
                QDesktopServices.openUrl(QUrl.fromLocalFile(target))
            else:
                self._statusbar.showMessage("No publish directory available.", 3000)

    def _on_versions_requested(self, record: dict):
        try:
            versions = self._db.get_all_versions(
                record.get("project", ""),
                record.get("entity", ""),
                record.get("task", ""),
                record.get("publish_type", ""),
                record.get("publish_name", ""),
            )
        except Exception as e:
            versions = [record]

        dlg = VersionHistoryDialog(versions, parent=self)
        dlg.exec()

    def _on_view_mode(self, mode: str):
        if mode == "list":
            self._card_w = 160
        else:
            self._card_w = self._size_slider.value()
        self._size_slider.setValue(self._card_w)
        self._grid.update_card_width(self._card_w)

    def _on_size_changed(self, value: int):
        self._card_w = value
        self._grid.update_card_width(value)

    def _rebuild_index(self):
        progress = QProgressDialog("Rebuilding index…", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        QApplication.processEvents()

        try:
            self._db.rebuild_all()
            self._context_bar.populate()
            self._refresh()
            self._statusbar.showMessage("Index rebuilt successfully.", 5000)
        except Exception as e:
            logger.error("Rebuild failed: %s", e)
            self._statusbar.showMessage(f"Rebuild failed: {e}", 5000)
        finally:
            progress.close()

    def _refresh(self):
        context = self._context_bar.get_context()
        filters = self._sidebar.get_filters()
        search = self._search_edit.text().strip()

        merged_filters = {**context, **filters}
        # Remove keys not supported by query_asset_groups
        merged_filters.pop("publish_types", None)
        merged_filters.pop("date_range", None)
        merged_filters.pop("tag", None)

        # If multiple types selected, ignore type filter (show all)
        pub_types = filters.get("publish_types", [])
        if len(pub_types) == 1:
            merged_filters["publish_type"] = pub_types[0]
        else:
            merged_filters.pop("publish_type", None)

        try:
            records = self._db.query_asset_groups(merged_filters, search)
        except Exception as e:
            logger.error("Query failed: %s", e)
            records = []

        self._grid.set_records(records, self._card_w)
        self._metadata_panel.clear()

        try:
            stats = self._db.get_stats()
            last = stats.get("last_indexed", "")[:19].replace("T", " ") if stats.get("last_indexed") else "never"
            self._statusbar.showMessage(
                f"{len(records)} assets shown  ·  {stats['total']} total  ·  last indexed: {last}"
            )
        except Exception:
            self._statusbar.showMessage(f"{len(records)} assets shown")

    def set_houdini_context(self, context: dict):
        if context.get("project"):
            self._context_bar.set_context(context)
            self._refresh()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_instance = None


def show(houdini_context: dict = None):
    global _instance

    if _instance is not None:
        try:
            _instance.close()
        except Exception:
            pass
        _instance = None

    parent = None
    try:
        import hou
        parent = hou.qt.mainWindow()
    except ImportError:
        pass

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    try:
        db = AssetDatabase(DEFAULT_DB)
    except Exception as e:
        logger.error("Could not open AssetDatabase: %s", e)
        db = AssetDatabase()

    win = AssetBrowserWindow(db, parent=parent)

    if houdini_context:
        win.set_houdini_context(houdini_context)

    win.show()
    _instance = win
    return win
