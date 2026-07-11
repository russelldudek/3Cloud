from pathlib import Path
from weasyprint import HTML

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ARTIFACTS = {
    "resume.html": "russell-dudek-3cloud-resume.pdf",
    "cover-letter.html": "russell-dudek-3cloud-cover-letter.pdf",
    "interview-brief.html": "russell-dudek-3cloud-interview-brief.pdf",
    "delivery-seam-review.html": "3cloud-delivery-seam-review.pdf",
}


def build_pdfs() -> None:
    DOCS.mkdir(exist_ok=True)
    for source, target in ARTIFACTS.items():
        destination = DOCS / target
        HTML(filename=str(ROOT / source), base_url=str(ROOT)).write_pdf(str(destination))
        print(f"generated {destination}")


if __name__ == "__main__":
    build_pdfs()
