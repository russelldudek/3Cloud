import asyncio
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit"
AUDIT.mkdir(exist_ok=True)
OFFICIAL_HOME = "https://3cloudsolutions.com/"
VIEWPORTS = {
    "desktop-1440x900": (1440, 900),
    "laptop-1280x800": (1280, 800),
    "tablet-768x1024": (768, 1024),
    "mobile-390x844": (390, 844),
}
REQUIRED = [
    "index.html", "resume.html", "cover-letter.html", "interview-brief.html",
    "90-day-plan.html", "delivery-seam-review.html", "styles.css",
    "brand-tokens.css", "app.js", "brand-intelligence.md",
    "assets/brand/3cloud-logo-cognizant.png",
    "docs/russell-dudek-3cloud-resume.pdf",
    "docs/russell-dudek-3cloud-cover-letter.pdf",
    "docs/russell-dudek-3cloud-interview-brief.pdf",
    "docs/russell-dudek-3cloud-90-day-plan.pdf",
    "docs/3cloud-delivery-seam-review.pdf",
    "artifact-manifest.json", "campaign-metadata.json", "README.md",
]


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def source_checks():
    failures = []
    for rel in REQUIRED:
        path = ROOT / rel
        if not path.exists() or path.stat().st_size == 0:
            failures.append(f"missing_or_empty:{rel}")
    for html_name in ["index.html", "resume.html", "cover-letter.html", "interview-brief.html", "90-day-plan.html", "delivery-seam-review.html"]:
        soup = BeautifulSoup((ROOT / html_name).read_text(encoding="utf-8"), "html.parser")
        for link in soup.find_all("a", href=True):
            href = link["href"]
            parsed = urlparse(href)
            if parsed.scheme or href.startswith("#") or href.startswith("mailto:"):
                continue
            local = ROOT / parsed.path
            if not local.exists():
                failures.append(f"broken_link:{html_name}:{href}")
    return failures


def create_brand_comparison():
    official_path = AUDIT / "official-3cloud-home-1440x900.png"
    campaign_path = AUDIT / "desktop-1440x900.png"
    output_path = AUDIT / "brand-fidelity-side-by-side.png"
    if not official_path.exists() or not campaign_path.exists():
        return False

    official = Image.open(official_path).convert("RGB")
    campaign_full = Image.open(campaign_path).convert("RGB")
    campaign = campaign_full.crop((0, 0, min(1440, campaign_full.width), min(900, campaign_full.height)))
    official = official.resize((720, 450))
    campaign = campaign.resize((720, 450))
    canvas = Image.new("RGB", (1440, 500), "white")
    canvas.paste(official, (0, 50))
    canvas.paste(campaign, (720, 50))
    draw = ImageDraw.Draw(canvas)
    draw.text((20, 15), "Current official 3Cloud home page", fill="black")
    draw.text((740, 15), "Independent 3Cloud candidate campaign", fill="black")
    canvas.save(output_path)
    return output_path.exists() and output_path.stat().st_size > 0


async def main():
    failures = source_checks()
    use_file = os.environ.get("ROLEFORGE_FILE_AUDIT") == "1"
    port = free_port()
    server = None if use_file else subprocess.Popen(
        ["python", "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if server:
        time.sleep(1)
    base_url = (ROOT / "index.html").as_uri() if use_file else f"http://127.0.0.1:{port}/index.html"
    results = {"viewports": {}, "source_failures": failures, "reduced_motion": {}, "official_reference": {}}
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or None)
            for name, (width, height) in VIEWPORTS.items():
                page = await browser.new_page(viewport={"width": width, "height": height})
                errors = []
                page.on("console", lambda msg: errors.append(f"console:{msg.type}:{msg.text}") if msg.type == "error" else None)
                page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))
                response = await page.goto(base_url, wait_until="networkidle")
                logo_visible = await page.locator(".identity-lockup img").is_visible()
                qualifier = await page.locator(".identity-copy").inner_text()
                overflow = await page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")
                await page.screenshot(path=str(AUDIT / f"{name}.png"), full_page=True)
                results["viewports"][name] = {
                    "http_status": response.status if response else None,
                    "logo_visible": logo_visible,
                    "independent_candidate_qualifier": "Independent" in qualifier,
                    "horizontal_overflow": overflow,
                    "errors": errors,
                }
                if not logo_visible or "Independent" not in qualifier or overflow or errors:
                    failures.append(f"viewport:{name}")
                await page.close()

            official_page = await browser.new_page(viewport={"width": 1440, "height": 900})
            official_errors = []
            official_page.on("pageerror", lambda exc: official_errors.append(f"pageerror:{exc}"))
            try:
                official_response = await official_page.goto(OFFICIAL_HOME, wait_until="domcontentloaded", timeout=90000)
                await official_page.wait_for_timeout(5000)
                official_title = await official_page.title()
                official_font = await official_page.locator("body").evaluate("el => getComputedStyle(el).fontFamily")
                await official_page.screenshot(path=str(AUDIT / "official-3cloud-home-1440x900.png"), full_page=False)
                official_ok = bool(official_response and official_response.status < 400 and "3Cloud" in official_title)
                results["official_reference"] = {
                    "url": OFFICIAL_HOME,
                    "http_status": official_response.status if official_response else None,
                    "title": official_title,
                    "body_font_family": official_font,
                    "errors": official_errors,
                    "screenshot": "audit/official-3cloud-home-1440x900.png",
                    "passed": official_ok and not official_errors,
                }
                if not results["official_reference"]["passed"]:
                    failures.append("official_reference")
            except Exception as exc:
                results["official_reference"] = {"url": OFFICIAL_HOME, "passed": False, "error": repr(exc)}
                failures.append("official_reference")
            finally:
                await official_page.close()

            page = await browser.new_page(viewport={"width": 1280, "height": 800}, reduced_motion="reduce")
            await page.goto(base_url, wait_until="networkidle")
            animation_name = await page.locator(".thread-data").evaluate("el => getComputedStyle(el).animationName")
            await page.screenshot(path=str(AUDIT / "reduced-motion-1280x800.png"), full_page=True)
            results["reduced_motion"] = {"thread_animation_name": animation_name, "passed": animation_name == "none"}
            if animation_name != "none":
                failures.append("reduced_motion")

            tabs = page.locator('[role="tab"]')
            await tabs.nth(0).focus()
            await page.keyboard.press("ArrowRight")
            selected = await tabs.nth(1).get_attribute("aria-selected")
            panel_visible = await page.locator("#panel-compose").is_visible()
            results["keyboard_tabs"] = {"selected_second_tab": selected == "true", "panel_visible": panel_visible}
            if selected != "true" or not panel_visible:
                failures.append("keyboard_tabs")
            await page.close()
            await browser.close()
    finally:
        if server:
            server.terminate()
            server.wait(timeout=10)

    results["brand_comparison_artifact"] = {
        "path": "audit/brand-fidelity-side-by-side.png",
        "passed": create_brand_comparison(),
    }
    if not results["brand_comparison_artifact"]["passed"]:
        failures.append("brand_comparison_artifact")

    results["failures"] = sorted(set(failures))
    results["passed"] = not results["failures"]
    (AUDIT / "render-audit.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit("Audit failed: " + ", ".join(sorted(set(failures))))
    print("Responsive, official-reference brand, interaction, and reduced-motion audit passed.")


if __name__ == "__main__":
    asyncio.run(main())
