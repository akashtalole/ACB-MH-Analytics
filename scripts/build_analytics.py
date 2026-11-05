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
    # from 2014: registrations roughly doubled that year (583 -> 1,245), so earlier years would distort the fit
    full = [y for y in stats["yearly"] if not y["partial"] and y["year"] >= 2014]
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
        f"Trap cases fell from {next(y['trap'] for y in stats['yearly'] if y['year'] == t['from_year']):,} in {t['from_year']} to {next(y['trap'] for y in stats['yearly'] if y['year'] == t['to_year']):,} in {t['to_year']} "
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

    o = a["official"]
    conv = [c for c in o["convictions"] if not c["partial"]]
    if conv:
        peak = max(conv, key=lambda c: c["cases"])
        last = conv[-1]
        out.append(f"Convicted cases peaked at {peak['cases']} in {peak['year']} and were {last['cases']} in {last['year']} "
                   f"({last['per_100_traps']} per 100 traps registered that year).")
        aged = [c for c in conv if c["age"]]
        early = [c["age"]["median"] for c in aged if c["year"] <= 2019]
        late = [c["age"]["median"] for c in aged if c["year"] >= 2023]
        if early and late:
            out.append(f"The typical convicted case is getting older: median {st.median(early):g} years from registration to "
                       f"conviction up to 2019, {st.median(late):g} years from 2023 on.")
    san = o.get("sanction")
    if san:
        out.append(f"{san['totals']['total']} cases are awaiting prosecution sanction; {san['over_90_pct']}% have waited more than 90 days, "
                   f"and {san['competent_pct']}% sit with the competent authority rather than the Government.")
    b = o["bribe"]
    if len(b) >= 2:
        out.append(f"Average bribe per trap case rose from \u20b9{b[0]['avg_per_case']:,} ({b[0]['year']}) to \u20b9{b[-1]['avg_per_case']:,} "
                   f"({b[-1]['year']}), in the years with complete department tables.")
    return out


# --------------------------------------------------------------------------- official statistics
# Everything below is derived from docs/data/history.json (written by parse_statistics.py from the
# PDFs on https://acb.maharashtra.gov.in/statistics).

CLASS_KEYS = ["c1", "c2", "c3", "c4", "other", "private"]


def load_history() -> dict:
    return json.loads((DATA / "history.json").read_text(encoding="utf-8"))


def merged_summary(hist: dict) -> dict[int, dict]:
    """year -> {trap, da, other, total}.

    Every yearly PDF repeats earlier years, and the files sometimes disagree (typos). The newest file
    wins, unless its trap + assets + other does not add up to the printed total; in that case the
    combination of values seen in any file that does add up is used. Every disagreement is recorded
    in hist["_conflicts"] so it can be shown as a data-quality note.
    """
    cands: dict[int, dict[str, dict[int, int]]] = defaultdict(lambda: defaultdict(dict))
    for fy in sorted(hist["yearly"], key=int):
        rec = hist["yearly"][fy]
        sm = dict(rec.get("summary", {}))
        # the file's own year is the last, unlabelled column of the summary table; take it from the
        # printed department/region totals instead (trap cases, assets cases, other cases)
        if fy not in sm and rec.get("trap_totals") and rec.get("da_totals") and rec.get("other_totals"):
            t, d, o = rec["trap_totals"]["cases"], rec["da_totals"]["cases"], rec["other_totals"]["cases"]
            sm[fy] = {"trap": t, "da": d, "other": o, "total": t + d + o}
        for y, vals in sm.items():
            for k, v in vals.items():
                cands[int(y)][k][int(fy)] = v
    out: dict[int, dict] = {}
    conflicts = []
    for y, fields in cands.items():
        newest = {k: m[max(m)] for k, m in fields.items()}
        chosen = dict(newest)
        parts = ("trap", "da", "other")
        if all(k in newest for k in (*parts, "total")) and sum(newest[k] for k in parts) != newest["total"]:
            from itertools import product
            options = [sorted(set(fields[k].values())) for k in parts]
            for combo in product(*options):
                if sum(combo) == newest["total"]:
                    chosen.update(dict(zip(parts, combo)))
                    break
        for k, m in fields.items():
            if len(set(m.values())) > 1 and chosen[k] != newest[k] or (len(set(m.values())) > 1 and y >= 2009 and k == "trap"):
                conflicts.append((y, k, newest[k], chosen[k], max(m)))
        out[y] = chosen
    hist["_conflicts"] = conflicts
    return out


def build_stats(hist: dict) -> dict:
    """The latest-year snapshot, in the shape the dashboard already consumes (stats.json)."""
    summ = merged_summary(hist)
    latest = max(int(y) for y in hist["yearly"] if hist["yearly"][y].get("trap_by_dept"))
    cur = hist["yearly"][str(latest)]
    years = sorted(y for y in summ if y >= 2009)
    yearly = []
    for y in years:
        v = summ[y]
        total = v.get("total") or sum(v.get(k, 0) for k in ("trap", "da", "other"))
        yearly.append({"year": y, "trap": v.get("trap"), "da": v.get("da", 0), "other": v.get("other", 0),
                       "total": total, "partial": y == latest})
    regs = [dict(region=r, **cur["regions"][r]) for r in
            ["Mumbai", "Thane", "Pune", "Nashik", "Nagpur", "Amravati", "Chh. Sambhajinagar", "Nanded"] if r in cur["regions"]]
    tot = lambda k: sum(r[k] for r in regs)
    mr = {k: tot(k) for k in ("trap_cases", "trap_accused", "da_cases", "da_accused", "other_cases", "other_accused")}
    notes = []
    for w in hist["warnings"]:
        y = w.split()[0]
        if "conviction" in w:
            m = re.findall(r"'cases': (\d+)", w)
            if len(m) >= 2:
                notes.append(f"{y} convictions: the department rows add up to {m[0]} cases but the PDF prints {m[1]}; "
                             f"yearly conviction counts use the printed total and the department split is not shown for that year.")
                continue
        if " da: " in w:
            notes.append(f"{y} disproportionate-assets table: department rows add up to 10 cases / 17 accused but the PDF's own total row says 11 / 19; both kept as printed.")
            continue
        notes.append(w)
    for y, k, old, new, _ in hist.get("_conflicts", []):
        if old != new:
            notes.append(f"{y} {k}: ACB's yearly files disagree ({old} vs {new}); the value consistent with the printed total ({new}) is used.")
    doc = next((d for d in hist["documents"] if d["year"] == latest and d["kind"] == "yearly"), {})
    return {
        "source": "ACB Maharashtra statistics page (official PDFs), parsed from their text layer",
        "source_url": doc.get("url"), "as_of": hist["generated_at"][:10], "period": {"from": f"{latest}-01-01"},
        "yearly": yearly, "regions": regs, "region_totals": mr,
        "trap_by_dept": [{"dept": r["dept"], **{k: r[k] for k in ("cases", *CLASS_KEYS, "accused", "amount")}}
                         for r in cur["trap_by_dept"]],
        "trap_totals": cur.get("trap_totals"),
        "da_by_dept": cur.get("da_by_dept", []), "da_totals": cur.get("da_totals"),
        "other_by_dept": cur.get("other_by_dept", []), "other_totals": cur.get("other_totals"),
        "notes": notes,
    }


def complete_years(hist: dict, summ: dict) -> dict[int, dict]:
    """Yearly files whose trap total equals the final yearly figure, i.e. a full-year dataset
    (the in-progress year and snapshots taken mid-year are excluded from trends)."""
    out = {}
    for ys, rec in hist["yearly"].items():
        y = int(ys)
        t = rec.get("trap_totals")
        if t and summ.get(y, {}).get("trap") == t["cases"] and y < date.today().year:
            out[y] = rec
    return out


def official(hist: dict, summ: dict) -> dict:
    full = complete_years(hist, summ)
    years = sorted(full)
    # ---- long-run
    longrun = [{"year": y, "trap": summ[y].get("trap"), "total": summ[y].get("total")} for y in sorted(summ) if y >= 2009]

    # ---- bribe amounts and accused per case (trap cases)
    bribe = []
    for y in years:
        t = full[y]["trap_totals"]
        bribe.append({"year": y, "cases": t["cases"], "accused": t["accused"], "amount": t["amount"],
                      "avg_per_case": round(t["amount"] / t["cases"]), "accused_per_case": round(t["accused"] / t["cases"], 2),
                      "private_pct": round(100 * t["private"] / t["accused"], 1),
                      "senior_pct": round(100 * (t["c1"] + t["c2"]) / t["accused"], 1)})

    # ---- region trend (trap cases). Prefer a yearly file's region table; for years without one
    #      (2022, 2024, 2025) fall back to the case-status snapshot, which has the same regional counts.
    cur_year = date.today().year
    regs = ["Mumbai", "Thane", "Pune", "Nashik", "Nagpur", "Amravati", "Chh. Sambhajinagar", "Nanded"]
    by_year: dict[int, dict[str, int]] = {}
    for ys, rec in hist["yearly"].items():
        y = int(ys)
        r = rec.get("regions") or {}
        if r and "trap_cases" in next(iter(r.values())) and (y == cur_year or sum(v["trap_cases"] for v in r.values()) == summ.get(y, {}).get("trap")):
            by_year[y] = {k: v["trap_cases"] for k, v in r.items()}
    for ys, rec in hist["pipeline"].items():
        y = int(ys)
        r = rec.get("regions") or {}
        if y not in by_year and r and (y == cur_year or sum(v["trap"] for v in r.values()) == summ.get(y, {}).get("trap")):
            by_year[y] = {k: v["trap"] for k, v in r.items()}
    ry_years = sorted(by_year)
    region_trend = {"years": ry_years, "regions": regs,
                    "trap_cases": [[by_year[y].get(r, 0) for y in ry_years] for r in regs]}

    # ---- department trend (complete years only)
    tot_by_dept: Counter = Counter()
    for y in years:
        for d in full[y]["trap_by_dept"]:
            tot_by_dept[d["dept"]] += d["cases"]
    top = [d for d, _ in tot_by_dept.most_common(8)]
    dept_trend = {"years": years, "depts": top,
                  "cases": [[next((d["cases"] for d in full[y]["trap_by_dept"] if d["dept"] == name), 0) for y in years] for name in top],
                  "avg_bribe": [[(lambda r: round(r["amount"] / r["cases"]) if r and r["cases"] else None)(
                      next((d for d in full[y]["trap_by_dept"] if d["dept"] == name), None)) for y in years] for name in top]}

    # ---- class mix of accused in trap cases
    class_mix = {"years": years, "classes": CLASS_KEYS,
                 "pct": [[round(100 * full[y]["trap_totals"][k] / full[y]["trap_totals"]["accused"], 1) for y in years] for k in CLASS_KEYS]}

    # ---- convictions
    conv = []
    for ys in sorted(hist["conviction"], key=int):
        c = hist["conviction"][ys]
        t = c.get("totals")
        if not t:
            continue
        y = int(ys)
        age = c.get("age_at_conviction")
        traps = summ.get(y, {}).get("trap")
        conv.append({"year": y, "cases": t["cases"], "accused": t["accused"], "fine": t["fine"],
                     "fine_per_accused": round(t["fine"] / t["accused"]) if t["accused"] else None,
                     "partial": y == date.today().year,
                     "per_100_traps": round(100 * t["cases"] / traps, 1) if traps else None,
                     "by_dept_complete": sum(d["cases"] for d in c["by_dept"]) == t["cases"],
                     "senior_pct": round(100 * (t["c1"] + t["c2"]) / t["accused"], 1) if t["accused"] else None,
                     "age": age})
    latest_conv = next((c for c in reversed(conv) if c["by_dept_complete"] and not c["partial"]), None)
    conv_dept = None
    if latest_conv:
        rows = hist["conviction"][str(latest_conv["year"])]["by_dept"]
        conv_dept = {"year": latest_conv["year"], "rows": sorted(rows, key=lambda r: -r["cases"])}

    # ---- pipeline: status of cases by registration year (snapshot as of last ACB update)
    pipe = []
    for ys in sorted(hist["pipeline"], key=int):
        p = hist["pipeline"][ys]
        t = p.get("totals")
        if not t or not p.get("regions"):
            continue
        n = t["total"]
        sp = t["sanction_pending_govt"] + t["sanction_pending_competent"]
        pipe.append({"year": int(ys), "registered": n, "investigation_pending": t["investigation_pending"],
                     "sanction_pending": sp, "sanction_received": t["sanction_received"],
                     "chargesheet_filed": t["chargesheet_filed"],
                     "pending_inv_pct": round(100 * t["investigation_pending"] / n, 1),
                     "chargesheet_pct": round(100 * t["chargesheet_filed"] / n, 1),
                     "partial": int(ys) == date.today().year})
    pipe_regions = None
    if pipe:
        pr = hist["pipeline"][str(pipe[-1]["year"])]["regions"]
        pipe_regions = [{"region": r, **v, "pending_inv_pct": round(100 * v["investigation_pending"] / v["total"], 1) if v["total"] else 0}
                        for r, v in sorted(pr.items(), key=lambda kv: -kv[1]["investigation_pending"] / max(kv[1]["total"], 1))]

    # ---- sanction backlog
    san = None
    sp = hist["sanction_pending"].get(str(date.today().year)) or (hist["sanction_pending"] or {}).get(max(hist["sanction_pending"], default="0"))
    if sp and sp.get("totals") and sp.get("rows"):
        t = sp["totals"]
        san = {"year": sp["year"], "totals": t, "over_90_pct": round(100 * t["over_90"] / t["total"], 1),
               "competent_pct": round(100 * t["with_competent"] / t["total"], 1),
               "rows": sorted([r for r in sp["rows"] if r["total"]], key=lambda r: -r["total"])}

    return {"longrun": longrun, "bribe": bribe, "region_trend": region_trend, "dept_trend": dept_trend,
            "class_mix": class_mix, "convictions": conv, "conviction_dept": conv_dept, "pipeline": pipe,
            "pipeline_regions": pipe_regions, "sanction": san,
            "conflicts": [{"year": y, "field": k, "old": o, "new": n, "file_year": f} for y, k, o, n, f in hist.get("_conflicts", [])],
            "complete_years": years}


def main() -> None:
    recs = json.loads((DATA / "records.json").read_text(encoding="utf-8"))["records"]
    hist = load_history()
    stats = build_stats(hist)
    (DATA / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
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
        "official": official(hist, merged_summary(hist)),
    }
    a["insights"] = insights(a, stats)
    (DATA / "analytics.json").write_text(json.dumps(a, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote analytics.json;", len(uniq), "unique cases from", len(recs), "postings")
    for line in a["insights"]:
        print("-", line)


if __name__ == "__main__":
    main()
