#!/usr/bin/env python3
"""Derive advanced analytics from docs/data/records.json and docs/data/stats.json.

Output: docs/data/analytics.json. stdlib only. Every figure is computed here
(not in the browser) so the method is reviewable in one place.

Caveats that matter for interpretation:
* "Unique cases" is an ESTIMATE built from website postings (FIR + press release
  for the same case are merged). It is not an official count.
* Seasonality/weekday figures describe when items are *posted*, not when the
  offence or trap happened.
"""
from __future__ import annotations

import json
import re
import statistics as st
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "docs" / "data"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
START = "2018-06-01"  # website launched May 2018; earlier dates are legacy/typo entries


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def unique_cases(records: list[dict]) -> list[dict]:
    """Merge FIR + press-release postings of the same case.

    Key: (CR no, CR year, region) when all three are parseable, otherwise the
    normalised title. A case is dated by its earliest posting.
    """
    groups: dict[tuple, dict] = {}
    for r in records:
        if not r["date"] or r["date"] < START:
            continue
        key = (("cr", r["cr_no"], r["cr_year"], r["region"])
               if r["cr_no"] and r["cr_year"] and r["region"] else ("t", norm_title(r["title"])))
        g = groups.setdefault(key, {"date": r["date"], "region": r["region"], "kinds": set(), "n": 0})
        g["date"] = min(g["date"], r["date"])
        g["region"] = g["region"] or r["region"]
        g["kinds"].add(r["kind"])
        g["n"] += 1
    return list(groups.values())


def trend(stats: dict) -> dict:
    full = [y for y in stats["yearly"] if not y["partial"]]
    xs, ys = [y["year"] for y in full], [y["trap"] for y in full]
    slope, intercept = st.linear_regression(xs, ys)
    r = st.correlation(xs, ys)
    n = len(xs) - 1
    yoy = [{"year": full[i]["year"], "pct": round(100 * (ys[i] / ys[i - 1] - 1), 1)} for i in range(1, len(full))]
    peak = max(full, key=lambda y: y["trap"])
    return {
        "slope_per_year": round(slope, 1), "r2": round(r * r, 2),
        "fit": [{"year": x, "trap": round(intercept + slope * x, 1)} for x in xs + [stats["yearly"][-1]["year"]]],
        "cagr_pct": round(100 * ((ys[-1] / ys[0]) ** (1 / n) - 1), 1),
        "from_year": xs[0], "to_year": xs[-1],
        "peak_year": peak["year"], "peak": peak["trap"],
        "change_vs_peak_pct": round(100 * (ys[-1] / peak["trap"] - 1), 1),
        "yoy": yoy,
    }


def projection(stats: dict, uniq: list[dict]) -> dict:
    """Full-year 2026 trap projection from year-to-date.

    pace:     YTD / elapsed days * 365 (assumes a flat rate).
    seasonal: YTD / (share of a typical year's postings that fall on or before
              the same calendar day), using 2019-2025 website postings as a
              proxy for seasonality. Reported as a range across those years.
    """
    asof = date.fromisoformat(stats["as_of"])
    ytd = stats["yearly"][-1]["trap"]
    elapsed = (asof - date(asof.year, 1, 1)).days + 1
    shares = []
    for y in range(2019, asof.year):
        ys = [u for u in uniq if u["date"].startswith(str(y))]
        if len(ys) >= 100:
            cut = date(y, asof.month, asof.day).isoformat()
            shares.append(sum(1 for u in ys if u["date"] <= cut) / len(ys))
    out = {"ytd": ytd, "elapsed_days": elapsed, "pace": round(ytd / elapsed * 365)}
    if shares:
        out.update({
            "seasonal": round(ytd / st.mean(shares)),
            "seasonal_low": round(ytd / max(shares)), "seasonal_high": round(ytd / min(shares)),
            "share_ytd_mean": round(st.mean(shares), 3),
        })
    full = [y for y in stats["yearly"] if not y["partial"]]
    out["prev_year"] = full[-1]["trap"]
    return out


def concentration(stats: dict) -> dict:
    rows = [d for d in stats["trap_by_dept"] if d["cases"] > 0]
    rows.sort(key=lambda d: d["cases"], reverse=True)
    total = sum(d["cases"] for d in rows)
    cum, pareto = 0, []
    for d in rows:
        cum += d["cases"]
        pareto.append({"dept": d["dept"], "cases": d["cases"], "cum_pct": round(100 * cum / total, 1)})
    hhi = round(sum((d["cases"] / total) ** 2 for d in rows) * 10000)
    depts = []
    for d in rows:
        senior = d["c1"] + d["c2"]
        depts.append({
            "dept": d["dept"], "cases": d["cases"], "accused": d["accused"],
            "accused_per_case": round(d["accused"] / d["cases"], 2),
            "avg_bribe": round(d["amount"] / d["cases"]) if d["cases"] else 0,
            "private_pct": round(100 * d["private"] / d["accused"], 1) if d["accused"] else 0,
            "senior_pct": round(100 * senior / d["accused"], 1) if d["accused"] else 0,
            "amount": d["amount"],
        })
    t = stats["trap_totals"]
    cls = {k: t[k] for k in ("c1", "c2", "c3", "c4", "other", "private")}
    return {
        "hhi": hhi, "n_depts": len(rows), "top3_pct": pareto[2]["cum_pct"],
        "top5_pct": pareto[4]["cum_pct"], "n_for_80pct": next(i + 1 for i, p in enumerate(pareto) if p["cum_pct"] >= 80),
        "pareto": pareto, "depts": depts,
        "class_mix_pct": {k: round(100 * v / t["accused"], 1) for k, v in cls.items()},
        "avg_bribe_overall": round(t["amount"] / t["cases"]),
        "median_bribe_per_case_by_dept": round(st.median(d["avg_bribe"] for d in depts if d["cases"] >= 3)),
    }


def regions(stats: dict) -> list[dict]:
    tot = stats["region_totals"]["trap_cases"]
    out = []
    for r in stats["regions"]:
        allc = r["trap_cases"] + r["da_cases"] + r["other_cases"]
        out.append({
            "region": r["region"], "trap_cases": r["trap_cases"], "share_pct": round(100 * r["trap_cases"] / tot, 1),
            "accused_per_trap": round(r["trap_accused"] / r["trap_cases"], 2),
            "non_trap_pct": round(100 * (allc - r["trap_cases"]) / allc, 1) if allc else 0,
            "all_cases": allc,
        })
    return sorted(out, key=lambda r: -r["trap_cases"])


def calendar(uniq: list[dict]) -> dict:
    """Year x month matrix of unique cases, plus weekday profile of raw postings."""
    m: dict[int, list[int]] = defaultdict(lambda: [0] * 12)
    for u in uniq:
        y, mo = int(u["date"][:4]), int(u["date"][5:7])
        if y >= 2019:
            m[y][mo - 1] += 1
    years = sorted(m)
    avg = [round(st.mean(m[y][i] for y in years if y < date.today().year), 1) for i in range(12)]
    return {"months": MONTHS, "years": years, "matrix": [m[y] for y in years], "avg_by_month": avg}


def weekdays(records: list[dict]) -> dict:
    c = Counter(date.fromisoformat(r["date"]).weekday() for r in records if r["date"] and r["date"] >= START)
    tot = sum(c.values())
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return {"labels": names, "counts": [c[i] for i in range(7)], "pct": [round(100 * c[i] / tot, 1) for i in range(7)]}


def monthly_series(uniq: list[dict], today: date) -> dict:
    """Unique cases per complete month, 3-month moving average, and anomaly flags.

    An anomaly is a month whose count is > 2 sample standard deviations from the
    mean of the preceding 12 months (needs 12 months of history).
    """
    c = Counter(u["date"][:7] for u in uniq if u["date"] >= "2019-01-01")
    cur = today.strftime("%Y-%m")
    keys = sorted(k for k in c if k < cur)  # drop the in-progress month
    y, m = map(int, keys[0].split("-"))
    allk = []
    while f"{y}-{m:02d}" <= keys[-1]:
        allk.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    vals = [c.get(k, 0) for k in allk]
    ma = [round(st.mean(vals[max(0, i - 2): i + 1]), 1) for i in range(len(vals))]
    anomalies = []
    for i in range(12, len(vals)):
        hist = vals[i - 12: i]
        sd = st.stdev(hist)
        if sd and abs(vals[i] - st.mean(hist)) > 2 * sd:
            anomalies.append({"month": allk[i], "count": vals[i], "baseline": round(st.mean(hist), 1),
                              "direction": "high" if vals[i] > st.mean(hist) else "low"})
    return {"months": allk, "values": vals, "ma3": ma, "anomalies": anomalies}


def dedupe_vs_official(records: list[dict], uniq: list[dict], stats: dict) -> list[dict]:
    raw = Counter(r["date"][:4] for r in records if r["date"] and r["date"] >= START)
    un = Counter(u["date"][:4] for u in uniq)
    out = []
    for y in stats["yearly"]:
        if y["year"] < 2019:
            continue
        k = str(y["year"])
        out.append({"year": y["year"], "official_trap": y["trap"], "official_all": y["total"], "raw_postings": raw[k],
                    "unique_cases": un[k], "coverage_pct": round(100 * un[k] / y["total"], 1),
                    "partial": y["partial"]})
    return out


def region_year(uniq: list[dict]) -> dict:
    regs = sorted({u["region"] for u in uniq if u["region"]})
    ys = sorted({int(u["date"][:4]) for u in uniq if u["date"] >= "2019-01-01"})
    c = Counter((u["region"], int(u["date"][:4])) for u in uniq if u["region"])
    tot = {y: sum(c[(r, y)] for r in regs) for y in ys}
    return {"regions": regs, "years": ys,
            "share_pct": [[round(100 * c[(r, y)] / tot[y], 1) if tot[y] else 0 for y in ys] for r in regs],
            "counts": [[c[(r, y)] for y in ys] for r in regs]}


def insights(a: dict, stats: dict) -> list[str]:
    t, p, c, w = a["trend"], a["projection"], a["concentration"], a["weekdays"]
    out = [
        f"Trap cases fell from {stats['yearly'][0]['trap']:,} in {t['from_year']} to {stats['yearly'][-2]['trap']:,} in {t['to_year']} "
        f"({t['cagr_pct']:+.1f}% a year compounded); the linear trend loses about {abs(t['slope_per_year']):.0f} cases a year (R² = {t['r2']}).",
        f"{c['top3_pct']}% of 2026 trap cases come from just three departments, and {c['n_for_80pct']} of {c['n_depts']} active departments "
        f"account for 80% (concentration index HHI = {c['hhi']:,}).",
        f"Tuesday to Thursday account for {sum(w['pct'][1:4]):.0f}% of website postings; Sundays only {w['pct'][6]}%.",
    ]
    if "seasonal" in p:
        out.append(f"At the current pace 2026 would end near {p['pace']:,} trap cases "
                   f"(seasonally adjusted {p['seasonal_low']:,}–{p['seasonal_high']:,}) versus {p['prev_year']:,} in 2025.")
    hi = max((d for d in a["concentration"]["depts"] if d["cases"] >= 5), key=lambda d: d["accused_per_case"])
    out.append(f"Among departments with 5+ trap cases, {hi['dept']} has the most accused per case ({hi['accused_per_case']}), i.e. the most multi-accused cases.")
    return out


def main() -> None:
    recs = json.loads((DATA / "records.json").read_text(encoding="utf-8"))["records"]
    stats = json.loads((DATA / "stats.json").read_text(encoding="utf-8"))
    uniq = unique_cases(recs)
    today = date.today()
    a = {
        "method_notes": {
            "unique_cases": "Estimate: FIR and press-release postings merged by (CR no, CR year, region), else by normalised title.",
            "projection": "pace = YTD/elapsed days*365; seasonal = YTD / mean share of annual website postings up to the same date in 2019-2025.",
            "anomaly": "Month more than 2 standard deviations from the mean of the previous 12 months.",
        },
        "trend": trend(stats),
        "projection": projection(stats, uniq),
        "concentration": concentration(stats),
        "regions": regions(stats),
        "calendar": calendar(uniq),
        "weekdays": weekdays(recs),
        "monthly": monthly_series(uniq, today),
        "coverage": dedupe_vs_official(recs, uniq, stats),
        "region_year": region_year(uniq),
    }
    a["insights"] = insights(a, stats)
    (DATA / "analytics.json").write_text(json.dumps(a, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote analytics.json;", len(uniq), "unique cases from", len(recs), "postings")
    for line in a["insights"]:
        print("-", line)


if __name__ == "__main__":
    main()
