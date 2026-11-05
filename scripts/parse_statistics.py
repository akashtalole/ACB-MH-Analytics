#!/usr/bin/env python3
"""Parse the official ACB Maharashtra statistics PDFs (https://acb.maharashtra.gov.in/statistics).

The PDFs have a text layer, but Marathi text is stored in a legacy font encoding
(Kruti-Dev style, e.g. "ukansM" for नांदेड) while all digits are plain ASCII.
Tables are therefore parsed structurally (pdfplumber) and the small, closed set
of region / department names is mapped to English via KEY_TO_EN below.

Every table is validated against the totals row printed in the PDF. Rows that
cannot be mapped are kept under their raw key and reported (``unmapped`` in the
output) rather than guessed.

Outputs (docs/data/):
  history.json  all-year official figures (yearly, regions, departments, pipeline, convictions, sanctions)
  stats.json    latest-year snapshot, in the shape the dashboard already consumes

Usage:  python scripts/parse_statistics.py [--cache DIR] [--years 2025 2026]
        (default: parse every document; --years limits PDF re-parsing to those years and
        reuses the previous history.json for the rest, which keeps the daily CI run fast)
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data"
INDEX_URL = "https://acb.maharashtra.gov.in/statistics"

# --------------------------------------------------------------------------- names
# English names of the 47 departments in the order the 2026 "statistical information"
# PDF lists them (checked row-by-row against the printed numbers).
DEPT_ORDER_EN = [
    "Revenue / Land Records / Registration", "Police", "MSEDCL (power distribution)", "Municipal Corporation",
    "Nagar Palika", "Nagar Parishad", "Zilla Parishad", "Panchayat Samiti", "Forest",
    "Animal Husbandry, Dairy & Fisheries", "Food & Civil Supplies", "Water Resources", "Public Health",
    "State Excise", "Tribal Development", "Regional Transport (RTO)", "Water Supply", "Public Works",
    "Sales Tax / GST", "Law & Judiciary", "Industries, Energy & Labour", "Social Welfare", "Town Planning",
    "Finance", "Cooperation & Marketing", "Education", "Sports", "Food & Drugs", "Agriculture",
    "State Transport (ST)", "Other departments", "CIDCO", "Women & Child Development",
    "Mahatma Phule Backward Class Corp.", "MHADA", "MIDC", "Pollution Control Board", "BEST",
    "Weights & Measures", "Higher & Technical Education", "Skill Development",
    "Social Justice & Special Assistance", "Ports", "Prisons", "Nagpur Improvement Trust",
    "Charity Commissioner", "Silk Industries",
]

# Legacy-encoded spellings seen in older/other files -> English. Matched on the
# whitespace/punctuation-stripped key, by prefix.
ALIAS_PREFIX = [
    ("eglqy", "Revenue / Land Records / Registration"), ("egklqy", "Revenue / Land Records / Registration"),
    ("iksyhl", "Police"), ("iksyhl", "Police"),
    ("e-jk-fo-fo", "MSEDCL (power distribution)"), ("egkuxj", "Municipal Corporation"),
    ("uxjikyhdk", "Nagar Palika"), ("uxjifj", "Nagar Parishad"),
    ("ftYgkifj", "Zilla Parishad"), ("iapk;r", "Panchayat Samiti"),
    ("ou", "Forest"), ("i-nq-e", "Animal Husbandry, Dairy & Fisheries"),
    ("vUuoukxjh", "Food & Civil Supplies"), ("tylaink", "Water Resources"), ("ikVca/kkjs", "Water Resources"),
    ("lkoZtfudvkjksX;", "Public Health"), ("lkoZtuhdvkjksX;", "Public Health"), ("vkjksX;", "Public Health"),
    ("jkT;mRiknu", "State Excise"), ("vkfnoklh", "Tribal Development"),
    ("izknsf'kdifjogu", "Regional Transport (RTO)"), ("izknf'kdifjogu", "Regional Transport (RTO)"),
    ("ik.khiqjoBk", "Water Supply"), ("lkoZtfudcka/kdke", "Public Works"), ("lkoZtuhdcka/kdke", "Public Works"),
    ("foØhdj", "Sales Tax / GST"), ("fo/khoU;k;", "Law & Judiciary"),
    ("m|ksx", "Industries, Energy & Labour"), ("lekt", "Social Welfare"), ("uxjjpuk", "Town Planning"),
    ("uxjfodkl", "Town Planning"), ("foRrfoHkkx", "Finance"), ("lgdkj", "Cooperation & Marketing"),
    ("f'k{k.k", "Education"), ("fØMk", "Sports"), ("vUuovkS", "Food & Drugs"),
    ("d`\"kh", "Agriculture"), ("Ñ\"kh", "Agriculture"), ("—\"kh", "Agriculture"),
    ("jkT;ifjogu", "State Transport (ST)"), ("brjfoHkkx", "Other departments"), ("brj", "Other departments"),
    ("flMdks", "CIDCO"), ("lhMdks", "CIDCO"), ("efgyk", "Women & Child Development"),
    ("egkRekQqys", "Mahatma Phule Backward Class Corp."), ("EgkMk", "MHADA"), ("egkMk", "MHADA"),
    ("e-jk-vkS|ksfxd", "MIDC"), ("egkjk\"VªvkS|ksfxd", "MIDC"), ("egkeaMGegkjk\"VªvkS|ksfxd", "MIDC"),
    ("iznq\"k.k", "Pollution Control Board"), ("csLV", "BEST"), ("otuoekis", "Weights & Measures"),
    ("mPpo", "Higher & Technical Education"), ("mPpvkf.k", "Higher & Technical Education"),
    ("dkS'kY;", "Skill Development"), ("lkekftdU;k;", "Social Justice & Special Assistance"),
    ("canj", "Ports"), ("dkjkx`g", "Prisons"), ("ukxiwjlq/kkj", "Nagpur Improvement Trust"), ("ukxiqjlq/kkj", "Nagpur Improvement Trust"),
    (">ksiMi", "Slum Rehabilitation"), ("Hkweh", "Revenue / Land Records / Registration"), ("uksan.kh", "Revenue / Land Records / Registration"),
    ("foRr@/kekZnk;", "Law & Judiciary"), ("/kekZnk;", "Charity Commissioner"), ("jsf'ke", "Silk Industries"),
    ("oDQ", "Waqf Board"), ("oDqQ", "Waqf Board"), ("xzkefodkl", "Rural Development"),
    ("brjekxkloxhZ;", "Other backward class corporations"),
]

REGION_PREFIX = [
    ("ukansM", "Nanded"), ("Bk.ks", "Thane"), ("N=irh", "Chh. Sambhajinagar"), ("vkSjaxkckn", "Chh. Sambhajinagar"),
    ("iq.ks", "Pune"), ("ukf'kd", "Nashik"), ("ukxiwj", "Nagpur"), ("Ukkxiwj", "Nagpur"),
    ("vejkorh", "Amravati"), ("eqacbZ", "Mumbai"),
]
REGIONS = ["Mumbai", "Thane", "Pune", "Nashik", "Nagpur", "Amravati", "Chh. Sambhajinagar", "Nanded"]

# summary-table row labels (legacy-encoded) -> field
SUMMARY_ROWS = {"lkiGk": "trap", "vilaink": "da", "vU;Hkz\"Vkpkj": "other", ",dw.k": "total"}


def key(s: str | None) -> str:
    return re.sub(r"[\s\.\- ​]+", "", (s or "").replace("\n", " "))


def dept_en(raw: str) -> str | None:
    k = key(raw)
    if k.startswith("foHkkx") and len(k) > 6:  # some older files prefix the word "foHkkx" (department)
        k = k[6:]
    for p, en in ALIAS_PREFIX:
        if k.startswith(key(p)):
            return en
    return None


def region_en(raw: str) -> str | None:
    k = key(raw)
    for p, en in REGION_PREFIX:
        if k.startswith(key(p)):
            return en
    return None


def num(s) -> int | None:
    s = (s or "").replace(",", "").strip()
    return int(s) if re.fullmatch(r"\d+", s) else None


def cells(row) -> list[str]:
    return [(c or "").replace("\n", " ").strip() for c in row]


# --------------------------------------------------------------------------- catalogue
def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "acb-mh-analytics/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def classify(title: str) -> str | None:
    t = title.lower()
    if "daily update" in t:
        return "pipeline"
    if "conviction" in t:
        return "conviction"
    if "property confiscate" in t:
        return "property"
    if "d.s.o" in t:
        return "sanction_pending"
    if "not suspended" in t:
        return "not_suspended"
    if "not terminated" in t:
        return "not_terminated"
    if "statistical information" in t or re.match(r"statistics \d{4}", t):
        return "yearly"
    return None


def catalogue(cache: Path) -> list[dict]:
    page = fetch(INDEX_URL).decode("utf-8", "replace")
    rows = re.findall(r'<td scope="row"><span><img[^>]*>(.*?)</span></td>\s*<td[^>]*>(.*?)</td>.*?href=\'([^\']+)\'', page, re.S)
    out = []
    for title, year, url in rows:
        title = " ".join(html.unescape(title).split())
        try:
            y = int(year.strip())
        except ValueError:
            continue
        kind = classify(title)
        if kind:
            fn = cache / url.rsplit("/", 1)[-1]
            out.append({"year": y, "title": title, "kind": kind, "url": url, "file": fn})
    return out


def download(doc: dict) -> Path:
    fn: Path = doc["file"]
    if not fn.exists():
        fn.write_bytes(fetch(doc["url"]))
    return fn


# --------------------------------------------------------------------------- table helpers
def all_tables(pdf_path: Path) -> list[list[list[str]]]:
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            for tb in p.extract_tables():
                out.append([cells(r) for r in tb])
    return out


def glued_number(cell: str) -> str | None:
    """"foHkk1x" / "oHkkx3" -> "1" / "3": the word foHkkx (department) with a digit fused in by a font glitch."""
    digits = re.sub(r"\D", "", cell or "")
    if digits and re.sub(r"\d", "", cell) in ("foHkkx", "oHkkx", "foHkk", "oHkk", "Hkkx"):
        return digits
    return None


def to_int(s: str) -> int | None:
    """Digits (with optional thousands commas) -> int; a blank cell means zero in these tables."""
    s = (s or "").replace(",", "").strip()
    if s in ("", "-", "--", "\u2013", "\u2014"):
        return 0
    return int(s) if re.fullmatch(r"\d+", s) else None


def row_nums(c: list[str], n: int) -> tuple[str, list[int]] | None:
    """(label, n ints) for a numbered row [serial, label, (label tail), v1..vn, ...], else None."""
    if len(c) < 3 or not re.fullmatch(r"\d{1,3}\.?", c[0] or "") or not c[1] or num(c[1]) is not None:
        return None
    g = glued_number(c[2])
    if g:
        c = c[:2] + [g] + c[3:]
    for off in (2, 3):  # a wrapped label can spill into the next cell
        tail = c[off: off + n]
        if len(tail) == n:
            vals = [to_int(x) for x in tail]
            if None not in vals and any(re.fullmatch(r"[\d,]+", (x or "")) for x in tail):
                return c[1], vals
    return None


def total_row(tb, n: int):
    for c in tb:
        if c and any((x or "").startswith((",dw.k", ",dq.k")) for x in c[:3]):
            nums = [num(x) for x in c if num(x) is not None]
            if len(nums) >= n:
                return nums[-n:]
    return None


def header_text(tb) -> str:
    t = " ".join(" ".join(r) for r in tb[:3])
    return t.replace("\u201d", '"').replace("\u201c", '"')


# --------------------------------------------------------------------------- yearly file
DEPT_COLS = ["cases", "c1", "c2", "c3", "c4", "other", "private", "accused"]


def dept_rows(tables, with_amount: bool):
    n = 9 if with_amount else 8
    rows, unmapped = [], []
    for tb in tables:
        for c in tb:
            r = row_nums(c, n)
            if r:
                label, nums = r
                en = dept_en(label)
                if en is None:
                    unmapped.append(label)
                rec = {"dept": en or f"UNMAPPED:{key(label)}", **dict(zip(DEPT_COLS, nums[:8]))}
                if with_amount:
                    rec["amount"] = nums[8]
                rows.append(rec)
    tot = None
    for tb in tables:
        tot = total_row(tb, n) or tot
    return rows, unmapped, tot


def check_dept(tag, rows, tot, with_amount, warnings):
    cols = DEPT_COLS + (["amount"] if with_amount else [])
    totd = dict(zip(cols, tot)) if tot else None
    if tot:
        got = [sum(r[c] for r in rows) for c in cols]
        if got != list(tot):
            warnings.append(f"{tag}: department rows sum {got} != printed total {list(tot)}")
    for r in rows:
        if r["c1"] + r["c2"] + r["c3"] + r["c4"] + r["other"] + r["private"] != r["accused"]:
            warnings.append(f"{tag}: class split != accused for {r['dept']}")
    return totd


def parse_yearly(path: Path, year: int) -> dict:
    warnings: list[str] = []
    tables = all_tables(path)
    res: dict = {"year": year, "warnings": warnings, "unmapped": []}

    # 1) yearly summary: years across the top, rows trap / DA / other / total
    summary: dict = {}
    for tb in tables:
        yrs = [int(x) for x in re.findall(r"\b(20[012]\d)\b", " ".join(tb[0]))]
        if len(yrs) >= 3 and "ifj{ks=" not in header_text(tb)[:60] and not summary:
            for c in tb[1:]:
                lab = key(c[1] if len(c) > 1 else "")
                for pat, f in SUMMARY_ROWS.items():
                    if lab.startswith(key(pat)):
                        vals = [num(x) for x in c[2:]]
                        for y, v in zip(yrs, vals):
                            if v is not None:
                                summary.setdefault(y, {})[f] = v
    res["summary"] = summary

    # 2) region table. Row order is fixed (see REGIONS), so when wrapped text garbles a name the
    #    serial number identifies the region.
    regions = {}
    for tb in tables:
        if "ifj{ks=" in header_text(tb) and "oxZ" not in header_text(tb):
            for c in tb:
                if len(c) < 4 or not re.fullmatch(r"[1-8]", c[0] or ""):
                    continue
                reg = region_en(c[1]) or REGIONS[int(c[0]) - 1]
                tail = c[2:]
                for n, names in ((8, ["trap_cases", "trap_accused", "da_cases", "da_accused", "other_cases",
                                       "other_accused", "total_cases", "total_accused"]),
                                  (4, ["trap_cases", "da_cases", "other_cases", "total_cases"])):
                    vals = [to_int(x) for x in tail[:n]]
                    rest_blank = all(x == "" for x in tail[n:])
                    if len(tail) >= n and None not in vals and rest_blank:
                        regions[reg] = dict(zip(names, vals))
                        break
            if regions:
                break
    res["regions"] = regions

    # 3) department tables. Header words decide which table a block belongs to; a table split over
    #    pages (continuation, no header words) is attached to the previous category.
    groups: dict[str, list] = {"trap": [], "da": [], "other": []}
    cur = None
    for tb in tables:
        ht = header_text(tb)
        if "oxZ" not in ht or "byksls" not in ht or ("ifj{ks=" in ht and "oxZ" not in ht):
            if not (cur and any(row_nums(c, 8) for c in tb)):
                continue
        k = key(ht)
        width = max(len(r) for r in tb)
        if "oxZ" in ht and "byksls" in ht:
            if "vilaink" in k:
                cur = "da"
            elif "vU;Hkz" in k:
                cur = "other"
            elif "lkiGk" in k:
                cur = "trap"
            elif cur in ("da", "trap") and width <= 10:  # untitled table without an amount column = other corruption
                cur = "other"
        if cur:
            groups[cur].append(tb)
    for name, with_amount in (("trap", True), ("da", True), ("other", False)):
        if groups[name]:
            rows, um, tot = dept_rows(groups[name], with_amount)
            if rows:
                res[f"{name}_by_dept"] = rows
                res[f"{name}_totals"] = check_dept(f"{year} {name}", rows, tot, with_amount, warnings)
                res["unmapped"] += um
    return res


# --------------------------------------------------------------------------- pipeline file (daily update)
PIPE_COLS = ["trap", "da", "other", "total", "investigation_pending", "sanction_pending_govt",
             "sanction_pending_competent", "sanction_received", "chargesheet_filed"]
PIPE_MIN_YEAR = 2020  # 2016-2019 files carry an extra column of unknown meaning; 2014-15 not verified


def parse_pipeline(path: Path, year: int) -> dict:
    warnings: list[str] = []
    rows, tot = {}, None
    for tb in all_tables(path):
        for c in tb:
            if len(c) > 1 and re.fullmatch(r"\d", c[0] or "") and region_en(c[1]):
                vals = [to_int(x) for x in c[2:]]
                nums = [v for v in vals if v is not None]
                if len(nums) == 9:
                    rows[region_en(c[1])] = dict(zip(PIPE_COLS, nums))
        t = total_row(tb, 9)
        if t:
            tot = dict(zip(PIPE_COLS, t))
    if year < PIPE_MIN_YEAR:
        return {"year": year, "regions": {}, "totals": None, "warnings": [], "skipped": "layout not verified"}
    if rows and tot:
        got = {k: sum(r[k] for r in rows.values()) for k in PIPE_COLS}
        if got != tot:
            warnings.append(f"pipeline: region rows {got} != printed total {tot}")
    return {"year": year, "regions": rows, "totals": tot, "warnings": warnings}


# --------------------------------------------------------------------------- conviction file
CONV_COLS = ["cases", "c1", "c2", "c3", "c4", "other", "private", "accused", "fine"]
CR_RE = re.compile(r"(?:xq-?j-?ua-?|xqjdz|xq\.j\.ua\.?|dz\.?)\D{0,3}?(\d{1,5})[@/\-](\d{4})")


def parse_conviction(path: Path, year: int) -> dict:
    warnings: list[str] = []
    depts, unmapped, tot = [], [], None
    case_years: list[int] = []
    n_case_rows = 0
    first = True
    for tb in all_tables(path):
        w = max(len(r) for r in tb)
        if w >= 10:
            for c in tb:
                r = row_nums(c, 9)
                if r:
                    label, nums = r
                    en = dept_en(label)
                    if en is None:
                        unmapped.append(label)
                    depts.append({"dept": en or f"UNMAPPED:{key(label)}", **dict(zip(CONV_COLS, nums))})
            t = total_row(tb, 9)
            tot = dict(zip(CONV_COLS, t)) if t else tot
        elif w == 5:  # case-level rows: only aggregated (registration year), never stored
            for c in tb:
                if len(c) == 5 and re.fullmatch(r"\d+", c[0] or ""):
                    n_case_rows += 1
                    m = CR_RE.search(re.sub(r"\s+", "", c[3]))
                    if m:
                        case_years.append(int(m[2]))
    if depts and tot:
        got = {k: sum(d[k] for d in depts) for k in CONV_COLS}
        if got != tot:
            warnings.append(f"conviction: dept rows {got} != printed total {tot}")
    ages = sorted(year - y for y in case_years if 0 <= year - y <= 40)
    return {"year": year, "by_dept": depts, "totals": tot, "unmapped": unmapped, "warnings": warnings,
            "case_rows": n_case_rows, "case_rows_with_cr_year": len(case_years),
            "age_at_conviction": _summ(ages)}


def _summ(v: list[int]) -> dict | None:
    if len(v) < 5:
        return None
    return {"n": len(v), "median": v[len(v) // 2], "mean": round(sum(v) / len(v), 1),
            "p25": v[len(v) // 4], "p75": v[(3 * len(v)) // 4], "share_10plus_pct": round(100 * sum(a >= 10 for a in v) / len(v), 1)}


# --------------------------------------------------------------------------- sanction pending (Annexure-2)
# Departments (प्रशासकीय विभाग) in the fixed order of the Annexure-2 table.
SANCTION_DEPTS_EN = [
    "Revenue", "Home (Police / Prisons / Excise)", "Rural Development & Panchayat Raj", "Urban Development",
    "Energy", "School Education & Sports", "Public Health", "Agriculture", "Transport",
    "Cooperation, Marketing & Textiles", "Forest", "Public Works", "Law & Judiciary",
    "Food, Civil Supplies & Consumer Protection", "Finance", "Social Justice & Special Assistance",
    "Water Resources", "Tribal Development", "Medical Education & Drugs", "Women & Child Development",
    "Other departments",
]
SANCTION_COLS = ["total", "under_90", "over_90", "with_govt", "with_competent"]


def parse_sanction(path: Path, year: int) -> dict:
    """Cases awaiting prosecution sanction (अभियोगपूर्व मंजुरी): by administrative department,
    split into pending <90 / >90 days and by who holds the file (Government vs competent authority).
    Only the main table is used; the following pages break down "Other departments" and would
    double-count."""
    warnings: list[str] = []
    rows, tot = [], None
    for tb in all_tables(path):
        cand = []
        for c in tb:
            if len(c) >= 7 and re.fullmatch(r"\d{1,2}", c[0] or "") and c[1] and num(c[1]) is None:
                vals = [num(x) for x in c[-5:]]
                if None not in vals:
                    cand.append(dict(zip(SANCTION_COLS, vals)))
        t = None
        for c in tb:
            if any((x or "").startswith((",dq.k", ",dw.k")) for x in c[:3]):
                n = [num(x) for x in c if num(x) is not None]
                if len(n) >= 5:
                    t = dict(zip(SANCTION_COLS, n[-5:]))
        if len(cand) >= 15 and t:
            rows, tot = cand, t
            break
    if len(rows) != len(SANCTION_DEPTS_EN):
        warnings.append(f"sanction: expected {len(SANCTION_DEPTS_EN)} departments, found {len(rows)}")
    else:
        for r, name in zip(rows, SANCTION_DEPTS_EN):
            r["dept"] = name
    if rows and tot:
        got = {k: sum(r[k] for r in rows) for k in SANCTION_COLS}
        if got != tot:
            warnings.append(f"sanction: rows {got} != printed total {tot}")
    return {"year": year, "rows": rows, "totals": tot, "warnings": warnings}


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(ROOT / ".cache" / "statistics"))
    ap.add_argument("--years", nargs="*", type=int, help="only (re)parse these years; keep the rest from history.json")
    args = ap.parse_args()
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)

    prev = {}
    hist_path = OUT / "history.json"
    if args.years and hist_path.exists():
        prev = json.loads(hist_path.read_text(encoding="utf-8"))

    docs = catalogue(cache)
    print(f"{len(docs)} documents on the statistics page")
    hist = {"yearly": {}, "pipeline": {}, "conviction": {}, "sanction_pending": {}, "documents": [],
            "unmapped": [], "warnings": []}
    for k in ("yearly", "pipeline", "conviction", "sanction_pending"):
        hist[k] = dict(prev.get(k, {})) if args.years else {}
    if args.years:  # keep notes about the years that are not re-parsed
        redo = tuple(f"{y} " for y in args.years)
        hist["warnings"] = [w for w in prev.get("warnings", []) if not w.startswith(redo)]
        hist["unmapped"] = [w for w in prev.get("unmapped", []) if not w.startswith(redo)]

    parsers = {"yearly": parse_yearly, "pipeline": parse_pipeline, "conviction": parse_conviction,
               "sanction_pending": parse_sanction}
    for d in docs:
        hist["documents"].append({"year": d["year"], "title": d["title"], "kind": d["kind"], "url": d["url"]})
        if d["kind"] not in parsers or (args.years and d["year"] not in args.years):
            continue
        try:
            res = parsers[d["kind"]](download(d), d["year"])
        except Exception as e:  # keep going; one bad PDF must not kill the refresh
            hist["warnings"].append(f"{d['year']} {d['kind']}: failed to parse ({type(e).__name__}: {e})")
            continue
        hist[d["kind"]][str(d["year"])] = res
        for w in res.get("warnings", []):
            hist["warnings"].append(f"{d['year']} {d['kind']}: {w}")
        for u in res.get("unmapped", []):
            hist["unmapped"].append(f"{d['year']} {d['kind']}: {u}")
        print(f"  parsed {d['year']} {d['kind']:<16}", {k: len(v) if isinstance(v, (list, dict)) else v
                                                        for k, v in res.items() if k in ('regions', 'trap_by_dept', 'by_dept', 'rows')})
    hist["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT.mkdir(parents=True, exist_ok=True)
    hist_path.write_text(json.dumps(hist, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {hist_path}; {len(hist['warnings'])} warnings, {len(set(hist['unmapped']))} distinct unmapped names")
    for w in hist["warnings"][:40]:
        print("WARN", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
