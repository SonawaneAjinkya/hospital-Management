"""
Week 5: Bed Demand Prediction
Predicts how many beds will be needed on a given future date, based on
historical daily admission counts (day-of-week + rolling trend features).

Uses GradientBoostingRegressor (an XGBoost-style gradient-boosted tree,
available in scikit-learn — swap for `xgboost.XGBRegressor` with the same
.fit/.predict API if you install the xgboost package).

Run: python3 bed_demand_model.py   (from the models/ directory)
Outputs: bed_demand_model.pkl
"""

import pandas as pd
import numpy as np
import os
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def build_daily_series():
    """Aggregate admissions into a daily count time series with features."""
    admissions = pd.read_csv(f"{DATA_DIR}/admissions_clean.csv", parse_dates=["admission_date"])
    daily = admissions.groupby("admission_date").size().rename("admissions").reset_index()

    # Fill in missing dates with 0 admissions (important — gaps skew trend features)
    full_range = pd.date_range(daily["admission_date"].min(), daily["admission_date"].max())
    daily = daily.set_index("admission_date").reindex(full_range, fill_value=0)
    daily.index.name = "date"
    daily = daily.reset_index()

    # Feature engineering
    daily["day_of_week"] = daily["date"].dt.dayofweek
    daily["day_of_month"] = daily["date"].dt.day
    daily["is_weekend"] = (daily["day_of_week"] >= 5).astype(int)
    daily["rolling_7d_avg"] = daily["admissions"].rolling(7, min_periods=1).mean()
    daily["rolling_3d_avg"] = daily["admissions"].rolling(3, min_periods=1).mean()
    daily["lag_1"] = daily["admissions"].shift(1).fillna(0)
    daily["lag_7"] = daily["admissions"].shift(7).fillna(0)

    return daily


def train():
    daily = build_daily_series()
    features = ["day_of_week", "day_of_month", "is_weekend",
                "rolling_7d_avg", "rolling_3d_avg", "lag_1", "lag_7"]
    target = "admissions"

    X = daily[features]
    y = daily[target]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False  # time series -> no shuffle
    )

    models = {
        "LinearRegression": LinearRegression(),
        "GradientBoosting": GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42
        ),
    }

    best_model, best_name, best_mae = None, None, np.inf
    for name, model in models.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)
        print(f"{name}: MAE={mae:.2f}  R2={r2:.3f}")
        if mae < best_mae:
            best_model, best_name, best_mae = model, name, mae

    print(f"\nBest model: {best_name} (MAE={best_mae:.2f})")

    joblib.dump({"model": best_model, "features": features, "model_name": best_name},
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "bed_demand_model.pkl"))
    print("Saved bed_demand_model.pkl")

    return best_model, features, daily


def predict_next_n_days(model, features, daily, n_days=7):
    """Roll forward day by day, recomputing lag/rolling features each step."""
    history = daily.copy()
    predictions = []
    for i in range(n_days):
        last_date = history["date"].max()
        next_date = last_date + pd.Timedelta(days=1)
        row = {
            "date": next_date,
            "day_of_week": next_date.dayofweek,
            "day_of_month": next_date.day,
            "is_weekend": int(next_date.dayofweek >= 5),
            "rolling_7d_avg": history["admissions"].tail(7).mean(),
            "rolling_3d_avg": history["admissions"].tail(3).mean(),
            "lag_1": history["admissions"].iloc[-1],
            "lag_7": history["admissions"].iloc[-7] if len(history) >= 7 else 0,
        }
        X_next = pd.DataFrame([row])[features]
        pred = max(0, round(model.predict(X_next)[0]))
        predictions.append({"date": next_date.date().isoformat(), "predicted_admissions": pred})
        row["admissions"] = pred
        history = pd.concat([history, pd.DataFrame([row])], ignore_index=True)
    return predictions


if __name__ == "__main__":
    model, features, daily = train()
    print("\nNext 7 days forecast:")
    for p in predict_next_n_days(model, features, daily, n_days=7):
        print(f"  {p['date']}: {p['predicted_admissions']} predicted admissions")
