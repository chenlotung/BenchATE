import ast
from pathlib import Path
import time

import pytest
from PySide6.QtWidgets import QApplication
from app.models import ConnectionStatus, OutputState
from app.gui.main_window import MainWindow
from app.config import load_application


def test_gui_start_page_switch_preserves_session_and_demo_label(manager, qtbot):
    window = MainWindow(manager, load_application())
    qtbot.addWidget(window)
    window.show()
    device_id = next(iter(manager.configs))
    manager.send(device_id, "connect")
    qtbot.waitUntil(lambda: manager.states[device_id].status == ConnectionStatus.CONNECTED)
    worker = manager.workers[device_id]
    driver = worker.driver
    for index in (1, 0, 1):
        window.navigation.setCurrentRow(index)
        QApplication.processEvents()
        assert manager.workers[device_id] is worker and worker.driver is driver
    assert "DEMO MODE" in window.banner.text()
    assert len(window.monitoring.cards) == 6
    assert window.pages.count() == 2
    window.toggle_theme()
    window.toggle_theme()
    window.close()
    qtbot.waitUntil(lambda: window.allow_close)


def test_duplicate_physical_resource_rejected(manager):
    from dataclasses import replace
    config = next(iter(manager.configs.values()))
    with pytest.raises(ValueError, match="Duplicate"):
        manager.add(replace(config, device_id="another"))


def test_gui_stale_data_keeps_value_and_disables_output(manager, qtbot):
    window = MainWindow(manager, load_application())
    qtbot.addWidget(window)
    device_id = next(iter(manager.configs))
    manager.send(device_id, "connect")
    qtbot.waitUntil(lambda: manager.states[device_id].status == ConnectionStatus.CONNECTED)
    manager.send(device_id, "monitor", enabled=True)
    qtbot.waitUntil(lambda: (device_id, "CH1") in manager.data.latest)
    manager.send(device_id, "fault", fault="timeout")
    qtbot.waitUntil(lambda: manager.states[device_id].status == ConnectionStatus.TIMEOUT, timeout=3000)
    card = window.monitoring.cards[device_id]
    card.refresh()
    assert "Stale" in card.values["voltage"].text()
    assert "Unknown" in card.output_state.text()
    assert not card.on.isEnabled()
    window.close()
    qtbot.waitUntil(lambda: window.allow_close)


def test_gui_modules_do_not_import_visa_or_issue_scpi():
    root = Path(__file__).resolve().parents[1]/"app/gui"
    for file in root.rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not name.name.startswith("pyvisa") for name in node.names)
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("pyvisa", "app.protocol"))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in ("query", "write", "read_raw", "open_resource")


def test_resource_aliases_canonicalize_to_one_physical_session():
    from app.instruments import canonical_resource
    assert canonical_resource("USB::0x1234::0x5678::SN::INSTR") == canonical_resource("USB0::0x1234::0x5678::SN::0::INSTR")
    assert canonical_resource("TCPIP::192.0.2.1::INSTR") == canonical_resource("TCPIP0::192.0.2.1::inst0::INSTR")


def test_windows_soak_memory_sampler_is_available():
    import sys
    from app.main import private_memory_bytes
    if sys.platform == "win32":
        assert private_memory_bytes() > 0
