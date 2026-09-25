"""
Hospital Management Dashboard — role-based access.

Three roles, each seeing only what they need:
  - receptionist  : admit/discharge patients, bed availability
  - medical_staff : add medicine, restock/dispense, medicine alerts
  - admin         : everything above + staff scheduling, bed-demand
                    forecast, full occupancy analytics, user management

Run: streamlit run app.py   (from the dashboard/ directory)
Default logins (change these — see shared/auth.py / data/seed_users.py):
  reception1 / Recep@123     (receptionist)
  medstaff1  / MedStaff@123  (medical_staff)
  admin1     / Admin@123     (admin)
"""

import sys
import os
import sqlite3
import joblib
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "models"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

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
import db_write  # noqa: E402
import auth  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "bed_demand_model.pkl")
DB_PATH = os.path.join(DATA_DIR, "hospital.db")

st.set_page_config(page_title="Hospital Management System", layout="wide")

ROLE_LABELS = {
    "receptionist": "🧾 Receptionist",
    "medical_staff": "💊 Medical Staff",
    "admin": "🛡️ Administrator",
}


# ------------------------------------------------------------------
# LOGIN GATE — nothing below renders until this passes
# ------------------------------------------------------------------
def login_screen():
    st.title("🏥 Hospital Management System")
    st.subheader("Log in")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        user = auth.authenticate(username, password)
        if user:
            st.session_state["user"] = user
            st.rerun()
        else:
            st.error("Invalid username or password (or account disabled).")

    st.caption(
        "Default demo logins — change these before real use: "
        "reception1 / Recep@123 · medstaff1 / MedStaff@123 · admin1 / Admin@123"
    )


if "user" not in st.session_state:
    login_screen()
    st.stop()

user = st.session_state["user"]
role = user["role"]

# ------------------------------------------------------------------
# TOP BAR — who's logged in + logout
# ------------------------------------------------------------------
top_left, top_right = st.columns([5, 1])
with top_left:
    st.title("🏥 Hospital Management System")
    st.caption(f"Logged in as **{user['full_name']}** — {ROLE_LABELS.get(role, role)}")
with top_right:
    st.write("")
    if st.button("Log out"):
        del st.session_state["user"]
        st.rerun()

st.divider()


# ==================================================================
# RECEPTIONIST SECTION — patients + bed availability only
# ==================================================================
def render_patients_and_beds(show_full_occupancy_analytics=False):
    st.header("🛏️ Bed Availability")

    conn = sqlite3.connect(DB_PATH)
    overall = conn.execute("""
        SELECT
            ROUND(100.0*SUM(CASE WHEN status='occupied' THEN 1 ELSE 0 END)/COUNT(*),2),
            SUM(CASE WHEN status='occupied' THEN 1 ELSE 0 END),
            COUNT(*)
        FROM beds
    """).fetchone()

    by_ward = pd.read_sql("""
        SELECT ward,
               COUNT(*) AS total_beds,
               SUM(CASE WHEN status='occupied' THEN 1 ELSE 0 END) AS occupied,
               SUM(CASE WHEN status='vacant' THEN 1 ELSE 0 END) AS vacant,
               SUM(CASE WHEN status='maintenance' THEN 1 ELSE 0 END) AS maintenance
        FROM beds GROUP BY ward ORDER BY ward
    """, conn)

    vacant_beds = pd.read_sql(
        "SELECT bed_id, ward FROM beds WHERE status='vacant' ORDER BY ward, bed_id", conn
    )
    conn.close()

    col1, col2, col3 = st.columns(3)
    col1.metric("Occupied Beds", f"{overall[1]} / {overall[2]}")
    col2.metric("Vacant Beds", f"{overall[2] - overall[1]}")
    col3.metric("Overall Occupancy", f"{overall[0]}%")

    st.write("**Available beds by ward** (use this to decide where to admit)")
    st.dataframe(by_ward, use_container_width=True)

    with st.expander("See individual vacant bed IDs"):
        st.dataframe(vacant_beds, use_container_width=True)

    if show_full_occupancy_analytics:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.bar(by_ward["ward"], by_ward["occupied"] / (by_ward["total_beds"]) * 100, color="#2a9d8f")
        ax.set_ylabel("Occupancy %")
        ax.set_title("Occupancy by Ward")
        plt.xticks(rotation=20)
        st.pyplot(fig)

    st.divider()

    # --- Admit / Discharge forms ---
    col_admit, col_discharge = st.columns(2)

    with col_admit:
        st.subheader("➕ Admit Patient")
        with st.form("admit_patient_form"):
            p_name = st.text_input("Name")
            p_age = st.number_input("Age", min_value=0, max_value=120, value=30)
            p_gender = st.selectbox("Gender", ["M", "F", "Other"])
            p_disease = st.text_input("Disease / reason for admission")
            p_ward = st.selectbox("Ward", sorted(by_ward["ward"].tolist()))
            submitted = st.form_submit_button("Admit patient")
            if submitted:
                if not p_name or not p_disease:
                    st.error("Name and disease are required.")
                else:
                    try:
                        result = db_write.add_patient_and_admit(
                            p_name, int(p_age), p_gender, p_disease, p_ward,
                            admitted_by=user["user_id"],
                        )
                        st.success(f"Admitted patient #{result['patient_id']} to bed #{result['bed_id']} ({p_ward})")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    with col_discharge:
        st.subheader("🚪 Discharge Patient")
        conn = sqlite3.connect(DB_PATH)
        currently_admitted = pd.read_sql("""
            SELECT p.patient_id, p.name, p.disease, b.ward, b.bed_id, p.admission_date
            FROM patients p
            JOIN admissions a ON p.patient_id = a.patient_id
            JOIN beds b ON a.bed_id = b.bed_id
            WHERE a.discharge_date IS NULL
            ORDER BY p.admission_date
        """, conn)
        conn.close()

        st.caption(f"{len(currently_admitted)} patients currently admitted")
        with st.form("discharge_form"):
            if len(currently_admitted):
                options = [
                    f"#{row.patient_id} — {row.name} ({row.ward}, bed {row.bed_id})"
                    for row in currently_admitted.itertuples()
                ]
                choice = st.selectbox("Select patient to discharge", options)
                d_patient_id = int(choice.split("—")[0].strip().lstrip("#"))
            else:
                st.info("No patients currently admitted.")
                d_patient_id = None
            submitted = st.form_submit_button("Discharge")
            if submitted and d_patient_id:
                try:
                    result = db_write.discharge_patient(d_patient_id, discharged_by=user["user_id"])
                    st.success(f"Discharged patient #{result['patient_id']}, freed bed #{result['bed_id_freed']}")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

        st.dataframe(currently_admitted, use_container_width=True)


# ==================================================================
# MEDICAL STAFF SECTION — medicines only
# ==================================================================
def render_medicines():
    st.header("💊 Medicine Stock")

    medicines, txns = load_medicine_data()
    alerts = rule_based_alerts(medicines)

    a1, a2, a3 = st.columns(3)
    a1.metric("Low Stock", len(alerts["low_stock"]))
    a2.metric("Expiring in 30 Days", len(alerts["expiring_soon"]))
    a3.metric("Already Expired", len(alerts["already_expired"]))

    tab1, tab2, tab3, tab4 = st.tabs(["Low Stock", "Expiring Soon", "Expired", "Unusual Consumption"])
    with tab1:
        st.dataframe(alerts["low_stock"], use_container_width=True)
    with tab2:
        st.dataframe(alerts["expiring_soon"], use_container_width=True)
    with tab3:
        st.dataframe(alerts["already_expired"], use_container_width=True)
    with tab4:
        features = detect_anomalies(build_consumption_features(medicines, txns))
        anomalies = features[features["is_anomaly"]].sort_values("total_dispensed", ascending=False)
        st.dataframe(
            anomalies[["name", "total_dispensed", "avg_dispense_qty", "max_single_dispense", "days_of_supply_left"]],
            use_container_width=True,
        )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("➕ Add New Medicine")
        with st.form("add_medicine_form"):
            m_name = st.text_input("Medicine name")
            m_category = st.selectbox("Category", ["Tablet", "Syrup", "Injection", "Inhaler", "IV Fluid"])
            m_stock = st.number_input("Initial stock", min_value=0, value=100)
            m_reorder = st.number_input("Reorder level", min_value=0, value=20)
            m_expiry = st.date_input("Expiry date")
            m_price = st.number_input("Unit price", min_value=0.0, value=10.0)
            submitted = st.form_submit_button("Add medicine")
            if submitted:
                if not m_name:
                    st.error("Medicine name is required.")
                else:
                    result = db_write.add_medicine(
                        m_name, m_category, int(m_stock), int(m_reorder),
                        m_expiry.isoformat(), float(m_price), performed_by=user["user_id"],
                    )
                    st.success(f"Added medicine #{result['med_id']}: {result['name']} (stock: {result['stock']})")
                    st.rerun()

    with col2:
        st.subheader("📦 Intake / Outgoing Record")
        st.caption("Restock = intake. Dispense = outgoing (given to a patient).")
        with st.form("restock_dispense_form"):
            rd_med_id = st.number_input("Medicine ID", min_value=1, step=1)
            rd_qty = st.number_input("Quantity", min_value=1, value=10)
            rd_action = st.radio("Action", ["Restock (intake)", "Dispense (outgoing)"])
            submitted = st.form_submit_button("Submit")
            if submitted:
                try:
                    if rd_action.startswith("Restock"):
                        result = db_write.restock_medicine(int(rd_med_id), int(rd_qty), performed_by=user["user_id"])
                    else:
                        result = db_write.dispense_medicine(int(rd_med_id), int(rd_qty), performed_by=user["user_id"])
                    st.success(f"Medicine #{result['med_id']} new stock: {result['new_stock']}")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    st.subheader("Full Medicine List")
    st.dataframe(medicines, use_container_width=True)

    st.subheader("Recent Transactions (intake/outgoing log)")
    conn = sqlite3.connect(DB_PATH)
    recent_txns = pd.read_sql("""
        SELECT t.txn_date, m.name AS medicine, t.txn_type, t.quantity, u.username AS performed_by
        FROM medicine_transactions t
        JOIN medicines m ON t.med_id = m.med_id
        LEFT JOIN users u ON t.performed_by = u.user_id
        ORDER BY t.txn_date DESC, t.txn_id DESC
        LIMIT 50
    """, conn)
    conn.close()
    st.dataframe(recent_txns, use_container_width=True)


# ==================================================================
# ADMIN-ONLY SECTIONS — bed demand forecast, staff scheduling, users
# ==================================================================
def render_forecast():
    st.header("📈 Bed Demand Forecast")
    days_ahead = st.slider("Days to forecast", 1, 14, 7)

    if os.path.exists(MODEL_PATH):
        bundle = joblib.load(MODEL_PATH)
        model, features = bundle["model"], bundle["features"]
        daily = build_daily_series()
        forecast = predict_next_n_days(model, features, daily, n_days=days_ahead)
        forecast_df = pd.DataFrame(forecast)

        fig2, ax2 = plt.subplots(figsize=(10, 3))
        ax2.plot(forecast_df["date"], forecast_df["predicted_admissions"], marker="o", color="#e76f51")
        ax2.set_title(f"Predicted Admissions — Next {days_ahead} Days")
        plt.xticks(rotation=30)
        st.pyplot(fig2)
        st.dataframe(forecast_df, use_container_width=True)
    else:
        st.warning("Model not trained yet. Run `models/bed_demand_model.py` first.")


def render_staff():
    st.header("🩺 Staff & Scheduling")

    staff, beds = load_staff_data()
    patient_load = current_patient_load_by_ward(beds)
    required = required_staff_per_ward(patient_load)
    plan = assign_staff_to_wards(staff, required)

    c1, c2 = st.columns(2)
    c1.write("**Required staff by ward**")
    c1.json(required)
    c2.metric("Total staff required", sum(required.values()))
    c2.metric("Total staff available", len(staff))

    st.dataframe(plan, use_container_width=True)

    st.subheader("➕ Add Staff Member")
    with st.form("add_staff_form"):
        s_name = st.text_input("Name", key="staff_name")
        s_role = st.selectbox("Role", ["Doctor", "Nurse", "Technician", "Admin", "Support"])
        s_dept = st.text_input("Department")
        s_start = st.time_input("Shift start")
        s_end = st.time_input("Shift end")
        submitted = st.form_submit_button("Add staff")
        if submitted:
            if not s_name or not s_dept:
                st.error("Name and department are required.")
            else:
                result = db_write.add_staff(s_name, s_role, s_dept, str(s_start), str(s_end))
                st.success(f"Added staff #{result['staff_id']}: {result['name']} ({result['role']})")
                st.rerun()

    st.subheader("🛏️ Add Bed")
    with st.form("add_bed_form"):
        b_ward = st.selectbox(
            "Ward", ["ICU", "General", "Pediatric", "Maternity", "Surgical", "Emergency"], key="bed_ward"
        )
        submitted = st.form_submit_button("Add bed")
        if submitted:
            result = db_write.add_bed(b_ward)
            st.success(f"Added bed #{result['bed_id']} to {result['ward']}")
            st.rerun()

    st.dataframe(staff, use_container_width=True)


def render_user_management():
    st.header("👤 User Management")
    st.caption("Create and manage login accounts for receptionists, medical staff, and other admins.")

    st.dataframe(pd.DataFrame(auth.list_users()), use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("➕ Create User")
        with st.form("create_user_form"):
            u_username = st.text_input("Username")
            u_password = st.text_input("Temporary password", type="password")
            u_role = st.selectbox("Role", auth.ROLES)
            u_fullname = st.text_input("Full name")
            submitted = st.form_submit_button("Create user")
            if submitted:
                if not u_username or not u_password or not u_fullname:
                    st.error("All fields are required.")
                else:
                    try:
                        result = auth.create_user(u_username, u_password, u_role, u_fullname)
                        st.success(f"Created user #{result['user_id']}: {result['username']} ({result['role']})")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    with col2:
        st.subheader("🔒 Enable / Disable User")
        with st.form("toggle_user_form"):
            existing = [u["username"] for u in auth.list_users()]
            t_username = st.selectbox("Username", existing) if existing else None
            t_active = st.radio("Set to", ["Active", "Disabled"])
            submitted = st.form_submit_button("Apply")
            if submitted and t_username:
                try:
                    auth.set_active(t_username, t_active == "Active")
                    st.success(f"'{t_username}' is now {t_active.lower()}.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))


# ==================================================================
# ROUTING — render only what this role is permitted to see
# ==================================================================
if role == "receptionist":
    render_patients_and_beds(show_full_occupancy_analytics=False)

elif role == "medical_staff":
    render_medicines()

elif role == "admin":
    tabs = st.tabs(["🛏️ Patients & Beds", "💊 Medicines", "🩺 Staff & Scheduling",
                     "📈 Forecast", "👤 Users"])
    with tabs[0]:
        render_patients_and_beds(show_full_occupancy_analytics=True)
    with tabs[1]:
        render_medicines()
    with tabs[2]:
        render_staff()
    with tabs[3]:
        render_forecast()
    with tabs[4]:
        render_user_management()

st.divider()
st.caption("Data is synthetic sample data generated for demo purposes — see data/generate_sample_data.py")
