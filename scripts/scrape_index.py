#!/usr/bin/env python3
"""Scrape the ACB Maharashtra press-release and FIR index pages.

Both pages are single server-rendered tables (title | date | PDF link), so no
JavaScript execution is needed. The output is data/records.json: one flat list
of records with cleaned dates and fields parsed from the free-text titles.

stdlib only, so the scheduled GitHub Action needs no dependency install.
"""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

BASE = "https://acb.maharashtra.gov.in"
SOURCES = {"press_release": f"{BASE}/press_release", "fir": f"{BASE}/fir"}
OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "records.json"

ROW_RE = re.compile(
    r'<td scope="row"><span><img[^>]*>(?P<title>.*?)</span></td>\s*'
    r"<td[^>]*>(?P<date>.*?)</td>.*?"
    r"href=['\"](?P<url>[^'\"]+)['\"]",
    re.S,
)

# "C.R. No. 33 -2026", "Cr No.187/2026", "Crime No29/2021", "CR 18/2018"
CR_RE = re.compile(
    r"(?:c\.?\s*r\.?|crime)\s*(?:no\.?)?\s*[:.]?\s*(\d{1,4})\s*[/\-–—]\s*(\d{4}|\d{2})\b",
    re.I,
)
SECTION_RE = re.compile(r"(?:u/s|sec(?:tion)?\.?)\s*([0-9]+[a-z]?(?:\(\d+\))?)", re.I)

# ACB units -> districts that (approximately) fall under them. The ACB's own
# range boundaries are not published on the site, so this is a heuristic used
# only for the optional "region" facet; unmatched titles get region=None.
REGION_DISTRICTS = {
    "Thane": ["thane", "palghar", "raigad", "alibag", "ratnagiri", "sindhudurg",
              "kalyan", "bhiwandi", "vasai", "navi mumbai", "panvel", "ulhasnagar",
              "dombivli", "mira bhayandar", "mira-bhayandar"],
    "Mumbai": ["mumbai", "bandra", "andheri", "borivali", "kurla", "colaba", "worli"],
    "Pune": ["pune", "satara", "sangli", "solapur", "kolhapur", "pimpri", "baramati",
             "karad", "ichalkaranji"],
    "Nashik": ["nashik", "nasik", "ahmednagar", "ahilyanagar", "dhule", "nandurbar",
               "jalgaon", "shirdi", "sangamner", "malegaon"],
    "Nagpur": ["nagpur", "wardha", "bhandara", "gondia", "chandrapur", "gadchiroli"],
    "Amravati": ["amravati", "akola", "washim", "buldhana", "buldana", "yavatmal"],
    "Chh. Sambhajinagar": ["aurangabad", "sambhajinagar", "jalna", "beed"],
    "Nanded": ["nanded", "latur", "parbhani", "hingoli", "osmanabad", "dharashiv"],
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "acb-mh-analytics/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8", errors="replace")


def clean_date(raw: str, today: date) -> tuple[str | None, bool]:
    """dd/mm/yyyy -> ISO date. Returns (iso|None, was_repaired).

    The source has typos like 0021 / 0221 / 0026 (zero-padded years) and 2030.
    Years below 1000 are repaired to 20YY from their last two digits; anything
    still outside 2009..today is dropped rather than guessed.
    """
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{1,4})\s*", raw or "")
    if not m:
        return None, False
    d, mo, y = (int(g) for g in m.groups())
    repaired = False
    if y < 1000:
        y, repaired = 2000 + y % 100, True
    try:
        out = date(y, mo, d)
    except ValueError:
        return None, False
    if not (2009 <= out.year <= today.year) or out > today:
        return None, False
    return out.isoformat(), repaired


def classify_region(title: str) -> str | None:
    t = title.lower()
    for region, words in REGION_DISTRICTS.items():
        if any(re.search(rf"\b{re.escape(w.strip())}\b", t) for w in words):
            return region
    return None


def parse_title(title: str) -> dict:
    cr = CR_RE.search(title)
    sec = SECTION_RE.search(title)
    low = title.lower()
    return {
        "cr_no": int(cr.group(1)) if cr else None,
        "cr_year": (int(cr.group(2)) if len(cr.group(2)) == 4 else 2000 + int(cr.group(2))) if cr else None,
        "section": sec.group(1) if sec else None,
        "region": classify_region(title),
        "is_da": bool(re.search(r"disproportionate|13\s*\(1\)\s*\((?:b|e)\)|\bd\.?a\.? case", low)),
    }


def parse_page(kind: str, page: str, today: date) -> list[dict]:
    records = []
    for m in ROW_RE.finditer(page):
        title = " ".join(html.unescape(re.sub(r"<[^>]+>", "", m["title"])).split())
        iso, repaired = clean_date(html.unescape(m["date"]).strip(), today)
        rec = {
            "kind": kind,
            "title": title,
            "date": iso,
            "date_raw": html.unescape(m["date"]).strip(),
            "date_repaired": repaired,
            "pdf": m["url"],
            **parse_title(title),
        }
        records.append(rec)
    return records


def main() -> int:
    today = datetime.now(timezone.utc).date()
    all_records: list[dict] = []
    for kind, url in SOURCES.items():
        recs = parse_page(kind, fetch(url), today)
        if len(recs) < 1000:  # the live tables hold >4000 rows; guard against layout changes
            print(f"ERROR: only {len(recs)} rows parsed from {url}", file=sys.stderr)
            return 1
        print(f"{kind}: {len(recs)} rows")
        all_records.extend(recs)

    # stable ids from the PDF filename so downstream joins survive reordering
    for r in all_records:
        r["id"] = r["pdf"].rsplit("/", 1)[-1].removesuffix(".pdf")
    all_records.sort(key=lambda r: (r["date"] or "", r["id"]), reverse=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCES,
        "records": all_records,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1e6:.1f} MB, {len(all_records)} records)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
