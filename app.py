from __future__ import annotations

import math
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QSpinBox, QSplitter, QStackedWidget, QToolButton, QVBoxLayout,
    QWidget,
)

from RigolWFM import Wfm


APP_NAME = "WFM Scope Viewer"
CHANNEL_COLORS = ("#F7D23E", "#39D98A", "#55A8FF", "#E774FF")
BG = "#080D16"
PANEL = "#111925"
GRID = (88, 106, 130, 95)


@dataclass(frozen=True)
class DisplayChannel:
    number: int
    times: np.ndarray
    volts: np.ndarray
    source: Any

    @property
    def points(self) -> int:
        return min(len(self.times), len(self.volts))


def human_number(value: float | int | None, unit: str = "") -> str:
    if value is None:
        return "—"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(value):
        return "—"
    prefixes = ((1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""),
                (1e-3, "m"), (1e-6, "µ"), (1e-9, "n"), (1e-12, "p"))
    magnitude = abs(value)
    for scale, prefix in prefixes:
        if magnitude >= scale or scale == 1e-12:
            return f"{value / scale:.4g} {prefix}{unit}".strip()
    return f"{value:.4g} {unit}".strip()


def public_metadata(obj: Any, excluded: Iterable[str] = ()) -> list[tuple[str, str]]:
    blocked = set(excluded)
    rows: list[tuple[str, str]] = []
    try:
        values = vars(obj)
    except TypeError:
        values = {}
    for key, value in values.items():
        if key.startswith("_") or key in blocked or value is None:
            continue
        if isinstance(value, (np.ndarray, bytes, bytearray, dict, list, tuple)):
            continue
        if callable(value):
            continue
        text = str(value)
        if len(text) <= 120:
            rows.append((key.replace("_", " ").title(), text))
    return sorted(rows)


def channel_settings(source: Any) -> list[tuple[str, str]]:
    """Return channel settings with user-facing units and compact rounding."""
    rows: list[tuple[str, str]] = []
    fields = (
        ("Coupling", "coupling", None),
        ("Scale", "volt_per_division", "V/Div"),
        ("Voltage scale", "volt_scale", "V"),
        ("Voltage offset", "volt_offset", "V"),
        ("Time base", "time_scale", "s/Div"),
        ("Time offset", "time_offset", "s"),
        ("Sample interval", "seconds_per_point", "s"),
        ("Probe", "probe_value", "×"),
        ("Inverted", "inverted", None),
    )
    for label, attribute, unit in fields:
        value = getattr(source, attribute, None)
        if value is None:
            continue
        if unit == "×":
            rows.append((label, f"{float(value):g}×"))
        elif unit:
            rows.append((label, human_number(value, unit)))
        else:
            rows.append((label, str(value)))
    return rows


def model_selection_metadata(wfm: Any) -> list[tuple[str, str]]:
    """Present the parser's user-model setting in plain language."""
    value = getattr(wfm, "user_name", None)
    if value is None:
        return []
    shown = "Automatic" if str(value).strip().lower() == "auto" else str(value)
    return [("Model Selection", shown)]


def enabled_channels(wfm: Any) -> list[DisplayChannel]:
    result = []
    for fallback, ch in enumerate(getattr(wfm, "channels", []), 1):
        times, volts = getattr(ch, "times", None), getattr(ch, "volts", None)
        if times is None or volts is None:
            continue
        number = int(getattr(ch, "channel_number", fallback))
        result.append(DisplayChannel(number, np.asarray(times), np.asarray(volts), ch))
    return sorted(result, key=lambda item: item.number)


class DropPanel(QFrame):
    open_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropPanel")
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel("∿")
        icon.setObjectName("dropIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Open a Rigol waveform")
        title.setObjectName("emptyTitle")
        hint = QLabel("Drop a .wfm file here or choose one from your computer")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button = QPushButton("Choose WFM file")
        button.clicked.connect(self.open_requested)
        layout.addWidget(icon)
        layout.addSpacing(12)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(16)
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignCenter)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if any(Path(url.toLocalFile()).suffix.lower() == ".wfm" for url in urls):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() == ".wfm":
                self.window().load_file(path)
                event.acceptProposedAction()
                return


class ScopePlot(pg.PlotWidget):
    def __init__(self) -> None:
        super().__init__(background=BG)
        self.setMinimumHeight(240)
        self.getPlotItem().showGrid(x=True, y=True, alpha=0.22)
        self.getPlotItem().setMenuEnabled(True)
        self.getPlotItem().getViewBox().setMouseMode(pg.ViewBox.RectMode)
        self.getAxis("bottom").setTextPen("#9BAABD")
        self.getAxis("left").setTextPen("#9BAABD")
        self.getAxis("bottom").setPen(pg.mkPen(GRID))
        self.getAxis("left").setPen(pg.mkPen(GRID))


class MetadataPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        header = QLabel("FILE DESCRIPTION")
        header.setObjectName("eyebrow")
        self.filename = QLabel("No file loaded")
        self.filename.setObjectName("metaTitle")
        self.filename.setWordWrap(True)
        self.summary = QLabel("")
        self.summary.setObjectName("muted")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter metadata…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        outer.addWidget(header)
        outer.addWidget(self.filename)
        outer.addWidget(self.summary)
        outer.addSpacing(8)
        outer.addWidget(self.search)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget()
        self.cards = QVBoxLayout(self.content)
        self.cards.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.content)
        outer.addWidget(scroll, 1)

    def clear(self) -> None:
        while self.cards.count():
            item = self.cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def card(self, title: str, rows: list[tuple[str, str]], color: str | None = None):
        frame = QFrame()
        frame.setObjectName("metaCard")
        frame.setProperty("searchText", (title + " " + " ".join(sum(([a, b] for a, b in rows), []))).lower())
        layout = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setObjectName("cardTitle")
        if color:
            heading.setStyleSheet(f"color: {color};")
        layout.addWidget(heading)
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        for row, (key, value) in enumerate(rows):
            k = QLabel(key)
            k.setObjectName("metaKey")
            v = QLabel(value)
            v.setObjectName("metaValue")
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            v.setWordWrap(True)
            grid.addWidget(k, row, 0, alignment=Qt.AlignmentFlag.AlignTop)
            grid.addWidget(v, row, 1, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(grid)
        self.cards.addWidget(frame)

    def populate(self, path: Path, wfm: Any, channels: list[DisplayChannel]) -> None:
        self.clear()
        self.filename.setText(path.name)
        self.summary.setText(f"{len(channels)} analog channel{'s' if len(channels) != 1 else ''} detected")
        general = [("Path", str(path)), ("Size", human_number(path.stat().st_size, "B")),
                   ("Channels", ", ".join(f"CH{c.number}" for c in channels) or "None")]
        general += model_selection_metadata(wfm)
        general += public_metadata(
            wfm,
            {"channels", "logic_channels", "logic_times", "user_name"},
        )
        self.card("GENERAL", general)
        for index, channel in enumerate(channels):
            t = channel.times[:channel.points].astype(float, copy=False)
            v = channel.volts[:channel.points].astype(float, copy=False)
            duration = abs(float(t[-1] - t[0])) if len(t) > 1 else 0.0
            sample_rate = (len(t) - 1) / duration if duration > 0 else None
            rows = [("Points", f"{channel.points:,}"), ("Duration", human_number(duration, "s")),
                    ("Sample rate", human_number(sample_rate, "Sa/s")),
                    ("Minimum", human_number(float(np.nanmin(v)), "V")),
                    ("Maximum", human_number(float(np.nanmax(v)), "V")),
                    ("Mean", human_number(float(np.nanmean(v)), "V")),
                    ("RMS", human_number(float(np.sqrt(np.nanmean(v ** 2))), "V"))]
            rows += channel_settings(channel.source)
            rows += public_metadata(
                channel.source,
                {"times", "volts", "raw", "channel_number", "points", "coupling",
                 "volt_per_division", "volt_scale", "volt_offset", "time_scale",
                 "time_offset", "seconds_per_point", "probe_value", "inverted"},
            )
            self.card(f"CH{channel.number}", rows, CHANNEL_COLORS[(channel.number - 1) % 4])
        logic = getattr(wfm, "logic_channels", None)
        if logic:
            self.card("LOGIC CHANNELS", [("Detected", ", ".join(map(str, logic.keys()))),
                                          ("Count", str(len(logic)))])
        self._filter(self.search.text())

    def _filter(self, text: str) -> None:
        query = text.strip().lower()
        for i in range(self.cards.count()):
            widget = self.cards.itemAt(i).widget()
            widget.setVisible(not query or query in widget.property("searchText"))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 860)
        self.setMinimumSize(980, 640)
        self.wfm = None
        self.path: Path | None = None
        self.channels: list[DisplayChannel] = []
        self.plots: list[ScopePlot] = []
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        top = QFrame()
        top.setObjectName("topbar")
        top.setMinimumHeight(54)
        top_layout = QHBoxLayout(top)
        brand = QLabel("WFM  /  SCOPE VIEWER")
        brand.setObjectName("brand")
        self.file_label = QLabel("No waveform loaded")
        self.file_label.setObjectName("muted")
        open_button = QPushButton("Open WFM")
        open_button.clicked.connect(self.open_file)
        top_layout.addWidget(brand)
        top_layout.addSpacing(18)
        top_layout.addWidget(self.file_label, 1)
        top_layout.addWidget(open_button)
        layout.addWidget(top)

        self.stack = QStackedWidget()
        self.drop_panel = DropPanel()
        self.drop_panel.open_requested.connect(self.open_file)
        self.stack.addWidget(self.drop_panel)
        self.viewer = QWidget()
        viewer_layout = QVBoxLayout(self.viewer)
        viewer_layout.setContentsMargins(14, 12, 14, 14)
        controls = QHBoxLayout()
        mode_label = QLabel("VIEW")
        mode_label.setObjectName("eyebrow")
        self.overlay = QToolButton(text="Overlay")
        self.separate = QToolButton(text="Separate")
        for button in (self.overlay, self.separate):
            button.setCheckable(True)
        self.overlay.setChecked(True)
        modes = QButtonGroup(self)
        modes.setExclusive(True)
        modes.addButton(self.overlay)
        modes.addButton(self.separate)
        self.overlay.clicked.connect(self.render_plots)
        self.separate.clicked.connect(self.render_plots)
        self.channel_chips = QHBoxLayout()
        self.point_limit = QSpinBox()
        self.point_limit.setRange(1_000, 1_000_000)
        self.point_limit.setSingleStep(10_000)
        self.point_limit.setValue(100_000)
        self.point_limit.setSuffix(" pts")
        self.point_limit.setToolTip("Maximum displayed points per channel")
        self.point_limit.valueChanged.connect(self.render_plots)
        auto = QPushButton("Autoscale")
        auto.clicked.connect(self.autoscale)
        export = QPushButton("Export PNG")
        export.clicked.connect(self.export_png)
        controls.addWidget(mode_label)
        controls.addWidget(self.overlay)
        controls.addWidget(self.separate)
        controls.addSpacing(14)
        controls.addLayout(self.channel_chips)
        controls.addStretch()
        controls.addWidget(self.point_limit)
        controls.addWidget(auto)
        controls.addWidget(export)
        viewer_layout.addLayout(controls)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.plot_host = QWidget()
        self.plot_layout = QGridLayout(self.plot_host)
        self.plot_layout.setContentsMargins(0, 8, 8, 0)
        self.metadata = MetadataPanel()
        self.metadata.setMinimumWidth(330)
        self.metadata.setMaximumWidth(500)
        split.addWidget(self.plot_host)
        split.addWidget(self.metadata)
        split.setSizes([1000, 390])
        split.setStretchFactor(0, 1)
        viewer_layout.addWidget(split, 1)
        self.stack.addWidget(self.viewer)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        action = QAction("Open", self)
        action.setShortcut(QKeySequence.StandardKey.Open)
        action.triggered.connect(self.open_file)
        self.addAction(action)

    def open_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Open waveform", str(self.path.parent if self.path else Path.home()),
                                                   "Rigol waveform (*.wfm);;All files (*)")
        if filename:
            self.load_file(Path(filename))

    def load_file(self, path: Path) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            wfm = Wfm.from_file(str(path))
            channels = enabled_channels(wfm)
            if not channels:
                raise ValueError("This capture does not contain any enabled analog channels.")
            self.wfm, self.path, self.channels = wfm, path, channels
            self.file_label.setText(f"{path.name}  ·  {len(channels)} channel{'s' if len(channels) != 1 else ''}")
            self.metadata.populate(path, wfm, channels)
            self._render_chips()
            self.render_plots()
            self.stack.setCurrentWidget(self.viewer)
            self.setWindowTitle(f"{path.name} — {APP_NAME}")
        except Exception as exc:
            QMessageBox.critical(self, "Unable to open waveform", f"{exc}\n\n{traceback.format_exc(limit=2)}")
        finally:
            QApplication.restoreOverrideCursor()

    def _render_chips(self) -> None:
        while self.channel_chips.count():
            item = self.channel_chips.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for channel in self.channels:
            chip = QLabel(f"● CH{channel.number}")
            chip.setStyleSheet(f"color: {CHANNEL_COLORS[(channel.number - 1) % 4]}; font-weight: 700;")
            self.channel_chips.addWidget(chip)

    def _clear_plots(self) -> None:
        self.plots.clear()
        while self.plot_layout.count():
            item = self.plot_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def _plot_channel(self, plot: ScopePlot, channel: DisplayChannel, legend: bool = False) -> None:
        n = channel.points
        stride = max(math.ceil(n / self.point_limit.value()), 1)
        color = CHANNEL_COLORS[(channel.number - 1) % 4]
        plot.plot(channel.times[:n:stride], channel.volts[:n:stride], pen=pg.mkPen(color, width=1.35),
                  name=f"CH{channel.number}" if legend else None, connect="finite")
        plot.setLabel("bottom", "Time", units="s")
        plot.setLabel("left", "Signal", units="V")

    def render_plots(self) -> None:
        if not self.channels:
            return
        self._clear_plots()
        if self.overlay.isChecked():
            plot = ScopePlot()
            plot.addLegend(offset=(12, 12), brush=pg.mkBrush(17, 25, 37, 210), labelTextColor="#DCE7F5")
            for channel in self.channels:
                self._plot_channel(plot, channel, True)
            self.plot_layout.addWidget(plot, 0, 0)
            self.plots.append(plot)
        else:
            columns = 1 if len(self.channels) == 1 else 2
            for index, channel in enumerate(self.channels):
                plot = ScopePlot()
                self._plot_channel(plot, channel)
                self.plot_layout.addWidget(plot, index // columns, index % columns)
                self.plots.append(plot)
        self.autoscale()

    def autoscale(self) -> None:
        for plot in self.plots:
            plot.enableAutoRange()

    def export_png(self) -> None:
        if not self.plots:
            return
        default = (self.path.with_suffix(".png") if self.path else Path("waveform.png"))
        filename, _ = QFileDialog.getSaveFileName(self, "Export plot", str(default), "PNG image (*.png)")
        if filename:
            pixmap = self.plot_host.grab()
            if not pixmap.save(filename, "PNG"):
                QMessageBox.warning(self, "Export failed", "The PNG image could not be saved.")

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QWidget { background: #0B111B; color: #DCE7F5; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QFrame#topbar { background: #0E1622; border-bottom: 1px solid #243247; }
            QFrame#topbar QWidget { background: transparent; }
            QLabel#brand { font-weight: 800; letter-spacing: 2px; color: #72C7FF; font-size: 14px; }
            QLabel#muted, QLabel#metaKey { color: #8291A5; }
            QLabel#eyebrow { color: #708199; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; }
            QLabel#metaTitle { font-size: 18px; font-weight: 750; }
            QLabel#cardTitle { font-weight: 800; letter-spacing: 1px; }
            QLabel#metaValue { color: #DCE7F5; }
            QLabel#dropIcon { color: #46BAFF; font-size: 54px; font-weight: 300; }
            QLabel#emptyTitle { font-size: 24px; font-weight: 750; }
            QFrame#dropPanel { border: 1px dashed #33445D; border-radius: 16px; margin: 80px; }
            QFrame#metaCard { background: #111925; border: 1px solid #202D40; border-radius: 8px; }
            QPushButton, QToolButton { background: #172337; border: 1px solid #2B3C55; border-radius: 6px; padding: 7px 13px; font-weight: 650; }
            QPushButton:hover, QToolButton:hover { background: #20314A; border-color: #4A86B3; }
            QToolButton:checked { color: #07101A; background: #62C4FF; border-color: #62C4FF; }
            QLineEdit, QSpinBox { background: #0C131F; border: 1px solid #29384D; border-radius: 6px; padding: 7px; }
            QSplitter::handle { background: #1E2A3B; width: 1px; }
            QScrollArea { background: transparent; }
            QScrollBar:vertical { background: #0C131F; width: 10px; }
            QScrollBar::handle:vertical { background: #34445C; border-radius: 5px; min-height: 24px; }
        """)


def main() -> int:
    pg.setConfigOptions(antialias=False, foreground="#9BAABD")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    if len(sys.argv) > 1:
        candidate = Path(sys.argv[1])
        if candidate.is_file():
            window.load_file(candidate)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
