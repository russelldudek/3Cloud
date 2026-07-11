from pathlib import Path
from weasyprint import HTML

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
DOCS.mkdir(exist_ok=True)
ARTIFACTS = {
    'resume.html': 'russell-dudek-3cloud-resume.pdf',
    'cover-letter.html': 'russell-dudek-3cloud-cover-letter.pdf',
    'interview-brief.html': 'russell-dudek-3cloud-interview-brief.pdf',
    'delivery-seam-review.html': '3cloud-delivery-seam-review.pdf',
}
for source, target in ARTIFACTS.items():
    HTML(filename=str(ROOT / source), base_url=str(ROOT)).write_pdf(str(DOCS / target))
    print(f'generated {DOCS / target}')
