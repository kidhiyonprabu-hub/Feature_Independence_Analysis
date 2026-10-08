import pandas as pd
from scipy.stats import chi2_contingency


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
