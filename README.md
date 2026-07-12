# 3Cloud Candidate Campaign

Independent RoleForge candidate campaign for Russell Dudek's application to **Senior Consultant - AI** at 3Cloud.

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

The campaign uses the current official 3Cloud logo for nominative employer identification, current official-site color and typography evidence, and explicit independent-candidate language. It does not imply endorsement.

## PDF build and audit

Run:

```bash
python scripts/build_pdfs.py
python scripts/render_audit.py
```

PDF generation asserts the required page counts. The Playwright audit checks desktop, laptop, tablet, mobile, reduced motion, visible official identity, independent-candidate labeling, keyboard tab behavior, internal links, and PDF download routes.

## Evidence integrity

The campaign does not claim multi-year Azure delivery tenure. It addresses that gap directly and relies on verified adjacent evidence in AI workflow design, operating transformation, integration, evaluation/governance, quality systems, and technical-business translation.
