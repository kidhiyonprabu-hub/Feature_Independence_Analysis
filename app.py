import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from scipy.stats import chi2_contingency

from backend.analysis import analyze_features, is_categorical_column, is_identifier


st.set_page_config(
    page_title="Feature Independence Analysis",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #f6f8ff 0%, #eef8ff 55%, #f4fff9 100%);
        color: #172033;
    }
    .stApp [data-testid="stMarkdownContainer"],
    .stApp [data-testid="stMarkdownContainer"] p,
    .stApp [data-testid="stMarkdownContainer"] h1,
    .stApp [data-testid="stMarkdownContainer"] h2,
    .stApp [data-testid="stMarkdownContainer"] h3,
    .stApp [data-testid="stMarkdownContainer"] strong,
    .stApp label,
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stMetricLabel"],
    .stApp [data-testid="stMetricValue"] {
        color: #172033 !important;
    }
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #ffffff, #f0f5ff);
        border: 1px solid #dce6ff;
        padding: 16px;
        border-radius: 16px;
        box-shadow: 0 5px 18px rgba(49, 75, 145, 0.08);
    }
    .hero {
        background: linear-gradient(110deg, #4338ca, #087e8b);
        color: white;
        padding: 25px 30px;
        border-radius: 20px;
        margin-bottom: 22px;
    }
    .hero h1 { color: #ffffff !important; }
    .hero p { color: #e5f4ff; margin-bottom: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
      <h1>📊 Feature Independence Analysis</h1>
      <p>Explore relationships between categorical features and a target using the Chi-Square test.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


def show_association_chart(results: pd.DataFrame) -> None:
    chart_data = results.sort_values("Cramér's V")
    colors = [
        "#16a085" if value < 0.05 else "#6875e8"
        for value in chart_data["Adjusted p-value"]
    ]
    figure, axis = plt.subplots(figsize=(9, max(3, len(chart_data) * 0.48)))
    axis.barh(chart_data["Feature"], chart_data["Cramér's V"], color=colors)
    axis.set_xlabel("Cramér's V (association strength)")
    axis.set_title("Feature association strength")
    axis.set_xlim(0, max(1.0, chart_data["Cramér's V"].max() * 1.15))
    figure.patch.set_facecolor("#f6f8ff")
    axis.set_facecolor("#f6f8ff")
    figure.tight_layout()
    st.pyplot(figure, width="stretch")
    plt.close(figure)


uploaded_file = st.file_uploader(
    "📂 Upload your dataset (CSV required)",
    type=["csv"],
    help="Upload the latest CSV file you want to analyze. Results update automatically after upload.",
)

if uploaded_file is None:
    st.info("Upload a CSV file to run the Chi-Square analysis. No sample data is analyzed automatically.")
    st.stop()

try:
    df = pd.read_csv(uploaded_file)
    st.success(f"Analyzing uploaded dataset: {uploaded_file.name}")
except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError, ValueError) as error:
    st.error(f"CSV-ஐ படிக்க முடியவில்லை: {error}")
    st.stop()

if df.empty or len(df.columns) < 2:
    st.error("The CSV must contain at least two columns and one data row.")
    st.stop()

st.subheader(f"📋 Uploaded Dataset ({len(df):,} rows)")
st.dataframe(df, height=420, width="stretch")

available_columns = [
    column
    for column in df.columns
    if not is_identifier(column, df)
    and df[column].nunique(dropna=True) > 1
]

auto_categorical_columns = [
    column
    for column in available_columns
    if is_categorical_column(column, df)
]
categorical_columns = st.multiselect(
    "🏷️ Select categorical columns to analyze",
    options=available_columns,
    default=auto_categorical_columns,
    help=(
        "Text, boolean, and category columns are detected automatically. "
        "Low-cardinality numeric columns are included too; select or deselect "
        "columns to classify numeric codes or exclude continuous measurements."
    ),
)
if len(categorical_columns) < 2:
    st.error(
        "Select at least two categorical columns with more than one value. "
        "You can include numeric-coded categories using the selector above."
    )
    st.stop()

default_target = (
    "Placement" if "Placement" in categorical_columns else categorical_columns[-1]
)
target = st.selectbox(
    "🎯 Select a target feature",
    categorical_columns,
    index=categorical_columns.index(default_target),
    help="Each other categorical feature will be tested against the selected target.",
)
results = analyze_features(df, target, categorical_columns)

if results.empty:
    st.warning("No eligible features were found to test against the selected target.")
    st.stop()

significant_count = int((results["Adjusted p-value"] < 0.05).sum())
metric_columns = st.columns(4)
metric_columns[0].metric("Total rows", f"{len(df):,}")
metric_columns[1].metric("Features tested", len(results))
metric_columns[2].metric("Significant associations", significant_count)
metric_columns[3].metric("Missing values", int(df.isna().sum().sum()))

st.subheader(f"✨ Feature Associations with {target}")
st.markdown(
    """
    **How to read this:** An adjusted p-value below 0.05 suggests a statistically significant association,
    not cause and effect. A p-value at or above 0.05 means there is not enough evidence to claim an
    association; it does not prove independence. Cramér's V is bias-corrected and ranges from 0 (weaker)
    to 1 (stronger association). Sparse expected counts are flagged because they can make the Chi-Square
    approximation unreliable.
    """
)

chart_column, table_column = st.columns([1, 1.3])
with chart_column:
    show_association_chart(results)
with table_column:
    display_results = results.copy()
    display_results["Chi-Square"] = display_results["Chi-Square"].map(
        lambda value: f"{value:.3f}"
    )
    for column in ("p-value", "Adjusted p-value"):
        display_results[column] = display_results[column].map(
            lambda value: f"{value:.4g}"
        )
    display_results["Cramér's V"] = display_results["Cramér's V"].map(
        lambda value: f"{value:.3f}"
    )
    display_results["Expected cells < 5 (%)"] = display_results[
        "Expected cells < 5 (%)"
    ].map(lambda value: f"{value:.1f}%")
    st.dataframe(display_results, hide_index=True, width="stretch")

st.subheader("🔎 Detailed Test Results")
selected_feature = st.selectbox("Select a feature", results["Feature"].tolist())
selected_result = results.loc[results["Feature"] == selected_feature].iloc[0]
pair_data = df[[selected_feature, target]].dropna()
observed = pd.crosstab(pair_data[selected_feature], pair_data[target])
chi_columns = st.columns(4)
chi_columns[0].metric("Chi-Square statistic", f"{selected_result['Chi-Square']:.3f}")
chi_columns[1].metric("p-value", f"{selected_result['p-value']:.4g}")
selected_cramers_v = selected_result["Cramér's V"]
chi_columns[2].metric("Cramér's V", f"{selected_cramers_v:.3f}")
chi_columns[3].metric("Rows used", f"{int(selected_result['Rows used'])}")
st.caption(
    f"Pairwise rows excluded because either value was missing: "
    f"{int(selected_result['Rows excluded']):,}"
)

detail_left, detail_right = st.columns(2)
with detail_left:
    st.markdown("**Observed counts**")
    st.dataframe(observed, width="stretch")
with detail_right:
    _, _, _, expected = chi2_contingency(observed)
    expected_df = pd.DataFrame(
        expected,
        index=observed.index,
        columns=observed.columns,
    )
    st.markdown("**Expected counts (if there were no association)**")
    st.dataframe(expected_df.style.format("{:.2f}"), width="stretch")

if not selected_result["Test reliable"]:
    st.warning(
        f"Chi-Square assumptions may not hold: "
        f"{selected_result['Expected cells < 5 (%)']:.1f}% of expected cells are below 5 and "
        f"{selected_result['Expected cells < 1 (%)']:.1f}% are below 1. "
        "Treat the p-value as uncertain and consider more data or a suitable alternative test."
    )
if selected_result["Adjusted p-value"] < 0.05:
    if selected_result["Test reliable"]:
        st.success(
            f"{selected_feature} and {target} have a statistically significant association "
            "(Bonferroni-adjusted p-value < 0.05). This does not imply causation."
        )
    else:
        st.warning(
            f"The adjusted p-value suggests an association between {selected_feature} and {target}, "
            "but sparse expected counts make the Chi-Square result unreliable."
        )
else:
    st.info(
        f"There is not enough evidence of a statistically significant association between "
        f"{selected_feature} and {target} (Bonferroni-adjusted p-value ≥ 0.05). "
        "This does not prove the features are independent."
    )

st.caption(
    "Note: Bonferroni-adjusted p-values are used because multiple features are tested."
)
