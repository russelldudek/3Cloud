from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BRAND_DIR = ROOT / "assets" / "brand"
BRAND_DIR.mkdir(parents=True, exist_ok=True)

OFFICIAL_HOME = "https://3cloudsolutions.com/"
ASSETS = {
    "3cloud-logo-cognizant.png": "https://3cloudsolutions.com/wp-content/uploads/2026/01/3cloud-logo-cognizant-1.png",
    "3cloud-logo-blue.jpg": "https://3cloudsolutions.com/wp-content/uploads/2021/08/3Cloud-Logo-Blue-500x500.jpg",
}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; RoleForgeBrandAudit/1.0; +https://github.com/russelldudek/3Cloud)"
})

provenance: dict[str, object] = {
    "official_home": OFFICIAL_HOME,
    "assets": {},
    "stylesheets": [],
    "font_families": [],
    "sampled_colors": [],
}

for filename, url in ASSETS.items():
    response = session.get(url, timeout=45)
    response.raise_for_status()
    destination = BRAND_DIR / filename
    destination.write_bytes(response.content)
    with Image.open(destination) as image:
        provenance["assets"][filename] = {
            "source_url": url,
            "status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "pixel_dimensions": list(image.size),
            "mode": image.mode,
        }

home = session.get(OFFICIAL_HOME, timeout=45)
home.raise_for_status()
soup = BeautifulSoup(home.text, "html.parser")
stylesheet_urls: list[str] = []
for link in soup.find_all("link", href=True):
    rel = {str(item).lower() for item in (link.get("rel") or [])}
    if "stylesheet" in rel:
        stylesheet_urls.append(urljoin(OFFICIAL_HOME, link["href"]))

font_counter: Counter[str] = Counter()
color_counter: Counter[str] = Counter()
css_records: list[dict[str, object]] = []

for stylesheet_url in dict.fromkeys(stylesheet_urls):
    try:
        response = session.get(stylesheet_url, timeout=45)
        response.raise_for_status()
    except requests.RequestException as exc:
        css_records.append({"url": stylesheet_url, "error": str(exc)})
        continue

    css = response.text
    css_records.append({
        "url": stylesheet_url,
        "status": response.status_code,
        "bytes": len(response.content),
    })

    for declaration in re.findall(r"font-family\s*:\s*([^;}]+)", css, flags=re.IGNORECASE):
        normalized = re.sub(r"\s+", " ", declaration.strip())
        font_counter[normalized] += 1

    for color in re.findall(r"#[0-9a-fA-F]{6}\b", css):
        color_counter[color.upper()] += 1

provenance["stylesheets"] = css_records
provenance["font_families"] = [
    {"value": value, "occurrences": count}
    for value, count in font_counter.most_common(30)
]
provenance["sampled_colors"] = [
    {"value": value, "occurrences": count}
    for value, count in color_counter.most_common(40)
]

(BRAND_DIR / "provenance.json").write_text(
    json.dumps(provenance, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

summary_lines = [
    "# Automated official-source snapshot",
    "",
    f"Official homepage: {OFFICIAL_HOME}",
    "",
    "## Downloaded assets",
]
for filename, record in provenance["assets"].items():
    summary_lines.append(
        f"- {filename}: {record['source_url']} — {record['pixel_dimensions'][0]}×{record['pixel_dimensions'][1]} px, {record['mode']}"
    )
summary_lines.extend(["", "## Most frequent declared font-family values"])
for item in provenance["font_families"][:15]:
    summary_lines.append(f"- {item['value']} ({item['occurrences']})")
summary_lines.extend(["", "## Most frequent six-digit CSS colors"])
for item in provenance["sampled_colors"][:20]:
    summary_lines.append(f"- {item['value']} ({item['occurrences']})")
summary_lines.extend([
    "",
    "Generated from current official 3Cloud web properties. This snapshot is evidence, not an official brand guide.",
])
(BRAND_DIR / "source-snapshot.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

print(f"refreshed brand package in {BRAND_DIR}")
