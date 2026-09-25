# 🏥 Hospital Management Analytics System

An end-to-end analytics platform for hospital operations: bed occupancy
tracking, admission forecasting, staff scheduling optimization, and
medicine stock alerts — built with SQL, Python, scikit-learn, FastAPI,
and a plain HTML/CSS/JS frontend, packaged with Docker.

> **Frontend note:** the original Streamlit dashboard (`dashboard/app.py`)
> is still in the repo but is no longer the primary frontend. A plain
> HTML/CSS/JS frontend now lives in `frontend/` — see "Running the
> Frontend" below. It talks to the same FastAPI backend, so nothing on
> the backend needed to change for the switch except adding admin-only
> endpoints for bed-count and user management (see "New: Bed Management"
> below).

## Project Structure

```
hospital-system/
├── sql/
│   ├── schema.sql              # Full database schema (7 tables)
│   └── analysis_queries.sql    # 10 core analytical SQL queries
├── data/
│   ├── generate_sample_data.py # Synthetic data generator
│   ├── *.csv                   # Generated sample datasets
│   ├── *_clean.csv             # Cleaned versions (post Week 3-4)
│   └── hospital.db             # SQLite database — schema + data loaded
├── notebooks/
│   ├── clean_and_explore.py    # Cleaning + EDA (demo "notebook")
│   └── figures/                # Saved charts (occupancy, trends, LOS, age)
├── models/
│   ├── bed_demand_model.py     # Regression: forecasts daily admissions
│   ├── staff_scheduling.py     # Staff-to-ward assignment optimization
│   ├── medicine_alerts.py      # Rule-based + anomaly-detection stock alerts
│   └── bed_demand_model.pkl    # Trained model (generated on first run)
├── shared/
│   ├── db_write.py              # Single source of truth for all writes to hospital.db
│   └── auth.py                  # Login, password hashing, role permissions
├── api/
│   └── main.py                  # FastAPI: /login + read endpoints + write endpoints (audit-tracked)
├── dashboard/
│   └── app.py                   # Streamlit app: login screen + role-gated sections
├── docs/
│   ├── roadmap.md
│   └── ER_diagram.md           # Mermaid ER diagram
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Entity-Relationship Diagram

See [`docs/ER_diagram.md`](docs/ER_diagram.md) for the full Mermaid diagram
(renders natively on GitHub). Summary: `patients` and `beds` are linked
through an `admissions` bridge table (full occupancy history, not just a
snapshot); `staff_shifts` and `medicine_transactions` are log tables that
make trend analysis and consumption-anomaly detection possible.

## Roles & Access Control

Three roles, each seeing only what they need — enforced in both the
dashboard (hides sections entirely) and available for the API to enforce
the same way in a separate frontend:

| Role | Can do | Cannot see |
|---|---|---|
| **Receptionist** | Admit/discharge patients, view bed availability by ward | Medicines, staff scheduling, forecasts, user management |
| **Medical Staff** | Add medicines, restock (intake) / dispense (outgoing), view stock alerts | Patient admission/discharge, beds, staff, user management |
| **Admin** | Everything — all of the above, plus staff scheduling, bed-demand forecasting, full occupancy analytics, and creating/disabling user accounts | — |

**Default demo logins** (change these before real use — see below):

| Username | Password | Role |
|---|---|---|
| `reception1` | `Recep@123` | receptionist |
| `medstaff1` | `MedStaff@123` | medical_staff |
| `admin1` | `Admin@123` | admin |

Seed them into a fresh database with:
```bash
python3 data/seed_users.py
```

**Passwords** are hashed with PBKDF2-HMAC-SHA256 (`shared/auth.py`) —
never stored in plain text. To change a password:
```python
import sys; sys.path.append("shared")
import auth
auth.change_password("admin1", "NewStrongerPassword!")
```

**Audit trail:** every admission, discharge, and medicine transaction
records *which user* performed it (`admitted_by`, `discharged_by`,
`performed_by` columns) — so you can always answer "who admitted this
patient" or "who dispensed this medicine."

## Quick Start (local, no Docker)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Regenerate sample data — hospital.db already ships with
#    500 patients, 120 beds, 60 staff, 40 medicines loaded
cd data && python3 generate_sample_data.py && cd ..

# 2b. Seed default login accounts (one per role — see "Roles & Access Control" above)
python3 data/seed_users.py

# 3. Clean + explore (writes notebooks/figures/*.png)
cd notebooks && python3 clean_and_explore.py && cd ..

# 4. Train the bed-demand model (writes models/bed_demand_model.pkl)
cd models && python3 bed_demand_model.py && cd ..

# 5. Run the API
cd api && uvicorn main:app --reload --port 8000
# → docs at http://localhost:8000/docs

# 6. Run the frontend (in a separate terminal) — see "Running the Frontend" below
```

## Quick Start (Docker)

```bash
docker compose up --build
# API        → http://localhost:8000/docs
# Dashboard  → http://localhost:8501
```

## Running the Frontend

The frontend in `frontend/` is plain HTML/CSS/JS — no build step, no
npm, no framework. It calls the FastAPI backend directly (`API_BASE` in
`frontend/js/api.js`, defaults to `http://localhost:8000`).

```bash
# with the API already running on port 8000, in another terminal:
cd frontend
python3 -m http.server 5500
# → open http://localhost:5500 in your browser
```

Log in with any of the demo accounts (see "Roles & Access Control"
above). The tabs shown adjust automatically to the logged-in user's
role — receptionists see Patients & Beds, medical staff see Medicines,
and admins see everything plus Manage Beds, Staff Scheduling, Bed
Forecast, and Users.

If you host the API somewhere other than `localhost:8000`, update
`API_BASE` at the top of `frontend/js/api.js`.

## New: Admin Bed Management

Since the real number of beds per ward often isn't known up front, admins
now have two ways to manage it (Manage Beds tab, or directly via the API):

- **Set total beds for a ward** — type the real number and save;
  the system adds or removes vacant beds automatically to match it.
  It will never remove an occupied bed — if you try to set a ward's
  total below its current occupied count, it's rejected with an
  explanation.
- **Add / remove one bed at a time** — for fine-grained control.

These are gated to the `admin` role only, both in the UI (the tab is
hidden for other roles) and in the API itself (`admin_user_id` is
checked server-side against the `users` table — see `_require_admin` in
`api/main.py` — so the check can't be bypassed by calling the API
directly).

New endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /beds` | List every bed (optionally `?ward=ICU`) |
| `GET /beds/summary` | Per-ward totals: occupied / vacant / maintenance |
| `POST /beds/set_total` | Admin sets a ward's total bed count |
| `DELETE /beds/{bed_id}` | Admin removes one (non-occupied) bed |
| `GET /users` | Admin lists all user accounts |
| `POST /users` | Admin creates a user account |
| `POST /users/{username}/active` | Admin enables/disables a user account |

## API Usage Examples

```bash
curl http://localhost:8000/occupancy
# {"overall_occupancy_pct": 63.33, "occupied": 76, "vacant": 38, "maintenance": 6, "total_beds": 120}

curl http://localhost:8000/predict_beds?days=7
# [{"date": "2026-09-25", "predicted_admissions": 1}, ...]

curl http://localhost:8000/schedule_staff
# {"patient_load_by_ward": {...}, "assignments": [...]}

curl http://localhost:8000/medicine_alerts
# {"low_stock": [...], "expiring_soon": [...], "already_expired": [...], "unusual_consumption": [...]}
```

## Adding Data From a Separate Site or App

Everything above is read-only analytics. If a separate website, mobile
app, or the dashboard itself needs to **add** data — admit a patient,
restock a medicine, add a staff member — it must write to the *same*
`data/hospital.db` file, or the dashboard/API will show stale numbers.

**Where the database lives:** a single SQLite file at `data/hospital.db`
on the server. There is one copy — not one per user. Every reader and
writer (API, dashboard, or an external site) points at that same file.

**How writes are wired up:**
- `shared/db_write.py` is the *only* place in the codebase that writes to
  the DB — both `api/main.py` and `dashboard/app.py` import it, so there's
  one source of truth and no duplicated/diverging logic.
- The API exposes write endpoints for exactly this purpose — an external
  site doesn't need direct DB access at all, it just calls these:

  | Endpoint | Purpose |
  |---|---|
  | `POST /login` | Authenticate a user, returns their role + user_id |
  | `POST /patients` | Admit a new patient (assigns first vacant bed in the ward) |
  | `POST /patients/discharge` | Discharge a patient, frees their bed |
  | `POST /staff` | Add a staff member |
  | `POST /medicines` | Add a new medicine |
  | `POST /medicines/restock` | Add stock to an existing medicine (intake) |
  | `POST /medicines/dispense` | Record medicine given to a patient (outgoing; validates against available stock) |
  | `POST /beds` | Add a new bed to a ward |

  A separate frontend should call `/login` first, then pass the returned
  `user_id` as `admitted_by` / `discharged_by` / `performed_by` on the
  write calls that accept it — that's what builds the audit trail.

  Example:
  ```bash
  curl -X POST http://localhost:8000/login \
    -H "Content-Type: application/json" \
    -d '{"username":"reception1","password":"Recep@123"}'
  # {"user_id": 1, "username": "reception1", "role": "receptionist", "full_name": "..."}

  curl -X POST http://localhost:8000/patients \
    -H "Content-Type: application/json" \
    -d '{"name":"Jane Doe","age":42,"gender":"F","disease":"Pneumonia","ward":"General","admitted_by":1}'
  # {"patient_id": 501, "bed_id": 9, "ward": "General"}
  ```
- The dashboard also has its own "➕ Add Data" forms in the sidebar for
  admitting/discharging patients, adding staff, and restocking medicine —
  useful for a hospital admin who just wants a UI, no API calls needed.

**Building a separate frontend?** Point it at the FastAPI endpoints above
(CORS is already open in `api/main.py`) rather than talking to SQLite
directly — that keeps validation (e.g. "can't dispense more than is in
stock", "no vacant beds in that ward") in one place.

**Scaling past one server:** SQLite serializes writes (one at a time),
which is fine for a single hospital's admin traffic. If you outgrow that
— many concurrent writers, multiple servers — migrate to PostgreSQL using
the same `sql/schema.sql` (swap `AUTOINCREMENT` → `SERIAL`) and point
`shared/db_write.py` at it via a connection string instead of a file path.

## SQL — Sample Queries

```bash
sqlite3 data/hospital.db
sqlite> .read sql/analysis_queries.sql
```

10 queries covering: overall + per-ward occupancy rate, expiry alerts,
low-stock alerts, daily admission trends, average length of stay by
disease, staff-to-patient ratio, top dispensed medicines, and current
patient roster.

## Models

| Model | Method | What it does |
|---|---|---|
| Bed demand forecast | Linear Regression / Gradient Boosting (scikit-learn) | Predicts daily admissions N days ahead using day-of-week, rolling averages, and lag features |
| Staff scheduling | Rule-based greedy assignment (department-matched, ratio-driven) | Assigns available staff to wards to meet minimum staff-to-patient ratios |
| Medicine alerts | Rule-based thresholds + IsolationForest anomaly detection | Flags low stock, expiring/expired stock, and abnormal consumption patterns |

> **Note on XGBoost:** the original plan specified XGBoost; this build
> uses scikit-learn's `GradientBoostingRegressor` (same gradient-boosted-
> tree approach, same `.fit()`/`.predict()` API) since `xgboost` wasn't
> installable in the offline build environment. Swap it in
> `models/bed_demand_model.py` by importing `from xgboost import XGBRegressor`
> and adding it to the `models` dict — no other changes needed.

## Sample Data

Synthetically generated — **no real patient data**. Includes intentional
messiness (missing ages/disease values) so the cleaning step in
`notebooks/clean_and_explore.py` has something real to do.

| Table | Rows |
|---|---|
| patients | 500 |
| beds | 120 |
| admissions | 500 |
| staff | 60 |
| staff_shifts | 1,360 |
| medicines | 40 |
| medicine_transactions | 744 |

## Roadmap / Build Log

See [`docs/roadmap.md`](docs/roadmap.md) for what was built at each stage
and the decisions made along the way.

## Moving to Production

- Swap SQLite → PostgreSQL: reuse `sql/schema.sql` with minor type edits
  (`AUTOINCREMENT` → `SERIAL`).
- Add authentication to the FastAPI endpoints (e.g. OAuth2 + JWT) before
  exposing beyond a local network.
- Retrain `bed_demand_model.py` on a schedule (cron / Airflow) as real
  admission data accumulates.
- Replace the synthetic data generator with a real ETL pipeline from the
  hospital's actual EHR/HIS system.

## License

MIT — add your own `LICENSE` file before publishing.
#   h o s p i t a l - M a n a g e m e n t  
 