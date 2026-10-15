import math

import pandas as pd
from scipy.stats import chi2_contingency, chisquare


def is_identifier(column: str, data: pd.DataFrame) -> bool:
    normalized_name = column.strip().lower().replace("-", "_").replace(" ", "_")
    return (
        normalized_name == "id"
        or normalized_name.endswith("_id")
        or (len(data) > 1 and data[column].nunique(dropna=True) == len(data))
    )


def is_categorical_column(column: str, data: pd.DataFrame) -> bool:
    dtype = data[column].dtype
    if (
        pd.api.types.is_object_dtype(dtype)
        or pd.api.types.is_string_dtype(dtype)
        or pd.api.types.is_bool_dtype(dtype)
        or isinstance(dtype, pd.CategoricalDtype)
    ):
        return True

    if pd.api.types.is_numeric_dtype(dtype):
        unique_values = data[column].nunique(dropna=True)
        max_categorical_values = min(50, max(10, int(len(data) ** 0.5)))
        return 1 < unique_values <= max_categorical_values

    return False


def cramers_v(chi2: float, sample_size: int, rows: int, columns: int) -> float:
    if sample_size <= 1:
        return 0.0

    phi_squared = chi2 / sample_size
    correction = ((rows - 1) * (columns - 1)) / (sample_size - 1)
    phi_squared_corrected = max(0.0, phi_squared - correction)
    rows_corrected = rows - ((rows - 1) ** 2) / (sample_size - 1)
    columns_corrected = columns - ((columns - 1) ** 2) / (sample_size - 1)
    denominator = min(rows_corrected - 1, columns_corrected - 1)
    return (
        (phi_squared_corrected / denominator) ** 0.5
        if denominator > 0
        else 0.0
    )


def analyze_features(
    data: pd.DataFrame,
    target: str,
    categorical_columns: list[str],
) -> pd.DataFrame:
    results = []
    for feature in categorical_columns:
        if feature == target or is_identifier(feature, data):
            continue

        pair_data = data[[feature, target]].dropna()
        observed = pd.crosstab(pair_data[feature], pair_data[target])
        if len(pair_data) == 0 or observed.shape[0] < 2 or observed.shape[1] < 2:
            continue

        chi2, p_value, degrees_of_freedom, expected = chi2_contingency(observed)
        expected_below_5_percent = (expected < 5).mean() * 100
        expected_below_1_percent = (expected < 1).mean() * 100
        results.append(
            {
                "Feature": feature,
                "Chi-Square": chi2,
                "p-value": p_value,
                "Degrees of freedom": degrees_of_freedom,
                "Cramér's V": cramers_v(
                    chi2,
                    len(pair_data),
                    observed.shape[0],
                    observed.shape[1],
                ),
                "Rows used": len(pair_data),
                "Rows excluded": len(data) - len(pair_data),
                "Expected cells < 5 (%)": expected_below_5_percent,
                "Expected cells < 1 (%)": expected_below_1_percent,
                "Test reliable": (
                    expected_below_1_percent == 0
                    and expected_below_5_percent <= 20
                ),
            }
        )

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df["Adjusted p-value"] = (
            results_df["p-value"] * len(results_df)
        ).clip(upper=1.0)
        results_df["Result"] = results_df["Adjusted p-value"].apply(
            lambda value: "Significant" if value < 0.05 else "Not significant"
        )
        results_df = results_df.sort_values("p-value").reset_index(drop=True)
    return results_df


def build_contingency_tables(
    data: pd.DataFrame,
    feature: str,
    target: str,
) -> dict[str, object]:
    pair_data = data[[feature, target]].dropna()
    observed = pd.crosstab(pair_data[feature], pair_data[target])
    _, _, _, expected = chi2_contingency(observed)
    return {
        "row_labels": [str(value) for value in observed.index],
        "column_labels": [str(value) for value in observed.columns],
        "observed": observed.values.tolist(),
        "expected": expected.tolist(),
    }


def perform_goodness_of_fit_test(
    categories: list[str],
    observed: list[float],
    expected_mode: str = "equal",
    expected_values: list[float] | None = None,
) -> dict[str, object]:
    if len(categories) < 2:
        raise ValueError("Enter at least two categories.")
    if any(not isinstance(category, str) or not category.strip() for category in categories):
        raise ValueError("Category names must not be empty.")

    normalized_categories = [category.strip() for category in categories]
    if len(set(normalized_categories)) != len(normalized_categories):
        raise ValueError("Category names must be unique.")
    if len(observed) != len(normalized_categories):
        raise ValueError("Enter one observed frequency for each category.")

    def validated_values(values: list[float], label: str) -> list[float]:
        parsed = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{label} must contain numeric values.")
            try:
                numeric_value = float(value)
            except OverflowError as error:
                raise ValueError(f"{label} must contain finite values.") from error
            if not math.isfinite(numeric_value):
                raise ValueError(f"{label} must contain finite values.")
            if numeric_value < 0:
                raise ValueError(f"{label} must be non-negative.")
            parsed.append(numeric_value)
        return parsed

    observed_values = validated_values(observed, "Observed frequencies")
    observed_total = sum(observed_values)
    if not math.isfinite(observed_total):
        raise ValueError("Observed frequencies must have a finite total.")
    if observed_total <= 0:
        raise ValueError("The observed frequencies must have a positive total.")

    if expected_mode == "equal":
        expected_frequencies = [observed_total / len(normalized_categories)] * len(
            normalized_categories
        )
    elif expected_mode in {"frequencies", "proportions"}:
        if expected_values is None:
            raise ValueError("Enter expected values for every category.")
        if len(expected_values) != len(normalized_categories):
            raise ValueError("Enter one expected value for each category.")
        values = validated_values(expected_values, "Expected values")
        if expected_mode == "frequencies":
            expected_total = sum(values)
            if not math.isfinite(expected_total):
                raise ValueError("Expected frequencies must have a finite total.")
            if not math.isclose(
                expected_total, observed_total, rel_tol=1e-8, abs_tol=1e-8
            ):
                raise ValueError(
                    "Expected frequencies must sum to the observed total."
                )
            expected_frequencies = values
        else:
            proportions_total = sum(values)
            if not math.isfinite(proportions_total):
                raise ValueError("Expected proportions must have a finite total.")
            if not math.isclose(
                proportions_total, 1.0, rel_tol=1e-8, abs_tol=1e-8
            ):
                raise ValueError("Expected proportions must sum to 1.")
            expected_frequencies = [value * observed_total for value in values]
    else:
        raise ValueError(
            "Expected mode must be equal, frequencies, or proportions."
        )

    if any(value <= 0 for value in expected_frequencies):
        raise ValueError("Expected frequencies must be greater than zero.")
    if any(value < 5 for value in expected_frequencies):
        raise ValueError(
            "Each expected frequency must be at least 5 for the Chi-Square approximation."
        )

    statistic, p_value = chisquare(
        f_obs=observed_values,
        f_exp=expected_frequencies,
    )
    alpha = 0.05
    significant = bool(p_value < alpha)
    conclusion = (
        "Reject the null hypothesis: the observed frequencies differ significantly "
        "from the expected distribution."
        if significant
        else "Fail to reject the null hypothesis: there is not enough evidence that "
        "the observed frequencies differ from the expected distribution."
    )

    return {
        "categories": normalized_categories,
        "observed": observed_values,
        "expected": expected_frequencies,
        "chi_square": float(statistic),
        "degrees_of_freedom": len(normalized_categories) - 1,
        "p_value": float(p_value),
        "alpha": alpha,
        "significant": significant,
        "conclusion": conclusion,
        "expected_mode": expected_mode,
    }
