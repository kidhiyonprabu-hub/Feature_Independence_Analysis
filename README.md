# Signal Lab

Signal Lab is a local statistics app with a React frontend, a FastAPI backend, and a Streamlit alternative. It supports a Chi-Square Test of Independence for categorical features in uploaded CSV files and a Chi-Square Goodness of Fit Test for manually entered category frequencies.

The data table includes every CSV column and starts by showing up to 50 rows. Use the rows-per-page control and previous/next buttons to browse larger files; scroll the table horizontally to see columns that do not fit on screen.

Results distinguish statistical significance from association strength. The dashboard counts only statistically significant results that meet expected-count guidelines as reliable signals; it separately flags significant p-values from tests with sparse expected counts. A non-significant result means there is not enough evidence to claim an association; it does not prove independence. The app reports rows excluded from each pairwise test due to missing values. Association does not imply causation.

## Statistical tests

- **Chi-Square Test of Independence:** Upload a CSV, select categorical features and a target, and compare each feature with the target. Results include Bonferroni-adjusted p-values, expected-count assumption checks, and bias-corrected Cramér's V.
- **Chi-Square Goodness of Fit Test:** Enter category names and their observed frequencies, then choose an equal distribution or provide expected frequencies or proportions. The test reports the observed and expected counts, chi-square statistic, degrees of freedom, p-value, significance level (`alpha = 0.05`), conclusion, and a comparison chart. Expected proportions must sum to 1; expected frequencies must sum to the observed total. Every expected frequency must be at least 5 for the chi-square approximation.

For example, the Goodness of Fit test can use categories `Maths, Science, English, Computer` and observed frequencies `20, 30, 25, 25`. Selecting **Equal distribution** produces expected frequencies `25, 25, 25, 25`. The same test is available from the React interface and the Streamlit alternative. The FastAPI route is `POST /api/goodness-of-fit`.

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

Open `http://127.0.0.1:8000`. To run the Streamlit alternative instead, use `.\venv\Scripts\python.exe -m streamlit run app.py` and choose a test type at the top of the page.

## Run tests

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py"
```
