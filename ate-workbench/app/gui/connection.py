"""Device discovery, connection table and instrument preferences."""

import json
from dataclasses import replace
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QHeaderView,
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QDialogButtonBox,
    QPlainTextEdit,
    QInputDialog,
)

from app.models import ConnectionStatus
from app.drivers import DRIVERS

class DeviceTableModel(QAbstractTableModel):
    columns = ("Device Name", "Manufacturer", "Model", "Connection", "VISA Resource", "Identification",
               "Status", "Latency", "Last Check", "Driver")

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.ids = list(manager.configs)
        manager.changed.connect(self.refresh)
        manager.state_changed.connect(self.state_update)

    def refresh(self):
        self.beginResetModel()
        self.ids = list(self.manager.configs)
        self.endResetModel()

    def state_update(self, device_id, _):
        if device_id in self.ids:
            row = self.ids.index(device_id)
            self.dataChanged.emit(self.index(row, 0), self.index(row, len(self.columns)-1))

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.ids)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.columns[section]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        device_id = self.ids[index.row()]
        cfg, state = self.manager.configs[device_id], self.manager.states[device_id]
        if role == Qt.ItemDataRole.ToolTipRole:
            return state.error or self.manager.capabilities(device_id).notes
        if role == Qt.ItemDataRole.ForegroundRole and index.column() == 6:
            return QColor("#32c4b5" if state.status == ConnectionStatus.CONNECTED else "#e7ac61")
        if role == Qt.ItemDataRole.DisplayRole:
            return (cfg.name, cfg.manufacturer, cfg.model, cfg.connection, cfg.resource,
                    state.identification, state.status.value,
                    f"{state.latency_ms:.1f} ms" if state.latency_ms is not None else "—",
                    state.last_check or "—", cfg.driver + " (hardware unverified)")[index.column()]


class InstrumentDialog(QDialog):
    """Edit preferences only; identity, transport and channels come from discovery."""
    def __init__(self, manager, existing, parent=None):
        super().__init__(parent)
        self.existing = existing
        self.setWindowTitle("Instrument Settings")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.name = QLineEdit(existing.name)
        self.timeout = QSpinBox()
        self.timeout.setRange(100, 60000)
        self.timeout.setValue(existing.timeout_ms)
        self.timeout.setSuffix(" ms")
        self.poll = QSpinBox()
        self.poll.setRange(100, 60000)
        self.poll.setValue(existing.poll_interval_ms)
        self.poll.setSuffix(" ms")
        form.addRow("Detected Model", QLabel(existing.manufacturer + " " + existing.model))
        form.addRow("Detected Channels", QLabel(", ".join(existing.channels)))
        form.addRow("Device Name", self.name)
        form.addRow("Timeout", self.timeout)
        form.addRow("Polling Interval", self.poll)
        self.error = QLabel()
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def validate(self):
        try:
            if not self.name.text().strip():
                raise ValueError("Device name is required")
            self.result_config = replace(self.existing, name=self.name.text().strip(),
                timeout_ms=self.timeout.value(), poll_interval_ms=self.poll.value())
            self.accept()
        except ValueError as exc:
            self.error.setText(str(exc))


class ConnectionPage(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 20)
        title = QLabel("Instrument Connection")
        title.setObjectName("Title")
        layout.addWidget(title)
        description = QLabel("Scan USB devices and connect supported models. Optional LAN IPs: leave blank to skip.")
        description.setObjectName("Muted")
        layout.addWidget(description)
        addresses = QHBoxLayout()
        self.scope_ip = QLineEdit()
        self.scope_ip.setObjectName("scopeIp")
        self.scope_ip.setPlaceholderText("Optional IPv4 — blank skips Scope")
        self.ac_ip = QLineEdit()
        self.ac_ip.setObjectName("acSourceIp")
        self.ac_ip.setPlaceholderText("Optional IPv4 — blank skips AC Source")
        for label, widget in (("Scope IP (MSO44B)", self.scope_ip), ("AC Source IP (61512)", self.ac_ip)):
            addresses.addWidget(QLabel(label))
            addresses.addWidget(widget, 1)
        layout.addLayout(addresses)
        toolbar = QHBoxLayout()
        self.scan_button = QPushButton("Scan && Connect")
        self.scan_button.setObjectName("scanConnect")
        self.scan_button.clicked.connect(self.scan)
        toolbar.addWidget(self.scan_button)
        for text, action in (("Settings", self.edit), ("Remove", self.remove),
            ("Disconnect", lambda: self.send("disconnect")), ("Test Connection", lambda: self.send("test"))):
            button = QPushButton(text)
            button.clicked.connect(action)
            toolbar.addWidget(button)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self.resource_label = QLabel("Ready to scan. Only supported Chroma / Tektronix / RIGOL models are listed.")
        self.resource_label.setWordWrap(True)
        self.resource_label.setObjectName("Muted")
        layout.addWidget(self.resource_label)
        self.table = QTableView()
        self.model = DeviceTableModel(manager)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 145)
        self.table.setColumnWidth(2, 145)
        self.table.setColumnWidth(4, 230)
        self.table.setColumnWidth(5, 230)
        self.table.setColumnWidth(6, 155)
        self.table.setColumnWidth(9, 240)
        layout.addWidget(self.table, 1)
        row = QHBoxLayout()
        bench = QPushButton("Communication Benchmark…")
        bench.clicked.connect(self.benchmark)
        row.addWidget(bench)
        cancel = QPushButton("Cancel Benchmark")
        cancel.clicked.connect(lambda: self.send("benchmark_cancel"))
        row.addWidget(cancel)
        row.addWidget(QLabel("Read-only queries only • default 100 iterations • increases communication load"))
        row.addStretch()
        layout.addLayout(row)
        self.events = QPlainTextEdit()
        self.events.setReadOnly(True)
        self.events.setMaximumBlockCount(150)
        self.events.setMaximumHeight(135)
        layout.addWidget(self.events)
        manager.resources_ready.connect(self.resources)
        manager.scan_progress.connect(self.resource_label.setText)
        manager.scan_changed.connect(self.scan_changed)
        manager.completed.connect(self.completed)
        manager.error.connect(self.events.appendPlainText)

    def selected(self):
        index = self.table.currentIndex()
        if not index.isValid():
            self.events.appendPlainText("Select an instrument first.")
            return None
        return self.model.ids[index.row()]

    def send(self, kind):
        device_id = self.selected()
        if device_id:
            try:
                self.manager.send(device_id, kind)
            except Exception as exc:
                self.manager.error.emit(str(exc))

    def scan(self):
        self.manager.scan(scope_ip=self.scope_ip.text(), ac_ip=self.ac_ip.text())

    def scan_changed(self, scanning):
        self.scan_button.setEnabled(not scanning)
        self.scan_button.setText("Scanning…" if scanning else "Scan && Connect")
        self.scope_ip.setEnabled(not scanning)
        self.ac_ip.setEnabled(not scanning)

    def edit(self):
        device_id = self.selected()
        if not device_id:
            return
        if self.manager.states[device_id].status in (ConnectionStatus.CONNECTED, ConnectionStatus.CONNECTING):
            self.events.appendPlainText("Disconnect before editing configuration.")
            return
        dialog = InstrumentDialog(self.manager, self.manager.configs[device_id], self)
        if dialog.exec():
            cfg = dialog.result_config
            old = self.manager.configs[device_id]
            try:
                # Validate replacement using a temporary ID-independent check before removing.
                if any(c.device_id != device_id and c.resource.strip().upper() == cfg.resource.strip().upper()
                       for c in self.manager.configs.values()):
                    raise ValueError("Resource is already assigned")
                self.manager.remove(device_id)
                try:
                    self.manager.add(cfg)
                except Exception:
                    self.manager.add(old)
                    raise
            except Exception as exc:
                self.manager.error.emit(str(exc))

    def remove(self):
        device_id = self.selected()
        if device_id:
            try:
                self.manager.remove(device_id)
            except ValueError as exc:
                self.manager.error.emit(str(exc))

    def resources(self, resources, backend):
        self.resource_label.setText(f"Backend: {backend}\n{self.manager.scan_summary}")

    def benchmark(self):
        device_id = self.selected()
        if not device_id:
            return
        config = self.manager.configs[device_id]
        queries = DRIVERS[config.driver][0](config, lambda: None).safe_queries()
        label, ok = QInputDialog.getItem(self, "Benchmark query", "Safe read-only query", list(queries), 0, False)
        if not ok:
            return
        count, ok = QInputDialog.getInt(self, "Communication Benchmark", "Temporarily increases communication load.\nIterations:", 100, 1, 10000)
        if ok:
            self.manager.send(device_id, "benchmark", query=queries[label], count=count)

    def completed(self, device_id, kind, payload):
        if kind == "screenshot":
            return
        name = self.manager.configs[device_id].name if device_id in self.manager.configs else device_id
        result = payload.get("result")
        self.events.appendPlainText(f"{name} / {kind}: {json.dumps(result, ensure_ascii=False, default=str)}")
