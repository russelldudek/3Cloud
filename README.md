# 3Cloud Candidate Campaign

Independent RoleForge candidate campaign for Russell Dudek's application to **Senior Consultant - AI** at 3Cloud.

## Campaign status

**Complete.** The campaign source, official brand package, six HTML routes, five generated PDFs, responsive and reduced-motion evidence, official-reference comparison, live GitHub Pages audit, and full-site clipping regression audit are committed to `main`.

- Live site: https://russelldudek.github.io/3Cloud/
- Job posting: https://job-boards.greenhouse.io/3cloud/jobs/8229697002?gh_jid=8229697002
- Publication branch: `main`

## Thesis

**AI delivery scales at the seams.**

The campaign argues that the mandate is to turn cross-practice architecture into reliable AI delivery, then convert project learning into governed, reusable patterns that improve client value and delivery leverage at post-acquisition scale.

## Main routes

- `index.html` — candidate vision and interactive Delivery Weave
- `resume.html` — exactly two printable pages
- `cover-letter.html` — exactly one printable page
- `interview-brief.html` — five-page thesis brief
- `90-day-plan.html` — two-page entry plan
- `delivery-seam-review.html` — one-page operating worksheet

## Brand package

- `brand-intelligence.md`
- `brand-tokens.css`
- `assets/brand/`

The campaign uses the current official 3Cloud logo for nominative employer identification, source-sampled official-site colors, public typography evidence, and explicit independent-candidate language. It does not imply endorsement.

## Full-site QA

A user-reported bottom clipping defect on `delivery-seam-review.html` exposed a shared document-layout flaw: screen sheets were fixed to 11 inches with hidden overflow while footers were absolutely positioned inside the same canvas.

The repair preserves fixed US Letter print output while allowing web document sheets to grow with their content. Tablet and mobile footers now participate in normal flow, document width recomposes below 840px, and document headings use semantic H1 structure.

The permanent `scripts/site_qa.py` regression suite checks:

- all six routes at 1440×900, 1280×800, 768×1024, and 390×844;
- hidden fixed-canvas overflow, bottom clipping, and footer collisions;
- horizontal overflow, broken images, console errors, heading structure, and accessible controls;
- keyboard operation of the Delivery Weave and reduced-motion behavior;
- every internal route and PDF link;
- exact PDF page counts and rendered thumbnails for all eleven PDF pages.

The baseline run produced 48 findings. The repaired live run produced zero critical, high, or medium findings.

## Audit evidence

- `artifact-manifest.json`
- `audit/render-audit.json`
- `audit/full-site-qa-summary.json`
- `audit/brand-fidelity-side-by-side.png`
- `audit/live-pages-audit.json`
- desktop, laptop, tablet, mobile, reduced-motion, official-reference, and live screenshots under `audit/`

PDF generation asserts the required page counts. Browser audits verify visible company identity, independent-candidate labeling, purposeful motion, keyboard tab behavior, reduced motion, responsive composition, reciprocal document navigation, live routes, and byte equality between each live PDF and its committed `main` file.

## Reproducible checks

```bash
python scripts/build_pdfs.py
python scripts/render_audit.py
python scripts/site_qa.py --base-url http://127.0.0.1:8000/ --repo-root . --output /tmp/3cloud-site-qa
```

## Evidence integrity

The campaign does not claim multi-year Azure delivery tenure. It addresses that gap directly and relies on verified adjacent evidence in AI workflow design, operating transformation, integration, evaluation/governance, quality systems, and technical-business translation.
