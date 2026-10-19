"""Application settings, device preferences and rotating logs."""

import json
import os
import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

from app.models import DeviceConfig

ROOT = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[1])


def load_application(root=ROOT):
    return json.loads((Path(root)/"config/application.json").read_text(encoding="utf-8"))


def load_devices(path):
    path = Path(path)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Instrument config must be a JSON list")
    return [DeviceConfig(**item) for item in payload]


def save_devices(path, configs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps([c.to_dict() for c in configs], indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def configure_logging(path, command_logging=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s"))
    logging.basicConfig(level=logging.DEBUG if command_logging else logging.INFO, handlers=[handler], force=True)
    logging.getLogger("pyvisa").setLevel(logging.WARNING)
