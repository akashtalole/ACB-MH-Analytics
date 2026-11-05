# ACB Maharashtra Analytics

Independent, unofficial analytics of the Anti-Corruption Bureau (ACB), Maharashtra — trap cases,
disproportionate-assets cases and the FIRs / press releases published at
<https://acb.maharashtra.gov.in/fir> and <https://acb.maharashtra.gov.in/press_release>.
Served as a static site from `docs/` via GitHub Pages. A trap or FIR is an allegation, not a conviction.

## What's here (phase 1)

| Data | Source | Script | Output |
|---|---|---|---|
| ~8,600 FIR / press-release index rows (title, date, PDF link, parsed CR no., section, inferred region) | the two website tables | `scripts/scrape_index.py` | `docs/data/records.json` |
| Yearly 2014–2026, region and department tables (traps, assets, other) | the official statistics PDF (Marathi scan, hand-transcribed) | `scripts/build_stats.py` | `docs/data/stats.json` |

`build_stats.py` cross-checks every table against the PDF's printed totals. Known source inconsistencies
(trap bribe-amount column off by ₹26,200; the disproportionate-assets table does not sum to its total row;
other-corruption accused 68 vs 63) are kept as-is and shown on the site under *Data notes*.

**Phase 2 (planned):** OCR (Tesseract, Marathi + English) of the scanned case PDFs to extract accused
designation, department, bribe amount and outcome per case.

## Run locally

```bash
python scripts/scrape_index.py      # needs network; stdlib only
python scripts/build_stats.py
python -m unittest discover -s tests
python -m http.server -d docs 8000  # open http://localhost:8000
```

## Deploy

`.github/workflows/pages.yml` runs on push to `main`, daily, and on demand: tests, re-scrape, rebuild stats,
deploy `docs/`. One-time setup: repo **Settings → Pages → Source: GitHub Actions**.

## Caveats

- Website postings are not official case counts (the site lists fewer items than the official totals).
- *Region* in the explorer is inferred from place names in titles; ~30% of items stay blank.
- Source dates contain typos; obvious zero-padded years are repaired, others left undated.
