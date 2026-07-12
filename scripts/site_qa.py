import argparse
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import fitz
from pypdf import PdfReader
from playwright.async_api import async_playwright

ROUTES = [
    "index.html",
    "resume.html",
    "cover-letter.html",
    "interview-brief.html",
    "90-day-plan.html",
    "delivery-seam-review.html",
]

VIEWPORTS = {
    "desktop-1440x900": (1440, 900),
    "laptop-1280x800": (1280, 800),
    "tablet-768x1024": (768, 1024),
    "mobile-390x844": (390, 844),
}

PDFS = {
    "docs/russell-dudek-3cloud-resume.pdf": 2,
    "docs/russell-dudek-3cloud-cover-letter.pdf": 1,
    "docs/russell-dudek-3cloud-interview-brief.pdf": 5,
    "docs/russell-dudek-3cloud-90-day-plan.pdf": 2,
    "docs/3cloud-delivery-seam-review.pdf": 1,
}


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-")


def add_finding(findings: list[dict], *, severity: str, code: str, route: str, viewport: str, detail: str) -> None:
    findings.append({
        "severity": severity,
        "code": code,
        "route": route,
        "viewport": viewport,
        "detail": detail,
    })


def audit_pdfs(repo_root: Path, output_dir: Path, findings: list[dict]) -> dict:
    pdf_results: dict[str, dict] = {}
    render_dir = output_dir / "pdf-pages"
    render_dir.mkdir(parents=True, exist_ok=True)

    for rel_path, expected_pages in PDFS.items():
        path = repo_root / rel_path
        result = {"exists": path.exists(), "expected_pages": expected_pages}
        if not path.exists() or path.stat().st_size == 0:
            result["error"] = "missing_or_empty"
            add_finding(
                findings,
                severity="critical",
                code="pdf_missing_or_empty",
                route=rel_path,
                viewport="pdf",
                detail="The committed PDF is missing or empty.",
            )
            pdf_results[rel_path] = result
            continue

        reader = PdfReader(str(path))
        result["actual_pages"] = len(reader.pages)
        result["bytes"] = path.stat().st_size
        if len(reader.pages) != expected_pages:
            add_finding(
                findings,
                severity="critical",
                code="pdf_page_count",
                route=rel_path,
                viewport="pdf",
                detail=f"Expected {expected_pages} pages, found {len(reader.pages)}.",
            )

        document = fitz.open(path)
        rendered_pages = []
        for index, page in enumerate(document):
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            out_path = render_dir / f"{safe_name(Path(rel_path).stem)}-page-{index + 1}.png"
            pix.save(out_path)
            rendered_pages.append(str(out_path.relative_to(output_dir)))

            blocks = page.get_text("blocks")
            page_height = page.rect.height
            max_text_bottom = max((block[3] for block in blocks), default=0)
            result.setdefault("page_metrics", []).append({
                "page": index + 1,
                "page_height": round(page_height, 2),
                "max_text_bottom": round(max_text_bottom, 2),
                "bottom_clearance": round(page_height - max_text_bottom, 2),
            })
            if max_text_bottom > page_height - 2:
                add_finding(
                    findings,
                    severity="high",
                    code="pdf_bottom_edge_risk",
                    route=rel_path,
                    viewport=f"pdf-page-{index + 1}",
                    detail=f"Text ends only {page_height - max_text_bottom:.1f}pt above the physical page edge.",
                )

        document.close()
        result["rendered_pages"] = rendered_pages
        pdf_results[rel_path] = result

    return pdf_results


async def inspect_route(page, base_url: str, route: str, viewport_name: str, width: int, height: int, output_dir: Path, findings: list[dict]) -> dict:
    await page.set_viewport_size({"width": width, "height": height})
    errors: list[str] = []
    warnings: list[str] = []
    page.on("console", lambda msg: errors.append(f"console:{msg.type}:{msg.text}") if msg.type == "error" else warnings.append(f"console:{msg.type}:{msg.text}") if msg.type == "warning" else None)
    page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))

    url = urljoin(base_url, route)
    response = await page.goto(url, wait_until="networkidle", timeout=90000)
    await page.wait_for_timeout(250)

    screenshot_dir = output_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_dir / f"{safe_name(Path(route).stem)}--{viewport_name}.png"
    await page.screenshot(path=str(screenshot_path), full_page=True)

    status = response.status if response else None
    title = await page.title()
    metrics = await page.evaluate(
        """
        () => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          scrollHeight: document.documentElement.scrollHeight,
          clientHeight: document.documentElement.clientHeight,
          lang: document.documentElement.lang,
          h1Count: document.querySelectorAll('h1').length,
          duplicateIds: [...document.querySelectorAll('[id]')]
            .map(el => el.id)
            .filter((id, i, ids) => ids.indexOf(id) !== i),
          brokenImages: [...document.images]
            .filter(img => !img.complete || img.naturalWidth === 0)
            .map(img => img.getAttribute('src')),
          missingAlt: [...document.images]
            .filter(img => !img.hasAttribute('alt'))
            .map(img => img.getAttribute('src')),
          unnamedControls: [...document.querySelectorAll('a,button,input,select,textarea')]
            .filter(el => {
              const name = (el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || el.value || '').trim();
              const r = el.getBoundingClientRect();
              return r.width > 0 && r.height > 0 && !name;
            }).length,
        })
        """
    )

    if status is None or status >= 400:
        add_finding(findings, severity="critical", code="route_status", route=route, viewport=viewport_name, detail=f"HTTP status was {status}.")
    if metrics["scrollWidth"] > metrics["clientWidth"] + 1:
        add_finding(findings, severity="high", code="horizontal_overflow", route=route, viewport=viewport_name, detail=f"Document width {metrics['scrollWidth']}px exceeds viewport {metrics['clientWidth']}px.")
    if errors:
        add_finding(findings, severity="high", code="runtime_error", route=route, viewport=viewport_name, detail="; ".join(errors))
    if metrics["brokenImages"]:
        add_finding(findings, severity="critical", code="broken_image", route=route, viewport=viewport_name, detail=", ".join(metrics["brokenImages"]))
    if metrics["missingAlt"]:
        add_finding(findings, severity="medium", code="missing_alt", route=route, viewport=viewport_name, detail=", ".join(metrics["missingAlt"]))
    if metrics["duplicateIds"]:
        add_finding(findings, severity="high", code="duplicate_id", route=route, viewport=viewport_name, detail=", ".join(metrics["duplicateIds"]))
    if metrics["h1Count"] < 1:
        add_finding(findings, severity="medium", code="missing_h1", route=route, viewport=viewport_name, detail="No H1 was found.")
    if not metrics["lang"]:
        add_finding(findings, severity="medium", code="missing_lang", route=route, viewport=viewport_name, detail="The html element has no lang attribute.")
    if metrics["unnamedControls"]:
        add_finding(findings, severity="medium", code="unnamed_control", route=route, viewport=viewport_name, detail=f"{metrics['unnamedControls']} visible controls have no accessible name.")

    paper_metrics = []
    if await page.locator(".paper").count():
        paper_metrics = await page.locator(".paper").evaluate_all(
            """
            papers => papers.map((paper, index) => {
              const paperStyle = getComputedStyle(paper);
              const paperRect = paper.getBoundingClientRect();
              const footer = paper.querySelector('.doc-foot');
              const footerRect = footer ? footer.getBoundingClientRect() : null;
              let contentBottom = paperRect.top;
              let offender = null;
              for (const child of paper.children) {
                if (child.classList.contains('doc-foot')) continue;
                const rect = child.getBoundingClientRect();
                if (rect.bottom > contentBottom) {
                  contentBottom = rect.bottom;
                  offender = child.tagName.toLowerCase() + (child.className ? '.' + String(child.className).trim().replace(/\\s+/g, '.') : '');
                }
              }
              const hidden = ['hidden', 'clip'].includes(paperStyle.overflowY) || ['hidden', 'clip'].includes(paperStyle.overflow);
              return {
                index,
                clientHeight: paper.clientHeight,
                scrollHeight: paper.scrollHeight,
                overflow: paperStyle.overflow,
                overflowY: paperStyle.overflowY,
                paperTop: paperRect.top,
                paperBottom: paperRect.bottom,
                contentBottom,
                footerTop: footerRect ? footerRect.top : null,
                footerBottom: footerRect ? footerRect.bottom : null,
                hiddenOverflow: hidden && paper.scrollHeight > paper.clientHeight + 1,
                bottomClip: hidden && contentBottom > paperRect.bottom + 1,
                footerOverlap: footerRect ? contentBottom > footerRect.top + 1 : false,
                offender,
              };
            })
            """
        )

        for paper in paper_metrics:
            label = f"paper {paper['index'] + 1}"
            if paper["hiddenOverflow"]:
                add_finding(
                    findings,
                    severity="critical",
                    code="document_fixed_canvas_overflow",
                    route=route,
                    viewport=viewport_name,
                    detail=f"{label} has scrollHeight {paper['scrollHeight']}px inside a {paper['clientHeight']}px overflow-hidden canvas.",
                )
            if paper["bottomClip"]:
                add_finding(
                    findings,
                    severity="critical",
                    code="document_bottom_clipped",
                    route=route,
                    viewport=viewport_name,
                    detail=f"{label} content reaches {paper['contentBottom']:.1f}px beyond the visible paper bottom {paper['paperBottom']:.1f}px; last block: {paper['offender']}.",
                )
            if paper["footerOverlap"]:
                add_finding(
                    findings,
                    severity="critical",
                    code="document_footer_overlap",
                    route=route,
                    viewport=viewport_name,
                    detail=f"{label} content bottom {paper['contentBottom']:.1f}px crosses footer top {paper['footerTop']:.1f}px; last block: {paper['offender']}.",
                )

    return {
        "url": url,
        "status": status,
        "title": title,
        "viewport": {"width": width, "height": height},
        "screenshot": str(screenshot_path.relative_to(output_dir)),
        "metrics": metrics,
        "paper_metrics": paper_metrics,
        "console_errors": errors,
        "console_warnings": warnings,
    }


async def audit_site(base_url: str, repo_root: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    findings: list[dict] = []
    results: dict[str, dict] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for route in ROUTES:
            results[route] = {}
            for viewport_name, (width, height) in VIEWPORTS.items():
                context = await browser.new_context(viewport={"width": width, "height": height})
                page = await context.new_page()
                results[route][viewport_name] = await inspect_route(
                    page,
                    base_url,
                    route,
                    viewport_name,
                    width,
                    height,
                    output_dir,
                    findings,
                )
                await context.close()

        # Purposeful interaction and keyboard path on the primary campaign page.
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        await page.goto(urljoin(base_url, "index.html"), wait_until="networkidle", timeout=90000)
        tabs = page.locator('[role="tab"]')
        interaction = {"tab_count": await tabs.count()}
        if await tabs.count() >= 2:
            await tabs.nth(0).focus()
            await page.keyboard.press("ArrowRight")
            interaction["second_selected"] = await tabs.nth(1).get_attribute("aria-selected") == "true"
            interaction["compose_panel_visible"] = await page.locator("#panel-compose").is_visible()
        else:
            interaction["second_selected"] = False
            interaction["compose_panel_visible"] = False
        if not interaction["second_selected"] or not interaction["compose_panel_visible"]:
            add_finding(findings, severity="high", code="keyboard_tab_interaction", route="index.html", viewport="laptop-1280x800", detail="ArrowRight did not select and reveal the second Delivery Weave tab.")
        await context.close()

        # Reduced-motion check.
        context = await browser.new_context(viewport={"width": 1280, "height": 800}, reduced_motion="reduce")
        page = await context.new_page()
        await page.goto(urljoin(base_url, "index.html"), wait_until="networkidle", timeout=90000)
        animation_name = await page.locator(".thread-data").evaluate("el => getComputedStyle(el).animationName")
        reduced_motion = {"thread_animation_name": animation_name, "passed": animation_name == "none"}
        if not reduced_motion["passed"]:
            add_finding(findings, severity="high", code="reduced_motion", route="index.html", viewport="reduced-motion", detail=f"Animation name remained {animation_name!r}.")
        await context.close()

        # Link and PDF-route status checks.
        context = await browser.new_context()
        request = context.request
        link_checks: dict[str, dict] = {}
        for route in ROUTES:
            page = await context.new_page()
            await page.goto(urljoin(base_url, route), wait_until="domcontentloaded", timeout=90000)
            hrefs = await page.locator("a[href]").evaluate_all("links => [...new Set(links.map(link => link.href))]")
            for href in hrefs:
                if not href.startswith(base_url):
                    continue
                if href in link_checks:
                    continue
                response = await request.get(href, timeout=90000)
                link_checks[href] = {"status": response.status, "ok": response.ok}
                if not response.ok:
                    add_finding(findings, severity="critical", code="broken_internal_link", route=route, viewport="link-check", detail=f"{href} returned {response.status}.")
            await page.close()
        await context.close()
        await browser.close()

    pdf_results = audit_pdfs(repo_root, output_dir, findings)

    critical_or_high = [finding for finding in findings if finding["severity"] in {"critical", "high"}]
    report = {
        "base_url": base_url,
        "routes": ROUTES,
        "viewports": VIEWPORTS,
        "results": results,
        "interaction": interaction,
        "reduced_motion": reduced_motion,
        "link_checks": link_checks,
        "pdfs": pdf_results,
        "findings": findings,
        "summary": {
            "total_findings": len(findings),
            "critical": sum(1 for item in findings if item["severity"] == "critical"),
            "high": sum(1 for item in findings if item["severity"] == "high"),
            "medium": sum(1 for item in findings if item["severity"] == "medium"),
            "passed": not critical_or_high,
        },
    }

    (output_dir / "site-qa.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 3Cloud Full-Site QA",
        "",
        f"- Base URL: `{base_url}`",
        f"- Routes: {len(ROUTES)}",
        f"- Rendered route/viewport combinations: {len(ROUTES) * len(VIEWPORTS)}",
        f"- Critical findings: {report['summary']['critical']}",
        f"- High findings: {report['summary']['high']}",
        f"- Medium findings: {report['summary']['medium']}",
        f"- Passed: {report['summary']['passed']}",
        "",
        "## Findings",
        "",
    ]
    if findings:
        for index, finding in enumerate(findings, 1):
            lines.append(f"{index}. **{finding['severity'].upper()} · {finding['code']}** — `{finding['route']}` / `{finding['viewport']}` — {finding['detail']}")
    else:
        lines.append("No findings.")
    (output_dir / "site-qa-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if critical_or_high:
        raise SystemExit(f"QA failed with {len(critical_or_high)} critical/high findings. See {output_dir / 'site-qa.json'}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://russelldudek.github.io/3Cloud/")
    parser.add_argument("--output", default="/tmp/3cloud-site-qa")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    base_url = args.base_url if args.base_url.endswith("/") else args.base_url + "/"
    asyncio.run(audit_site(base_url, Path(args.repo_root).resolve(), Path(args.output).resolve()))


if __name__ == "__main__":
    main()
