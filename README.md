# Signal Lab

Signal Lab is a local CSV analysis app with a React frontend and a FastAPI backend. It tests categorical features against a selected target with a Chi-Square test, Bonferroni-adjusted p-values, and bias-corrected Cramér's V. The React website is the primary interface; `app.py` is a retained Streamlit alternative.

The data table includes every CSV column and starts by showing up to 50 rows. Use the rows-per-page control and previous/next buttons to browse larger files; scroll the table horizontally to see columns that do not fit on screen.

Results distinguish statistical significance from association strength. The dashboard counts only statistically significant results that meet expected-count guidelines as reliable signals; it separately flags significant p-values from tests with sparse expected counts. A non-significant result means there is not enough evidence to claim an association; it does not prove independence. The app reports rows excluded from each pairwise test due to missing values. Association does not imply causation.

## Run in development

Install the Python and frontend dependencies once:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm install
```

Start the backend in one terminal from the project root:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Start the frontend in a second terminal:

```powershell
cd frontend
npm run dev
```

Open the Vite URL printed in the second terminal (usually `http://127.0.0.1:5173`). This is the main React website. The API docs are available at `http://127.0.0.1:8000/docs`.

## Build and run as one app

```powershell
cd frontend
npm run build
cd ..
.\venv\Scripts\python.exe -m uvicorn backend.main:app
```

Open `http://127.0.0.1:8000`. To run the older Streamlit alternative instead, use `.\venv\Scripts\python.exe -m streamlit run app.py`.
