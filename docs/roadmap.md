# Build Log

| Stage | Focus | Status |
|---|---|---|
| 1–2 | SQL schema + sample datasets | ✅ Done |
| 3–4 | Data cleaning (Pandas) + SQL trend analysis + visualization | ✅ Done |
| 5–6 | Modeling: bed-demand regression, staff scheduling, stock anomaly detection | ✅ Done |
| 7 | FastAPI (`/predict_beds`, `/schedule_staff`, `/medicine_alerts`) + Streamlit dashboard | ✅ Done |
| 8 | GitHub polish: README, ER diagram, Docker, requirements.txt | ✅ Done |

## Stage 1–2 — Setup & Data
- `sql/schema.sql` — 7 tables. Added `admissions`, `staff_shifts`, and
  `medicine_transactions` as history/log tables beyond the original 4,
  since occupancy-rate trends and consumption-anomaly detection need
  history, not a snapshot.
- `data/generate_sample_data.py` — 500 patients, 120 beds, 60 staff, 40
  medicines, with realistic missing-value messiness baked in.
- `data/hospital.db` — SQLite DB, schema applied, sample data loaded.
- `sql/analysis_queries.sql` — 10 verified queries.

## Stage 3–4 — Cleaning & Exploration
- `notebooks/clean_and_explore.py` — imputes missing age (median) and
  disease ("Unknown"), validates discharge-after-admission, drops
  duplicates, re-loads a `*_clean` table set into the DB.
- 4 charts saved to `notebooks/figures/`: occupancy by ward, daily
  admissions trend, length-of-stay by disease (boxplot), age distribution.

## Stage 5–6 — Modeling
- `models/bed_demand_model.py` — Linear Regression vs Gradient Boosting,
  picks the better by MAE (Linear Regression won on this sample data,
  MAE≈0.97), trains on day-of-week/rolling-average/lag features, forecasts
  N days ahead via iterative rollout.
- `models/staff_scheduling.py` — computes required staff per ward from a
  configurable minimum staff-to-patient ratio, greedily assigns available
  staff (preferring department-matched staff first), flags shortfalls.
- `models/medicine_alerts.py` — rule-based thresholds (low stock, expiring
  ≤30 days, already expired) plus an IsolationForest over consumption
  features (total/avg/max dispensed, event count) to catch unusual usage
  patterns that fixed thresholds miss.

## Stage 7 — Deployment
- `api/main.py` — FastAPI app reusing the exact model/scheduling/alert
  logic from `models/`, so API results always match what the scripts
  produce. Auto docs at `/docs`.
- `dashboard/app.py` — single-page Streamlit dashboard: occupancy metrics
  + chart, bed-demand forecast slider + chart, staff assignment table,
  medicine alerts in tabs.

## Stage 8 — Polish
- `requirements.txt`, `Dockerfile`, `docker-compose.yml` (API + dashboard
  as separate services, sharing `data/` and `models/` via volumes).
- `docs/ER_diagram.md` — Mermaid ER diagram (renders on GitHub).
- Full README with quick-start (local + Docker), API examples, model
  descriptions, and a production checklist.

## Decisions & environment notes
- SQLite chosen for zero-setup portability; swap for PostgreSQL later
  using the same `schema.sql` with `AUTOINCREMENT` → `SERIAL`.
- No `faker` package or internet access in the build environment — names/
  diseases/wards generated from realistic hand-written pools instead of
  a library; `fastapi`/`streamlit`/`xgboost` weren't installable locally
  either, so those three files are syntax-checked but not live-executed
  here — install via `requirements.txt` on your machine to run them.
- Used scikit-learn's `GradientBoostingRegressor` in place of `xgboost`
  for the same reason (see README "Models" section for the swap-back).
