import unittest
from astra.grounding import box_center


class GroundingTests(unittest.TestCase):
    def test_asymmetric_scaling(self):
        self.assertEqual(box_center([700, 200, 800, 300], 1920, 1080), (1440, 270))

    def test_edge(self):
        self.assertEqual(box_center([999, 999, 1000, 1000], 800, 600), (799, 599))

    def test_bad_boxes_stop(self):
        for box in [None, [], [0, 0, 1920, 1080], [30, 10, 20, 15], [1., 2, 3, 4]]:
            with self.assertRaises(ValueError):
                box_center(box, 1920, 1080)
