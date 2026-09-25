"""
Week 5-6: Medicine Stock Alerts
Two layers:
  1. Rule-based: low stock (below reorder level), expiring soon, already expired.
  2. Anomaly detection: flags medicines whose recent dispense rate is
     abnormal (IsolationForest on consumption pattern) — catches things
     rule-based thresholds miss, e.g. a sudden spike in usage that will
     blow through stock before the next scheduled reorder.

Run: python3 medicine_alerts.py   (from the models/ directory)
"""

import pandas as pd
import numpy as np
import os
from sklearn.ensemble import IsolationForest

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def load_data():
    medicines = pd.read_csv(f"{DATA_DIR}/medicines.csv", parse_dates=["expiry_date"])
    txns = pd.read_csv(f"{DATA_DIR}/medicine_transactions.csv", parse_dates=["txn_date"])
    return medicines, txns


# ------------------------------------------------------------------
# 1. RULE-BASED ALERTS
# ------------------------------------------------------------------
def rule_based_alerts(medicines, today=None):
    today = today or pd.Timestamp.now().normalize()
    medicines = medicines.copy()
    medicines["days_to_expiry"] = (medicines["expiry_date"] - today).dt.days

    low_stock = medicines[medicines["stock"] <= medicines["reorder_level"]]
    expiring_soon = medicines[medicines["days_to_expiry"].between(0, 30)]
    already_expired = medicines[medicines["days_to_expiry"] < 0]

    return {
        "low_stock": low_stock[["med_id", "name", "stock", "reorder_level"]],
        "expiring_soon": expiring_soon[["med_id", "name", "stock", "expiry_date", "days_to_expiry"]],
        "already_expired": already_expired[["med_id", "name", "stock", "expiry_date"]],
    }


# ------------------------------------------------------------------
# 2. ANOMALY DETECTION ON CONSUMPTION PATTERNS
# ------------------------------------------------------------------
def build_consumption_features(medicines, txns):
    """One row per medicine: recent dispense stats used to spot anomalies."""
    dispense = txns[txns["txn_type"] == "dispense"]

    features = dispense.groupby("med_id").agg(
        total_dispensed=("quantity", "sum"),
        avg_dispense_qty=("quantity", "mean"),
        dispense_events=("quantity", "count"),
        max_single_dispense=("quantity", "max"),
        std_dispense_qty=("quantity", "std"),
    ).reset_index()
    features["std_dispense_qty"] = features["std_dispense_qty"].fillna(0)

    features = features.merge(medicines[["med_id", "name", "stock"]], on="med_id", how="right")
    features = features.fillna(0)

    # Days of stock remaining at current average daily consumption rate
    features["days_of_supply_left"] = np.where(
        features["avg_dispense_qty"] > 0,
        features["stock"] / (features["total_dispensed"] / 60).replace(0, np.nan),
        np.inf,
    )
    features["days_of_supply_left"] = features["days_of_supply_left"].replace(np.inf, 9999).fillna(9999)

    return features


def detect_anomalies(features):
    model_cols = ["total_dispensed", "avg_dispense_qty", "dispense_events",
                  "max_single_dispense", "std_dispense_qty"]
    X = features[model_cols]

    if len(X) < 5:
        features["is_anomaly"] = False
        return features

    iso = IsolationForest(contamination=0.1, random_state=42)
    features["anomaly_score"] = iso.fit_predict(X)
    features["is_anomaly"] = features["anomaly_score"] == -1
    return features


if __name__ == "__main__":
    medicines, txns = load_data()

    print("=== RULE-BASED ALERTS ===")
    alerts = rule_based_alerts(medicines)
    for name, df in alerts.items():
        print(f"\n-- {name} ({len(df)}) --")
        print(df.to_string(index=False) if len(df) else "  none")

    print("\n=== ANOMALY DETECTION (unusual consumption patterns) ===")
    features = build_consumption_features(medicines, txns)
    features = detect_anomalies(features)
    anomalies = features[features["is_anomaly"]].sort_values("total_dispensed", ascending=False)
    print(anomalies[["name", "total_dispensed", "avg_dispense_qty",
                      "max_single_dispense", "days_of_supply_left"]].to_string(index=False))

    features.to_csv("medicine_consumption_analysis.csv", index=False)
    print("\nSaved medicine_consumption_analysis.csv")
