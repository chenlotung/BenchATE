"""Check consumer-only packaging, PDF content, links and archive integrity."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

from markdown_it import MarkdownIt
from pypdf import PdfReader

from release_documents import release_text
from build_portable import RELEASE_BUNDLE, RELEASE_ROOT_NAMES, USER_DOCUMENTS

ROOT = Path(__file__).resolve().parents[1]


def compact(text):
    return re.sub(r"\s+", "", text)


def body_text(page):
    text = page.extract_text()
    # Page furniture is emitted first in the PDF content stream; omit only that
    # exact prefix so a paragraph crossing pages can be checked continuously.
    return re.sub(r"^ATE WORKBENCH\s+/\s+DOCUMENTATION\n[^\n]+\n\d+\n", "", text, count=1)


def validate(bundle):
    bundle = Path(bundle).resolve()
    assert bundle == RELEASE_BUNDLE.resolve()
    assert {p.name for p in bundle.iterdir()} <= RELEASE_ROOT_NAMES
    assert not any((bundle/name).exists() for name in ("docs", "app", "scripts", "tests", "README.pdf", "requirements-tested.txt"))
    assert not list(bundle.rglob("*.md")), "Markdown remained in release"
    assert not (bundle/"NI_VISA_INSTALLATION_zh-TW.txt").exists()
    assert not (bundle/"README_PORTABLE.txt").exists()
    parser = MarkdownIt("commonmark", {"html": False}).enable("table")
    checked_links = 0
    page_counts = {}
    for source_name, destination in USER_DOCUMENTS.items():
        source = ROOT/source_name
        target = bundle/Path(destination).with_suffix(".pdf")
        assert target.exists(), target
        reader = PdfReader(target)
        text = compact("\n".join(body_text(p) for p in reader.pages))
        markdown = source.read_text(encoding="utf-8-sig")
        markdown = markdown.replace("docs/NI_VISA_INSTALLATION_zh-TW.md", "NI_VISA_INSTALLATION_zh-TW.md")
        for token in parser.parse(release_text(markdown)):
            if token.type == "inline":
                for child in token.children or []:
                    if child.type in ("text", "code_inline") and compact(child.content):
                        assert compact(child.content) in text, (target, child.content)
            elif token.type in ("fence", "code_block"):
                assert compact(token.content) in text, (target, "code block")
        for page in reader.pages:
            for reference in page.get("/Annots", []):
                uri = reference.get_object().get("/A", {}).get("/URI", "")
                if not uri:
                    continue
                parts = urlsplit(uri)
                if not parts.scheme and parts.path:
                    linked = (target.parent/unquote(parts.path)).resolve()
                    assert linked.is_relative_to(bundle) and linked.is_file(), (target, uri)
                    assert linked.suffix.lower() != ".md", (target, uri)
                    checked_links += 1
        page_counts[target.relative_to(bundle).as_posix()] = len(reader.pages)
    # Vendor Markdown licenses are readable PDFs too; inspect every generated PDF.
    report = json.loads((ROOT/"tmp/release_documents.json").read_text(encoding="utf-8"))
    for record in report["converted"]:
        path = bundle/record["pdf"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["pdf_sha256"], path
    for path in bundle.rglob("*.pdf"):
        reader = PdfReader(path)
        assert reader.pages and all(body_text(page).strip() for page in reader.pages), path
        page_counts[path.relative_to(bundle).as_posix()] = len(reader.pages)
    return {"passed": True, "documentation_profile": "end_user", "user_documents_checked": len(USER_DOCUMENTS),
            "generated_pdfs_checked": len(page_counts), "local_pdf_links_checked": checked_links,
            "developer_documents_excluded": True, "page_counts": page_counts}


def render(bundle, poppler, proof_dir):
    from PIL import Image, ImageDraw
    proof_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(bundle.rglob("*.pdf"))
    def one(item):
        number, path = item
        prefix = proof_dir/f"{number:02d}-{path.stem}"
        for old in proof_dir.glob(prefix.name+"-*.png"):
            assert old.resolve().is_relative_to(proof_dir.resolve())
            old.unlink()
        subprocess.run([str(poppler), "-r", "95", "-png", str(path), str(prefix)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return [(png, path.relative_to(bundle).as_posix()) for png in sorted(proof_dir.glob(prefix.name+"-*.png"))]
    with ThreadPoolExecutor(max_workers=4) as executor:
        pages = [page for group in executor.map(one, enumerate(paths)) for page in group]
    sheets = []
    for start in range(0, len(pages), 12):
        group = pages[start:start+12]
        sheet = Image.new("RGB", (1280, 4*480), "#dce2e8")
        draw = ImageDraw.Draw(sheet)
        for index, (path, title) in enumerate(group):
            with Image.open(path) as original:
                thumb = original.copy()
                thumb.thumbnail((305, 440))
                x, y = (index % 4)*320, (index//4)*480
                sheet.paste(thumb, (x+(320-thumb.width)//2, y+22))
                draw.text((x+6, y+5), title[-48:], fill="black")
        path = proof_dir/f"contact-{start//12+1:02d}.png"
        sheet.save(path)
        sheets.append(str(path))
    return {"rendered_pages": len(pages), "contact_sheets": sheets}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=RELEASE_BUNDLE)
    parser.add_argument("--poppler", type=Path)
    args = parser.parse_args()
    result = validate(args.bundle)
    archive = ROOT/"releases/ATEWorkbench-0.1.0-windows-x64.zip"
    with ZipFile(archive) as stream:
        assert stream.testzip() is None
        manifest = json.loads(stream.read("ATEWorkbench/manifest.json"))
        assert not any(name.lower().endswith(".md") for name in stream.namelist())
        for name, checksum in manifest["files"].items():
            assert hashlib.sha256(stream.read("ATEWorkbench/"+name)).hexdigest() == checksum, name
    result["zip_integrity_and_manifest"] = "passed"
    if args.poppler:
        result.update(render(args.bundle, args.poppler, ROOT/"tmp/pdfs/release_review"))
    output = ROOT/"docs/validation/release_pdf_checks.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
