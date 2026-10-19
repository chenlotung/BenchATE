from datetime import datetime
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QPushButton, QStackedWidget, QApplication)

from app.models import ConnectionStatus
from app.gui.connection import ConnectionPage
from app.gui.monitoring import MonitoringPage
from app.gui.themes import apply_theme


class MainWindow(QMainWindow):
    def __init__(self, manager, settings):
        super().__init__()
        self.manager, self.settings = manager, settings
        self.theme = settings["application"]["theme"]
        self.shutting_down = False
        self.allow_close = False
        self.last_error = ""
        self.backend_text = "DEMO simulated backend" if manager.demo else "VISA: not scanned"
        self.setWindowTitle("ATE Workbench" + (" — DEMO MODE" if manager.demo else " — Real Instrument Mode"))
        self.resize(1480, 980)
        self.setMinimumSize(1180, 760)
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        sidebar = QWidget()
        sidebar.setFixedWidth(215)
        left = QVBoxLayout(sidebar)
        left.setContentsMargins(14, 22, 14, 16)
        brand = QLabel("ATE\nWORKBENCH")
        brand.setStyleSheet("font-size: 19pt; font-weight: 700; padding: 8px;")
        left.addWidget(brand)
        self.banner = QLabel("DEMO MODE\nSynthetic data" if manager.demo else "REAL INSTRUMENTS\nOutput control enabled by approval")
        self.banner.setObjectName("ModeBanner")
        self.banner.setWordWrap(True)
        left.addWidget(self.banner)
        self.navigation = QListWidget()
        self.navigation.setObjectName("Navigation")
        self.navigation.addItems(["Instrument Connection", "Monitoring Dashboard"])
        left.addWidget(self.navigation, 1)
        theme = QPushButton("Switch Light / Dark")
        theme.clicked.connect(self.toggle_theme)
        left.addWidget(theme)
        hint = QLabel("V1.0 scope\nConnection · Monitor · Control")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        left.addWidget(hint)
        row.addWidget(sidebar)
        self.pages = QStackedWidget()
        self.connection = ConnectionPage(manager)
        self.monitoring = MonitoringPage(manager)
        self.pages.addWidget(self.connection)
        self.pages.addWidget(self.monitoring)
        row.addWidget(self.pages, 1)
        self.setCentralWidget(host)
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.summary = QLabel()
        self.statusBar().addWidget(self.summary, 1)
        self.clock_label = QLabel()
        self.statusBar().addPermanentWidget(self.clock_label)
        manager.error.connect(self.show_error)
        manager.resources_ready.connect(self.resources)
        self.timer = QTimer(self)
        self.timer.setInterval(settings["acquisition"]["gui_refresh_interval_ms"])
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.shutdown_timer = QTimer(self)
        self.shutdown_timer.setInterval(100)
        self.shutdown_timer.timeout.connect(self.check_shutdown)
        self.refresh()

    def resources(self, _, backend):
        self.backend_text = backend

    def show_error(self, message):
        self.last_error = message
        self.statusBar().setToolTip(message)
        self.refresh()

    def refresh(self):
        connected = sum(s.status == ConnectionStatus.CONNECTED for s in self.manager.states.values())
        monitoring = sum(s.monitoring for s in self.manager.states.values())
        mode = "DEMO MODE" if self.manager.demo else "Real Mode"
        self.summary.setText(f"{mode}  |  {self.backend_text[:70]}  |  Connected {connected}  |  Monitoring {monitoring}"
                             + (f"  |  {self.last_error[:75]}" if self.last_error else ""))
        self.clock_label.setText(datetime.now().astimezone().strftime("%Y-%m-%d  %H:%M:%S %Z"))
        self.monitoring.refresh()

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        apply_theme(QApplication.instance(), self.theme)
        dark = self.theme == "dark"
        for plot in self.monitoring.trends.plots.values():
            plot.setBackground("#101c2c" if dark else "#ffffff")

    def closeEvent(self, event):
        if self.allow_close:
            event.accept()
            return
        event.ignore()
        if self.shutting_down:
            return
        self.shutting_down = True
        self.centralWidget().setEnabled(False)
        self.summary.setText("Closing sessions and saving queued CSV records… Physical outputs are not modified.")
        self.timer.stop()
        self.manager.begin_shutdown()
        self.shutdown_timer.start()

    def check_shutdown(self):
        if self.manager.stopped():
            # Request logger drain without blocking the GUI on disk writes.
            if not hasattr(self, "logger_closing"):
                self.manager.data.csv.request_close()
                self.logger_closing = True
            if not self.manager.data.csv.thread.is_alive():
                self.shutdown_timer.stop()
                self.allow_close = True
                self.close()
