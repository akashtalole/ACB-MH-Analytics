# ACB Maharashtra Analytics

Independent, unofficial analytics of the Anti-Corruption Bureau (ACB), Maharashtra — trap cases,
disproportionate-assets cases and the FIRs / press releases published at
<https://acb.maharashtra.gov.in/fir> and <https://acb.maharashtra.gov.in/press_release>.
Served as a static site from `docs/` via GitHub Pages. A trap or FIR is an allegation, not a conviction.

## What's here

| Data | Source | Script | Output |
|---|---|---|---|
| ~8,600 FIR / press-release index rows (title, date, PDF link, parsed CR no., section, inferred region) | the FIR and press-release tables | `scripts/scrape_index.py` | `docs/data/records.json` |
| Official statistics 2009–2026: yearly totals, regions, departments and classes, bribe amounts, convictions, case status, pending sanctions | the PDFs on <https://acb.maharashtra.gov.in/statistics> | `scripts/parse_statistics.py` | `docs/data/history.json` |
| Derived analytics (trend and projection, concentration, seasonality, convictions, pipeline, sanction backlog) and the latest-year snapshot | the two datasets above | `scripts/build_analytics.py` | `docs/data/analytics.json`, `docs/data/stats.json` |

The statistics PDFs have a text layer, but Marathi text uses a legacy font encoding (digits are plain ASCII),
so tables are parsed structurally with pdfplumber and a small closed set of region and department names is
mapped to English. **Every table is checked against the totals row printed in the PDF.** Remaining mismatches
(for example the 2026 disproportionate-assets table, and a few wrapped rows in older conviction summaries) are
source inconsistencies, kept as printed and shown under *Data notes*. Conflicts between yearly files are resolved
with the printed total as a consistency check and listed too.

Known gaps: the 2022 and 2024 "statistical information" files contain only the case-status table, and the 2025 file
is a mid-year snapshot, so department-level trends skip those years. Case-status files before 2020 have an extra
column of unknown meaning and are not used. Case-level conviction rows name individuals; the parser reads only the
registration year from them and never stores names.

**Not yet done:** OCR of the scanned FIR / press-release PDFs (accused designation, bribe amount, outcome per case).

## Run locally

```bash
python scripts/scrape_index.py      # needs network; stdlib only
python scripts/parse_statistics.py   # needs: pip install pdfplumber; add --years 2026 for a quick refresh
python scripts/build_analytics.py
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
