import asyncio
import json
import unittest

from fastapi import HTTPException

from backend.analysis import perform_goodness_of_fit_test
from backend.main import goodness_of_fit


class GoodnessOfFitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.categories = ["Maths", "Science", "English", "Computer"]
        self.observed = [20, 30, 25, 25]

    def test_equal_distribution_matches_example(self) -> None:
        result = perform_goodness_of_fit_test(
            self.categories,
            self.observed,
        )

        self.assertEqual(result["expected"], [25.0] * 4)
        self.assertAlmostEqual(result["chi_square"], 2.0)
        self.assertEqual(result["degrees_of_freedom"], 3)
        self.assertAlmostEqual(result["p_value"], 0.5724067044708798)
        self.assertEqual(result["alpha"], 0.05)
        self.assertFalse(result["significant"])
        self.assertIn("Fail to reject", result["conclusion"])

    def test_expected_frequencies_and_proportions_are_supported(self) -> None:
        frequencies = perform_goodness_of_fit_test(
            self.categories,
            self.observed,
            "frequencies",
            [20, 30, 25, 25],
        )
        proportions = perform_goodness_of_fit_test(
            self.categories,
            self.observed,
            "proportions",
            [0.2, 0.3, 0.25, 0.25],
        )

        self.assertEqual(frequencies["expected"], self.observed)
        self.assertEqual(proportions["expected"], self.observed)
        self.assertEqual(frequencies["chi_square"], 0.0)
        self.assertEqual(proportions["chi_square"], 0.0)

    def test_significant_difference_is_reported(self) -> None:
        result = perform_goodness_of_fit_test(
            self.categories,
            [10, 10, 10, 70],
        )

        self.assertTrue(result["significant"])
        self.assertLess(result["p_value"], result["alpha"])
        self.assertIn("Reject the null hypothesis", result["conclusion"])

    def test_invalid_inputs_are_rejected(self) -> None:
        invalid_cases = [
            (["Maths"], [20], "equal", None),
            (self.categories, [20, -1, 25, 56], "equal", None),
            (self.categories, [0, 0, 0, 0], "equal", None),
            (self.categories, self.observed, "frequencies", [30] * 4),
            (self.categories, self.observed, "proportions", [0.2] * 4),
            (self.categories, self.observed, "frequencies", [25, 25, 25, -5]),
            (self.categories, [1, 1, 1, 1], "equal", None),
            (["Maths", "Maths"], [50, 50], "equal", None),
        ]

        for categories, observed, mode, expected in invalid_cases:
            with self.subTest(mode=mode, categories=categories):
                with self.assertRaises(ValueError):
                    perform_goodness_of_fit_test(
                        categories,
                        observed,
                        mode,
                        expected,
                    )

    def test_api_returns_statistics_and_rejects_invalid_expected_totals(self) -> None:
        async def exercise_endpoint() -> None:
            result = await goodness_of_fit(
                categories=json.dumps(self.categories),
                observed_frequencies=json.dumps(self.observed),
                expected_mode="equal",
                expected_values=None,
            )
            self.assertEqual(result["categories"], self.categories)
            self.assertEqual(result["expected"], [25.0] * 4)
            self.assertEqual(result["degrees_of_freedom"], 3)

            with self.assertRaises(HTTPException) as error:
                await goodness_of_fit(
                    categories=json.dumps(self.categories),
                    observed_frequencies=json.dumps(self.observed),
                    expected_mode="frequencies",
                    expected_values=json.dumps([30] * 4),
                )
            self.assertEqual(error.exception.status_code, 400)
            self.assertIn("sum to the observed total", error.exception.detail)

        asyncio.run(exercise_endpoint())


if __name__ == "__main__":
    unittest.main()
