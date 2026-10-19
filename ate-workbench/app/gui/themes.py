from pathlib import Path
import os
from PySide6.QtGui import QPalette, QColor, QFontDatabase


def apply_theme(app, theme="dark"):
    # Offscreen validation on Windows may not enumerate the system font database.
    if not QFontDatabase.families():
        fonts = Path(os.environ.get("WINDIR", "C:/Windows"))/"Fonts"
        for name in ("segoeui.ttf", "seguisb.ttf", "consola.ttf", "msjh.ttc"):
            if (fonts/name).exists():
                QFontDatabase.addApplicationFont(str(fonts/name))
    dark = theme == "dark"
    colors = {"bg": "#0d1522" if dark else "#edf1f7", "panel": "#162233" if dark else "#ffffff",
              "field": "#101c2c" if dark else "#f4f7fb", "fg": "#e3edf8" if dark else "#172b43",
              "muted": "#91a6c0" if dark else "#52667d", "border": "#2b3d54" if dark else "#cbd5e1"}
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in ((QPalette.ColorRole.Window, colors["bg"]), (QPalette.ColorRole.WindowText, colors["fg"]),
                        (QPalette.ColorRole.Base, colors["field"]), (QPalette.ColorRole.Text, colors["fg"]),
                        (QPalette.ColorRole.Button, colors["panel"]), (QPalette.ColorRole.ButtonText, colors["fg"]),
                        (QPalette.ColorRole.ToolTipBase, colors["panel"]), (QPalette.ColorRole.ToolTipText, colors["fg"]),
                        (QPalette.ColorRole.Highlight, "#168a88")):
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(colors["muted"]))
    app.setPalette(palette)
    app.setStyleSheet("""
        QWidget { font-family: 'Segoe UI'; font-size: 10pt; color: %(fg)s; }
        QMainWindow, QDialog { background: %(bg)s; }
        QFrame#Card { background: %(panel)s; border: 1px solid %(border)s; border-radius: 10px; }
        QLabel#Title { font-size: 23pt; font-weight: 600; }
        QLabel#CardTitle { font-size: 13pt; font-weight: 600; }
        QLabel#Muted { color: %(muted)s; }
        QLabel#ModeBanner { color: #fac154; font-weight: 700; padding: 6px; }
        QLabel#Number { font-family: 'Cascadia Mono', 'Consolas'; font-size: 19pt; font-weight: 600; }
        QPushButton { background: %(field)s; border: 1px solid %(border)s; border-radius: 5px; padding: 7px 11px; }
        QPushButton:hover { border-color: #32c4b5; }
        QPushButton:disabled { color: %(muted)s; background: %(panel)s; }
        QPushButton#Primary { background: #147f7b; color: white; }
        QPushButton#OutputOn { color: #fac154; border-color: #9c7d36; }
        QPushButton#OutputOff { color: #ff9298; border-color: #8b4d5c; }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: %(field)s; border: 1px solid %(border)s; border-radius: 4px; padding: 5px; }
        QTableView { background: %(panel)s; alternate-background-color: %(field)s; border: 1px solid %(border)s; gridline-color: %(border)s; }
        QHeaderView::section { background: %(field)s; color: %(muted)s; padding: 7px; border: 0; }
        QListWidget#Navigation { background: %(panel)s; border: none; padding: 8px; }
        QListWidget#Navigation::item { padding: 13px 6px; border-radius: 5px; }
        QListWidget#Navigation::item:selected { background: #147f7b; color: white; }
        QScrollArea { border: none; background: transparent; }
        QGroupBox { border: 1px solid %(border)s; border-radius: 6px; margin-top: 12px; padding: 12px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        QStatusBar { background: %(panel)s; color: %(muted)s; }
    """ % colors)
    return colors
