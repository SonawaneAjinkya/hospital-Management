# 🏥 Hospital Management Analytics System

**An end-to-end hospital operations platform** — bed occupancy tracking, admission forecasting, staff scheduling, and medicine stock alerts, wrapped in a role-based web app.

<p>
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python 3.11">
  <img src="https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/scikit--learn-ML-F7931E?logo=scikitlearn&logoColor=white" alt="scikit-learn">
  <img src="https://img.shields.io/badge/SQLite-database-07405E?logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License">
</p>

Built with SQL, Python, scikit-learn, and FastAPI on the backend, with a lightweight HTML/CSS/JS frontend (a Streamlit dashboard is also included) — all packaged with Docker.

---

## 📋 Table of Contents

- [Features](#-features)
- [Project Structure](#-project-structure)
- [Entity-Relationship Diagram](#-entity-relationship-diagram)
- [Roles & Access Control](#-roles--access-control)
- [Quick Start](#-quick-start)
- [Running the Frontend](#-running-the-frontend)
- [API Reference](#-api-reference)
- [Models](#-models)
- [Sample Data](#-sample-data)
- [Moving to Production](#-moving-to-production)
- [Roadmap](#-roadmap)
- [License](#-license)

---

## ✨ Features

- 🛏️ **Bed occupancy tracking** — live per-ward occupied / vacant / maintenance counts
- 📈 **Admission forecasting** — predicts daily admissions N days ahead
- 👥 **Staff scheduling** — ratio-driven assignment of staff to wards
- 💊 **Medicine stock alerts** — low-stock, expiry, and anomaly-based consumption alerts
- 🔐 **Role-based access** — Receptionist / Medical Staff / Admin, enforced end-to-end
- 🧾 **Full audit trail** — every admission, discharge, and transaction is tied to a user
- 🐳 **One-command Docker deploy** — API + dashboard, ready to go

## 📂 Project Structure

```
hospital-system/
├── sql/
│   ├── schema.sql              # Full database schema (7 tables)
│   └── analysis_queries.sql    # 10 core analytical SQL queries
├── data/
│   ├── generate_sample_data.py # Synthetic data generator
│   ├── *.csv                   # Generated sample datasets
│   ├── *_clean.csv             # Cleaned versions
│   └── hospital.db             # SQLite database — schema + data loaded
├── notebooks/
│   ├── clean_and_explore.py    # Cleaning + EDA
│   └── figures/                # Saved charts (occupancy, trends, LOS, age)
├── models/
│   ├── bed_demand_model.py     # Forecasts daily admissions
│   ├── staff_scheduling.py     # Staff-to-ward assignment optimization
│   ├── medicine_alerts.py      # Rule-based + anomaly-detection stock alerts
│   └── bed_demand_model.pkl    # Trained model (generated on first run)
├── shared/
│   ├── db_write.py             # Single source of truth for all writes to hospital.db
│   └── auth.py                 # Login, password hashing, role permissions
├── api/
│   └── main.py                 # FastAPI: auth + read endpoints + audit-tracked write endpoints
├── dashboard/
│   └── app.py                  # Streamlit app: login + role-gated sections
├── frontend/                   # Plain HTML/CSS/JS frontend (primary UI)
├── docs/
│   ├── roadmap.md
│   └── ER_diagram.md           # Mermaid ER diagram
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 🗺️ Entity-Relationship Diagram

Full diagram in [`docs/ER_diagram.md`](docs/ER_diagram.md) (renders natively on GitHub).

**Summary:** `patients` and `beds` are linked through an `admissions` bridge table that keeps full occupancy history, not just a snapshot. `staff_shifts` and `medicine_transactions` are log tables, which is what makes trend analysis and consumption-anomaly detection possible.

## 🔐 Roles & Access Control

Three roles, each seeing only what they need — enforced in the frontend/dashboard *and* on the API itself.

| Role | Can do | Cannot see |
|---|---|---|
| **Receptionist** | Admit/discharge patients, view bed availability by ward | Medicines, staff scheduling, forecasts, user management |
| **Medical Staff** | Add medicines, restock / dispense, view stock alerts | Patient admission/discharge, beds, staff, user management |
| **Admin** | Everything above, plus staff scheduling, forecasting, full analytics, and user management | — |

**Demo logins** (⚠️ change before real use):

| Username | Password | Role |
|---|---|---|
| `reception1` | `Recep@123` | receptionist |
| `medstaff1` | `MedStaff@123` | medical_staff |
| `admin1` | `Admin@123` | admin |

Seed them into a fresh database:
```bash
python3 data/seed_users.py
```

Passwords are hashed with PBKDF2-HMAC-SHA256 (`shared/auth.py`) — never stored in plain text.

## 🚀 Quick Start

### Option A — Docker (recommended)

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| API docs | http://localhost:8000/docs |
| Streamlit dashboard | http://localhost:8501 |

### Option B — Local, no Docker

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Regenerate sample data — hospital.db already ships with
#    500 patients, 120 beds, 60 staff, 40 medicines loaded
cd data && python3 generate_sample_data.py && cd ..

# 3. Seed default login accounts
python3 data/seed_users.py

# 4. Clean + explore (writes notebooks/figures/*.png)
cd notebooks && python3 clean_and_explore.py && cd ..

# 5. Train the bed-demand model
cd models && python3 bed_demand_model.py && cd ..

# 6. Run the API
cd api && uvicorn main:app --reload --port 8000
# → docs at http://localhost:8000/docs
```

## 🖥️ Running the Frontend

The frontend in `frontend/` is plain HTML/CSS/JS — no build step, no npm. It talks to the FastAPI backend directly.

```bash
# with the API already running on port 8000, in another terminal:
cd frontend
python3 -m http.server 5500
# → open http://localhost:5500
```

Log in with any demo account above — the visible tabs adapt automatically to the logged-in user's role.

> If the API is hosted somewhere other than `localhost:8000`, update `API_BASE` at the top of `frontend/js/api.js`.

## 🔌 API Reference

<details>
<summary><strong>Core endpoints</strong></summary>

| Endpoint | Purpose |
|---|---|
| `POST /login` | Authenticate a user, returns role + user_id |
| `GET /occupancy` | Overall + per-ward bed occupancy |
| `GET /predict_beds?days=N` | Forecast admissions N days ahead |
| `GET /schedule_staff` | Ward-by-ward staff assignments |
| `GET /medicine_alerts` | Low stock / expiring / anomalous consumption |

</details>

<details>
<summary><strong>Write endpoints (audit-tracked)</strong></summary>

| Endpoint | Purpose |
|---|---|
| `POST /patients` | Admit a patient (auto-assigns a vacant bed) |
| `POST /patients/discharge` | Discharge a patient, frees their bed |
| `POST /staff` | Add a staff member |
| `POST /medicines` | Add a new medicine |
| `POST /medicines/restock` | Add stock (intake) |
| `POST /medicines/dispense` | Record medicine given (validated against stock) |
| `POST /beds` | Add a new bed to a ward |

</details>

<details>
<summary><strong>Admin-only endpoints</strong></summary>

| Endpoint | Purpose |
|---|---|
| `GET /beds/summary` | Per-ward occupied / vacant / maintenance totals |
| `POST /beds/set_total` | Set a ward's total bed count |
| `DELETE /beds/{bed_id}` | Remove a non-occupied bed |
| `GET /users` | List all user accounts |
| `POST /users` | Create a user account |
| `POST /users/{username}/active` | Enable/disable a user account |

</details>

**Example:**

```bash
curl http://localhost:8000/occupancy
# {"overall_occupancy_pct": 63.33, "occupied": 76, "vacant": 38, "maintenance": 6, "total_beds": 120}

curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"reception1","password":"Recep@123"}'
# {"user_id": 1, "username": "reception1", "role": "receptionist", "full_name": "..."}
```

A separate frontend or app can integrate purely through these endpoints (CORS is already open in `api/main.py`) — no need to touch SQLite directly.

## 🤖 Models

| Model | Method | What it does |
|---|---|---|
| Bed demand forecast | Linear Regression / Gradient Boosting (scikit-learn) | Predicts daily admissions using day-of-week, rolling averages, and lag features |
| Staff scheduling | Rule-based greedy assignment | Assigns staff to wards to meet minimum staff-to-patient ratios |
| Medicine alerts | Rule-based thresholds + IsolationForest | Flags low stock, expiring/expired stock, abnormal consumption |

## 📊 Sample Data

Synthetically generated — **no real patient data.**

| Table | Rows |
|---|---|
| patients | 500 |
| beds | 120 |
| admissions | 500 |
| staff | 60 |
| staff_shifts | 1,360 |
| medicines | 40 |
| medicine_transactions | 744 |

## 🏭 Moving to Production

- Swap SQLite → PostgreSQL: reuse `sql/schema.sql` with minor type edits (`AUTOINCREMENT` → `SERIAL`)
- Add OAuth2 + JWT to the FastAPI endpoints before exposing beyond a local network
- Retrain `bed_demand_model.py` on a schedule as real admission data accumulates
- Replace the synthetic data generator with a real ETL pipeline from the hospital's EHR/HIS system

## 🗺️ Roadmap

See [`docs/roadmap.md`](docs/roadmap.md) for the full build log and decisions made along the way.

## 📄 License

MIT — see [`LICENSE`](LICENSE).
