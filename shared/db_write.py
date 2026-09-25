"""
Shared DB-write layer.

Both the API (api/main.py) and the dashboard (dashboard/app.py) import
this module so there is exactly ONE place that writes to hospital.db —
avoids the API and dashboard drifting out of sync or duplicating
validation logic.

All functions open a fresh connection per call (safe for SQLite's
single-writer model) and commit before returning.
"""

import sqlite3
import os
from datetime import date

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DATA_DIR, "hospital.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ------------------------------------------------------------------
# PATIENTS + ADMISSIONS  (adding a patient = admitting them to a bed)
# ------------------------------------------------------------------
def add_patient_and_admit(name, age, gender, disease, ward, admission_date=None, admitted_by=None):
    """
    Adds a new patient and admits them to the first vacant bed in the
    requested ward. Returns the new patient_id and bed_id, or raises
    ValueError if no bed is available in that ward.
    admitted_by: optional users.user_id of whoever processed this (for audit trail).
    """
    admission_date = admission_date or date.today().isoformat()
    conn = _connect()
    try:
        cur = conn.cursor()

        cur.execute("SELECT bed_id FROM beds WHERE ward = ? AND status = 'vacant' LIMIT 1", (ward,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"No vacant beds in ward '{ward}'")
        bed_id = row[0]

        cur.execute(
            """INSERT INTO patients (name, age, gender, disease, admission_date, discharge_date)
               VALUES (?, ?, ?, ?, ?, NULL)""",
            (name, age, gender, disease, admission_date),
        )
        patient_id = cur.lastrowid

        cur.execute(
            """INSERT INTO admissions (patient_id, bed_id, admission_date, discharge_date, admitted_by)
               VALUES (?, ?, ?, NULL, ?)""",
            (patient_id, bed_id, admission_date, admitted_by),
        )

        cur.execute(
            "UPDATE beds SET status = 'occupied', patient_id = ? WHERE bed_id = ?",
            (patient_id, bed_id),
        )

        conn.commit()
        return {"patient_id": patient_id, "bed_id": bed_id, "ward": ward}
    finally:
        conn.close()


def discharge_patient(patient_id, discharge_date=None, discharged_by=None):
    """Marks a patient discharged and frees their bed."""
    discharge_date = discharge_date or date.today().isoformat()
    conn = _connect()
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT bed_id FROM admissions WHERE patient_id = ? AND discharge_date IS NULL",
            (patient_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"No active admission found for patient_id {patient_id}")
        bed_id = row[0]

        cur.execute(
            "UPDATE patients SET discharge_date = ? WHERE patient_id = ?",
            (discharge_date, patient_id),
        )
        cur.execute(
            "UPDATE admissions SET discharge_date = ?, discharged_by = ? WHERE patient_id = ? AND discharge_date IS NULL",
            (discharge_date, discharged_by, patient_id),
        )
        cur.execute(
            "UPDATE beds SET status = 'vacant', patient_id = NULL WHERE bed_id = ?",
            (bed_id,),
        )

        conn.commit()
        return {"patient_id": patient_id, "bed_id_freed": bed_id, "discharge_date": discharge_date}
    finally:
        conn.close()


# ------------------------------------------------------------------
# STAFF
# ------------------------------------------------------------------
def add_staff(name, role, department, shift_start, shift_end):
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO staff (name, role, department, shift_start, shift_end)
               VALUES (?, ?, ?, ?, ?)""",
            (name, role, department, shift_start, shift_end),
        )
        conn.commit()
        return {"staff_id": cur.lastrowid, "name": name, "role": role}
    finally:
        conn.close()


# ------------------------------------------------------------------
# MEDICINES
# ------------------------------------------------------------------
def add_medicine(name, category, stock, reorder_level, expiry_date, unit_price, performed_by=None):
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO medicines (name, category, stock, reorder_level, expiry_date, unit_price)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, category, stock, reorder_level, expiry_date, unit_price),
        )
        med_id = cur.lastrowid

        # Log the initial stock as a "restock" transaction so consumption
        # analysis stays accurate
        cur.execute(
            """INSERT INTO medicine_transactions (med_id, txn_type, quantity, txn_date, performed_by)
               VALUES (?, 'restock', ?, ?, ?)""",
            (med_id, stock, date.today().isoformat(), performed_by),
        )
        conn.commit()
        return {"med_id": med_id, "name": name, "stock": stock}
    finally:
        conn.close()


def restock_medicine(med_id, quantity, txn_date=None, performed_by=None):
    """Adds stock to an existing medicine and logs the transaction."""
    txn_date = txn_date or date.today().isoformat()
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT stock FROM medicines WHERE med_id = ?", (med_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"No medicine found with med_id {med_id}")

        new_stock = row[0] + quantity
        cur.execute("UPDATE medicines SET stock = ? WHERE med_id = ?", (new_stock, med_id))
        cur.execute(
            """INSERT INTO medicine_transactions (med_id, txn_type, quantity, txn_date, performed_by)
               VALUES (?, 'restock', ?, ?, ?)""",
            (med_id, quantity, txn_date, performed_by),
        )
        conn.commit()
        return {"med_id": med_id, "new_stock": new_stock}
    finally:
        conn.close()


def dispense_medicine(med_id, quantity, txn_date=None, performed_by=None):
    """Records medicine being dispensed to a patient; reduces stock."""
    txn_date = txn_date or date.today().isoformat()
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT stock FROM medicines WHERE med_id = ?", (med_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"No medicine found with med_id {med_id}")
        if row[0] < quantity:
            raise ValueError(f"Insufficient stock: have {row[0]}, requested {quantity}")

        new_stock = row[0] - quantity
        cur.execute("UPDATE medicines SET stock = ? WHERE med_id = ?", (new_stock, med_id))
        cur.execute(
            """INSERT INTO medicine_transactions (med_id, txn_type, quantity, txn_date, performed_by)
               VALUES (?, 'dispense', ?, ?, ?)""",
            (med_id, quantity, txn_date, performed_by),
        )
        conn.commit()
        return {"med_id": med_id, "new_stock": new_stock}
    finally:
        conn.close()


# ------------------------------------------------------------------
# BEDS
# ------------------------------------------------------------------
def add_bed(ward, status="vacant"):
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO beds (ward, status, patient_id) VALUES (?, ?, NULL)", (ward, status))
        conn.commit()
        return {"bed_id": cur.lastrowid, "ward": ward, "status": status}
    finally:
        conn.close()


def set_bed_maintenance(bed_id, under_maintenance=True):
    conn = _connect()
    try:
        cur = conn.cursor()
        new_status = "maintenance" if under_maintenance else "vacant"
        cur.execute("UPDATE beds SET status = ? WHERE bed_id = ?", (new_status, bed_id))
        conn.commit()
        return {"bed_id": bed_id, "status": new_status}
    finally:
        conn.close()


def remove_bed(bed_id):
    """Deletes a single bed. Refuses to delete an occupied bed."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT status, ward FROM beds WHERE bed_id = ?", (bed_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"No bed found with bed_id {bed_id}")
        status, ward = row
        if status == "occupied":
            raise ValueError(f"Bed {bed_id} is occupied — discharge the patient before removing it")

        cur.execute("DELETE FROM beds WHERE bed_id = ?", (bed_id,))
        conn.commit()
        return {"bed_id": bed_id, "ward": ward, "removed": True}
    finally:
        conn.close()


def list_beds(ward=None):
    """Returns every bed row, optionally filtered to one ward."""
    conn = _connect()
    try:
        cur = conn.cursor()
        if ward:
            cur.execute("SELECT bed_id, ward, status, patient_id FROM beds WHERE ward = ? ORDER BY bed_id", (ward,))
        else:
            cur.execute("SELECT bed_id, ward, status, patient_id FROM beds ORDER BY ward, bed_id")
        cols = ["bed_id", "ward", "status", "patient_id"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def ward_bed_summary():
    """Per-ward bed counts: total / occupied / vacant / maintenance."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT ward,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status='occupied' THEN 1 ELSE 0 END) AS occupied,
                   SUM(CASE WHEN status='vacant' THEN 1 ELSE 0 END) AS vacant,
                   SUM(CASE WHEN status='maintenance' THEN 1 ELSE 0 END) AS maintenance
            FROM beds
            GROUP BY ward
            ORDER BY ward
        """)
        cols = ["ward", "total", "occupied", "vacant", "maintenance"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def set_ward_bed_total(ward, target_total):
    """
    Admin control: set how many beds a ward has in total.
    - If target_total > current count: adds new vacant beds to reach it.
    - If target_total < current count: removes vacant beds first, then beds
      under maintenance, to reach it. Never removes an occupied bed — raises
      ValueError if the target is lower than the number of occupied beds
      (i.e. you can't shrink below patients currently admitted there).
    Returns the resulting per-ward summary.
    """
    if target_total < 0:
        raise ValueError("Total beds cannot be negative")

    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT bed_id, status FROM beds WHERE ward = ?", (ward,))
        rows = cur.fetchall()
        current_total = len(rows)
        occupied = [r for r in rows if r[1] == "occupied"]
        vacant = [r for r in rows if r[1] == "vacant"]
        maintenance = [r for r in rows if r[1] == "maintenance"]

        if target_total < len(occupied):
            raise ValueError(
                f"Can't set '{ward}' to {target_total} beds — {len(occupied)} beds there are "
                f"currently occupied. Discharge patients first."
            )

        if target_total > current_total:
            to_add = target_total - current_total
            for _ in range(to_add):
                cur.execute("INSERT INTO beds (ward, status, patient_id) VALUES (?, 'vacant', NULL)", (ward,))

        elif target_total < current_total:
            to_remove = current_total - target_total
            removable = vacant + maintenance  # occupied beds are never touched
            for bed_id, _ in removable[:to_remove]:
                cur.execute("DELETE FROM beds WHERE bed_id = ?", (bed_id,))

        conn.commit()

        cur.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN status='occupied' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status='vacant' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status='maintenance' THEN 1 ELSE 0 END)
            FROM beds WHERE ward = ?
        """, (ward,))
        total, occ, vac, maint = cur.fetchone()
        return {"ward": ward, "total": total or 0, "occupied": occ or 0, "vacant": vac or 0, "maintenance": maint or 0}
    finally:
        conn.close()
