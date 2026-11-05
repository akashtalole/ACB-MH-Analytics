#!/usr/bin/env python3
"""Build data/stats.json from the ACB Maharashtra official statistics PDF
("वर्षनिहाय सापळा, अपसंपदा व अन्य भ्रष्टाचार प्रकरणांची माहिती", 01-01-2026 to 02-11-2026).

The PDF is a Marathi scan with Devanagari numerals, so the figures below were
transcribed by hand from the rendered pages. Every table is cross-checked
against the totals printed in the PDF; run this script to re-verify. Where the
PDF's own totals do not reconcile with its rows, that is recorded in
`notes` instead of being silently "fixed".

To load a newer statistics PDF, replace the tables below and re-run.
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "stats.json"
AS_OF = "2026-11-02"
PERIOD = {"from": "2026-01-01", "to": AS_OF}
SOURCE = "ACB Maharashtra — statistics PDF supplied by the maintainer (period 01-01-2026 to 02-11-2026)"

YEARS = list(range(2014, 2027))  # 2026 = year to date
TRAP = [1245, 1234, 985, 875, 891, 866, 630, 764, 728, 795, 683, 669, 609]
DA = [48, 35, 17, 22, 22, 20, 12, 7, 12, 12, 31, 9, 11]
OTHER = [23, 10, 14, 28, 23, 5, 21, 2, 9, 5, 7, 2, 12]
TOTAL = [1316, 1279, 1016, 925, 936, 891, 663, 773, 749, 812, 721, 680, 632]

# region: (trap cases, trap accused, DA cases, DA accused, other cases, other accused)
REGIONS = {
    "Mumbai": (32, 49, 1, 1, 1, 9),
    "Thane": (81, 112, 1, 2, 0, 0),
    "Pune": (106, 149, 4, 7, 0, 0),
    "Nashik": (126, 203, 1, 2, 1, 1),
    "Nagpur": (57, 82, 2, 3, 7, 43),
    "Amravati": (62, 87, 0, 0, 3, 15),
    "Chh. Sambhajinagar": (97, 128, 0, 0, 0, 0),
    "Nanded": (48, 61, 2, 4, 0, 0),
}
REGIONS_PUBLISHED_TOTAL = (609, 871, 11, 19, 12, 68)

# Trap cases by department: (en, mr, cases, c1, c2, c3, c4, other_public_servants, private, accused, amount_rs)
# c1..c4 = Class 1-4 government servants; "other" = इलोसे; "private" = खाजगी व्यक्ती.
TRAP_DEPTS = [
    ("Revenue / Land Records / Registration", "महसूल/भूमी अभिलेख/नोंदणी", 148, 8, 10, 115, 10, 15, 46, 204, 4016730),
    ("Police", "पोलीस", 98, 5, 25, 96, 0, 4, 21, 151, 7304200),
    ("MSEDCL (power distribution)", "म.रा.वि.वि.कं.मर्यादित", 42, 4, 10, 14, 10, 5, 6, 49, 1475900),
    ("Municipal Corporation", "महानगर पालिका", 32, 4, 10, 23, 2, 2, 6, 47, 1448000),
    ("Nagar Palika", "नगर पालिका", 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ("Nagar Parishad", "नगर परिषद", 10, 1, 1, 3, 0, 6, 2, 13, 424000),
    ("Zilla Parishad", "जिल्हा परिषद", 19, 5, 1, 19, 1, 2, 5, 33, 1110400),
    ("Panchayat Samiti", "पंचायत समिती", 63, 0, 1, 38, 4, 28, 9, 80, 2074300),
    ("Forest", "वन विभाग", 25, 2, 4, 30, 3, 1, 6, 46, 5386900),
    ("Animal Husbandry, Dairy & Fisheries", "प.दु.म. विभाग", 3, 2, 1, 1, 0, 0, 1, 5, 80000),
    ("Food & Civil Supplies", "अन्न व नागरी पुरवठा", 4, 0, 0, 3, 0, 1, 0, 4, 43700),
    ("Water Resources", "जलसंपदा विभाग", 9, 4, 0, 6, 0, 0, 0, 10, 390300),
    ("Public Health", "सार्वजनिक आरोग्य विभाग", 23, 4, 4, 12, 2, 4, 4, 30, 637300),
    ("State Excise", "राज्य उत्पादन शुल्क", 2, 0, 1, 1, 0, 0, 0, 2, 250000),
    ("Tribal Development", "आदिवासी विकास", 1, 0, 0, 1, 0, 0, 0, 1, 23350),
    ("Regional Transport (RTO)", "प्रादेशिक परिवहन विभाग", 13, 2, 1, 4, 0, 0, 11, 18, 103600),
    ("Water Supply", "पाणीपुरवठा विभाग", 2, 2, 1, 0, 0, 0, 0, 3, 230000),
    ("Public Works", "सार्वजनिक बांधकाम विभाग", 9, 3, 4, 3, 1, 0, 1, 12, 2242000),
    ("Sales Tax / GST", "विक्रीकर विभाग", 10, 3, 7, 2, 0, 0, 3, 15, 2186000),
    ("Law & Judiciary", "विधी व न्याय विभाग", 2, 1, 0, 1, 0, 0, 0, 2, 10000),
    ("Industries, Energy & Labour", "उद्योग, ऊर्जा व कामगार विभाग", 4, 0, 0, 1, 0, 1, 2, 4, 22400),
    ("Social Welfare", "समाज कल्याण विभाग", 10, 1, 1, 6, 0, 6, 1, 15, 359500),
    ("Town Planning", "नगर रचना विभाग", 3, 2, 3, 2, 0, 0, 1, 8, 150000),
    ("Finance", "वित्त विभाग", 3, 0, 2, 5, 0, 0, 0, 7, 66000),
    ("Cooperation & Marketing", "सहकार व पणन विभाग", 12, 1, 2, 6, 0, 4, 7, 20, 357500),
    ("Education", "शिक्षण विभाग", 29, 2, 8, 24, 3, 6, 6, 49, 1085790),
    ("Sports", "क्रीडा विभाग", 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ("Food & Drugs", "अन्न व औषधी द्रव्ये विभाग", 2, 1, 1, 1, 0, 0, 0, 3, 0),
    ("Agriculture", "कृषी विभाग", 15, 1, 4, 11, 0, 1, 3, 20, 375900),
    ("State Transport (ST)", "राज्य परिवहन विभाग", 3, 0, 0, 2, 0, 0, 1, 3, 400102),
    ("Other departments", "इतर विभाग", 3, 0, 1, 0, 0, 1, 2, 4, 639400),
    ("CIDCO", "सिडको विभाग", 1, 0, 0, 1, 0, 0, 1, 2, 200000),
    ("Women & Child Development", "महिला व बाल विकास विभाग", 4, 0, 0, 4, 0, 1, 1, 6, 77000),
    ("Mahatma Phule Backward Class Corp.", "महात्मा फुले मागासवर्गीय", 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ("MHADA", "म्हाडा विभाग", 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ("MIDC", "महाराष्ट्र औद्योगिक वि.मंडल", 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ("Pollution Control Board", "प्रदुषण नियंत्रण मंडळ", 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ("BEST", "बेस्ट", 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ("Weights & Measures", "वजन व मापे विभाग", 1, 0, 1, 0, 0, 0, 0, 1, 24000),
    ("Higher & Technical Education", "उच्च व तंत्र शिक्षण विभाग", 1, 1, 0, 0, 0, 0, 0, 1, 0),
    ("Skill Development", "कौशल्य विकास विभाग", 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ("Social Justice & Special Assistance", "सामाजिक न्याय व विशेष सहाय्य", 1, 0, 1, 0, 0, 0, 0, 1, 25000),
    ("Ports", "बंदर विभाग", 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ("Prisons", "कारागृह विभाग", 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ("Nagpur Improvement Trust", "नागपूर सुधार प्रन्यास विभाग", 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ("Charity Commissioner", "धर्मादाय आयुक्त", 1, 0, 1, 0, 0, 0, 0, 1, 0),
    ("Silk Industries", "रेशीम उद्योग विभाग", 1, 0, 0, 1, 0, 0, 0, 1, 5000),
]
TRAP_DEPTS_PUBLISHED_TOTAL = (609, 59, 106, 436, 36, 88, 146, 871, 33198072)

# Disproportionate-assets cases by department; same columns, amount = assets found (Rs).
DA_DEPTS = [
    ("Revenue / Land Records / Registration", "महसूल/भूमी अभिलेख/नोंदणी", 3, 1, 0, 2, 0, 0, 2, 5, 16136070),
    ("Municipal Corporation", "महानगर पालिका", 2, 1, 0, 1, 0, 0, 0, 2, 14142497),
    ("Town Planning / Urban Development", "नगर विकास/नगर रचना विभाग", 1, 0, 1, 0, 0, 0, 1, 2, 27841942),
    ("Zilla Parishad", "जिल्हा परिषद", 1, 0, 0, 1, 0, 0, 1, 2, 8289614),
    ("Public Works", "सार्वजनिक बांधकाम विभाग", 1, 0, 0, 1, 0, 0, 1, 2, 9574851),
    ("Agriculture", "कृषी विभाग", 1, 1, 0, 0, 0, 0, 1, 2, 43784930),
    ("CIDCO", "सिडको विभाग", 1, 1, 0, 0, 0, 0, 1, 2, 19447905),
]
DA_PUBLISHED_TOTAL = (11, 5, 1, 5, 0, 0, 8, 19, 272299105)

# Other-corruption cases (accused by class: c1..c4, other, private)
OTHER_DEPTS = [
    ("Water Resources", "जलसंपदा विभाग", 10, 39, 0, 0, 0, 0, 14, 53, None),
    ("Agriculture", "कृषी विभाग", 1, 1, 0, 0, 0, 0, 0, 1, None),
    ("MHADA", "म्हाडा विभाग", 1, 9, 0, 0, 0, 0, 0, 9, None),
]
OTHER_PUBLISHED_TOTAL = (12, 49, 0, 0, 0, 0, 14, 63, None)

COLS = ["cases", "c1", "c2", "c3", "c4", "other", "private", "accused", "amount"]


def rows_as_dicts(rows):
    return [{"dept": r[0], "dept_mr": r[1], **dict(zip(COLS, r[2:]))} for r in rows]


def column_sums(rows):
    return tuple(sum((r[i] or 0) for r in rows) for i in range(2, 11))


def check(name, rows, published, notes):
    got = column_sums(rows)
    pub = tuple(0 if v is None else v for v in published)
    ok = got == pub
    for r in rows:  # internal consistency: class split must add up to accused
        assert sum(r[3:9]) == r[9], f"{name}: class split != accused for {r[0]}"
    if not ok:
        notes.append(
            f"{name}: department rows sum to {got} but the PDF's printed total row is {pub} "
            f"(cases, c1, c2, c3, c4, other, private, accused, amount; difference in amount "
            f"{got[8] - pub[8]:+,}). Both are kept; headline figures use the PDF's printed totals."
        )
    print(f"{name:<12} reconciles={ok}")
    return ok


def main() -> None:
    notes: list[str] = []

    for i, y in enumerate(YEARS):  # yearly table: cases = trap + DA + other
        assert TRAP[i] + DA[i] + OTHER[i] == TOTAL[i], f"yearly total mismatch {y}"

    reg_sum = tuple(sum(v[i] for v in REGIONS.values()) for i in range(6))
    assert reg_sum == REGIONS_PUBLISHED_TOTAL, (reg_sum, REGIONS_PUBLISHED_TOTAL)
    assert reg_sum[0] == TRAP[-1] and reg_sum[2] == DA[-1] and reg_sum[4] == OTHER[-1]

    check("trap", TRAP_DEPTS, TRAP_DEPTS_PUBLISHED_TOTAL, notes)
    check("disproportionate-assets", DA_DEPTS, DA_PUBLISHED_TOTAL, notes)
    check("other", OTHER_DEPTS, OTHER_PUBLISHED_TOTAL, notes)
    if OTHER_PUBLISHED_TOTAL[7] != REGIONS_PUBLISHED_TOTAL[5]:
        notes.append(
            f"Other-corruption accused is {REGIONS_PUBLISHED_TOTAL[5]} in the region table but "
            f"{OTHER_PUBLISHED_TOTAL[7]} in the department table; both are as printed in the PDF."
        )

    payload = {
        "source": SOURCE,
        "period": PERIOD,
        "as_of": AS_OF,
        "yearly": [
            {"year": y, "trap": TRAP[i], "da": DA[i], "other": OTHER[i], "total": TOTAL[i],
             "partial": y == YEARS[-1]}
            for i, y in enumerate(YEARS)
        ],
        "regions": [
            dict(region=k, trap_cases=v[0], trap_accused=v[1], da_cases=v[2], da_accused=v[3],
                 other_cases=v[4], other_accused=v[5])
            for k, v in REGIONS.items()
        ],
        "region_totals": dict(zip(
            ["trap_cases", "trap_accused", "da_cases", "da_accused", "other_cases", "other_accused"],
            REGIONS_PUBLISHED_TOTAL)),
        "trap_by_dept": rows_as_dicts(TRAP_DEPTS),
        "trap_totals": dict(zip(COLS, TRAP_DEPTS_PUBLISHED_TOTAL)),
        "da_by_dept": rows_as_dicts(DA_DEPTS),
        "da_totals": dict(zip(COLS, DA_PUBLISHED_TOTAL)),
        "other_by_dept": rows_as_dicts(OTHER_DEPTS),
        "other_totals": dict(zip(COLS, OTHER_PUBLISHED_TOTAL)),
        "notes": notes,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT)
    for n in notes:
        print("NOTE:", n)


if __name__ == "__main__":
    main()
