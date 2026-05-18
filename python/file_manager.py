"""
Houdini FX Pipeline — File Manager dialog (PySide6).
Card Grid layout.
"""

import logging
import re
import sys
from datetime import datetime, date
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QComboBox, QPushButton, QDialog,
        QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox,
        QScrollArea, QFrame, QSizePolicy, QGridLayout,
    )
    from PySide6.QtCore import Qt, QUrl, QRect, QEvent, Signal
    from PySide6.QtGui import (
        QFont, QFontDatabase, QKeySequence, QDesktopServices, QShortcut,
        QPainter, QPainterPath, QColor, QLinearGradient, QRadialGradient,
        QPen, QBrush,
    )
except ImportError:
    raise RuntimeError("PySide6 is required. Install it or run from inside Houdini.")

import pipeline
import naming_conventions

logger = logging.getLogger("pipeline")

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

C_BG      = "#1a1c1f"
C_BG2     = "#232629"
C_BG3     = "#2c3034"
C_BG4     = "#383d42"
C_LINE    = "#3a3f44"
C_LINE2   = "#4a5057"
C_TEXT    = "#e8e8e6"
C_TEXT2   = "#b3b6b8"
C_TEXT3   = "#7e8389"
C_TEXT4   = "#5a5f64"
C_ACCENT  = "#ff7a1a"
C_ACCENT2 = "#ffae6e"
C_OK      = "#6dd58c"

DENSITY_MIN_W = {"comfy": 240, "regular": 200, "compact": 168}
DENSITY_THUMB_H = {"comfy": 135, "regular": 113, "compact": 95}

_QSS = f"""
QWidget {{ background: {C_BG}; color: {C_TEXT};
           font-family: "Inter Tight", "Segoe UI", Arial, sans-serif; font-size: 13px; }}
QMainWindow {{ background: {C_BG}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: {C_BG}; border: none; }}
QScrollBar:vertical {{ background: {C_BG}; width: 10px; border: none; }}
QScrollBar::handle:vertical {{ background: {C_BG4}; border-radius: 5px;
    min-height: 20px; margin: 2px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QPushButton {{ background: {C_BG3}; color: {C_TEXT}; border: 1px solid {C_LINE};
               border-radius: 5px; padding: 5px 10px; font-size: 12px; font-weight: 500; }}
QPushButton:hover {{ background: {C_BG4}; }}
QPushButton#primary {{ background: {C_ACCENT}; color: #fff; border-color: {C_ACCENT}; }}
QPushButton#primary:hover {{ background: {C_ACCENT2}; border-color: {C_ACCENT2}; }}
QPushButton#icon-btn {{ background: transparent; border: 1px solid transparent;
                         color: {C_TEXT2}; border-radius: 5px; padding: 0; }}
QPushButton#icon-btn:hover {{ background: {C_BG3}; color: {C_TEXT}; }}
QPushButton#seg-btn {{ background: transparent; border: none; color: {C_TEXT2};
                        border-radius: 4px; padding: 4px 10px; font-size: 12px; }}
QPushButton#seg-btn:hover {{ color: {C_TEXT}; }}
QPushButton#seg-btn[active="true"] {{ background: {C_BG3}; color: {C_TEXT}; }}
QPushButton#chip-btn {{ background: {C_BG}; border: 1px solid {C_LINE};
                         border-radius: 999px; color: {C_TEXT2};
                         padding: 4px 10px; font-size: 12px; }}
QPushButton#chip-btn:hover {{ border-color: {C_LINE2}; color: {C_TEXT}; }}
QPushButton#chip-btn[active="true"] {{ background: rgba(255,122,26,0.14);
                                        border-color: {C_ACCENT}; color: {C_ACCENT2}; }}
QPushButton#qbtn {{ background: rgba(0,0,0,160); border: 1px solid rgba(255,255,255,25);
                     border-radius: 4px; color: white; padding: 0; }}
QPushButton#qbtn:hover {{ background: rgba(0,0,0,220); }}
QLineEdit {{ background: {C_BG}; border: 1px solid {C_LINE}; border-radius: 5px;
             color: {C_TEXT}; padding: 5px 8px; font-size: 12px; }}
QLineEdit:focus {{ border-color: {C_LINE2}; }}
QComboBox {{ background: {C_BG3}; border: 1px solid {C_LINE}; border-radius: 4px;
             color: {C_TEXT}; padding: 4px 8px; font-size: 12px; min-width: 80px; }}
QComboBox:hover {{ border-color: {C_LINE2}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {C_BG3}; border: 1px solid {C_LINE};
                                selection-background-color: {C_BG4}; color: {C_TEXT}; }}
QDialog {{ background: {C_BG2}; }}
QLabel {{ background: transparent; }}
QGroupBox {{ border: 1px solid {C_LINE}; border-radius: 5px; margin-top: 8px; padding: 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; color: {C_TEXT3}; font-size: 11px; }}
QMessageBox {{ background: {C_BG2}; }}
QFrame#titlebar, QFrame#toolbar, QFrame#statusbar {{ background: {C_BG2};
    border: none; }}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _format_date(mtime: float) -> str:
    dt = datetime.fromtimestamp(mtime)
    today = date.today()
    if dt.date() == today:
        return f"today, {dt.strftime('%H:%M')}"
    if dt.date() == date.fromordinal(today.toordinal() - 1):
        return "yesterday"
    return dt.strftime("%b %d")


def _format_date_full(mtime: float) -> str:
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")


_PH_KEYWORDS = {
    1: ["smoke", "steam", "mist", "fog", "vapor", "vapour"],
    2: ["dust", "sand", "grain", "powder"],
    3: ["ice", "snow", "crystal", "freeze", "frost", "hail"],
    4: ["fire", "flame", "burn", "ember", "spark", "pyro", "explosion", "blast"],
    5: ["debris", "rock", "stone", "shatter", "break", "fracture", "gravel"],
    6: ["water", "splash", "flip", "ocean", "wave", "liquid", "fluid", "rain"],
}


def _ph_type(task: str) -> int:
    t = task.lower()
    for ph, kws in _PH_KEYWORDS.items():
        if any(k in t for k in kws):
            return ph
    return 7


def _mono_font() -> QFont:
    f = QFont("JetBrains Mono" if QFontDatabase.hasFamily("JetBrains Mono") else "Courier New")
    f.setPixelSize(11)
    return f


# ---------------------------------------------------------------------------
# Procedural thumbnail painter
# ---------------------------------------------------------------------------

def _draw_thumbnail(painter: QPainter, w: int, h: int, ph: int, dim: float = 1.0):
    r = QRect(0, 0, w, h)
    base = QLinearGradient(0, 0, w, h)
    base.setColorAt(0, QColor("#1f2226"))
    base.setColorAt(1, QColor("#2a2e33"))
    painter.fillRect(r, QBrush(base))

    grid_pen = QPen(QColor(255, 255, 255, 6))
    grid_pen.setWidth(1)
    painter.setPen(grid_pen)
    for y in range(0, h + 32, 32):
        painter.drawLine(0, y, w, y)
    for x in range(0, w + 32, 32):
        painter.drawLine(x, 0, x, h)
    painter.setPen(Qt.NoPen)

    if ph == 1:
        for cx, cy, rw, a in [(0.35, 0.60, 0.60, 115), (0.70, 0.45, 0.50, 90), (0.50, 0.75, 0.40, 65)]:
            g = QRadialGradient(cx * w, cy * h, rw * w * 0.5)
            g.setColorAt(0, QColor(255, 255, 255, a))
            g.setColorAt(1, QColor(255, 255, 255, 0))
            painter.fillRect(r, QBrush(g))
    elif ph == 2:
        g = QRadialGradient(0.50 * w, 0.70 * h, 0.70 * w * 0.5)
        g.setColorAt(0, QColor(255, 150, 80, 115))
        g.setColorAt(1, QColor(255, 150, 80, 0))
        painter.fillRect(r, QBrush(g))
        g2 = QRadialGradient(0.30 * w, 0.50 * h, 0.40 * w * 0.5)
        g2.setColorAt(0, QColor(255, 200, 120, 90))
        g2.setColorAt(1, QColor(255, 200, 120, 0))
        painter.fillRect(r, QBrush(g2))
    elif ph == 3:
        lg = QLinearGradient(0, h * 0.3, 0, h)
        lg.setColorAt(0, QColor(120, 180, 255, 0))
        lg.setColorAt(0.6, QColor(120, 180, 255, 64))
        lg.setColorAt(1.0, QColor(180, 220, 255, 115))
        painter.fillRect(r, QBrush(lg))
        g2 = QRadialGradient(0.60 * w, 0.80 * h, 0.40 * w * 0.5)
        g2.setColorAt(0, QColor(200, 230, 255, 128))
        g2.setColorAt(1, QColor(200, 230, 255, 0))
        painter.fillRect(r, QBrush(g2))
    elif ph == 4:
        g = QRadialGradient(0.50 * w, 0.95 * h, 0.50 * w)
        g.setColorAt(0, QColor(255, 90, 30, 140))
        g.setColorAt(1, QColor(255, 90, 30, 0))
        painter.fillRect(r, QBrush(g))
        g2 = QRadialGradient(0.50 * w, 0.85 * h, 0.30 * w)
        g2.setColorAt(0, QColor(255, 200, 80, 140))
        g2.setColorAt(1, QColor(255, 200, 80, 0))
        painter.fillRect(r, QBrush(g2))
    elif ph == 5:
        for cx, cy, sz, a in [(0.20, 0.30, 2, 220), (0.60, 0.20, 1.5, 180),
                               (0.75, 0.60, 2.5, 220), (0.40, 0.70, 2, 200),
                               (0.85, 0.40, 1.5, 220), (0.30, 0.50, 1.5, 150),
                               (0.50, 0.35, 2, 220)]:
            painter.setBrush(QColor(255, 255, 255, int(a)))
            painter.drawEllipse(int(cx * w - sz), int(cy * h - sz), int(sz * 2), int(sz * 2))
    elif ph == 6:
        lg = QLinearGradient(0, 0, 0, h)
        lg.setColorAt(0, QColor(80, 140, 200, 76))
        lg.setColorAt(1, QColor(40, 90, 160, 128))
        painter.fillRect(r, QBrush(lg))
        g2 = QRadialGradient(0.50 * w, 0.70 * h, 0.60 * w * 0.5)
        g2.setColorAt(0, QColor(255, 255, 255, 76))
        g2.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(r, QBrush(g2))
    else:
        g = QRadialGradient(0.50 * w, 0.50 * h, 0.30 * w)
        g.setColorAt(0, QColor(255, 255, 255, 20))
        g.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(r, QBrush(g))

    if dim < 1.0:
        painter.fillRect(r, QColor(0, 0, 0, int((1.0 - dim) * 200)))


# ---------------------------------------------------------------------------
# _ThumbnailWidget
# ---------------------------------------------------------------------------

class _ThumbnailWidget(QWidget):
    open_clicked   = Signal()
    copy_clicked   = Signal()
    reveal_clicked = Signal()
    card_clicked   = Signal()

    def __init__(self, ph: int, ver: str,
                 is_latest: bool = False, dim: float = 1.0,
                 thumb_h: int = 113, parent=None):
        super().__init__(parent)
        self._ph = ph
        self._ver = ver
        self._is_latest = is_latest
        self._dim = dim
        self._hovered = False
        self.setFixedHeight(thumb_h)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_Hover, True)
        self.setMouseTracking(True)

    def _btn_rects(self) -> list:
        margin, bw, gap = 8, 26, 4
        rects = []
        for i in range(3):
            x = self.width() - margin - (i + 1) * bw - i * gap
            rects.append(QRect(x, margin, bw, bw))
        return rects  # [open, copy, reveal]

    def event(self, ev):
        if ev.type() == QEvent.HoverEnter:
            self._hovered = True
            self.update()
        elif ev.type() == QEvent.HoverLeave:
            self._hovered = False
            self.update()
        return super().event(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._hovered:
            rects = self._btn_rects()
            pos = ev.position().toPoint()
            if rects[0].contains(pos):
                self.open_clicked.emit()
                return
            if rects[1].contains(pos):
                self.copy_clicked.emit()
                return
            if rects[2].contains(pos):
                self.reveal_clicked.emit()
                return
        self.card_clicked.emit()
        super().mousePressEvent(ev)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        _draw_thumbnail(p, w, h, self._ph, self._dim)
        self._draw_overlays(p, w, h)
        p.end()

    def _draw_overlays(self, p: QPainter, w: int, h: int):
        margin = 8
        bh = 18

        # Badge font
        bf = QFont("Inter Tight" if QFontDatabase.hasFamily("Inter Tight") else "Arial")
        bf.setPixelSize(10)
        bf.setBold(True)
        p.setFont(bf)
        fm = p.fontMetrics()

        def draw_badge(x, y, text, bg: QColor, fg: QColor):
            tw = fm.horizontalAdvance(text)
            bw_ = tw + 14
            path = QPainterPath()
            path.addRoundedRect(x, y, bw_, bh, 9, 9)
            p.fillPath(path, bg)
            p.setPen(fg)
            p.drawText(x + 7, y + bh - 5, text)
            return bw_

        # Badge top-left — LATEST only (publish status is not tracked for hip files)
        if self._is_latest:
            draw_badge(margin, margin, "LATEST", QColor(C_ACCENT), QColor("white"))

        # Version text bottom-left (mono bold)
        mf = QFont("JetBrains Mono" if QFontDatabase.hasFamily("JetBrains Mono") else "Courier New")
        mf.setPixelSize(13)
        mf.setBold(True)
        p.setFont(mf)
        p.setPen(QColor("white"))
        p.drawText(margin, h - margin - 2, self._ver)

        # Hover: play icon + action buttons
        if self._hovered:
            cx, cy = w // 2, h // 2
            rr = 19
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 115))
            p.drawEllipse(cx - rr, cy - rr, rr * 2, rr * 2)
            play = QPainterPath()
            play.moveTo(cx - 5, cy - 8)
            play.lineTo(cx - 5, cy + 8)
            play.lineTo(cx + 9, cy)
            play.closeSubpath()
            p.fillPath(play, QColor("white"))

            # Action buttons: Open, Copy, Reveal
            symbols = ["▶", "⎘", "⎓"]
            for i, (rect, sym) in enumerate(zip(self._btn_rects(), symbols)):
                p.setBrush(QColor(0, 0, 0, 160))
                p.setPen(QPen(QColor(255, 255, 255, 25)))
                p.drawRoundedRect(rect, 4, 4)
                sf = QFont(mf)
                sf.setPixelSize(11)
                sf.setBold(False)
                p.setFont(sf)
                p.setPen(QColor("white"))
                p.drawText(rect, Qt.AlignCenter, sym)


# ---------------------------------------------------------------------------
# _HipCard
# ---------------------------------------------------------------------------

class _HipCard(QFrame):
    open_requested   = Signal(str)
    copy_requested   = Signal(str)
    reveal_requested = Signal(str)
    selected_changed = Signal(object)

    def __init__(self, hip_path: Path, parsed: dict | None, is_latest: bool,
                 all_versions: list, density: str = "regular", parent=None):
        super().__init__(parent)
        self._hip_path = hip_path
        self._parsed = parsed
        self._is_latest = is_latest
        self._all_versions = all_versions
        self._selected = False
        self.setFrameShape(QFrame.NoFrame)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self._build(density)
        self._set_border(C_LINE)

    def _set_border(self, color: str):
        self.setStyleSheet(f"""
            QFrame {{
                background: {C_BG2};
                border: 1px solid {color};
                border-radius: 6px;
            }}
        """)

    def _build(self, density: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        parsed = self._parsed
        task = (parsed.get("task", "unknown") if parsed else "unknown") or "unknown"
        ver  = (parsed.get("version_str", "v???") if parsed else "v???") or "v???"
        ph   = _ph_type(task)

        n = len(self._all_versions)
        idx = self._all_versions.index(self._hip_path) if self._hip_path in self._all_versions else 0
        dim = 1.0 if n <= 1 or self._is_latest else 0.70 + (idx / max(1, n - 1)) * 0.22

        thumb_h = DENSITY_THUMB_H.get(density, 113)
        self._thumb = _ThumbnailWidget(ph=ph, ver=ver, is_latest=self._is_latest,
                                       dim=dim, thumb_h=thumb_h)
        self._thumb.card_clicked.connect(lambda: self.selected_changed.emit(self))
        self._thumb.open_clicked.connect(lambda: self.open_requested.emit(str(self._hip_path)))
        self._thumb.copy_clicked.connect(lambda: self.copy_requested.emit(str(self._hip_path)))
        self._thumb.reveal_clicked.connect(lambda: self.reveal_requested.emit(str(self._hip_path)))
        layout.addWidget(self._thumb)

        meta = QWidget()
        meta.setStyleSheet(f"background: {C_BG2};")
        ml = QVBoxLayout(meta)
        ml.setContentsMargins(12, 10, 12, 11)
        ml.setSpacing(4)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        tl = QLabel(task)
        tl.setStyleSheet(f"color: {C_TEXT}; font-weight: 600; font-size: 13px;")
        tl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        size_str = _format_size(hip_path.stat().st_size) if (hip_path := self._hip_path).exists() else ""
        sl = QLabel(size_str)
        sl.setStyleSheet(f"color: {C_TEXT3}; font-family: 'JetBrains Mono', monospace; font-size: 11px;")
        sl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        row1.addWidget(tl, stretch=1)
        row1.addWidget(sl)
        ml.addLayout(row1)

        mtime_str = _format_date(self._hip_path.stat().st_mtime) if self._hip_path.exists() else ""
        dl = QLabel(mtime_str)
        dl.setStyleSheet(f"color: {C_TEXT3}; font-family: 'JetBrains Mono', monospace; font-size: 11px;")
        ml.addWidget(dl)

        layout.addWidget(meta)

    def event(self, ev):
        if ev.type() == QEvent.HoverEnter and not self._selected:
            self._set_border(C_LINE2)
        elif ev.type() == QEvent.HoverLeave and not self._selected:
            self._set_border(C_LINE)
        return super().event(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.selected_changed.emit(self)
        super().mousePressEvent(ev)

    def set_selected(self, v: bool):
        self._selected = v
        self._set_border(C_ACCENT if v else C_LINE)

    @property
    def hip_path(self) -> Path:
        return self._hip_path

    @property
    def parsed(self) -> dict | None:
        return self._parsed


# ---------------------------------------------------------------------------
# _NewVersionCard
# ---------------------------------------------------------------------------

class _NewVersionCard(QFrame):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setMinimumHeight(120)
        self._apply(False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)
        self._plus = QLabel("＋")
        self._plus.setAlignment(Qt.AlignCenter)
        self._ttl = QLabel("New version")
        self._ttl.setAlignment(Qt.AlignCenter)
        self._ttl.setStyleSheet("font-weight: 600; font-size: 13px; background: transparent;")
        lay.addStretch()
        lay.addWidget(self._plus)
        lay.addWidget(self._ttl)
        lay.addStretch()
        self._set_color(C_TEXT3)

    def _apply(self, hovered: bool):
        border = C_ACCENT if hovered else C_LINE2
        bg = "rgba(255,122,26,0.08)" if hovered else "transparent"
        self.setStyleSheet(f"QFrame {{ border: 1.5px dashed {border}; border-radius: 6px; background: {bg}; }}")

    def _set_color(self, c: str):
        self._plus.setStyleSheet(f"font-size: 22px; color: {c}; background: transparent;")
        self._ttl.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {c}; background: transparent;")

    def event(self, ev):
        if ev.type() == QEvent.HoverEnter:
            self._apply(True)
            self._set_color(C_ACCENT2)
        elif ev.type() == QEvent.HoverLeave:
            self._apply(False)
            self._set_color(C_TEXT3)
        return super().event(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(ev)


# ---------------------------------------------------------------------------
# _CardGrid — responsive column grid
# ---------------------------------------------------------------------------

class _CardGrid(QWidget):
    def __init__(self, density: str = "regular", parent=None):
        super().__init__(parent)
        self._density = density
        self._cards: list = []
        self._cols = 0
        self._lay = QGridLayout(self)
        self._lay.setSpacing(14)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def set_cards(self, cards: list):
        for c in self._cards:
            self._lay.removeWidget(c)
        self._cards = list(cards)
        self._cols = 0
        self._relayout()

    def set_density(self, density: str):
        self._density = density
        self._cols = 0
        self._relayout()

    def _calc_cols(self) -> int:
        min_w = DENSITY_MIN_W.get(self._density, 200)
        spacing = self._lay.horizontalSpacing()
        avail = self.width()
        if avail <= 0:
            return 3
        return max(1, (avail + spacing) // (min_w + spacing))

    def _relayout(self):
        cols = self._calc_cols()
        if cols == self._cols:
            return
        self._cols = cols
        for c in self._cards:
            self._lay.removeWidget(c)
        for i, card in enumerate(self._cards):
            row, col = divmod(i, cols)
            self._lay.addWidget(card, row, col)
            card.show()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._relayout()


# ---------------------------------------------------------------------------
# _TaskGroup
# ---------------------------------------------------------------------------

class _TaskGroup(QWidget):
    def __init__(self, task: str, cards: list, new_card: _NewVersionCard | None,
                 density: str = "regular", parent=None):
        super().__init__(parent)
        self._task = task

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 26)
        lay.setSpacing(0)

        # Header
        head = QWidget()
        head.setStyleSheet(f"border-bottom: 1px solid {C_LINE};")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(2, 0, 2, 10)
        hl.setSpacing(10)

        n = len(cards)
        nl = QLabel(task)
        nl.setStyleSheet(f"color: {C_TEXT}; font-size: 14px; font-weight: 600; border: none;")
        cl = QLabel(f"{n} version{'s' if n != 1 else ''}")
        cl.setStyleSheet(f"color: {C_TEXT3}; font-size: 12px; border: none;")

        latest_ver = ""
        for c in reversed(cards):
            if isinstance(c, _HipCard) and c.parsed:
                latest_ver = c.parsed.get("version_str", "")
                break

        ll = QLabel(f"latest <b>{latest_ver}</b>" if latest_ver else "")
        ll.setTextFormat(Qt.RichText)
        ll.setStyleSheet(f"color: {C_TEXT3}; font-size: 11px; font-family: 'JetBrains Mono', monospace; border: none;")

        hl.addWidget(nl)
        hl.addWidget(cl)
        hl.addStretch()
        hl.addWidget(ll)
        lay.addWidget(head)

        sp = QWidget()
        sp.setFixedHeight(14)
        sp.setStyleSheet("border: none;")
        lay.addWidget(sp)

        all_cards = list(cards)
        if new_card:
            all_cards.append(new_card)
        self._grid = _CardGrid(density=density)
        self._grid.set_cards(all_cards)
        lay.addWidget(self._grid)

    def set_density(self, density: str):
        self._grid.set_density(density)


# ---------------------------------------------------------------------------
# _DetailDrawer
# ---------------------------------------------------------------------------

class _DetailDrawer(QFrame):
    open_requested   = Signal(str)
    copy_requested   = Signal(str)
    reveal_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedWidth(320)
        self.setStyleSheet(f"QFrame {{ background: {C_BG2}; border-left: 1px solid {C_LINE}; }}")

        self._current_path: str | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        head = QWidget()
        head.setStyleSheet(f"background: {C_BG2}; border-bottom: 1px solid {C_LINE};")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(14, 12, 14, 12)
        hl.setSpacing(6)
        htxt = QWidget()
        htxt.setStyleSheet("border: none; background: transparent;")
        htl = QVBoxLayout(htxt)
        htl.setContentsMargins(0, 0, 0, 0)
        htl.setSpacing(2)
        self._sub = QLabel("VERSION DETAIL")
        self._sub.setStyleSheet(f"color: {C_TEXT3}; font-size: 10px; letter-spacing: 2px; background: transparent;")
        self._ttl = QLabel("—")
        self._ttl.setStyleSheet(f"color: {C_TEXT}; font-weight: 600; font-family: 'JetBrains Mono', monospace; background: transparent;")
        htl.addWidget(self._sub)
        htl.addWidget(self._ttl)
        hl.addWidget(htxt, stretch=1)
        lay.addWidget(head)

        # Scrollable body
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet(f"background: {C_BG2}; border: none;")
        self._body = QWidget()
        self._body.setStyleSheet(f"background: {C_BG2};")
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(0, 0, 0, 0)
        self._body_lay.setSpacing(0)
        self._body_lay.addStretch()
        self._scroll.setWidget(self._body)
        lay.addWidget(self._scroll, stretch=1)

        # Actions
        acts = QWidget()
        acts.setStyleSheet(f"background: {C_BG2}; border-top: 1px solid {C_LINE};")
        al = QGridLayout(acts)
        al.setContentsMargins(14, 12, 14, 12)
        al.setSpacing(8)
        self._btn_open   = QPushButton("Open in Houdini")
        self._btn_copy   = QPushButton("Copy path")
        self._btn_reveal = QPushButton("Reveal")
        self._btn_open.setObjectName("primary")
        al.addWidget(self._btn_open,   0, 0, 1, 2)
        al.addWidget(self._btn_copy,   1, 0)
        al.addWidget(self._btn_reveal, 1, 1)
        self._btn_open.clicked.connect(lambda: self._current_path and self.open_requested.emit(self._current_path))
        self._btn_copy.clicked.connect(lambda: self._current_path and self.copy_requested.emit(self._current_path))
        self._btn_reveal.clicked.connect(lambda: self._current_path and self.reveal_requested.emit(self._current_path))
        lay.addWidget(acts)

    def show_hip(self, hip_path: Path, parsed: dict | None, all_versions: list):
        self._current_path = str(hip_path)
        task = (parsed.get("task", "unknown") if parsed else "unknown") or "unknown"
        ver  = (parsed.get("version_str", "v???") if parsed else "v???") or "v???"
        self._ttl.setText(f"{task} · {ver}")

        while self._body_lay.count() > 1:
            item = self._body_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        kvs = [
            ("name", hip_path.name),
            ("size", _format_size(hip_path.stat().st_size) if hip_path.exists() else "—"),
            ("saved", _format_date_full(hip_path.stat().st_mtime) if hip_path.exists() else "—"),
        ]
        self._body_lay.insertWidget(0, self._make_kv_section("File", kvs))
        self._body_lay.insertWidget(1, self._make_history_section(all_versions, hip_path))

    def _make_kv_section(self, title: str, kvs: list) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {C_BG2}; border-bottom: 1px solid {C_LINE};")
        l = QVBoxLayout(w)
        l.setContentsMargins(14, 12, 14, 12)
        l.setSpacing(8)
        h4 = QLabel(title.upper())
        h4.setStyleSheet(f"color: {C_TEXT3}; font-size: 10px; letter-spacing: 2px; font-weight: 600; background: transparent;")
        l.addWidget(h4)
        grid = QWidget()
        grid.setStyleSheet("background: transparent;")
        gl = QGridLayout(grid)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(6)
        gl.setColumnMinimumWidth(0, 50)
        for i, (k, v) in enumerate(kvs):
            kl = QLabel(k)
            kl.setStyleSheet(f"color: {C_TEXT3}; font-family: 'JetBrains Mono', monospace; font-size: 11px; background: transparent;")
            vl = QLabel(str(v))
            vl.setStyleSheet(f"color: {C_TEXT}; font-family: 'JetBrains Mono', monospace; font-size: 11px; background: transparent;")
            vl.setWordWrap(True)
            gl.addWidget(kl, i, 0, Qt.AlignTop)
            gl.addWidget(vl, i, 1, Qt.AlignTop)
        l.addWidget(grid)
        return w

    def _make_history_section(self, all_versions: list, current: Path) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {C_BG2}; border-bottom: 1px solid {C_LINE};")
        l = QVBoxLayout(w)
        l.setContentsMargins(14, 12, 14, 12)
        l.setSpacing(4)
        h4 = QLabel("VERSION HISTORY")
        h4.setStyleSheet(f"color: {C_TEXT3}; font-size: 10px; letter-spacing: 2px; font-weight: 600; background: transparent;")
        l.addWidget(h4)
        for hip in reversed(all_versions):
            prs = pipeline.parse_hip_filename(hip.name)
            ver_s = (prs.get("version_str", hip.stem) if prs else hip.stem) or hip.stem
            is_cur = hip == current
            bg = "rgba(255,122,26,0.10)" if is_cur else "transparent"
            row = QWidget()
            row.setStyleSheet(f"border-radius: 4px; background: {bg};")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(8, 5, 8, 5)
            rl.setSpacing(8)
            vc = C_ACCENT2 if is_cur else C_TEXT
            vl = QLabel(ver_s)
            vl.setStyleSheet(f"color: {vc}; font-weight: 600; font-family: 'JetBrains Mono', monospace; font-size: 11px; background: transparent; min-width: 36px;")
            wl = QLabel(_format_date(hip.stat().st_mtime) if hip.exists() else "")
            wl.setStyleSheet(f"color: {C_TEXT3}; font-family: 'JetBrains Mono', monospace; font-size: 11px; background: transparent;")
            szl = QLabel(_format_size(hip.stat().st_size) if hip.exists() else "")
            szl.setStyleSheet(f"color: {C_TEXT3}; font-family: 'JetBrains Mono', monospace; font-size: 11px; background: transparent;")
            rl.addWidget(vl)
            rl.addWidget(wl, stretch=1)
            rl.addWidget(szl)
            l.addWidget(row)
        return w


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
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)

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
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)

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
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)

    def _accept(self):
        if not self._shot.text().strip():
            QMessageBox.warning(self, "Validation", "Shot code is required.")
            return
        self.accept()

    def shot_code(self) -> str:
        return self._shot.text().strip()


class NewVersionDialog(QDialog):
    def __init__(self, entity: str, work_houdini: Path, parent=None):
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
        self._preview.setStyleSheet(f"color: {C_TEXT3};")
        form.addRow("File:", self._preview)
        self._task_combo.currentTextChanged.connect(self._update_preview)
        self._update_preview(self._task_combo.currentText())
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)

    def _update_preview(self, raw: str):
        try:
            task = naming_conventions.validate_task(raw)
            path = pipeline.next_hip_path(self._work_houdini, self._entity, task)
            self._preview.setText(path.name)
            self._preview.setStyleSheet(f"color: {C_TEXT3};")
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
# _SegControl — horizontal segmented button group
# ---------------------------------------------------------------------------

class _SegControl(QFrame):
    changed = Signal(str)  # emits value of selected option

    def __init__(self, options: list, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(f"QFrame {{ background: {C_BG}; border: 1px solid {C_LINE}; border-radius: 5px; padding: 2px; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(0)
        self._btns: dict[str, QPushButton] = {}
        for value, label in options:
            btn = QPushButton(label)
            btn.setObjectName("seg-btn")
            btn.setProperty("active", "false")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, v=value: self._select(v))
            lay.addWidget(btn)
            self._btns[value] = btn
        if options:
            self._select(options[0][0])

    def _select(self, value: str):
        for v, btn in self._btns.items():
            active = v == value
            btn.setProperty("active", "true" if active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.changed.emit(value)

    def value(self) -> str:
        for v, btn in self._btns.items():
            if btn.property("active") == "true":
                return v
        return ""

    def set_value(self, value: str):
        self._select(value)


# ---------------------------------------------------------------------------
# FileManagerWindow
# ---------------------------------------------------------------------------

class FileManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FX File Manager")
        self.setMinimumSize(1000, 640)
        self._density = "regular"
        self._group_mode = "task"
        self._task_filter: str | None = None  # None = all
        self._selected_card: _HipCard | None = None
        self._task_groups: list[_TaskGroup] = []
        self._all_cards: list[_HipCard] = []
        self._drawer_visible = True
        self._build_ui()
        self._populate_projects()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_titlebar())
        root.addWidget(self._build_toolbar())

        # Main area: scroll + drawer
        self._main_row = QWidget()
        self._main_row.setStyleSheet(f"background: {C_BG};")
        mr_lay = QHBoxLayout(self._main_row)
        mr_lay.setContentsMargins(0, 0, 0, 0)
        mr_lay.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet(f"background: {C_BG}; border: none;")
        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet(f"background: {C_BG};")
        self._scroll_lay = QVBoxLayout(self._scroll_content)
        self._scroll_lay.setContentsMargins(16, 16, 16, 20)
        self._scroll_lay.setSpacing(0)
        self._scroll_lay.addStretch()
        self._scroll.setWidget(self._scroll_content)
        mr_lay.addWidget(self._scroll, stretch=1)

        self._drawer = _DetailDrawer()
        self._drawer.open_requested.connect(self._on_open_path)
        self._drawer.copy_requested.connect(self._on_copy_path)
        self._drawer.reveal_requested.connect(self._on_reveal_path)
        mr_lay.addWidget(self._drawer)

        root.addWidget(self._main_row, stretch=1)
        root.addWidget(self._build_statusbar())

        QShortcut(QKeySequence("F5"), self, self._refresh_hips)
        QShortcut(QKeySequence("Return"), self, self._open_selected)
        QShortcut(QKeySequence("N"), self, self._on_new_version)

    def _build_titlebar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("titlebar")
        bar.setStyleSheet(f"QFrame#titlebar {{ background: {C_BG2}; border-bottom: 1px solid {C_LINE}; }}")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(12)

        # Logo
        logo_box = QFrame()
        logo_box.setFixedSize(18, 18)
        logo_box.setStyleSheet(f"background: {C_ACCENT}; border-radius: 4px;")
        logo_lbl = QLabel("FX")
        logo_lbl.setParent(logo_box)
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet("color: white; font-weight: 700; font-size: 10px; background: transparent;")
        logo_lbl.setGeometry(0, 0, 18, 18)
        title_lbl = QLabel("File Manager")
        title_lbl.setStyleSheet(f"color: {C_TEXT}; font-weight: 700; font-size: 13px;")
        lay.addWidget(logo_box)
        lay.addWidget(title_lbl)

        # Separator
        sep = QFrame()
        sep.setFixedSize(1, 18)
        sep.setStyleSheet(f"background: {C_LINE};")
        lay.addWidget(sep)

        # Breadcrumb: project combo / seq combo / shot combo
        self._project_combo = QComboBox()
        self._project_combo.currentIndexChanged.connect(self._on_project_changed)
        self._seq_combo = QComboBox()
        self._seq_combo.currentIndexChanged.connect(self._on_seq_changed)
        self._shot_combo = QComboBox()
        self._shot_combo.currentIndexChanged.connect(self._on_shot_changed)

        sep_lbl = lambda: self._make_sep_label("/")
        lay.addWidget(self._project_combo)
        lay.addWidget(sep_lbl())
        lay.addWidget(self._seq_combo)
        lay.addWidget(sep_lbl())
        lay.addWidget(self._shot_combo)

        lay.addStretch()

        # Search (static UI element)
        search_frame = QFrame()
        search_frame.setStyleSheet(f"QFrame {{ background: {C_BG}; border: 1px solid {C_LINE}; border-radius: 5px; }}")
        sf_lay = QHBoxLayout(search_frame)
        sf_lay.setContentsMargins(8, 5, 8, 5)
        sf_lay.setSpacing(8)
        search_lbl = QLabel("Search…")
        search_lbl.setStyleSheet(f"color: {C_TEXT3}; font-size: 12px; background: transparent; border: none;")
        kbd_lbl = QLabel("F5")
        kbd_lbl.setStyleSheet(f"color: {C_TEXT3}; font-size: 10px; font-family: 'JetBrains Mono', monospace; background: {C_BG3}; border: 1px solid {C_LINE}; border-radius: 3px; padding: 1px 5px;")
        sf_lay.addWidget(search_lbl)
        sf_lay.addWidget(kbd_lbl)
        lay.addWidget(search_frame)

        # Refresh button
        refresh_btn = QPushButton("↺")
        refresh_btn.setObjectName("icon-btn")
        refresh_btn.setFixedSize(30, 30)
        refresh_btn.setToolTip("Refresh (F5)")
        refresh_btn.clicked.connect(self._refresh_hips)
        lay.addWidget(refresh_btn)

        # Drawer toggle
        drawer_btn = QPushButton("⊟")
        drawer_btn.setObjectName("icon-btn")
        drawer_btn.setFixedSize(30, 30)
        drawer_btn.setToolTip("Toggle detail panel")
        drawer_btn.clicked.connect(self._toggle_drawer)
        lay.addWidget(drawer_btn)

        # Add buttons (collapsed into + menu or separate)
        add_proj_btn = QPushButton("+ Project")
        add_proj_btn.setToolTip("Add project")
        add_proj_btn.clicked.connect(self._on_add_project)
        add_seq_btn = QPushButton("+ Seq")
        add_seq_btn.setToolTip("Add sequence")
        add_seq_btn.clicked.connect(self._on_add_sequence)
        add_shot_btn = QPushButton("+ Shot")
        add_shot_btn.setToolTip("Add shot")
        add_shot_btn.clicked.connect(self._on_add_shot)
        lay.addWidget(add_proj_btn)
        lay.addWidget(add_seq_btn)
        lay.addWidget(add_shot_btn)

        return bar

    def _make_sep_label(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"color: {C_TEXT4}; font-size: 13px;")
        return l

    def _build_toolbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("toolbar")
        bar.setStyleSheet(f"QFrame#toolbar {{ background: {C_BG2}; border-bottom: 1px solid {C_LINE}; }}")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(8)

        # View seg
        self._view_seg = _SegControl([("all", "All tasks"), ("latest", "Latest only"), ("published", "Published")])
        self._view_seg.changed.connect(self._on_view_changed)
        lay.addWidget(self._view_seg)

        lay.addWidget(self._make_vr())

        # Task filter chips container
        self._chips_widget = QWidget()
        self._chips_widget.setStyleSheet("background: transparent;")
        self._chips_lay = QHBoxLayout(self._chips_widget)
        self._chips_lay.setContentsMargins(0, 0, 0, 0)
        self._chips_lay.setSpacing(6)
        lay.addWidget(self._chips_widget)

        lay.addStretch()

        # Density seg
        self._density_seg = _SegControl([("comfy", "⊞"), ("regular", "⊟"), ("compact", "⊠")])
        self._density_seg.changed.connect(self._on_density_changed)
        self._density_seg.set_value("regular")
        lay.addWidget(self._density_seg)

        lay.addWidget(self._make_vr())

        # Group seg
        self._group_seg = _SegControl([("task", "Group: Task"), ("flat", "Flat")])
        self._group_seg.changed.connect(self._on_group_changed)
        lay.addWidget(self._group_seg)

        lay.addWidget(self._make_vr())

        # New Version
        new_btn = QPushButton("＋ New Version")
        new_btn.setObjectName("primary")
        new_btn.setToolTip("New Houdini version (N)")
        new_btn.clicked.connect(self._on_new_version)
        lay.addWidget(new_btn)

        return bar

    def _make_vr(self) -> QFrame:
        vr = QFrame()
        vr.setFixedSize(1, 18)
        vr.setStyleSheet(f"background: {C_LINE};")
        return vr

    def _build_statusbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("statusbar")
        bar.setStyleSheet(f"""
            QFrame#statusbar {{
                background: {C_BG2};
                border-top: 1px solid {C_LINE};
                min-height: 28px;
            }}
        """)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 5, 14, 5)
        lay.setSpacing(16)

        self._status_conn = QLabel("● connected")
        self._status_conn.setStyleSheet(f"color: {C_OK}; font-family: 'JetBrains Mono', monospace; font-size: 11px;")
        self._status_files = QLabel("0 hip files")
        self._status_files.setStyleSheet(f"color: {C_TEXT3}; font-family: 'JetBrains Mono', monospace; font-size: 11px;")
        self._status_entity = QLabel("")
        self._status_entity.setStyleSheet(f"color: {C_TEXT}; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 500;")
        hints = QLabel("F5 refresh · ↵ open · ⌘C copy")
        hints.setStyleSheet(f"color: {C_TEXT4}; font-family: 'JetBrains Mono', monospace; font-size: 11px;")

        lay.addWidget(self._status_conn)
        lay.addWidget(self._status_files)
        lay.addWidget(self._status_entity)
        lay.addStretch()
        lay.addWidget(hints)
        return bar

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

    def _on_shot_changed(self, _index: int):
        self._refresh_hips()

    def _refresh_hips(self):
        self._clear_cards()
        project = self._project_combo.currentData()
        seq = self._seq_combo.currentText()
        shot = self._shot_combo.currentText()
        if not all([project, seq, shot]):
            self._status_files.setText("0 hip files")
            self._status_entity.setText("")
            return

        entity = f"{seq}_{shot}"
        self._status_entity.setText(entity)
        work_dir = pipeline.shot_work_houdini(project["folder"], seq, shot)
        hips = pipeline.find_hip_files(work_dir)

        # Group by task
        task_map: dict[str, list[Path]] = {}
        for hip in hips:
            parsed = pipeline.parse_hip_filename(hip.name)
            task = (parsed.get("task", "unknown") if parsed else "unknown") or "unknown"
            task_map.setdefault(task, []).append(hip)

        self._all_cards = []
        self._task_groups = []

        for task in sorted(task_map.keys()):
            versions = sorted(task_map[task])
            cards = []
            for hip in versions:
                parsed = pipeline.parse_hip_filename(hip.name)
                is_latest = hip == versions[-1]
                card = _HipCard(hip, parsed, is_latest, versions, self._density)
                card.open_requested.connect(self._on_open_path)
                card.copy_requested.connect(self._on_copy_path)
                card.reveal_requested.connect(self._on_reveal_path)
                card.selected_changed.connect(self._on_card_selected)
                cards.append(card)
                self._all_cards.append(card)

            new_card = _NewVersionCard()
            new_card.clicked.connect(lambda t=task: self._new_version_for_task(t))
            grp = _TaskGroup(task, cards, new_card, density=self._density)
            self._task_groups.append(grp)

        self._rebuild_chip_filters()
        self._apply_filters()
        self._status_files.setText(f"{len(hips)} hip file{'s' if len(hips) != 1 else ''} · {len(task_map)} task{'s' if len(task_map) != 1 else ''}")

    def _clear_cards(self):
        while self._scroll_lay.count() > 1:
            item = self._scroll_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._all_cards = []
        self._task_groups = []
        self._selected_card = None

    def _rebuild_chip_filters(self):
        # Remove old chips
        while self._chips_lay.count():
            item = self._chips_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # "All" chip
        all_btn = QPushButton(f"All  {len(self._all_cards)}")
        all_btn.setObjectName("chip-btn")
        all_btn.setProperty("active", "true" if self._task_filter is None else "false")
        all_btn.setCursor(Qt.PointingHandCursor)
        all_btn.clicked.connect(lambda: self._set_task_filter(None))
        self._chips_lay.addWidget(all_btn)

        # Per-task chips
        task_counts: dict[str, int] = {}
        for card in self._all_cards:
            task = (card.parsed.get("task", "unknown") if card.parsed else "unknown") or "unknown"
            task_counts[task] = task_counts.get(task, 0) + 1

        for task, count in sorted(task_counts.items()):
            btn = QPushButton(f"{task}  {count}")
            btn.setObjectName("chip-btn")
            btn.setProperty("active", "true" if self._task_filter == task else "false")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, t=task: self._set_task_filter(t))
            self._chips_lay.addWidget(btn)

        # Re-polish all
        for i in range(self._chips_lay.count()):
            w = self._chips_lay.itemAt(i).widget()
            if w:
                w.style().unpolish(w)
                w.style().polish(w)

    def _set_task_filter(self, task: str | None):
        self._task_filter = task
        self._rebuild_chip_filters()
        self._apply_filters()

    def _apply_filters(self):
        # Remove existing groups from scroll
        while self._scroll_lay.count() > 1:
            item = self._scroll_lay.takeAt(0)
            if item.widget():
                item.widget().hide()
                self._scroll_lay.removeItem(item)

        view = self._view_seg.value()
        idx = 0
        for grp in self._task_groups:
            task = grp._task
            if self._task_filter is not None and task != self._task_filter:
                continue
            self._scroll_lay.insertWidget(idx, grp)
            grp.show()
            idx += 1

    def _on_view_changed(self, value: str):
        # Could filter cards by latest/published — placeholder
        self._apply_filters()

    def _on_density_changed(self, density: str):
        self._density = density
        for grp in self._task_groups:
            grp.set_density(density)

    def _on_group_changed(self, mode: str):
        self._group_mode = mode

    def _toggle_drawer(self):
        self._drawer_visible = not self._drawer_visible
        self._drawer.setVisible(self._drawer_visible)

    # ------------------------------------------------------------------
    # Card selection
    # ------------------------------------------------------------------

    def _on_card_selected(self, card: _HipCard):
        if self._selected_card and self._selected_card is not card:
            self._selected_card.set_selected(False)
        self._selected_card = card
        card.set_selected(True)

        # Get all versions for this task
        task = (card.parsed.get("task", "unknown") if card.parsed else "unknown") or "unknown"
        same_task = [c.hip_path for c in self._all_cards
                     if (c.parsed.get("task") if c.parsed else "unknown") == task]

        self._drawer.show_hip(card.hip_path, card.parsed, same_task)
        if not self._drawer_visible:
            self._toggle_drawer()

    # ------------------------------------------------------------------
    # Hip actions
    # ------------------------------------------------------------------

    def _open_selected(self):
        if self._selected_card:
            self._on_open_path(str(self._selected_card.hip_path))

    def _on_open_path(self, path: str):
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
        except ImportError:
            QMessageBox.information(self, "Standalone", f"Would open: {path}")

    def _on_copy_path(self, path: str):
        QApplication.clipboard().setText(path)

    def _on_reveal_path(self, path: str):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

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

    def _on_new_version(self):
        project = self._project_combo.currentData()
        seq = self._seq_combo.currentText()
        shot = self._shot_combo.currentText()
        if not all([project, seq, shot]):
            return
        self._new_version_for_task(None)

    def _new_version_for_task(self, task: str | None):
        project = self._project_combo.currentData()
        seq = self._seq_combo.currentText()
        shot = self._shot_combo.currentText()
        if not all([project, seq, shot]):
            return
        entity = f"{seq}_{shot}"
        work_dir = pipeline.shot_work_houdini(project["folder"], seq, shot)
        dlg = NewVersionDialog(entity=entity, work_houdini=work_dir, parent=self)
        if task:
            try:
                idx = dlg._task_combo.findText(task)
                if idx >= 0:
                    dlg._task_combo.setCurrentIndex(idx)
                else:
                    dlg._task_combo.setCurrentText(task)
            except Exception:
                pass
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

    def closeEvent(self, event):
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(_QSS)

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
