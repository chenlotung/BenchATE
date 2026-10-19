"""Extract and launch the Windows EXE with Python paths removed from its environment."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    archive = ROOT/"releases/ATEWorkbench-0.1.0-windows-x64.zip"
    destination = ROOT/"tmp"/f"portable validation 測試 {datetime.now():%H%M%S}"
    destination.mkdir(parents=True, exist_ok=False)
    with ZipFile(archive) as stream:
        for member in stream.infolist():
            if not (destination/member.filename).resolve().is_relative_to(destination.resolve()):
                raise ValueError("Unsafe ZIP member path")
        assert stream.testzip() is None
        stream.extractall(destination)
    bundle = destination/"ATEWorkbench"
    executable = bundle/"ATEWorkbench.exe"
    manifest = json.loads((bundle/"manifest.json").read_text(encoding="utf-8"))
    for name, checksum in manifest["files"].items():
        assert hashlib.sha256((bundle/name).read_bytes()).hexdigest() == checksum, name
    environment = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH"):
        environment.pop(name, None)
    environment["PATH"] = str(Path(environment.get("WINDIR", "C:/Windows"))/"System32")
    environment["QT_QPA_PLATFORM"] = "offscreen"
    report = ROOT/"docs/validation/portable_smoke.json"
    process = subprocess.run([str(executable), "--demo", "--soak-seconds", "20", "--report", str(report)],
        cwd=destination, env=environment, timeout=60, check=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["complete"] and result["elapsed_seconds"] >= 20
    assert not result["errors"] and result["screenshot_received"]
    assert result["shutdown_workers_released"] and result["shutdown_csv_released"]
    assert len(result["frame_counts"]) == 6 and min(result["frame_counts"].values()) >= 17
    result["portable_validation"] = {
        "archive_integrity": "passed", "manifest_checksums": "passed", "python_removed_from_path": True,
        "executable": str(executable), "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "working_directory": str(destination), "unicode_and_space_path": True, "exit_code": process.returncode,
        "external_python_required_by_executable": False, "separate_clean_machine_tested": False}
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
