"""Instrument control cards and measurement trend charts."""

import time
import math
import numpy as np
import pyqtgraph as pg
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QCheckBox,
    QMessageBox,
    QWidget,
)

from app.models import ConnectionStatus, OutputState


class LimitsDialog(QDialog):
    def __init__(self, config, capabilities, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Approve Software Safety Limits")
        layout = QVBoxLayout(self)
        info = QLabel("Review limits for this instrument and test setup.\nApproval applies only to the current connection.")
        info.setWordWrap(True)
        layout.addWidget(info)
        form = QFormLayout()
        self.inputs = {}
        for name, parameter in capabilities.setpoints.items():
            row = QHBoxLayout()
            lo, hi = QDoubleSpinBox(), QDoubleSpinBox()
            for box in (lo, hi):
                box.setDecimals(max(parameter.decimals, 4))
                box.setRange(parameter.minimum, parameter.maximum)
                box.setSingleStep(parameter.resolution)
                box.setSuffix(f" {parameter.unit}")
            # Start at a zero-width limit if none was supplied; never default to hardware maxima.
            bounds = config.safety_limits.get(name, [parameter.minimum, parameter.minimum])
            lo.setValue(bounds[0])
            hi.setValue(bounds[1])
            row.addWidget(lo)
            row.addWidget(QLabel("to"))
            row.addWidget(hi)
            form.addRow(name.title(), row)
            self.inputs[name] = (lo, hi)
        layout.addLayout(form)
        self.approve = QCheckBox("I approve these limits for the connected test setup")
        layout.addWidget(self.approve)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.approve.toggled.connect(buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def limits(self):
        return {key: [lo.value(), hi.value()] for key, (lo, hi) in self.inputs.items()}


class DeviceCard(QFrame):
    def __init__(self, manager, device_id, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.manager, self.device_id = manager, device_id
        self.config = manager.configs[device_id]
        self.capabilities = manager.capabilities(device_id)
        self.last_capture = None
        self.last_frame_time = None
        self.readbacks = {}
        self.remote_override = None
        self.preview_pixmap = None
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 14, 17, 16)
        header = QHBoxLayout()
        title = QLabel(self.config.name)
        title.setObjectName("CardTitle")
        header.addWidget(title)
        header.addStretch()
        self.status = QLabel("Disconnected")
        header.addWidget(self.status)
        layout.addLayout(header)
        model = QLabel(f"{self.config.manufacturer}  ·  {self.config.model}")
        model.setObjectName("Muted")
        layout.addWidget(model)
        resource = QLabel(self.config.resource)
        resource.setObjectName("Muted")
        resource.setWordWrap(True)
        layout.addWidget(resource)
        self.identification = QLabel("Identity: not checked")
        self.identification.setWordWrap(True)
        self.identification.setObjectName("Muted")
        layout.addWidget(self.identification)
        channel_row = QHBoxLayout()
        self.channel = QComboBox()
        self.channel.addItems(self.config.channels)
        if self.config.driver == "chroma_6312a":
            self.channel.setToolTip("CH1 = slot 1 / 63106A; CH3 = slot 2 / 63106A")
        channel_row.addWidget(QLabel("Channel / phase"))
        channel_row.addWidget(self.channel)
        self.monitor = QPushButton("Start Monitoring")
        self.monitor.clicked.connect(self.toggle_monitor)
        channel_row.addWidget(self.monitor)
        layout.addLayout(channel_row)
        self.mode_info = QLabel("Remote: Unknown  ·  Mode: Unknown")
        layout.addWidget(self.mode_info)
        measurements = QGridLayout()
        self.values = {}
        for index, (name, unit) in enumerate(self.capabilities.measurements.items()):
            value = QLabel("—")
            value.setObjectName("Number")
            name_label = QLabel(name.replace("_", " ").title())
            name_label.setObjectName("Muted")
            measurements.addWidget(name_label, index // 3 * 2, index % 3)
            measurements.addWidget(value, index // 3 * 2 + 1, index % 3)
            self.values[name] = value
        layout.addLayout(measurements)
        self.timing = QLabel("Last update: —  ·  SCPI polling: — Hz")
        self.timing.setObjectName("Muted")
        self.timing.setWordWrap(True)
        layout.addWidget(self.timing)
        self.freshness = QLabel("Hardware sample rate: unverified")
        self.freshness.setWordWrap(True)
        self.freshness.setObjectName("Muted")
        layout.addWidget(self.freshness)
        self.inputs, self.control_widgets = {}, []
        if self.capabilities.setpoints:
            form = QGridLayout()
            form.addWidget(QLabel("Desired setpoint (not yet applied)"), 0, 0, 1, 2)
            for row, (name, p) in enumerate(self.capabilities.setpoints.items(), 1):
                box = QDoubleSpinBox()
                box.setRange(p.minimum, p.maximum)
                box.setDecimals(p.decimals)
                box.setSingleStep(p.resolution)
                box.setSuffix(f" {p.unit}")
                box.setValue(p.minimum)
                label = "Current (L1 + L2)" if name == "current" else name.title()
                form.addWidget(QLabel(label), row, 0)
                form.addWidget(box, row, 1)
                self.inputs[name] = box
            self.mode = QComboBox()
            self.mode.addItems(self.capabilities.modes)
            form.addWidget(QLabel("Desired mode"), len(self.inputs)+1, 0)
            form.addWidget(self.mode, len(self.inputs)+1, 1)
            layout.addLayout(form)
            row = QHBoxLayout()
            self.limit_button = QPushButton("Review Safety Limits…")
            self.limit_button.clicked.connect(self.approve_limits)
            row.addWidget(self.limit_button)
            self.apply_button = QPushButton("Apply Settings")
            self.apply_button.clicked.connect(self.apply_settings)
            row.addWidget(self.apply_button)
            layout.addLayout(row)
            self.control_widgets.extend([self.apply_button, self.limit_button, self.mode, *self.inputs.values()])
        self.readback = QLabel("Applied / readback: —")
        self.readback.setWordWrap(True)
        if self.capabilities.readback:
            layout.addWidget(self.readback)
        self.output_state = QLabel("Actual Output: Unknown")
        if self.capabilities.output:
            row = QHBoxLayout()
            self.on = QPushButton("Output ON" if self.config.driver == "chroma_61512" else "Load ON")
            self.on.setObjectName("OutputOn")
            self.off = QPushButton("Output OFF" if self.config.driver == "chroma_61512" else "Load OFF")
            self.off.setObjectName("OutputOff")
            self.on.clicked.connect(self.enable_output)
            self.off.clicked.connect(lambda: self.send("output_off"))
            row.addWidget(self.on)
            row.addWidget(self.off)
            row.addWidget(self.output_state)
            layout.addLayout(row)
            self.control_widgets.extend([self.on, self.off])
        remote_row = QHBoxLayout()
        self.remote_label = QLabel("Remote: Unknown")
        remote_row.addWidget(self.remote_label)
        self.remote_buttons = []
        for text, kind in (("Remote", "remote"), ("Return Local", "local")):
            button = QPushButton(text)
            button.setEnabled(self.capabilities.remote)
            button.setToolTip(self.capabilities.notes)
            button.clicked.connect(lambda checked=False, k=kind: self.send(k))
            self.remote_buttons.append(button)
            remote_row.addWidget(button)
        layout.addLayout(remote_row)
        if self.capabilities.screenshot:
            self.capture = QPushButton("Capture Screenshot")
            self.capture.setObjectName("Primary")
            self.capture.clicked.connect(lambda: self.send("screenshot"))
            layout.addWidget(self.capture)
            self.control_widgets.append(self.capture)
            self.preview = QLabel("No capture yet\nManual capture preserves current trigger and acquisition settings.")
            self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview.setWordWrap(True)
            self.preview.setMinimumHeight(180)
            layout.addWidget(self.preview)
            self.capture_time = QLabel("Last capture: —")
            layout.addWidget(self.capture_time)
        if manager.demo:
            row = QHBoxLayout()
            for text, fault in (("Simulate Timeout", "timeout"), ("Simulate Disconnect", "disconnect")):
                button = QPushButton(text)
                button.clicked.connect(lambda checked=False, f=fault: self.send("fault", fault=f))
                row.addWidget(button)
            layout.addLayout(row)
        self.message = QLabel(self.capabilities.notes)
        self.message.setObjectName("Muted")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        layout.addStretch()
        self.channel.currentTextChanged.connect(self.channel_changed)
        manager.completed.connect(self.completed)
        self.refresh()

    def send(self, kind, **payload):
        try:
            self.manager.send(self.device_id, kind, self.channel.currentText(), **payload)
        except Exception as exc:
            self.manager.error.emit(str(exc))

    def toggle_monitor(self):
        self.send("monitor", enabled=not self.manager.states[self.device_id].monitoring)

    def approve_limits(self):
        dialog = LimitsDialog(self.config, self.capabilities, self)
        if dialog.exec():
            self.send("limits", limits=dialog.limits())

    def apply_settings(self):
        active = self.current_output()
        confirmed_live = False
        if active != OutputState.OFF:
            confirmed_live = QMessageBox.question(self, "Change Active Output",
                "Output is ON or its state is unknown. Applying settings may change the physical output.\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
            if not confirmed_live:
                return
        self.send("apply", values={k: v.value() for k, v in self.inputs.items()},
                  mode=self.mode.currentText(), confirmed_live=confirmed_live)

    def enable_output(self):
        if QMessageBox.question(self, "Enable Physical Output",
                f"Enable {self.config.name} / {self.channel.currentText()} using its readback setpoints?\n"
                "Check the test setup and approved software limits. Unapplied input values will not be used.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.send("output_on", confirmed=True)

    def current_output(self):
        state = self.manager.states[self.device_id]
        if state.status != ConnectionStatus.CONNECTED:
            return OutputState.UNKNOWN
        checked = state.output_checked.get(self.channel.currentText(), 0)
        if time.monotonic()-checked > max(3, 3*self.config.poll_interval_ms/1000):
            return OutputState.UNKNOWN
        return state.output_states.get(self.channel.currentText(), OutputState.UNKNOWN)

    def channel_changed(self):
        self.last_frame_time = None
        self.refresh()

    def refresh(self):
        state = self.manager.states[self.device_id]
        connected = state.status == ConnectionStatus.CONNECTED
        self.status.setText(state.status.value)
        self.status.setStyleSheet(f"color: {'#32c4b5' if connected else '#e7ac61'}")
        self.identification.setText("Identity: " + (state.identification or "not checked"))
        self.monitor.setEnabled(connected and bool(self.capabilities.measurements))
        self.monitor.setText("Stop Monitoring" if state.monitoring else "Start Monitoring")
        for widget in self.control_widgets:
            widget.setEnabled(connected)
        for button in self.remote_buttons:
            button.setEnabled(connected and self.capabilities.remote)
        if self.capabilities.output:
            self.on.setEnabled(connected and state.limits_approved and not state.control_fault)
        if self.capabilities.setpoints:
            self.apply_button.setEnabled(connected and state.limits_approved)
            self.limit_button.setText("Safety Limits Approved" if state.limits_approved else "Review Safety Limits…")
        self.output_state.setText(f"Actual Output: {self.current_output().value}")
        frame = self.manager.data.latest.get((self.device_id, self.channel.currentText()))
        stale = not connected or (frame is not None and time.monotonic()-frame.monotonic_time > max(3, 3*self.config.poll_interval_ms/1000))
        if frame:
            fallback = self.manager.data.last_valid.get((self.device_id, frame.channel))
            for name, label in self.values.items():
                measurement = frame.measurements.get(name)
                invalid = measurement is not None and measurement.validity != "valid"
                shown = fallback.measurements.get(name) if invalid and fallback else measurement
                if shown is not None and shown.value is not None:
                    suffix = " · Stale" if stale else " · Invalid (last valid)" if invalid else ""
                    label.setText(f"{shown.value:.5g} {shown.unit}{suffix}")
                    label.setStyleSheet("color: #e7ac61; font-size: 15pt" if stale or invalid else "")
                    label.setToolTip(f"Timestamp: {(fallback.timestamp if invalid and fallback else frame.timestamp).isoformat()}\n"
                                     f"Validity: {measurement.validity if measurement else 'unavailable'}")
                else:
                    label.setText("—" if measurement is None else f"Invalid ({measurement.validity})")
                    label.setStyleSheet("font-size: 12pt")
            if self.last_frame_time != frame.monotonic_time:
                self.readbacks[frame.channel] = frame.setpoints
                self.last_frame_time = frame.monotonic_time
            remote = "Unknown" if stale else frame.remote
            if self.remote_override and self.remote_override[0] > frame.monotonic_time and connected:
                remote = self.remote_override[1]
            self.mode_info.setText(f"Remote: {remote}  ·  Mode: {frame.mode}")
            self.timing.setText(f"Last update: {frame.timestamp.strftime('%H:%M:%S')} {'(Stale)' if stale else ''}  ·  "
                                f"SCPI polling: {state.actual_rate:.2f} Hz  ·  Overruns: {state.overruns}")
            self.freshness.setText(frame.freshness)
            self.remote_label.setText(f"Remote: {remote}")
        else:
            for label in self.values.values():
                label.setText("—")
            self.timing.setText("Last update: —  ·  SCPI polling: — Hz")
        actual = self.readbacks.get(self.channel.currentText(), {})
        self.readback.setText("Applied / readback: " + (", ".join(
            f"{k} = {v:g} {self.capabilities.setpoints.get(k, self.capabilities.setpoints.get('current')).unit}"
            for k, v in actual.items()) or "—")
                             + (" (Unverified / Stale)" if stale and actual else ""))
        self.message.setText(state.error or self.capabilities.notes)

    def completed(self, device_id, kind, payload):
        if device_id != self.device_id:
            return
        result = payload.get("result")
        if kind == "apply":
            self.readbacks[payload["channel"]] = result
            frame = self.manager.data.latest.get((device_id, payload["channel"]))
            self.last_frame_time = frame.monotonic_time if frame else None
        elif kind in ("remote", "local"):
            self.remote_override = (time.monotonic(), result)
            self.remote_label.setText(f"Remote: {result}")
        elif kind == "screenshot":
            image = QImage.fromData(result, "PNG")
            if image.isNull():
                self.manager.error.emit("Screenshot could not be decoded; preview not updated")
                return
            self.preview_pixmap = QPixmap.fromImage(image)
            self.update_preview()
            self.last_capture = datetime.now().astimezone()
            self.capture_time.setText(f"Last capture: {self.last_capture.isoformat(timespec='seconds')}")
        self.refresh()

    def update_preview(self):
        if self.preview_pixmap:
            self.preview.setPixmap(self.preview_pixmap.scaled(self.preview.width(), 220,
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview()


class TrendPanel(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Measurement Trends"))
        self.device = QComboBox()
        self.device.setMinimumWidth(140)
        self.channel = QComboBox()
        self.window = QComboBox()
        self.window.addItem("Last 60 seconds", 60)
        self.window.addItem("Last 10 minutes", 600)
        self.pause = QCheckBox("Pause display")
        self.enabled = QCheckBox("Show curves")
        self.enabled.setChecked(True)
        auto = QPushButton("Auto Range")
        auto.clicked.connect(self.auto_range)
        for widget in (self.device, self.channel, self.window, self.enabled, self.pause, auto):
            toolbar.addWidget(widget)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self.metric_selector = QComboBox()
        toolbar.insertWidget(3, self.metric_selector)
        row = QHBoxLayout()
        self.plots, self.curves = {}, {}
        for name, unit, color in (("voltage", "V", "#37d1ba"), ("current", "A", "#fac154"), ("power", "W", "#83adff")):
            axis = pg.DateAxisItem(orientation="bottom")
            plot = pg.PlotWidget(axisItems={"bottom": axis}, background="#101c2c")
            plot.setTitle(name.title(), color="#b3c6df", size="10pt")
            plot.setLabel("left", unit)
            plot.showGrid(x=True, y=True, alpha=.18)
            self.curves[name] = plot.plot(pen=pg.mkPen(color, width=2), connect="finite")
            self.plots[name] = plot
            row.addWidget(plot)
        layout.addLayout(row)
        self.device.currentIndexChanged.connect(self.device_changed)
        self.metric_selector.currentIndexChanged.connect(self.update_visibility)
        manager.changed.connect(self.refresh_devices)
        self.refresh_devices()

    def refresh_devices(self):
        selected = self.device.currentData()
        self.device.blockSignals(True)
        self.device.clear()
        for device_id, config in self.manager.configs.items():
            if self.manager.capabilities(device_id).measurements:
                self.device.addItem(config.name, device_id)
        if selected:
            self.device.setCurrentIndex(max(0, self.device.findData(selected)))
        self.device.blockSignals(False)
        self.device_changed()

    def device_changed(self):
        device_id = self.device.currentData()
        self.channel.clear()
        self.metric_selector.clear()
        if device_id:
            self.channel.addItems(self.manager.configs[device_id].channels)
            self.metric_selector.addItem("Voltage / Current / Power", "all")
            for name, unit in self.manager.capabilities(device_id).measurements.items():
                if unit in ("V", "A", "W"):
                    self.metric_selector.addItem(f"{name.title()} ({unit})", name)
        for curve in self.curves.values():
            curve.setData([], [])
        self.update_visibility()

    def update_visibility(self):
        selected = self.metric_selector.currentData()
        for name, plot in self.plots.items():
            plot.setVisible(selected in ("all", name))

    def refresh(self):
        if self.pause.isChecked():
            return
        device_id = self.device.currentData()
        frames = self.manager.data.buffers.get((device_id, self.channel.currentText()), ())
        window = self.window.currentData() or 60
        now = time.time()
        for name, curve in self.curves.items():
            if not self.enabled.isChecked():
                curve.setData([], [])
                continue
            points = [(frame.timestamp.timestamp(),
                       frame.measurements[name].value if name in frame.measurements and frame.measurements[name].validity == "valid" else math.nan)
                      for frame in frames if frame.timestamp.timestamp() >= now-window]
            if points:
                curve.setData(np.asarray([p[0] for p in points]), np.asarray([p[1] for p in points], dtype=float))
            else:
                curve.setData([], [])
            self.plots[name].setXRange(now-window, now, padding=0)

    def auto_range(self):
        for plot in self.plots.values():
            plot.enableAutoRange(axis="y")
