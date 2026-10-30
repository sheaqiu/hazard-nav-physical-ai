import math
import unittest

from hazard_nav.scan_geometry import summarize_scan


class ScanGeometryTest(unittest.TestCase):
    def test_extracts_front_and_side_sectors(self):
        count = 360
        ranges = [4.0] * count
        ranges[0] = 0.42
        for index in range(80, 101):
            ranges[index] = 0.55
        for index in range(260, 281):
            ranges[index] = 0.65
        scan = summarize_scan(
            ranges,
            angle_min=0.0,
            angle_increment=2.0 * math.pi / count,
            range_max=4.0,
        )
        self.assertAlmostEqual(scan.front_m, 0.42)
        self.assertLessEqual(scan.left_m, 0.55)
        self.assertLessEqual(scan.right_m, 0.65)


if __name__ == "__main__":
    unittest.main()

