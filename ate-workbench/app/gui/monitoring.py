"""Monitoring dashboard and CSV controls."""

from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QGridLayout,
    QSplitter,
    QFileDialog,
)

from app.models import ConnectionStatus
from app.gui.widgets import DeviceCard, TrendPanel
from app.config import ROOT

class MonitoringPage(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 12)
        title = QLabel("Monitoring Dashboard")
        title.setObjectName("Title")
        layout.addWidget(title)
        toolbar = QHBoxLayout()
        hint = QLabel("1 Hz target polling  ·  independent instrument workers  ·  output state from readback")
        hint.setObjectName("Muted")
        toolbar.addWidget(hint)
        toolbar.addStretch()
        start = QPushButton("Start All")
        start.clicked.connect(lambda: self.monitor_all(True))
        stop = QPushButton("Stop All")
        stop.clicked.connect(lambda: self.monitor_all(False))
        self.log_button = QPushButton("Start CSV Logging…")
        self.log_button.clicked.connect(self.toggle_csv)
        for button in (start, stop, self.log_button):
            toolbar.addWidget(button)
        layout.addLayout(toolbar)
        self.split = QSplitter(Qt.Orientation.Vertical)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 8, 8, 8)
        self.grid.setSpacing(14)
        self.scroll.setWidget(self.grid_host)
        self.split.addWidget(self.scroll)
        self.trends = TrendPanel(manager)
        self.trends.setMinimumHeight(230)
        self.split.addWidget(self.trends)
        self.split.setSizes([650, 270])
        layout.addWidget(self.split, 1)
        self.cards = {}
        manager.changed.connect(self.rebuild)
        manager.state_changed.connect(self.state_changed)
        manager.data.csv.changed.connect(self.csv_changed)
        self.rebuild()

    def rebuild(self):
        for card in self.cards.values():
            card.setParent(None)
            card.deleteLater()
        self.cards = {}
        for index, device_id in enumerate(self.manager.configs):
            card = DeviceCard(self.manager, device_id)
            self.cards[device_id] = card
            self.grid.addWidget(card, index//2, index%2)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)

    def state_changed(self, device_id, state):
        if device_id in self.cards:
            self.cards[device_id].refresh()

    def monitor_all(self, enabled):
        for device_id, state in self.manager.states.items():
            if state.status == ConnectionStatus.CONNECTED:
                self.manager.send(device_id, "monitor", enabled=enabled)

    def refresh(self):
        for card in self.cards.values():
            card.refresh()
        self.trends.refresh()
        if not self.manager.data.csv.enabled:
            self.log_button.setText("Start CSV Logging…")

    def toggle_csv(self):
        if self.manager.data.csv.enabled:
            self.manager.data.csv.stop()
            self.log_button.setText("Start CSV Logging…")
            return
        mode = "demo" if self.manager.demo else "real"
        path, _ = QFileDialog.getSaveFileName(self, "New CSV Log",
            str(ROOT/"data"/f"{mode}_{datetime.now():%Y%m%d_%H%M%S}.csv"), "CSV (*.csv)")
        if path:
            self.manager.data.csv.start(path)
            self.log_button.setText("Stop CSV Logging")

    def csv_changed(self, path):
        self.log_button.setToolTip(path)
