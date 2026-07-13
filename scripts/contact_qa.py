import argparse
import io
import re
import sys
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from pypdf import PdfReader

REQUIRED = [
    "Pittsburgh, Pennsylvania",
    "412.287.8640",
    "russelldudek@gmail.com",
    "linkedin.com/in/russelldudek",
]

HTML_ROUTES = ["resume.html", "cover-letter.html"]
PDF_ROUTES = [
    "docs/russell-dudek-3cloud-resume.pdf",
    "docs/russell-dudek-3cloud-cover-letter.pdf",
]


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "RoleForge-contact-qa/1.0"})
    with urlopen(request, timeout=60) as response:
        if response.status >= 400:
            raise RuntimeError(f"{url}: HTTP {response.status}")
        return response.read()


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def check_text(label: str, text: str) -> list[str]:
    normalized = normalize(text)
    return [f"{label}: missing {item}" for item in REQUIRED if item not in normalized]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()

    failures: list[str] = []

    for route in HTML_ROUTES:
        url = urljoin(args.base_url, route)
        html = fetch(url).decode("utf-8", errors="replace")
        failures.extend(check_text(route, html))

    for route in PDF_ROUTES:
        url = urljoin(args.base_url, route)
        reader = PdfReader(io.BytesIO(fetch(url)))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        failures.extend(check_text(route, text))

    if failures:
        print("Contact QA failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Contact QA passed for resume HTML/PDF and cover-letter HTML/PDF.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
