"""
Generate synthetic-but-realistic hospital data for development/testing.
No real patient data is used — everything here is randomly generated.

Run: python generate_sample_data.py
Outputs: patients.csv, beds.csv, admissions.csv, staff.csv,
         staff_shifts.csv, medicines.csv, medicine_transactions.csv
"""

import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

OUT_DIR = "."

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh",
               "Ananya", "Diya", "Saanvi", "Aadhya", "Kiara", "Myra", "Anika",
               "James", "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia",
               "Rohan", "Priya", "Karan", "Neha", "Amit", "Sneha", "Raj", "Pooja"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Patel", "Reddy", "Iyer", "Nair",
              "Khan", "Singh", "Das", "Smith", "Johnson", "Brown", "Williams",
              "Joshi", "Mehta", "Rao", "Kapoor", "Chopra", "Pillai"]

DISEASES = ["Diabetes", "Hypertension", "Fracture", "Pneumonia", "Appendicitis",
            "COVID-19", "Cardiac Arrest", "Asthma", "Kidney Stones", "Dengue",
            "Malaria", "Tuberculosis", "Stroke", "Arthritis", "Migraine"]

WARDS = ["ICU", "General", "Pediatric", "Maternity", "Surgical", "Emergency"]

ROLES = ["Doctor", "Nurse", "Technician", "Admin", "Support"]
DEPARTMENTS = ["Cardiology", "Orthopedics", "Pediatrics", "General Medicine",
               "Emergency", "Surgery", "Radiology", "Administration"]

MED_NAMES = ["Paracetamol", "Amoxicillin", "Ibuprofen", "Insulin", "Metformin",
             "Aspirin", "Omeprazole", "Azithromycin", "Cetirizine", "Atorvastatin",
             "Losartan", "Salbutamol Inhaler", "ORS Sachets", "IV Saline",
             "Ceftriaxone", "Diclofenac Gel", "Vitamin D3", "Iron Folic Acid"]


def random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_date(start, end):
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))


def generate_beds(n_beds=120):
    rows = []
    for bed_id in range(1, n_beds + 1):
        ward = random.choices(WARDS, weights=[15, 40, 15, 10, 15, 5])[0]
        rows.append({"bed_id": bed_id, "ward": ward, "status": "vacant", "patient_id": None})
    return pd.DataFrame(rows)


def generate_patients_and_admissions(n_patients=500, beds_df=None):
    today = datetime(2026, 9, 24)
    start_range = today - timedelta(days=180)

    patients, admissions = [], []
    bed_ids = beds_df["bed_id"].tolist()

    for pid in range(1, n_patients + 1):
        admission_date = random_date(start_range, today)
        # ~70% already discharged, 30% still admitted
        if random.random() < 0.7:
            stay_days = int(np.random.exponential(scale=4)) + 1
            discharge_date = admission_date + timedelta(days=stay_days)
            if discharge_date > today:
                discharge_date = None
        else:
            discharge_date = None

        patients.append({
            "patient_id": pid,
            "name": random_name(),
            "age": int(np.clip(np.random.normal(45, 20), 0, 95)),
            "gender": random.choice(["M", "F", "Other"]),
            "disease": random.choice(DISEASES),
            "admission_date": admission_date.date().isoformat(),
            "discharge_date": discharge_date.date().isoformat() if discharge_date else None,
        })

        admissions.append({
            "admission_id": pid,
            "patient_id": pid,
            "bed_id": random.choice(bed_ids),
            "admission_date": admission_date.date().isoformat(),
            "discharge_date": discharge_date.date().isoformat() if discharge_date else None,
        })

    return pd.DataFrame(patients), pd.DataFrame(admissions)


def apply_bed_status(beds_df, admissions_df):
    beds_df = beds_df.copy()
    active = admissions_df[admissions_df["discharge_date"].isna()]
    occupied_map = active.drop_duplicates("bed_id").set_index("bed_id")["patient_id"]
    beds_df["status"] = beds_df["bed_id"].map(
        lambda b: "occupied" if b in occupied_map.index else "vacant"
    )
    # small fraction under maintenance
    maint_idx = beds_df.sample(frac=0.05, random_state=1).index
    beds_df.loc[maint_idx, "status"] = "maintenance"
    beds_df["patient_id"] = beds_df["bed_id"].map(occupied_map).where(
        beds_df["status"] == "occupied", None
    )
    return beds_df


def generate_staff(n_staff=60):
    rows = []
    for sid in range(1, n_staff + 1):
        role = random.choices(ROLES, weights=[25, 40, 15, 10, 10])[0]
        shift_start_hr = random.choice([6, 14, 22])  # 3 standard shifts
        shift_start = f"{shift_start_hr:02d}:00:00"
        shift_end = f"{(shift_start_hr + 8) % 24:02d}:00:00"
        rows.append({
            "staff_id": sid,
            "name": random_name(),
            "role": role,
            "department": random.choice(DEPARTMENTS),
            "shift_start": shift_start,
            "shift_end": shift_end,
        })
    return pd.DataFrame(rows)


def generate_staff_shifts(staff_df, days=30):
    today = datetime(2026, 9, 24)
    rows = []
    shift_id = 1
    for _, s in staff_df.iterrows():
        for d in range(days):
            if random.random() < 0.75:  # not every staff works every day
                shift_date = (today - timedelta(days=d)).date().isoformat()
                rows.append({
                    "shift_id": shift_id,
                    "staff_id": s["staff_id"],
                    "shift_date": shift_date,
                    "shift_start": s["shift_start"],
                    "shift_end": s["shift_end"],
                    "ward": random.choice(WARDS),
                })
                shift_id += 1
    return pd.DataFrame(rows)


def generate_medicines(n_meds=40):
    today = datetime(2026, 9, 24)
    rows = []
    for mid in range(1, n_meds + 1):
        name = random.choice(MED_NAMES) + f" {mid}"
        stock = random.randint(0, 500)
        expiry = today + timedelta(days=random.randint(-30, 720))  # some already expired
        rows.append({
            "med_id": mid,
            "name": name,
            "category": random.choice(["Tablet", "Syrup", "Injection", "Inhaler", "IV Fluid"]),
            "stock": stock,
            "reorder_level": random.randint(10, 50),
            "expiry_date": expiry.date().isoformat(),
            "unit_price": round(random.uniform(2, 500), 2),
        })
    return pd.DataFrame(rows)


def generate_medicine_transactions(meds_df, days=60):
    today = datetime(2026, 9, 24)
    rows = []
    txn_id = 1
    for _, m in meds_df.iterrows():
        for d in range(days):
            if random.random() < 0.3:
                txn_date = (today - timedelta(days=d)).date().isoformat()
                txn_type = random.choices(
                    ["dispense", "restock", "discard_expired"], weights=[70, 25, 5]
                )[0]
                qty = random.randint(1, 50) if txn_type == "dispense" else random.randint(20, 200)
                rows.append({
                    "txn_id": txn_id,
                    "med_id": m["med_id"],
                    "txn_type": txn_type,
                    "quantity": qty,
                    "txn_date": txn_date,
                })
                txn_id += 1
    return pd.DataFrame(rows)


if __name__ == "__main__":
    beds_df = generate_beds()
    patients_df, admissions_df = generate_patients_and_admissions(beds_df=beds_df)
    beds_df = apply_bed_status(beds_df, admissions_df)
    staff_df = generate_staff()
    shifts_df = generate_staff_shifts(staff_df)
    meds_df = generate_medicines()
    med_txn_df = generate_medicine_transactions(meds_df)

    # inject a bit of real-world messiness for the Week 3-4 cleaning step
    patients_df.loc[patients_df.sample(frac=0.03, random_state=2).index, "age"] = None
    patients_df.loc[patients_df.sample(frac=0.02, random_state=3).index, "disease"] = None

    patients_df.to_csv(f"{OUT_DIR}/patients.csv", index=False)
    beds_df.to_csv(f"{OUT_DIR}/beds.csv", index=False)
    admissions_df.to_csv(f"{OUT_DIR}/admissions.csv", index=False)
    staff_df.to_csv(f"{OUT_DIR}/staff.csv", index=False)
    shifts_df.to_csv(f"{OUT_DIR}/staff_shifts.csv", index=False)
    meds_df.to_csv(f"{OUT_DIR}/medicines.csv", index=False)
    med_txn_df.to_csv(f"{OUT_DIR}/medicine_transactions.csv", index=False)

    print("Generated:")
    print(f"  patients.csv              {len(patients_df)} rows")
    print(f"  beds.csv                  {len(beds_df)} rows")
    print(f"  admissions.csv            {len(admissions_df)} rows")
    print(f"  staff.csv                 {len(staff_df)} rows")
    print(f"  staff_shifts.csv          {len(shifts_df)} rows")
    print(f"  medicines.csv             {len(meds_df)} rows")
    print(f"  medicine_transactions.csv {len(med_txn_df)} rows")
