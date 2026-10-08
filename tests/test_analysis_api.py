import asyncio
from io import BytesIO
import unittest

import pandas as pd
from fastapi import UploadFile

from backend.analysis import (
    analyze_features,
    build_contingency_tables,
    is_categorical_column,
    is_identifier,
)
from backend.main import analyze_csv, inspect_csv, preview_csv


class CategoricalAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = pd.DataFrame(
            {
                "group_code": [1, 2, 1, 2, 3, 3] * 10,
                "measurement": list(range(60)),
                "outcome": ["A", "B", "A", "B", "C", "C"] * 10,
                "record_id": [f"r-{index}" for index in range(60)],
            }
        )

    def test_numeric_categories_are_detected_and_measurements_are_not(self) -> None:
        self.assertTrue(is_categorical_column("group_code", self.data))
        self.assertFalse(is_categorical_column("measurement", self.data))
        self.assertTrue(is_identifier("record_id", self.data))

    def test_selected_numeric_category_is_analyzed(self) -> None:
        results = analyze_features(
            self.data,
            "outcome",
            ["group_code", "measurement", "outcome", "record_id"],
        )
        self.assertEqual(results["Feature"].tolist(), ["group_code"])
        self.assertEqual(results.iloc[0]["Rows used"], 60)
        self.assertEqual(results.iloc[0]["Rows excluded"], 0)
        self.assertTrue(results.iloc[0]["Test reliable"])

    def test_bias_corrected_cramers_v_does_not_overstate_small_samples(self) -> None:
        small_data = pd.DataFrame(
            {"feature": ["A", "A", "B", "B"], "target": ["X", "Y", "X", "Y"]}
        )
        result = analyze_features(small_data, "target", ["feature", "target"])
        self.assertEqual(result.iloc[0]["Cramér's V"], 0.0)

    def test_sparse_expected_counts_mark_chi_square_result_as_unreliable(self) -> None:
        sparse_data = pd.DataFrame(
            {
                "feature": ["common"] * 10 + ["rare"],
                "target": ["A"] * 5 + ["B"] * 5 + ["A"],
            }
        )
        result = analyze_features(sparse_data, "target", ["feature", "target"])
        self.assertGreater(result.iloc[0]["Expected cells < 1 (%)"], 0)
        self.assertFalse(result.iloc[0]["Test reliable"])

    def test_pairwise_missing_values_are_reported(self) -> None:
        data = self.data.copy()
        data.loc[0, "group_code"] = None
        result = analyze_features(data, "outcome", ["group_code", "outcome"])
        self.assertEqual(result.iloc[0]["Rows used"], 59)
        self.assertEqual(result.iloc[0]["Rows excluded"], 1)

    def test_contingency_tables_include_observed_and_expected_counts(self) -> None:
        tables = build_contingency_tables(self.data, "group_code", "outcome")
        self.assertEqual(sum(map(sum, tables["observed"])), 60)
        self.assertAlmostEqual(sum(map(sum, tables["expected"])), 60)
        self.assertEqual(len(tables["row_labels"]), 3)

    def test_dataset_preview_includes_all_columns_and_paginates_every_row(self) -> None:
        csv_bytes = self.data.to_csv(index=False).encode("utf-8")

        async def exercise_preview() -> None:
            inspected = await inspect_csv(
                UploadFile(filename="complete.csv", file=BytesIO(csv_bytes))
            )
            self.assertEqual(len(inspected["preview"]), 50)
            self.assertEqual(
                set(inspected["preview"][0]),
                {"group_code", "measurement", "outcome", "record_id"},
            )

            last_page = await preview_csv(
                UploadFile(filename="complete.csv", file=BytesIO(csv_bytes)),
                page=2,
                page_size=50,
            )
            self.assertEqual(len(last_page["rows"]), 10)
            self.assertEqual(last_page["row_start"], 51)
            self.assertEqual(last_page["row_end"], 60)
            self.assertEqual(last_page["rows"][-1]["measurement"], 59)

        asyncio.run(exercise_preview())

    def test_inspect_and_analyze_endpoints_accept_uploaded_csv(self) -> None:
        csv_bytes = (
            b"group_code,measurement,outcome,record_id\n"
            b"1,10,A,r-1\n"
            b"2,11,B,r-2\n"
            b"1,12,A,r-3\n"
            b"2,13,B,r-4\n"
            b"3,14,C,r-5\n"
            b"3,15,C,r-6\n"
        )

        async def exercise_endpoints() -> None:
            inspected = await inspect_csv(
                UploadFile(filename="sample.csv", file=BytesIO(csv_bytes))
            )
            self.assertEqual(inspected["row_count"], 6)
            self.assertTrue(inspected["columns"][0]["categorical"])
            self.assertEqual(inspected["preview_page_size"], 50)
            self.assertEqual(inspected["preview"][0]["group_code"], 1)

            paged = await preview_csv(
                UploadFile(filename="sample.csv", file=BytesIO(csv_bytes)),
                page=1,
                page_size=2,
            )
            self.assertEqual(paged["page_count"], 3)
            self.assertEqual(paged["row_start"], 1)
            self.assertEqual(paged["row_end"], 2)
            self.assertEqual(len(paged["rows"]), 2)
            second_page = await preview_csv(
                UploadFile(filename="sample.csv", file=BytesIO(csv_bytes)),
                page=3,
                page_size=2,
            )
            self.assertEqual(second_page["row_start"], 5)
            self.assertEqual(second_page["row_end"], 6)

            analyzed = await analyze_csv(
                UploadFile(filename="sample.csv", file=BytesIO(csv_bytes)),
                target="outcome",
                categorical_columns='["group_code","outcome"]',
            )
            self.assertEqual(analyzed["features_tested"], 1)
            self.assertEqual(analyzed["significant_count"], 1)
            self.assertEqual(analyzed["reliable_significant_count"], 0)
            self.assertEqual(analyzed["results"][0]["feature"], "group_code")
            self.assertEqual(analyzed["results"][0]["rows_excluded"], 0)
            self.assertFalse(analyzed["results"][0]["test_reliable"])
            self.assertIn("observed", analyzed["results"][0]["contingency"])

        asyncio.run(exercise_endpoints())


if __name__ == "__main__":
    unittest.main()
