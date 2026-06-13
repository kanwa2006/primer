# PRIMER — Screenshot Capture Plan

This document defines the exact commands and filenames for capturing dashboard screenshots
for embedding in `README.md` and the GitHub social preview.

No screenshots have been generated yet. The live dashboard is at
**[kanwa2006.github.io/primer](https://kanwa2006.github.io/primer/)**.

---

## Prerequisites

- Node.js 20+
- `cd dashboard && npm ci` completed

---

## Option A — Capture from local dev server

```bash
cd dashboard
npm run dev
# Server starts at http://localhost:3000
```

Then capture each page below at **1440×900px** viewport (or 1280×800px minimum).

## Option B — Capture from the live GitHub Pages site

Visit `https://kanwa2006.github.io/primer/` directly after `v3-execution` is merged to `main`
and GitHub Pages has deployed.

---

## Pages to Capture

### 1. Dashboard home (`/`)

**URL:** `http://localhost:3000/` or `https://kanwa2006.github.io/primer/`

**What to show:**
- The full above-the-fold view including the framing banner
- The evaluation ledger table (COMMIT / DATE / VERDICT / DELTA / EGRESS columns)
- The repo identity and freshness anchor

**Filename:** `assets/screenshots/dashboard-home.png`

**README caption:** `PRIMER dashboard — evaluation history for a repository`

---

### 2. Evaluation detail (`/evaluations/1/`)

**URL:** `http://localhost:3000/evaluations/1` or `https://kanwa2006.github.io/primer/evaluations/1/`

**What to show:**
- VerdictHero: the signed delta, verdict label (▲ Helped / ▼ Hurt / ≈ Within noise), confidence ruler
- MetricsGrid: WITHOUT / WITH / VARIANCE / TASKS / COST tiles
- Scroll down slightly to include the per-task flip table

**Filename:** `assets/screenshots/eval-detail.png`

**README caption:** `Evaluation detail — signed delta with variance and per-task flip table`

---

### 3. Compare page (`/compare/`)

**URL:** `http://localhost:3000/compare` or `https://kanwa2006.github.io/primer/compare/`

**What to show:**
- The evaluation picker (two dropdowns)
- After selecting `?a=1&b=1`, the cross-delta panel and provenance diff

**Filename:** `assets/screenshots/comparison-view.png`

**README caption:** `Compare view — side-by-side provenance diff between two evaluation runs`

---

### 4. Repository overview (top of `/`)

**URL:** Same as home, but cropped to just the repo identity + verdict + badge row

**Filename:** `assets/screenshots/repository-overview.png`

**README caption:** `Repository overview — current verdict and evaluation count`

---

## After Capture

1. Create `assets/screenshots/` directory at repo root
2. Place all four `.png` files there
3. Commit: `git add assets/screenshots/ && git commit -m "docs: add dashboard screenshots"`
4. Replace the placeholder in `README.md` with:

```markdown
## Screenshots

### Dashboard home
![PRIMER dashboard — evaluation history for a repository](assets/screenshots/dashboard-home.png)

### Evaluation detail
![Evaluation detail — signed delta with variance and per-task flip table](assets/screenshots/eval-detail.png)

### Compare view
![Compare view — side-by-side provenance diff between two evaluation runs](assets/screenshots/comparison-view.png)
```

---

## Social Preview Image

For the GitHub social preview (1280×640px, uploaded in GitHub Settings → Social preview):

- **Background:** dark (`#18181b` zinc-900 or similar)
- **Left half:** cropped `eval-detail.png` showing VerdictHero with "+20.0 pp ▲ Helped"
- **Right half:** PRIMER wordmark + the shields.io badge showing the current score
- **Bottom strip:** the one-liner: "Every context-file tool generates. PRIMER measures."

This requires a design tool (Figma, Canva, etc.) or a screenshot compositor. It cannot be
auto-generated from the dashboard alone.

---

## Viewport Settings

| Capture | Viewport | Zoom |
|---------|----------|------|
| dashboard-home.png | 1440×900 | 100% |
| eval-detail.png | 1440×900 | 100% |
| comparison-view.png | 1440×900 | 100% |
| repository-overview.png | 1440×400 (cropped) | 100% |

Use a browser extension (e.g. GoFullPage, Awesome Screenshot) or
`playwright screenshot` for pixel-accurate captures.
