"""
Week 3-4: Data Cleaning & Exploratory Analysis
Cleans raw CSVs, re-loads a clean SQLite DB, runs trend queries,
and saves charts to notebooks/figures/.

Run: python3 clean_and_explore.py   (from the notebooks/ directory)
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # headless-safe
import matplotlib.pyplot as plt
import seaborn as sns
import os

sns.set_theme(style="whitegrid")
FIG_DIR = "figures"
os.makedirs(FIG_DIR, exist_ok=True)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
DB_PATH = f"{DATA_DIR}/hospital.db"

# ------------------------------------------------------------------
# 1. LOAD
# ------------------------------------------------------------------
patients = pd.read_csv(f"{DATA_DIR}/patients.csv")
beds = pd.read_csv(f"{DATA_DIR}/beds.csv")
admissions = pd.read_csv(f"{DATA_DIR}/admissions.csv")
staff = pd.read_csv(f"{DATA_DIR}/staff.csv")
shifts = pd.read_csv(f"{DATA_DIR}/staff_shifts.csv")
medicines = pd.read_csv(f"{DATA_DIR}/medicines.csv")
med_txn = pd.read_csv(f"{DATA_DIR}/medicine_transactions.csv")

print("Raw shapes:", {n: df.shape for n, df in
      [("patients", patients), ("beds", beds), ("admissions", admissions),
       ("staff", staff), ("shifts", shifts), ("medicines", medicines),
       ("med_txn", med_txn)]})

# ------------------------------------------------------------------
# 2. CLEAN
# ------------------------------------------------------------------
print("\nMissing values before cleaning:")
print(patients.isna().sum()[patients.isna().sum() > 0])

# Dates -> proper datetime
for col in ["admission_date", "discharge_date"]:
    patients[col] = pd.to_datetime(patients[col], errors="coerce")
    admissions[col] = pd.to_datetime(admissions[col], errors="coerce")

medicines["expiry_date"] = pd.to_datetime(medicines["expiry_date"], errors="coerce")
shifts["shift_date"] = pd.to_datetime(shifts["shift_date"], errors="coerce")
med_txn["txn_date"] = pd.to_datetime(med_txn["txn_date"], errors="coerce")

# Impute missing age with the median (robust to outliers)
patients["age"] = patients["age"].fillna(patients["age"].median()).astype(int)

# Impute missing disease with "Unknown" rather than dropping the row
patients["disease"] = patients["disease"].fillna("Unknown")

# Drop exact duplicate rows if any slipped in
before = len(patients)
patients = patients.drop_duplicates(subset="patient_id")
print(f"\nDropped {before - len(patients)} duplicate patient rows")

# Sanity-check: discharge_date should never be before admission_date
bad_rows = patients[patients["discharge_date"] < patients["admission_date"]]
if len(bad_rows):
    print(f"WARNING: {len(bad_rows)} rows have discharge before admission — dropping them")
    patients = patients[~patients.index.isin(bad_rows.index)]

print("\nMissing values after cleaning:")
remaining_na = patients.isna().sum()
remaining_na = remaining_na[remaining_na > 0]
print(remaining_na if not remaining_na.empty else "None")

# Derived column used throughout modeling: length of stay in days
patients["length_of_stay"] = (patients["discharge_date"] - patients["admission_date"]).dt.days

# Save cleaned versions
patients.to_csv(f"{DATA_DIR}/patients_clean.csv", index=False)
admissions.to_csv(f"{DATA_DIR}/admissions_clean.csv", index=False)

# ------------------------------------------------------------------
# 3. RE-LOAD CLEAN DATA INTO SQLITE (separate clean table so raw stays intact)
# ------------------------------------------------------------------
conn = sqlite3.connect(DB_PATH)
patients.to_sql("patients_clean", conn, if_exists="replace", index=False)
admissions.to_sql("admissions_clean", conn, if_exists="replace", index=False)
conn.commit()

# ------------------------------------------------------------------
# 4. TREND QUERIES (via SQL directly on the DB)
# ------------------------------------------------------------------
occupancy_by_ward = pd.read_sql("""
    SELECT ward,
           COUNT(*) AS total_beds,
           SUM(CASE WHEN status='occupied' THEN 1 ELSE 0 END) AS occupied,
           ROUND(100.0*SUM(CASE WHEN status='occupied' THEN 1 ELSE 0 END)/COUNT(*),2) AS occupancy_pct
    FROM beds GROUP BY ward ORDER BY occupancy_pct DESC
""", conn)
print("\nOccupancy by ward:\n", occupancy_by_ward)

daily_admissions = pd.read_sql("""
    SELECT admission_date, COUNT(*) AS admissions
    FROM admissions_clean
    GROUP BY admission_date ORDER BY admission_date
""", conn)

expiry_alerts = pd.read_sql("""
    SELECT name, stock, expiry_date,
           JULIANDAY(expiry_date) - JULIANDAY('now') AS days_to_expiry
    FROM medicines
    WHERE JULIANDAY(expiry_date) - JULIANDAY('now') BETWEEN 0 AND 30
    ORDER BY expiry_date
""", conn)
print("\nMedicines expiring within 30 days:\n", expiry_alerts)

conn.close()

# ------------------------------------------------------------------
# 5. VISUALIZE
# ------------------------------------------------------------------
# Occupancy by ward
plt.figure(figsize=(8, 5))
sns.barplot(data=occupancy_by_ward, x="ward", y="occupancy_pct", hue="ward",
            palette="viridis", legend=False)
plt.title("Bed Occupancy Rate by Ward")
plt.ylabel("Occupancy %")
plt.xlabel("Ward")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/occupancy_by_ward.png", dpi=120)
plt.close()

# Daily admissions trend
daily_admissions["admission_date"] = pd.to_datetime(daily_admissions["admission_date"])
plt.figure(figsize=(10, 5))
plt.plot(daily_admissions["admission_date"], daily_admissions["admissions"], marker="o", ms=3)
plt.title("Daily Admissions Trend")
plt.xlabel("Date")
plt.ylabel("Admissions")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/daily_admissions_trend.png", dpi=120)
plt.close()

# Length of stay distribution by disease (top 8 diseases by count)
top_diseases = patients["disease"].value_counts().head(8).index
subset = patients[patients["disease"].isin(top_diseases) & patients["length_of_stay"].notna()]
plt.figure(figsize=(10, 6))
sns.boxplot(data=subset, x="disease", y="length_of_stay", hue="disease",
            palette="Set2", legend=False)
plt.title("Length of Stay by Disease (Top 8)")
plt.xticks(rotation=30, ha="right")
plt.ylabel("Length of Stay (days)")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/length_of_stay_by_disease.png", dpi=120)
plt.close()

# Age distribution
plt.figure(figsize=(8, 5))
sns.histplot(patients["age"], bins=20, kde=True, color="steelblue")
plt.title("Patient Age Distribution")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/age_distribution.png", dpi=120)
plt.close()

print(f"\nSaved 4 charts to {FIG_DIR}/")
print("Cleaning + EDA complete.")
