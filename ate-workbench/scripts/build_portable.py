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
RELEASE_BUNDLE = ROOT/"build/release/ATEWorkbench"
USER_DOCUMENTS = {
    "README_PORTABLE.md": "README_PORTABLE.md",
    "docs/NI_VISA_INSTALLATION_zh-TW.md": "NI_VISA_INSTALLATION_zh-TW.md",
    "THIRD_PARTY_NOTICES.md": "THIRD_PARTY_NOTICES.md",
}
RELEASE_ROOT_NAMES = {"ATEWorkbench.exe", "_internal", "config", "data", "logs", "installers", "licenses",
                      "Start Demo.cmd", "Start Real.cmd", "manifest.json",
                      "README_PORTABLE.pdf", "NI_VISA_INSTALLATION_zh-TW.pdf", "THIRD_PARTY_NOTICES.pdf"}


def safe_generated_path(path):
    path = path.resolve()
    if not path.is_relative_to(ROOT) or path == ROOT:
        raise ValueError(f"Build destination outside project: {path}")
    return path


def make_zip(bundle, archive):
    unexpected = {p.name for p in bundle.iterdir()} - RELEASE_ROOT_NAMES
    if unexpected:
        raise ValueError(f"Non-release files in package: {sorted(unexpected)}")
    if {p.name for p in (bundle/"config").iterdir()} != {"application.json", "instruments.json"}:
        raise ValueError("Release must contain only default configuration files")
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
    runtime = safe_generated_path(dist/"ATEWorkbench")
    bundle = safe_generated_path(RELEASE_BUNDLE)
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
    elif not (runtime/"ATEWorkbench.exe").exists():
        raise SystemExit("Build the EXE before using --refresh-only")
    # Stage a clean consumer package. Never delete files from a previously run runtime folder.
    stage = bundle.resolve()
    if not stage.is_relative_to((ROOT/"build/release").resolve()) or stage.name != "ATEWorkbench":
        raise ValueError(f"Unsafe release staging directory: {stage}")
    if stage.exists():
        shutil.rmtree(stage)
    bundle.mkdir(parents=True)
    shutil.copy2(runtime/"ATEWorkbench.exe", bundle/"ATEWorkbench.exe")
    shutil.copytree(runtime/"_internal", bundle/"_internal")
    for folder in ("config", "data", "logs"):
        (bundle/folder).mkdir(exist_ok=True)
    for name in ("application.json", "instruments.json"):
        shutil.copy2(ROOT/"config"/name, bundle/"config"/name)
    for source, destination in USER_DOCUMENTS.items():
        text = (ROOT/source).read_text(encoding="utf-8")
        text = text.replace("docs/NI_VISA_INSTALLATION_zh-TW.md", "NI_VISA_INSTALLATION_zh-TW.md")
        (bundle/destination).write_text(text, encoding="utf-8")
    installers = bundle/"installers"
    installers.mkdir(exist_ok=True)
    shutil.copy2(VISA_INSTALLER, installers/VISA_INSTALLER.name)
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
    report_path = ROOT/"tmp/release_documents.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(
        json.dumps(document_report, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"application": "ATE Workbench", "version": "0.1.0", "platform": "Windows x64",
                "python": sys.version, "dependencies": versions,
                "visa_prerequisite": {"installer": f"installers/{VISA_INSTALLER.name}",
                    "install_target": "ni-visa_26.8", "online_installer": True,
                    "guide": "NI_VISA_INSTALLATION_zh-TW.pdf"},
                "documentation": {"format": "PDF", "quick_start": "README_PORTABLE.pdf",
                                  "markdown_included": False, "audience": "end_user"},
                "files": {}}
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
