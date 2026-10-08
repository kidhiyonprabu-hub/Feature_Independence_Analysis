from io import BytesIO
import json
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.analysis import (
    analyze_features,
    build_contingency_tables,
    is_categorical_column,
    is_identifier,
)


MAX_UPLOAD_BYTES = 15 * 1024 * 1024
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

app = FastAPI(
    title="Feature Independence Analysis API",
    description="Analyze categorical feature associations in uploaded CSV files.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


async def read_csv_upload(file: UploadFile) -> tuple[pd.DataFrame, bytes]:
    if file.filename and not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="CSV files must be 15 MB or smaller.",
        )
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded CSV is empty.")

    try:
        data = pd.read_csv(BytesIO(content))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError, ValueError) as error:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read the CSV: {error}",
        ) from error

    if data.empty or len(data.columns) < 2:
        raise HTTPException(
            status_code=400,
            detail="The CSV must contain at least two columns and one data row.",
        )
    if not data.columns.is_unique:
        raise HTTPException(
            status_code=400,
            detail="The CSV must have unique column names.",
        )
    return data, content


def get_available_columns(data: pd.DataFrame) -> list[str]:
    return [
        column
        for column in data.columns
        if not is_identifier(column, data)
        and data[column].nunique(dropna=True) > 1
    ]


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/inspect")
async def inspect_csv(file: UploadFile = File(...)) -> dict[str, object]:
    data, _ = await read_csv_upload(file)
    available_columns = get_available_columns(data)
    page_size = 50
    return {
        "filename": file.filename or "uploaded.csv",
        "row_count": len(data),
        "column_count": len(data.columns),
        "missing_count": int(data.isna().sum().sum()),
        "columns": [
            {
                "name": column,
                "dtype": str(data[column].dtype),
                "unique_values": int(data[column].nunique(dropna=True)),
                "missing": int(data[column].isna().sum()),
                "categorical": is_categorical_column(column, data),
                "available": column in available_columns,
            }
            for column in data.columns
        ],
        "preview": data.head(page_size).astype(object).where(pd.notna(data.head(page_size)), None).to_dict(
            orient="records"
        ),
        "preview_page": 1,
        "preview_page_size": page_size,
    }


@app.post("/api/preview")
async def preview_csv(
    file: UploadFile = File(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> dict[str, object]:
    data, _ = await read_csv_upload(file)
    page_count = max(1, (len(data) + page_size - 1) // page_size)
    if page > page_count:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page} does not exist. This dataset has {page_count} pages.",
        )

    start = (page - 1) * page_size
    page_data = data.iloc[start : start + page_size]
    rows = page_data.astype(object).where(pd.notna(page_data), None).to_dict(
        orient="records"
    )
    return {
        "page": page,
        "page_size": page_size,
        "page_count": page_count,
        "row_count": len(data),
        "row_start": start + 1,
        "row_end": start + len(page_data),
        "rows": rows,
    }


@app.post("/api/analyze")
async def analyze_csv(
    file: UploadFile = File(...),
    target: str = Form(...),
    categorical_columns: str = Form(...),
) -> dict[str, object]:
    data, _ = await read_csv_upload(file)
    available_columns = get_available_columns(data)

    try:
        selected_columns = json.loads(categorical_columns)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=400,
            detail="Categorical columns must be a JSON array.",
        ) from error
    if (
        not isinstance(selected_columns, list)
        or not all(isinstance(column, str) for column in selected_columns)
    ):
        raise HTTPException(
            status_code=400,
            detail="Categorical columns must be a list of column names.",
        )

    selected_columns = list(dict.fromkeys(selected_columns))
    if len(selected_columns) < 2:
        raise HTTPException(
            status_code=400,
            detail="Select at least two categorical columns.",
        )
    if any(column not in available_columns for column in selected_columns):
        raise HTTPException(
            status_code=400,
            detail="Selected columns must exist and contain at least two distinct values.",
        )
    if target not in selected_columns:
        raise HTTPException(
            status_code=400,
            detail="The target must be one of the selected categorical columns.",
        )

    results = analyze_features(data, target, selected_columns)
    if results.empty:
        raise HTTPException(
            status_code=422,
            detail="No eligible feature pairs were found for the selected target.",
        )

    rows = []
    for record in results.to_dict(orient="records"):
        feature = record["Feature"]
        rows.append(
            {
                "feature": feature,
                "chi_square": float(record["Chi-Square"]),
                "p_value": float(record["p-value"]),
                "adjusted_p_value": float(record["Adjusted p-value"]),
                "degrees_of_freedom": int(record["Degrees of freedom"]),
                "cramers_v": float(record["Cramér's V"]),
                "rows_used": int(record["Rows used"]),
                "rows_excluded": int(record["Rows excluded"]),
                "expected_cells_below_5_percent": float(
                    record["Expected cells < 5 (%)"]
                ),
                "expected_cells_below_1_percent": float(
                    record["Expected cells < 1 (%)"]
                ),
                "test_reliable": bool(record["Test reliable"]),
                "result": record["Result"],
                "contingency": build_contingency_tables(data, feature, target),
            }
        )

    return {
        "target": target,
        "rows": len(data),
        "missing_count": int(data.isna().sum().sum()),
        "features_tested": len(rows),
        "significant_count": sum(row["adjusted_p_value"] < 0.05 for row in rows),
        "reliable_significant_count": sum(
            row["adjusted_p_value"] < 0.05 and row["test_reliable"]
            for row in rows
        ),
        "results": rows,
    }


if FRONTEND_DIST.exists():
    assets_path = FRONTEND_DIST / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def serve_frontend(path: str) -> FileResponse:
        requested_file = FRONTEND_DIST / path
        if path and requested_file.is_file() and FRONTEND_DIST in requested_file.parents:
            return FileResponse(requested_file)
        return FileResponse(FRONTEND_DIST / "index.html")
