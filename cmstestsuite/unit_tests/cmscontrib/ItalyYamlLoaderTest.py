#!/usr/bin/env python3

"""Tests for helpers of the Italian YAML loader."""

import unittest

from cmscontrib.loaders.italy_yaml import normalize_testcase_codename


class TestNormalizeTestcaseCodename(unittest.TestCase):
    def test_numeric_codenames_are_padded(self):
        self.assertEqual(normalize_testcase_codename("0"), "000")
        self.assertEqual(normalize_testcase_codename(" 12 "), "012")
        self.assertEqual(normalize_testcase_codename("1234"), "1234")

    def test_non_numeric_codenames_are_kept(self):
        self.assertEqual(normalize_testcase_codename("7-01"), "7-01")
        self.assertEqual(normalize_testcase_codename(" p1-n3-06 "), "p1-n3-06")


if __name__ == "__main__":
    unittest.main()
