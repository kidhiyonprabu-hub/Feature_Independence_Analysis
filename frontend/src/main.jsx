import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Database,
  FileSpreadsheet,
  Fingerprint,
  LoaderCircle,
  LockKeyhole,
  Search,
  Sparkles,
  Upload,
  X,
  Zap,
} from "lucide-react";
import "./style.css";

const API_ROOT = "https://feature-independence-analysis-b9n3.onrender.com";

async function getApiError(response) {
  try {
    const payload = await response.json();
    return payload.detail || "The request could not be completed.";
  } catch {
    return "The server returned an unreadable response.";
  }
}

function formatPValue(value) {
  if (value < 0.0001) return "< 0.0001";
  return value.toFixed(4);
}

function App() {
  const [apiStatus, setApiStatus] = useState("checking");
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState(null);
  const [dataset, setDataset] = useState(null);
  const [previewPage, setPreviewPage] = useState(1);
  const [previewPageSize, setPreviewPageSize] = useState(50);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [selectedColumns, setSelectedColumns] = useState([]);
  const [target, setTarget] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [activeFeature, setActiveFeature] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_ROOT}/health`)
      .then((response) => {
        if (!response.ok) throw new Error("Backend is not responding.");
        return response.json();
      })
      .then(() => setApiStatus("online"))
      .catch(() => setApiStatus("offline"));
  }, []);

  const eligibleColumns = useMemo(
    () => dataset?.columns.filter((column) => column.available) ?? [],
    [dataset],
  );

  const filteredResults = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return [...(analysis?.results ?? [])]
      .filter((result) =>
        result.feature.toLowerCase().includes(normalizedSearch),
      )
      .sort((left, right) => right.cramers_v - left.cramers_v);
  }, [analysis, search]);

  const selectedResult =
    analysis?.results.find((result) => result.feature === activeFeature) ??
    analysis?.results[0];

  const significantResults =
    analysis?.results.filter(
      (result) => result.adjusted_p_value < 0.05,
    ) ?? [];

  const reliableSignificant = significantResults.filter(
    (result) => result.test_reliable,
  );

  const strongestSignificant = [
    ...(reliableSignificant.length
      ? reliableSignificant
      : significantResults),
  ].sort((left, right) => right.cramers_v - left.cramers_v)[0];

  const previewColumns = dataset?.columns ?? [];

  const previewPageCount = dataset
    ? Math.max(1, Math.ceil(dataset.row_count / previewPageSize))
    : 1;

  const previewStart = dataset?.preview.length
    ? (previewPage - 1) * previewPageSize + 1
    : 0;

  const previewEnd = dataset
    ? Math.min(previewPage * previewPageSize, dataset.row_count)
    : 0;

  const strongestAssociation = Math.max(
    0.1,
    ...(analysis?.results.map((result) => result.cramers_v) ?? []),
  );

  async function handleFile(fileToInspect) {
    if (!fileToInspect) return;

    setBusy(true);
    setError("");
    setFile(fileToInspect);
    setDataset(null);
    setAnalysis(null);
    setActiveFeature("");
    setPreviewPage(1);
    setPreviewPageSize(50);

    const body = new FormData();
    body.append("file", fileToInspect);

    try {
      const response = await fetch(`${API_ROOT}/api/inspect`, {
        method: "POST",
        body,
      });

      if (!response.ok) throw new Error(await getApiError(response));

      const inspected = await response.json();

      const defaults = inspected.columns
        .filter((column) => column.available && column.categorical)
        .map((column) => column.name);

      setDataset(inspected);
      setPreviewPage(inspected.preview_page);
      setPreviewPageSize(inspected.preview_page_size);
      setSelectedColumns(defaults);

      setTarget(
        defaults.includes("Placement")
          ? "Placement"
          : defaults[defaults.length - 1] ?? "",
      );
    } catch (inspectionError) {
      setFile(null);
      setError(inspectionError.message);
    } finally {
      setBusy(false);
    }
  }

  async function loadPreviewPage(page, pageSize) {
    if (!file) return;

    setPreviewBusy(true);
    setError("");

    const body = new FormData();
    body.append("file", file);

    try {
      const response = await fetch(
        `${API_ROOT}/api/preview?page=${page}&page_size=${pageSize}`,
        {
          method: "POST",
          body,
        },
      );

      if (!response.ok) throw new Error(await getApiError(response));

      const result = await response.json();

      setDataset((current) =>
        current ? { ...current, preview: result.rows } : current,
      );

      setPreviewPage(result.page);
      setPreviewPageSize(result.page_size);
    } catch (previewError) {
      setError(previewError.message);
    } finally {
      setPreviewBusy(false);
    }
  }

  function toggleColumn(columnName) {
    setAnalysis(null);

    const next = selectedColumns.includes(columnName)
      ? selectedColumns.filter((column) => column !== columnName)
      : [...selectedColumns, columnName];

    setSelectedColumns(next);

    if (!next.includes(target)) {
      setTarget(next[0] ?? "");
    }
  }

  function resetDetectedColumns() {
    const detected = eligibleColumns
      .filter((column) => column.categorical)
      .map((column) => column.name);

    setSelectedColumns(detected);

    setTarget(
      detected.includes("Placement")
        ? "Placement"
        : detected[detected.length - 1] ?? "",
    );

    setAnalysis(null);
  }

  async function runAnalysis(event) {
    event.preventDefault();

    if (!file || selectedColumns.length < 2 || !target) {
      setError(
        "Choose a CSV and at least two categorical columns to continue.",
      );
      return;
    }

    setBusy(true);
    setError("");

    const body = new FormData();
    body.append("file", file);
    body.append("target", target);
    body.append(
      "categorical_columns",
      JSON.stringify(selectedColumns),
    );

    try {
      const response = await fetch(`${API_ROOT}/api/analyze`, {
        method: "POST",
        body,
      });

      if (!response.ok) throw new Error(await getApiError(response));

      const result = await response.json();

      setAnalysis(result);
      setActiveFeature(result.results[0]?.feature ?? "");

      document
        .getElementById("results")
        ?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
    } catch (analysisError) {
      setError(analysisError.message);
    } finally {
      setBusy(false);
    }
  }

  function downloadResults() {
    if (!analysis) return;

    const headings = [
      "Feature",
      "Chi-Square",
      "p-value",
      "Adjusted p-value",
      "Cramer's V",
      "Rows used",
      "Rows excluded",
      "Chi-square assumptions met",
      "Result",
    ];

    const records = analysis.results.map((result) => [
      result.feature,
      result.chi_square,
      result.p_value,
      result.adjusted_p_value,
      result.cramers_v,
      result.rows_used,
      result.rows_excluded,
      result.test_reliable ? "Yes" : "No",
      result.result,
    ]);

    const csv = [headings, ...records]
      .map((record) =>
        record
          .map((value) =>
            `"${String(value).replaceAll('"', '""')}"`,
          )
          .join(","),
      )
      .join("\n");

    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv" }),
    );

    const link = document.createElement("a");
    link.href = url;
    link.download = "feature-independence-results.csv";
    link.click();

    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" aria-label="Signal Lab home">
          <span className="brand-mark">
            <Activity size={19} strokeWidth={2.5} />
          </span>

          <span>
            <strong>
              signal<span>lab</span>
            </strong>
            <small>DATA INTELLIGENCE</small>
          </span>
        </a>

        <div className="sidebar-label">WORKSPACE</div>

        <a className="nav-item active" href="#overview">
          <BarChart3 size={17} />
          <span>Association studio</span>
          <span className="nav-count">01</span>
        </a>

        <div className="sidebar-rule" />

        <div className="sidebar-label">QUICK GUIDE</div>

        <div className="guide-card">
          <span className="guide-icon">
            <Sparkles size={17} />
          </span>

          <strong>Find the signal</strong>

          <p>
            See which categories move together — and which are independent.
          </p>

          <a href="#how-to-read">
            How to read results <ArrowRight size={13} />
          </a>
        </div>

        <div className="sidebar-footer">
          <div className={`service-dot ${apiStatus}`} />

          <span>
            {apiStatus === "online"
              ? "Analysis engine ready"
              : apiStatus === "offline"
                ? "Backend not connected"
                : "Connecting to engine"}
          </span>

          <CircleHelp size={15} />
        </div>
      </aside>

      <main className="main-area" id="overview">
        <header className="topbar">
          <div className="breadcrumbs">
            Workspace <span>/</span>{" "}
            <strong>Association studio</strong>
          </div>

          <div className="topbar-right">
            <span className="privacy-pill">
              <LockKeyhole size={13} /> Files stay in this session
            </span>

            <span className="avatar">SL</span>
          </div>
        </header>

        <div className="page-content">
          <section className="hero">
            <div className="hero-copy">
              <div className="eyebrow">
                <span /> CATEGORICAL DATA · CHI-SQUARE
              </div>

              <h1>
                Find the signal
                <br />
                in your <em>categories.</em>
              </h1>

              <p>
                Discover which features are genuinely associated — powered by
                rigorous statistics, made easy to explore.
              </p>

              <div className="hero-trust">
                <span>
                  <Fingerprint size={15} /> Your data stays yours
                </span>

                <i />

                <span>
                  <Zap size={14} /> Results in seconds
                </span>
              </div>
            </div>

            <div className="hero-visual" aria-hidden="true">
              <div className="orb orb-back" />
              <div className="orb orb-front" />

              <div className="visual-card">
                <span className="visual-card-label">
                  ASSOCIATION STRENGTH
                </span>

                <div className="visual-bars">
                  <i style={{ width: "83%" }} />
                  <i style={{ width: "57%" }} />
                  <i style={{ width: "36%" }} />
                  <i style={{ width: "20%" }} />
                </div>

                <div className="visual-card-foot">
                  <span>Strong</span>
                  <span>Independent</span>
                </div>
              </div>

              <div className="visual-tag">
                <span /> p-value adjusted
              </div>
            </div>
          </section>

          {error && (
            <div className="error-banner" role="alert">
              <X size={17} />

              <span>{error}</span>

              <button
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            </div>
          )}

          <section className="section-block" id="upload">
            <div className="section-heading">
              <div>
                <div className="step-label">
                  <span>01</span> START WITH YOUR DATA
                </div>

                <h2>Bring your dataset</h2>

                <p>
                  Upload a CSV. We’ll spot the categories and prepare your
                  analysis.
                </p>
              </div>

              {dataset && (
                <span className="ready-pill">
                  <Check size={14} /> Dataset ready
                </span>
              )}
            </div>

            {!dataset ? (
              <label
                className={`upload-card ${busy ? "is-busy" : ""} ${
                  dragging ? "is-dragging" : ""
                }`}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragging(false);
                  handleFile(event.dataTransfer.files?.[0]);
                }}
              >
                <input
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(event) =>
                    handleFile(event.target.files?.[0])
                  }
                  disabled={busy}
                />

                <span className="upload-icon">
                  {busy ? (
                    <LoaderCircle className="spin" size={22} />
                  ) : (
                    <Upload size={22} />
                  )}
                </span>

                <strong>
                  {busy
                    ? "Reading your CSV…"
                    : "Drop your CSV here, or browse"}
                </strong>

                <span className="upload-hint">
                  CSV format · Up to 15 MB · No file is stored on the server
                </span>

                <span className="browse-button">
                  Choose a file <ArrowRight size={14} />
                </span>
              </label>
            ) : (
              <>
                <div className="file-summary">
                  <span className="file-icon">
                    <FileSpreadsheet size={20} />
                  </span>

                  <div className="file-name">
                    <strong>{dataset.filename}</strong>
                    <span>
                      {dataset.column_count} columns ·{" "}
                      {dataset.row_count.toLocaleString()} rows
                    </span>
                  </div>

                  <span className="file-size">
                    <span className="file-dot" />
                    {dataset.missing_count.toLocaleString()} missing values
                  </span>

                  <button
                    className="icon-button"
                    onClick={() => {
                      setFile(null);
                      setDataset(null);
                      setAnalysis(null);
                    }}
                    aria-label="Remove dataset"
                  >
                    <X size={17} />
                  </button>
                </div>

                <div className="preview-card">
                  <div className="card-heading">
                    <div>
                      <span className="heading-icon preview-heading-icon">
                        <Database size={16} />
                      </span>

                      <strong>Complete dataset</strong>

                      <span>Every row · every column</span>
                    </div>

                    <span className="preview-count">
                      {dataset.row_count.toLocaleString()} rows <i />{" "}
                      {dataset.column_count} columns
                    </span>
                  </div>

                  <div
                    className={`table-scroll preview-scroll ${
                      previewBusy ? "preview-loading" : ""
                    }`}
                  >
                    <table className="data-table preview-table">
                      <thead>
                        <tr>
                          <th className="row-number-heading">#</th>

                          {previewColumns.map((column) => (
                            <th key={column.name}>
                              <span>{column.name}</span>
                              <small>{column.dtype}</small>
                            </th>
                          ))}
                        </tr>
                      </thead>

                      <tbody>
                        {dataset.preview.map((row, rowIndex) => (
                          <tr key={`${previewPage}-${rowIndex}`}>
                            <td className="row-number">
                              {previewStart + rowIndex}
                            </td>

                            {previewColumns.map((column) => (
                              <td
                                key={column.name}
                                title={
                                  row[column.name] == null
                                    ? "Missing value"
                                    : String(row[column.name])
                                }
                              >
                                {row[column.name] == null ? (
                                  <span className="null-value">
                                    Missing
                                  </span>
                                ) : (
                                  String(row[column.name])
                                )}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="preview-footer">
                    <span className="table-note">
                      {previewBusy ? (
                        <>
                          <LoaderCircle className="spin" size={13} /> Loading
                          rows…
                        </>
                      ) : (
                        <>
                          Showing{" "}
                          <strong>
                            {previewStart.toLocaleString()}–
                            {previewEnd.toLocaleString()}
                          </strong>{" "}
                          of{" "}
                          <strong>
                            {dataset.row_count.toLocaleString()}
                          </strong>{" "}
                          rows <i /> Scroll horizontally to see all{" "}
                          {dataset.column_count} columns
                        </>
                      )}
                    </span>

                    <div className="table-controls">
                      <label className="rows-control">
                        Rows

                        <select
                          value={previewPageSize}
                          onChange={(event) =>
                            loadPreviewPage(
                              1,
                              Number(event.target.value),
                            )
                          }
                          disabled={previewBusy}
                          aria-label="Rows per page"
                        >
                          {[10, 25, 50, 100].map((size) => (
                            <option key={size} value={size}>
                              {size}
                            </option>
                          ))}
                        </select>
                      </label>

                      <span className="page-indicator">
                        Page <strong>{previewPage}</strong> of{" "}
                        {previewPageCount}
                      </span>

                      <button
                        className="page-button"
                        type="button"
                        onClick={() =>
                          loadPreviewPage(
                            previewPage - 1,
                            previewPageSize,
                          )
                        }
                        disabled={
                          previewPage <= 1 || previewBusy
                        }
                        aria-label="Previous page"
                      >
                        <ChevronLeft size={16} />
                      </button>

                      <button
                        className="page-button"
                        type="button"
                        onClick={() =>
                          loadPreviewPage(
                            previewPage + 1,
                            previewPageSize,
                          )
                        }
                        disabled={
                          previewPage >= previewPageCount ||
                          previewBusy
                        }
                        aria-label="Next page"
                      >
                        <ChevronRight size={16} />
                      </button>
                    </div>
                  </div>
                </div>
              </>
            )}
          </section>

          {dataset && (
            <form onSubmit={runAnalysis}>
              <section className="section-block config-section">
                <div className="section-heading">
                  <div>
                    <div className="step-label">
                      <span>02</span> TELL US WHAT TO COMPARE
                    </div>

                    <h2>Choose your categories</h2>

                    <p>
                      Text and low-cardinality numeric features are detected
                      automatically. Fine-tune the selection below.
                    </p>
                  </div>
                </div>

                <div className="config-card">
                  <div className="config-topline">
                    <div>
                      <strong>Features to include</strong>
                      <span>{selectedColumns.length} selected</span>
                    </div>

                    <button
                      type="button"
                      className="text-button"
                      onClick={resetDetectedColumns}
                    >
                      Reset to detected
                    </button>
                  </div>

                  <div className="feature-pills">
                    {eligibleColumns.map((column) => {
                      const chosen = selectedColumns.includes(
                        column.name,
                      );

                      return (
                        <button
                          type="button"
                          className={`feature-pill ${
                            chosen ? "selected" : ""
                          }`}
                          key={column.name}
                          aria-pressed={chosen}
                          onClick={() =>
                            toggleColumn(column.name)
                          }
                        >
                          <span className="checkbox">
                            {chosen && <Check size={12} />}
                          </span>

                          <span>{column.name}</span>

                          <small>
                            {column.unique_values} values
                          </small>
                        </button>
                      );
                    })}
                  </div>

                  <div className="target-row">
                    <div className="target-copy">
                      <span className="target-icon">
                        <Sparkles size={16} />
                      </span>

                      <span>
                        <strong>What should we explain?</strong>
                        <small>
                          Choose the outcome to compare every other feature
                          against.
                        </small>
                      </span>
                    </div>

                    <label className="select-wrap">
                      <select
                        value={target}
                        onChange={(event) => {
                          setTarget(event.target.value);
                          setAnalysis(null);
                        }}
                        disabled={!selectedColumns.length}
                      >
                        {selectedColumns.map((column) => (
                          <option key={column} value={column}>
                            {column}
                          </option>
                        ))}
                      </select>

                      <ChevronDown size={16} />
                    </label>
                  </div>

                  <div className="config-hint">
                    <CircleHelp size={14} /> Numeric categories can be
                    selected manually. Continuous measurements are best left
                    out of a Chi-Square test.
                  </div>
                </div>

                <button
                  className="analyze-button"
                  type="submit"
                  disabled={
                    busy ||
                    selectedColumns.length < 2 ||
                    !target
                  }
                >
                  {busy ? (
                    <LoaderCircle className="spin" size={18} />
                  ) : (
                    <Sparkles size={17} />
                  )}

                  {busy
                    ? "Analyzing features…"
                    : "Run association analysis"}

                  {!busy && <ArrowRight size={17} />}
                </button>
              </section>
            </form>
          )}

          {analysis && (
            <section
              className="section-block results-section"
              id="results"
            >
              <div className="section-heading results-heading">
                <div>
                  <div className="step-label">
                    <span>03</span> YOUR ANALYSIS
                  </div>

                  <h2>Here’s what moves together.</h2>

                  <p>
                    Each feature tested against{" "}
                    <strong>{analysis.target}</strong>. Association is not
                    proof of cause and effect.
                  </p>
                </div>

                <button
                  type="button"
                  className="export-button"
                  onClick={downloadResults}
                >
                  <ArrowDownToLine size={15} /> Export results
                </button>
              </div>

              <div className="metric-grid">
                <MetricCard
                  label="Rows analyzed"
                  value={analysis.rows.toLocaleString()}
                  detail="Uploaded observations"
                  icon={<Database size={17} />}
                />

                <MetricCard
                  label="Features tested"
                  value={analysis.features_tested}
                  detail="Against your target"
                  icon={<BarChart3 size={17} />}
                />

                <MetricCard
                  label="Reliable signals"
                  value={analysis.reliable_significant_count}
                  detail="Significant · assumptions met"
                  icon={<Sparkles size={17} />}
                  accent
                />

                <MetricCard
                  label="Missing values"
                  value={analysis.missing_count.toLocaleString()}
                  detail="Across the dataset"
                  icon={<CircleHelp size={17} />}
                />
              </div>

              <div
                className={`insight-card ${
                  strongestSignificant &&
                  !strongestSignificant.test_reliable
                    ? "insight-caution"
                    : ""
                }`}
                role="status"
              >
                <span className="insight-icon">
                  <Sparkles size={17} />
                </span>

                <div>
                  <strong>
                    {strongestSignificant
                      ? "Quick insight"
                      : "No clear signal detected"}
                  </strong>

                  <p>
                    {strongestSignificant
                      ? `${strongestSignificant.feature} is the strongest ${
                          strongestSignificant.test_reliable
                            ? "reliable "
                            : ""
                        }statistically significant association with ${
                          analysis.target
                        } (adjusted p = ${formatPValue(
                          strongestSignificant.adjusted_p_value,
                        )}, Cramér’s V = ${strongestSignificant.cramers_v.toFixed(
                          3,
                        )}).${
                          strongestSignificant.test_reliable
                            ? ""
                            : " No significant result met the expected-count guidelines; this result is uncertain, so confirm it with more data or an appropriate alternative test."
                        }`
                      : `No tested feature shows a statistically significant association with ${analysis.target} after correcting for multiple tests. This is not proof that the features are independent.`}
                  </p>
                </div>
              </div>

              <div className="results-grid">
                <div className="results-card association-card">
                  <div className="card-heading results-card-heading">
                    <div>
                      <span className="heading-icon">
                        <Activity size={16} />
                      </span>

                      <strong>Association leaderboard</strong>
                    </div>

                    <span className="sort-label">
                      BY CRAMÉR’S V
                    </span>
                  </div>

                  <div className="search-field">
                    <Search size={15} />

                    <input
                      value={search}
                      onChange={(event) =>
                        setSearch(event.target.value)
                      }
                      placeholder="Find a feature…"
                      aria-label="Search features"
                    />

                    <span>{filteredResults.length}</span>
                  </div>

                  <div className="association-list">
                    {filteredResults.map((result, index) => {
                      const isActive =
                        selectedResult?.feature === result.feature;

                      const significant =
                        result.adjusted_p_value < 0.05;

                      return (
                        <button
                          type="button"
                          className={`association-item ${
                            isActive ? "active" : ""
                          }`}
                          key={result.feature}
                          onClick={() =>
                            setActiveFeature(result.feature)
                          }
                        >
                          <span
                            className={`rank ${
                              index === 0 ? "top-rank" : ""
                            }`}
                          >
                            {String(index + 1).padStart(2, "0")}
                          </span>

                          <span className="association-content">
                            <span className="association-name">
                              {result.feature}

                              <small
                                className={
                                  significant ? "sig-text" : ""
                                }
                              >
                                {significant
                                  ? result.test_reliable
                                    ? "Significant"
                                    : "Significant · check counts"
                                  : "Not significant"}
                              </small>
                            </span>

                            <span className="bar-track">
                              <span
                                className={`bar-fill ${
                                  significant ? "sig-fill" : ""
                                }`}
                                style={{
                                  width: `${Math.max(
                                    2,
                                    (result.cramers_v /
                                      strongestAssociation) *
                                      100,
                                  )}%`,
                                }}
                              />
                            </span>
                          </span>

                          <span className="association-score">
                            {result.cramers_v.toFixed(2)}
                            <small>V</small>
                          </span>

                          <ArrowUpRight
                            className="item-arrow"
                            size={15}
                          />
                        </button>
                      );
                    })}

                    {!filteredResults.length && (
                      <div className="empty-search">
                        No features match your search.
                      </div>
                    )}
                  </div>

                  <div className="association-legend">
                    <span>
                      <i className="legend-dot strong" /> Significant
                      association
                    </span>

                    <span>
                      <i className="legend-dot neutral" /> Not significant
                    </span>
                  </div>
                </div>

                {selectedResult && (
                  <div className="results-card detail-card">
                    <div className="card-heading results-card-heading">
                      <div>
                        <span className="heading-icon detail-heading-icon">
                          <Fingerprint size={16} />
                        </span>

                        <strong>Feature deep-dive</strong>
                      </div>

                      <span
                        className={`significance-tag ${
                          selectedResult.adjusted_p_value < 0.05
                            ? "significant"
                            : ""
                        } ${
                          !selectedResult.test_reliable
                            ? "caution"
                            : ""
                        }`}
                      >
                        {selectedResult.test_reliable
                          ? selectedResult.result
                          : `${selectedResult.result} · caution`}
                      </span>
                    </div>

                    <div className="detail-title">
                      <span>
                        RELATIONSHIP WITH{" "}
                        {analysis.target.toUpperCase()}
                      </span>

                      <h3>
                        {selectedResult.feature}
                        <ArrowRight size={20} />
                        {analysis.target}
                      </h3>

                      <p>
                        {selectedResult.adjusted_p_value < 0.05
                          ? selectedResult.test_reliable
                            ? "Evidence of an association in this dataset; this does not imply causation."
                            : "The adjusted p-value suggests an association, but sparse counts make the chi-square approximation unreliable."
                          : selectedResult.test_reliable
                            ? "Not enough evidence of an association; this does not prove independence."
                            : "No significant association detected, but sparse counts make this test inconclusive."}
                      </p>
                    </div>

                    <div className="detail-stat-grid">
                      <div>
                        <small>CHI-SQUARE</small>
                        <strong>
                          {selectedResult.chi_square.toFixed(2)}
                        </strong>
                      </div>

                      <div>
                        <small>ADJ. P-VALUE</small>
                        <strong>
                          {formatPValue(
                            selectedResult.adjusted_p_value,
                          )}
                        </strong>
                      </div>

                      <div>
                        <small>DEGREES OF FREEDOM</small>
                        <strong>
                          {selectedResult.degrees_of_freedom}
                        </strong>
                      </div>

                      <div>
                        <small>USED / EXCLUDED</small>
                        <strong>
                          {selectedResult.rows_used.toLocaleString()} /{" "}
                          {selectedResult.rows_excluded.toLocaleString()}
                        </strong>
                      </div>
                    </div>

                    <div className="cramers-panel">
                      <div>
                        <span>Cramér’s V</span>
                        <strong>
                          {selectedResult.cramers_v.toFixed(3)}
                        </strong>
                      </div>

                      <span className="cramers-track">
                        <i
                          style={{
                            width: `${
                              selectedResult.cramers_v * 100
                            }%`,
                          }}
                        />
                      </span>

                      <div className="strength-scale">
                        <span>WEAKER</span>
                        <span>STRONGER</span>
                      </div>
                    </div>

                    {!selectedResult.test_reliable && (
                      <div className="warning-note">
                        <CircleHelp size={15} />

                        <span>
                          <strong>
                            Chi-square assumptions may not hold.
                          </strong>{" "}
                          {selectedResult.expected_cells_below_5_percent.toFixed(
                            1,
                          )}
                          % of expected cells are below 5 and{" "}
                          {selectedResult.expected_cells_below_1_percent.toFixed(
                            1,
                          )}
                          % are below 1. Treat the p-value as uncertain;
                          consider collecting more data or using a suitable
                          alternative test.
                        </span>
                      </div>
                    )}

                    <ContingencyTable
                      contingency={selectedResult.contingency}
                    />
                  </div>
                )}
              </div>

              <div className="method-note" id="how-to-read">
                <Sparkles size={15} />

                <span>
                  <strong>How to read this:</strong> adjusted p-value below
                  0.05 suggests a statistically significant association, not
                  causation. A result above 0.05 means there is not enough
                  evidence to claim an association—it does not prove
                  independence. Cramér’s V (bias-corrected) describes
                  association strength from 0 to 1. Bonferroni adjustment
                  accounts for multiple feature tests; sparse expected counts
                  are flagged because they can make the chi-square p-value
                  unreliable.
                </span>
              </div>
            </section>
          )}

          {!dataset && (
            <div className="empty-state">
              <span>
                <BarChart3 size={19} />
              </span>

              <div>
                <strong>Your analysis workspace is ready</strong>

                <p>
                  Upload a dataset above to see a live preview, select
                  features and uncover associations.
                </p>
              </div>

              <ArrowUpRight size={17} />
            </div>
          )}

          <footer className="page-footer">
            <span>
              Signal Lab <i /> Feature Independence Analysis
            </span>

            <span>
              <LockKeyhole size={12} /> Processed locally by your analysis
              engine
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
  icon,
  accent = false,
}) {
  return (
    <div
      className={`metric-card ${
        accent ? "metric-accent" : ""
      }`}
    >
      <div className="metric-top">
        <span>{label}</span>
        <i>{icon}</i>
      </div>

      <strong>{value}</strong>

      <small>{detail}</small>
    </div>
  );
}

function ContingencyTable({ contingency }) {
  if (!contingency) return null;

  const {
    row_labels,
    column_labels,
    observed,
    expected,
  } = contingency;

  return (
    <details className="contingency-details">
      <summary>
        Explore observed &amp; expected counts
        <ChevronDown size={15} />
      </summary>

      <div className="contingency-panel">
        <CountTable
          title="Observed counts"
          rowLabels={row_labels}
          columnLabels={column_labels}
          values={observed}
        />

        <CountTable
          title="Expected counts"
          rowLabels={row_labels}
          columnLabels={column_labels}
          values={expected}
          decimals
        />
      </div>
    </details>
  );
}

function CountTable({
  title,
  rowLabels,
  columnLabels,
  values,
  decimals = false,
}) {
  return (
    <div className="count-table-wrap">
      <div className="count-table-title">{title}</div>

      <div className="table-scroll">
        <table className="data-table count-table">
          <thead>
            <tr>
              <th>Category</th>

              {columnLabels.map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>

          <tbody>
            {rowLabels.map((label, index) => (
              <tr key={label}>
                <th>{label}</th>

                {values[index].map((value, valueIndex) => (
                  <td key={valueIndex}>
                    {decimals
                      ? Number(value).toFixed(1)
                      : value}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```
