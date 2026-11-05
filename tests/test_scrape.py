import sys, unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import scrape_index as s

TODAY = date(2026, 11, 5)


class CleanDate(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(s.clean_date("04/11/2026", TODAY), ("2026-11-04", False))

    def test_zero_padded_year_is_repaired(self):
        self.assertEqual(s.clean_date("02/08/0021", TODAY), ("2021-08-02", True))

    def test_future_or_garbage_dropped(self):
        self.assertEqual(s.clean_date("01/01/2030", TODAY)[0], None)
        self.assertEqual(s.clean_date("", TODAY)[0], None)
        self.assertEqual(s.clean_date("31/02/2021", TODAY)[0], None)


class ParseTitle(unittest.TestCase):
    def test_cr_variants(self):
        for title, want in [
            ("ACB Mumbai C.R. No. 33 –2026", (33, 2026)),
            ("Killa P.S. Malegaon Cr No.187/2026", (187, 2026)),
            ("Police station Gadchandur CR. NO.510/26", (510, 2026)),
            ("Police Station Harsul, Aurangabad City  Crime No29/2021", (29, 2021)),
        ]:
            p = s.parse_title(title)
            self.assertEqual((p["cr_no"], p["cr_year"]), want, title)

    def test_region_navi_mumbai_is_thane(self):
        self.assertEqual(s.parse_title("Panvel PS, Navi Mumbai Cr No 1/2024")["region"], "Thane")
        self.assertEqual(s.parse_title("ACB Mumbai C.R. No. 5-2021")["region"], "Mumbai")

    def test_unknown_region_is_none(self):
        self.assertIsNone(s.parse_title("Police station Bhokar Cr No 571/2026")["region"])


if __name__ == "__main__":
    unittest.main()
