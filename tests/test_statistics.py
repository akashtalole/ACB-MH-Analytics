import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import parse_statistics as ps
import build_analytics as ba


class Names(unittest.TestCase):
    def test_regions(self):
        self.assertEqual(ps.region_en("ukansM"), "Nanded")
        self.assertEqual(ps.region_en("N=irh laHkkthuxj"), "Chh. Sambhajinagar")
        self.assertIsNone(ps.region_en("garbled"))

    def test_departments(self):
        self.assertEqual(ps.dept_en("eglqy@Hkqeh vfHkys[k@uksan.kh"), "Revenue / Land Records / Registration")
        self.assertEqual(ps.dept_en("iksyhl"), "Police")
        self.assertEqual(ps.dept_en("foHkkx iksyhl"), "Police")  # leading word "foHkkx" is ignored
        self.assertIsNone(ps.dept_en("zzz unknown"))


class Rows(unittest.TestCase):
    def test_to_int(self):
        self.assertEqual(ps.to_int("1,32,24,691"), 13224691)
        self.assertEqual(ps.to_int(""), 0)
        self.assertEqual(ps.to_int("--"), 0)
        self.assertIsNone(ps.to_int("abc"))

    def test_glued_digit_in_word(self):
        self.assertEqual(ps.glued_number("foHkk1x"), "1")
        self.assertEqual(ps.glued_number("oHkkx3"), "3")
        self.assertIsNone(ps.glued_number("foHkkx"))
        self.assertIsNone(ps.glued_number("police"))

    def test_row_with_glued_count_is_recovered(self):
        row = ["42", "lkekftd U;k; o fo'ks\"k lgk¸;", "foHkk1x", "0", "1", "0", "0", "0", "0", "1", "25000", ""]
        label, nums = ps.row_nums(row, 9)
        self.assertEqual(nums, [1, 0, 1, 0, 0, 0, 0, 1, 25000])

    def test_blank_cells_are_zero(self):
        row = ["1", "iksyhl", "11", "2", "", "10", "", "", "1", "13", "326000"]
        _, nums = ps.row_nums(row, 9)
        self.assertEqual(nums, [11, 2, 0, 10, 0, 0, 1, 13, 326000])

    def test_header_rows_rejected(self):
        self.assertIsNone(ps.row_nums(["", "", "", "1", "2", "3"], 3))


class MergedSummary(unittest.TestCase):
    def test_newest_wins_unless_total_disagrees(self):
        hist = {"yearly": {
            "2014": {"summary": {2011: {"trap": 479, "da": 15, "other": 18, "total": 512}}},
            "2020": {"summary": {2011: {"trap": 437, "da": 10, "other": 16, "total": 512}}},  # typo, sums to 463
        }}
        out = ba.merged_summary(hist)
        self.assertEqual((out[2011]["trap"], out[2011]["da"], out[2011]["other"]), (479, 15, 18))
        self.assertTrue(hist["_conflicts"])

    def test_newest_kept_when_consistent(self):
        hist = {"yearly": {
            "2015": {"summary": {2014: {"trap": 1245, "da": 48, "other": 23, "total": 1316}}},
            "2018": {"summary": {2014: {"trap": 1245, "da": 49, "other": 22, "total": 1316}}},
        }}
        out = ba.merged_summary(hist)
        self.assertEqual(out[2014]["da"], 49)  # newest, and it still sums to the printed total


if __name__ == "__main__":
    unittest.main()
