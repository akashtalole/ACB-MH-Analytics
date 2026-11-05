import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_analytics as a


def rec(kind, date, cr, region, title="x"):
    return {"kind": kind, "date": date, "cr_no": cr, "cr_year": 2024 if cr else None, "region": region, "title": title}


class UniqueCases(unittest.TestCase):
    def test_fir_and_press_for_same_case_merge(self):
        u = a.unique_cases([rec("fir", "2024-03-05", 12, "Pune"), rec("press_release", "2024-03-04", 12, "Pune")])
        self.assertEqual(len(u), 1)
        self.assertEqual(u[0]["date"], "2024-03-04")  # earliest posting

    def test_different_regions_do_not_merge(self):
        u = a.unique_cases([rec("fir", "2024-03-05", 12, "Pune"), rec("fir", "2024-03-05", 12, "Nashik")])
        self.assertEqual(len(u), 2)

    def test_pre_launch_dates_ignored(self):
        self.assertEqual(a.unique_cases([rec("fir", "2012-01-01", 1, "Pune")]), [])


class Trend(unittest.TestCase):
    def test_linear_decline(self):
        stats = {"yearly": [{"year": 2020 + i, "trap": 100 - 10 * i, "partial": False} for i in range(5)]
                 + [{"year": 2025, "trap": 40, "partial": True}]}
        t = a.trend(stats)
        self.assertEqual(t["slope_per_year"], -10.0)
        self.assertEqual(t["r2"], 1.0)


if __name__ == "__main__":
    unittest.main()
