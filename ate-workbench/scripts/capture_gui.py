"""Produce review screenshots with demo instruments only; no output enable commands."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.instruments import InstrumentManager
from app.models import ConnectionStatus
from app.drivers.mock import demo_configs
from app.gui.main_window import MainWindow
from app.gui.themes import apply_theme
from app.config import load_application


def main():
    app = QApplication([])
    apply_theme(app)
    manager = InstrumentManager(demo=True)
    manager.remember(demo_configs())
    window = MainWindow(manager, load_application())
    window.show()
    output = ROOT/"docs/validation"
    output.mkdir(parents=True, exist_ok=True)
    started = set()
    def ready(device_id, state):
        if state.status == ConnectionStatus.CONNECTED and device_id not in started:
            started.add(device_id)
            if manager.capabilities(device_id).measurements:
                manager.send(device_id, "monitor", enabled=True)
            if manager.capabilities(device_id).screenshot:
                manager.send(device_id, "screenshot")
    manager.state_changed.connect(ready)
    window.connection.scope_ip.setText("192.0.2.44")
    window.connection.ac_ip.setText("192.0.2.12")
    window.connection.scan_button.click()
    def connection():
        window.grab().save(str(output/"connection_dark.png"))
        window.navigation.setCurrentRow(1)
    def dashboard():
        window.refresh()
        window.grab().save(str(output/"dashboard_dark.png"))
        window.monitoring.scroll.verticalScrollBar().setValue(window.monitoring.scroll.verticalScrollBar().maximum())
    def scope():
        window.grab().save(str(output/"scope_preview.png"))
        window.toggle_theme()
        window.navigation.setCurrentRow(0)
    def light():
        window.grab().save(str(output/"connection_light.png"))
        window.close()
    QTimer.singleShot(1500, connection)
    QTimer.singleShot(2200, dashboard)
    QTimer.singleShot(2800, scope)
    QTimer.singleShot(3400, light)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
