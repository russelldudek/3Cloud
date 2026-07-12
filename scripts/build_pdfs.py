from pathlib import Path
from weasyprint import HTML
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)
ARTIFACTS = {
    "resume.html": ("russell-dudek-3cloud-resume.pdf", 2),
    "cover-letter.html": ("russell-dudek-3cloud-cover-letter.pdf", 1),
    "interview-brief.html": ("russell-dudek-3cloud-interview-brief.pdf", 5),
    "90-day-plan.html": ("russell-dudek-3cloud-90-day-plan.pdf", 2),
    "delivery-seam-review.html": ("3cloud-delivery-seam-review.pdf", 1),
}

for source, (target, expected_pages) in ARTIFACTS.items():
    output = DOCS / target
    HTML(filename=str(ROOT / source), base_url=str(ROOT)).write_pdf(str(output))
    actual_pages = len(PdfReader(str(output)).pages)
    if actual_pages != expected_pages:
        raise SystemExit(f"{target}: expected {expected_pages} pages, got {actual_pages}")
    if output.stat().st_size == 0:
        raise SystemExit(f"{target}: empty PDF")
    print(f"{target}: {actual_pages} pages, {output.stat().st_size} bytes")
