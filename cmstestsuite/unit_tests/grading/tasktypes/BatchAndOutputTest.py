#!/usr/bin/env python3

"""Tests for the BatchAndOutput task type parameters."""

import unittest

from cms.grading.tasktypes.BatchAndOutput import BatchAndOutput


class TestBatchAndOutputParameters(unittest.TestCase):
    def test_full_parameters(self):
        tt = BatchAndOutput(["grader", ["", ""], "comparator", 4, "000,001"])
        self.assertEqual(tt.realprec_exp, 4)
        self.assertEqual(tt.output_only_testcases, {"000", "001"})

    def test_parameters_without_exponent(self):
        # Parameters imported before the real precision exponent existed lack
        # it, and must still be usable.
        tt = BatchAndOutput(["grader", ["", ""], "comparator", "000,001"])
        self.assertEqual(tt.realprec_exp, 6)
        self.assertEqual(tt.output_only_testcases, {"000", "001"})

    def test_parameters_without_exponent_nor_output_only(self):
        tt = BatchAndOutput(["grader", ["", ""], "comparator", ""])
        self.assertEqual(tt.realprec_exp, 6)
        self.assertEqual(tt.output_only_testcases, {""})


if __name__ == "__main__":
    unittest.main()
