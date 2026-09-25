
"""
Week 7: REST API
Endpoints:
  GET  /                      - health check
  GET  /predict_beds?days=7   - forecast admissions/bed demand for next N days
  GET  /schedule_staff        - staff assignment plan based on current occupancy
  GET  /medicine_alerts       - low stock / expiring / anomalous consumption
  GET  /occupancy             - current bed occupancy snapshot

Run: uvicorn main:app --reload --port 8000   (from the api/ directory)
Docs auto-generated at: http://localhost:8000/docs
"""

import sys
import os
import sqlite3
import joblib
import pandas as pd

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Make ../models importable so we reuse the exact same logic as the scripts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "models"))

from bed_demand_model import build_daily_series, predict_next_n_days  # noqa: E402
from staff_scheduling import (  # noqa: E402
    load_data as load_staff_data,
    current_patient_load_by_ward,
    required_staff_per_ward,
    assign_staff_to_wards,
)
from medicine_alerts import (  # noqa: E402
    load_data as load_medicine_data,
    rule_based_alerts,
    build_consumption_features,
    detect_anomalies,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
import db_write  # noqa: E402
import auth  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "bed_demand_model.pkl")
DB_PATH = os.path.join(DATA_DIR, "hospital.db")

app = FastAPI(
    title="Hospital Management Analytics API",
    description="Bed demand forecasting, staff scheduling, and medicine stock alerts.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ForecastDay(BaseModel):
    date: str
    predicted_admissions: int


class OccupancyResponse(BaseModel):
    overall_occupancy_pct: float
    occupied: int
    vacant: int
    maintenance: int
    total_beds: int


class NewPatientRequest(BaseModel):
    name: str
    age: int
    gender: str
    disease: str
    ward: str
    admission_date: str | None = None
    admitted_by: int | None = None  # users.user_id, for audit trail


class DischargeRequest(BaseModel):
    patient_id: int
    discharge_date: str | None = None
    discharged_by: int | None = None


class NewStaffRequest(BaseModel):
    name: str
    role: str
    department: str
    shift_start: str
    shift_end: str


class NewMedicineRequest(BaseModel):
    name: str
    category: str
    stock: int
    reorder_level: int
    expiry_date: str
    unit_price: float


class RestockRequest(BaseModel):
    med_id: int
    quantity: int
    performed_by: int | None = None


class DispenseRequest(BaseModel):
    med_id: int
    quantity: int
    performed_by: int | None = None


class NewBedRequest(BaseModel):
    ward: str
    status: str = "vacant"
    admin_user_id: int


class RemoveBedRequest(BaseModel):
    admin_user_id: int


class SetWardBedTotalRequest(BaseModel):
    ward: str
    total_beds: int
    admin_user_id: int


class LoginRequest(BaseModel):
    username: str
    password: str


class NewUserRequest(BaseModel):
    username: str
    password: str
    role: str
    full_name: str
    admin_user_id: int


class SetUserActiveRequest(BaseModel):
    active: bool
    admin_user_id: int


def _require_admin(user_id: int):
    """Raises 401/403 unless user_id belongs to an active admin. Used to gate bed management."""
    user = auth.get_user_by_id(user_id)
    if user is None or not user["active"]:
        raise HTTPException(status_code=401, detail="Invalid or inactive user")
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admin can manage beds")
    return user


@app.get("/")
def health_check():
    return {"status": "ok", "service": "hospital-management-api"}


@app.get("/occupancy", response_model=OccupancyResponse)
def occupancy():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("""
        SELECT
            ROUND(100.0*SUM(CASE WHEN status='occupied' THEN 1 ELSE 0 END)/COUNT(*),2),
            SUM(CASE WHEN status='occupied' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status='vacant' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status='maintenance' THEN 1 ELSE 0 END),
            COUNT(*)
        FROM beds
    """).fetchone()
    conn.close()
    return OccupancyResponse(
        overall_occupancy_pct=row[0], occupied=row[1], vacant=row[2],
        maintenance=row[3], total_beds=row[4],
    )


@app.get("/predict_beds", response_model=list[ForecastDay])
def predict_beds(days: int = Query(7, ge=1, le=30, description="Number of days to forecast")):
    if not os.path.exists(MODEL_PATH):
        raise HTTPException(status_code=503, detail="Model not trained yet. Run models/bed_demand_model.py first.")

    bundle = joblib.load(MODEL_PATH)
    model, features = bundle["model"], bundle["features"]
    daily = build_daily_series()
    predictions = predict_next_n_days(model, features, daily, n_days=days)
    return predictions


@app.get("/schedule_staff")
def schedule_staff():
    staff, beds = load_staff_data()
    patient_load = current_patient_load_by_ward(beds)
    required = required_staff_per_ward(patient_load)
    plan = assign_staff_to_wards(staff, required)

    return {
        "patient_load_by_ward": patient_load,
        "required_staff_by_ward": required,
        "total_staff_required": sum(required.values()),
        "total_staff_available": len(staff),
        "assignments": plan.to_dict(orient="records"),
    }


@app.get("/medicine_alerts")
def medicine_alerts():
    medicines, txns = load_medicine_data()
    alerts = rule_based_alerts(medicines)

    features = build_consumption_features(medicines, txns)
    features = detect_anomalies(features)
    anomalies = features[features["is_anomaly"]].sort_values("total_dispensed", ascending=False)

    return {
        "low_stock": alerts["low_stock"].to_dict(orient="records"),
        "expiring_soon": alerts["expiring_soon"].astype(str).to_dict(orient="records"),
        "already_expired": alerts["already_expired"].astype(str).to_dict(orient="records"),
        "unusual_consumption": anomalies[
            ["name", "total_dispensed", "avg_dispense_qty", "max_single_dispense", "days_of_supply_left"]
        ].to_dict(orient="records"),
    }


# ------------------------------------------------------------------
# AUTH — a separate site calls this first to get the user's role,
# then includes that user's user_id in subsequent write calls below
# so every action is attributable (see the *_by fields).
# ------------------------------------------------------------------

@app.post("/login")
def login(req: LoginRequest):
    user = auth.authenticate(req.username, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password (or account disabled)")
    return user


# ------------------------------------------------------------------
# USER MANAGEMENT — admin only
# ------------------------------------------------------------------

@app.get("/users")
def get_users(admin_user_id: int):
    _require_admin(admin_user_id)
    return auth.list_users()


@app.post("/users")
def create_user(req: NewUserRequest):
    _require_admin(req.admin_user_id)
    try:
        return auth.create_user(req.username, req.password, req.role, req.full_name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/users/{username}/active")
def set_user_active(username: str, req: SetUserActiveRequest):
    _require_admin(req.admin_user_id)
    try:
        auth.set_active(username, req.active)
        return {"username": username, "active": req.active}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ------------------------------------------------------------------
# WRITE ENDPOINTS — this is how a separate site/app adds data.
# All of these write to the SAME data/hospital.db file the read
# endpoints and the dashboard read from, via shared/db_write.py, so
# every client (API, dashboard, or an external site hitting this API)
# stays in sync with a single source of truth.
# ------------------------------------------------------------------

@app.post("/patients")
def create_patient(req: NewPatientRequest):
    """Admits a new patient to the first vacant bed in the given ward."""
    try:
        return db_write.add_patient_and_admit(
            req.name, req.age, req.gender, req.disease, req.ward,
            req.admission_date, req.admitted_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/patients/discharge")
def discharge_patient(req: DischargeRequest):
    try:
        return db_write.discharge_patient(req.patient_id, req.discharge_date, req.discharged_by)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/staff")
def create_staff(req: NewStaffRequest):
    return db_write.add_staff(req.name, req.role, req.department, req.shift_start, req.shift_end)


@app.post("/medicines")
def create_medicine(req: NewMedicineRequest):
    return db_write.add_medicine(
        req.name, req.category, req.stock, req.reorder_level, req.expiry_date, req.unit_price
    )


@app.post("/medicines/restock")
def restock_medicine(req: RestockRequest):
    try:
        return db_write.restock_medicine(req.med_id, req.quantity, performed_by=req.performed_by)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/medicines/dispense")
def dispense_medicine(req: DispenseRequest):
    try:
        return db_write.dispense_medicine(req.med_id, req.quantity, performed_by=req.performed_by)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/beds")
def get_beds(ward: str | None = None):
    """Lists every bed (optionally filtered to one ward) — used for the bed grid view."""
    return db_write.list_beds(ward)


@app.get("/beds/summary")
def beds_summary():
    """Per-ward bed counts: total / occupied / vacant / maintenance."""
    return db_write.ward_bed_summary()


@app.post("/beds")
def create_bed(req: NewBedRequest):
    """Adds a single bed to a ward. Admin only."""
    _require_admin(req.admin_user_id)
    return db_write.add_bed(req.ward, req.status)


@app.delete("/beds/{bed_id}")
def delete_bed(bed_id: int, req: RemoveBedRequest):
    """Removes a single (non-occupied) bed. Admin only."""
    _require_admin(req.admin_user_id)
    try:
        return db_write.remove_bed(bed_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/beds/set_total")
def set_ward_bed_total(req: SetWardBedTotalRequest):
    """
    Admin sets how many beds a ward should have in total. Since the actual
    bed count isn't always known up front, this lets an admin type in the
    real number for a ward and the system adds or removes beds to match it
    (never touching occupied beds).
    """
    _require_admin(req.admin_user_id)
    try:
        return db_write.set_ward_bed_total(req.ward, req.total_beds)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
