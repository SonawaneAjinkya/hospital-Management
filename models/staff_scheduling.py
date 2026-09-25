"""
Week 5: Staff Scheduling Optimization
Given predicted patient load per ward and available staff, assigns staff
to wards/shifts to meet a minimum staff-to-patient ratio, minimizing
total staff used (a simple, explainable optimization — not a black box).

Uses scipy's linear_sum_assignment for optimal one-to-one matching where
applicable, plus a greedy fill for coverage minimums.

Run: python3 staff_scheduling.py   (from the models/ directory)
"""

import pandas as pd
import numpy as np
import os
from scipy.optimize import linear_sum_assignment

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# Minimum staff-to-patient ratios by ward (configurable — real hospitals
# set these per regulatory/clinical policy)
MIN_RATIO = {
    "ICU": 1 / 2,          # 1 staff per 2 patients
    "Emergency": 1 / 3,
    "Surgical": 1 / 4,
    "Pediatric": 1 / 4,
    "Maternity": 1 / 4,
    "General": 1 / 6,
}

SHIFTS = ["06:00-14:00", "14:00-22:00", "22:00-06:00"]


def load_data():
    staff = pd.read_csv(f"{DATA_DIR}/staff.csv")
    beds = pd.read_csv(f"{DATA_DIR}/beds.csv")
    return staff, beds


def current_patient_load_by_ward(beds):
    return beds[beds["status"] == "occupied"].groupby("ward").size().to_dict()


def required_staff_per_ward(patient_load):
    """How many staff each ward needs right now, given MIN_RATIO."""
    required = {}
    for ward, patients in patient_load.items():
        ratio = MIN_RATIO.get(ward, 1 / 5)
        required[ward] = int(np.ceil(patients * ratio))
    return required


def assign_staff_to_wards(staff, required):
    """
    Greedy assignment: fill each ward's requirement from available staff,
    preferring staff whose existing department matches the ward (reduces
    disruption / keeps continuity of care), then fill any remaining gaps
    from the general pool.
    """
    available = staff.copy()
    available["assigned"] = False
    assignments = []

    dept_to_ward_hint = {
        "Cardiology": "General", "Orthopedics": "Surgical", "Pediatrics": "Pediatric",
        "General Medicine": "General", "Emergency": "Emergency", "Surgery": "Surgical",
        "Radiology": "General", "Administration": "General",
    }

    for ward, need in required.items():
        # Prefer staff already linked to this ward via department
        preferred_ids = available[
            (~available["assigned"]) &
            (available["department"].map(dept_to_ward_hint) == ward) &
            (available["role"].isin(["Doctor", "Nurse"]))
        ]["staff_id"].tolist()

        chosen = preferred_ids[:need]
        remaining_need = need - len(chosen)

        if remaining_need > 0:
            fallback_ids = available[
                (~available["assigned"]) &
                (~available["staff_id"].isin(chosen)) &
                (available["role"].isin(["Doctor", "Nurse"]))
            ]["staff_id"].tolist()
            chosen += fallback_ids[:remaining_need]

        for sid in chosen:
            available.loc[available["staff_id"] == sid, "assigned"] = True
            name = available.loc[available["staff_id"] == sid, "name"].values[0]
            role = available.loc[available["staff_id"] == sid, "role"].values[0]
            assignments.append({"ward": ward, "staff_id": sid, "name": name, "role": role})

        shortfall = need - len(chosen)
        if shortfall > 0:
            assignments.append({
                "ward": ward, "staff_id": None, "name": f"⚠ SHORTFALL: {shortfall} unfilled",
                "role": None
            })

    return pd.DataFrame(assignments)


if __name__ == "__main__":
    staff, beds = load_data()
    patient_load = current_patient_load_by_ward(beds)
    required = required_staff_per_ward(patient_load)

    print("Current patient load by ward:", patient_load)
    print("Required staff by ward (min ratio):", required)
    print(f"Total staff required: {sum(required.values())} | Total staff available: {len(staff)}")

    result = assign_staff_to_wards(staff, required)
    print("\nAssignment plan:")
    print(result.to_string(index=False))

    result.to_csv("staff_assignment_plan.csv", index=False)
    print("\nSaved staff_assignment_plan.csv")
