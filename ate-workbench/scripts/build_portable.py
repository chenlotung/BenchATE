"""Build a relocatable Windows x64 folder + ZIP. Run from the native Windows venv."""
import hashlib
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
VISA_INSTALLER = ROOT.parent/"ni-visa_26.8_online.exe"


def safe_generated_path(path):
    path = path.resolve()
    if not path.is_relative_to(ROOT) or path == ROOT:
        raise ValueError(f"Build destination outside project: {path}")
    return path


def make_zip(bundle, archive):
    if any(p.suffix.lower() == ".md" for p in bundle.rglob("*")):
        raise ValueError("Release must contain rendered PDFs, not Markdown files")
    for name in ("NI_VISA_INSTALLATION_zh-TW.txt", "README_PORTABLE.txt"):
        if (bundle/name).exists():
            raise ValueError(f"Legacy text documentation must not be released: {name}")
    with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=6) as stream:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                stream.write(path, path.relative_to(bundle.parent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-only", action="store_true", help="Refresh docs/manifest/ZIP without rebuilding the EXE")
    args = parser.parse_args()
    try:
        from release_documents import convert_release_documents
    except ImportError as exc:
        raise SystemExit('PDF build dependencies missing; install with pip install -e ".[build]"') from exc
    if sys.platform != "win32":
        raise SystemExit("Build on native Windows Python x64")
    if not VISA_INSTALLER.is_file():
        raise SystemExit(f"Required NI-VISA online installer missing: {VISA_INSTALLER}")
    dist = safe_generated_path(ROOT/"dist")
    build = safe_generated_path(ROOT/"build")
    bundle = safe_generated_path(dist/"ATEWorkbench")
    releases = safe_generated_path(ROOT/"releases")
    releases.mkdir(exist_ok=True)
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", "ATEWorkbench", "--distpath", str(dist), "--workpath", str(build),
        "--specpath", str(build), "--collect-submodules", "pyvisa.resources",
        "--collect-submodules", "pyvisa.ctwrapper", "--exclude-module", "pytest",
        "--exclude-module", "reportlab", "--exclude-module", "markdown_it",
        "--exclude-module", "pypdf", "--exclude-module", "pyvisa.testsuite", "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtWebEngineWidgets", str(ROOT/"main.py")]
    if not args.refresh_only:
        environment = dict(os.environ)
        windows = Path(environment.get("WINDIR", "C:/Windows"))
        # External tools (e.g. Poppler) can ship an incompatible icuuc.dll on PATH.
        # Build using native Python and Windows DLL search paths only.
        environment["PATH"] = os.pathsep.join(map(str, [Path(sys.executable).parent,
            Path(sys.base_prefix), Path(sys.base_prefix)/"DLLs", windows/"System32", windows]))
        environment.pop("PYTHONPATH", None)
        environment["PYINSTALLER_CONFIG_DIR"] = str(safe_generated_path(ROOT/"tmp/pyinstaller-cache"))
        subprocess.run(command, cwd=ROOT, env=environment, check=True)
    elif not (bundle/"ATEWorkbench.exe").exists():
        raise SystemExit("Build the EXE before using --refresh-only")
    for folder in ("config", "data", "logs", "docs"):
        (bundle/folder).mkdir(exist_ok=True)
    for name in ("application.json", "instruments.json"):
        shutil.copy2(ROOT/"config"/name, bundle/"config"/name)
    shutil.copytree(ROOT/"docs", bundle/"docs", dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("demo_1h.json", "demo_1h.png", "REQUIREMENTS_V1.md", "__pycache__"))
    originals = bundle/"docs/instruments/originals"
    originals.mkdir(parents=True, exist_ok=True)
    for manual in (ROOT.parent/"datasheet").glob("*.pdf"):
        shutil.copy2(manual, originals/manual.name)
    for path in (bundle/"docs").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        text = text.replace("../../../../datasheet/", "../originals/")
        text = text.replace("../../datasheet/", "instruments/originals/")
        path.write_text(text, encoding="utf-8")
    for name in ("README.md", "README_PORTABLE.md", "THIRD_PARTY_NOTICES.md", "requirements-tested.txt"):
        if (ROOT/name).exists():
            shutil.copy2(ROOT/name, bundle/name)
    installers = bundle/"installers"
    installers.mkdir(exist_ok=True)
    shutil.copy2(VISA_INSTALLER, installers/VISA_INSTALLER.name)
    shutil.copy2(bundle/"docs/NI_VISA_INSTALLATION_zh-TW.md", bundle/"NI_VISA_INSTALLATION_zh-TW.md")
    for name in ("NI_VISA_INSTALLATION_zh-TW.txt", "README_PORTABLE.txt"):
        legacy = safe_generated_path(bundle/name)
        legacy.unlink(missing_ok=True)
    # Retain the license files shipped with each dependency.
    licenses = bundle/"licenses"
    licenses.mkdir(exist_ok=True)
    packages = ("PySide6", "PySide6_Essentials", "PySide6_Addons", "shiboken6", "pyqtgraph", "numpy", "PyVISA", "PyInstaller")
    versions = {}
    for package in packages:
        distribution = importlib.metadata.distribution(package)
        versions[package] = distribution.version
        for item in distribution.files or ():
            if any(word in item.name.lower() for word in ("license", "copying", "copyright")):
                source = Path(distribution.locate_file(item))
                if source.is_file():
                    destination = licenses/package/Path(*item.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    (bundle/"Start Demo.cmd").write_text('@echo off\ncd /d "%~dp0"\nstart "" "%~dp0ATEWorkbench.exe" --demo\n', encoding="ascii")
    (bundle/"Start Real.cmd").write_text('@echo off\ncd /d "%~dp0"\nstart "" "%~dp0ATEWorkbench.exe"\n', encoding="ascii")
    documents = convert_release_documents(bundle)
    document_report = {"format": "PDF", "markdown_files_remaining": 0,
                       "legacy_text_copies_removed": True, "converted": documents}
    (bundle/"docs/validation/release_documents.json").write_text(
        json.dumps(document_report, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"application": "ATE Workbench", "version": "0.1.0", "platform": "Windows x64",
                "python": sys.version, "dependencies": versions, "one_hour_test": "Skipped at user request",
                "visa_prerequisite": {"installer": f"installers/{VISA_INSTALLER.name}",
                    "install_target": "ni-visa_26.8", "online_installer": True,
                    "guide": "NI_VISA_INSTALLATION_zh-TW.pdf", "system_installation_tested": False},
                "documentation": {"format": "PDF", "quick_start": "README_PORTABLE.pdf",
                                  "markdown_included": False},
                "hardware_verified": False, "files": {}}
    code = hashlib.sha256()
    for source in sorted((ROOT/"app").rglob("*.py")):
        code.update(source.relative_to(ROOT).as_posix().encode())
        code.update(source.read_bytes())
    manifest["app_source_sha256"] = code.hexdigest()
    for path in sorted(bundle.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            manifest["files"][path.relative_to(bundle).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (bundle/"manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    archive = releases/"ATEWorkbench-0.1.0-windows-x64.zip"
    make_zip(bundle, archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(json.dumps({"bundle": str(bundle), "zip": str(archive), "bytes": archive.stat().st_size, "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
