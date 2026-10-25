"""Simple scikit-learn daily milk-demand forecast; predictions are estimates, not bills."""
import sqlite3
from datetime import timedelta
import pandas as pd
from sklearn.linear_model import LinearRegression


def predict_next_days(database_path, days=7):
    con = sqlite3.connect(database_path)
    try:
        data = pd.read_sql_query(
            "SELECT delivery_date, SUM(litres) litres FROM deliveries GROUP BY delivery_date ORDER BY delivery_date", con
        )
    finally:
        con.close()
    if len(data) < 7:
        raise ValueError("At least seven dates of delivery history are required.")
    data["delivery_date"] = pd.to_datetime(data["delivery_date"])
    first_day = data["delivery_date"].min().date()
    data["day_number"] = (data["delivery_date"].dt.date - first_day).apply(lambda x: x.days)
    data["weekday"] = data["delivery_date"].dt.dayofweek
    data["month"] = data["delivery_date"].dt.month
    columns = ["day_number", "weekday", "month"]
    model = LinearRegression().fit(data[columns], data["litres"])
    last_day = data["delivery_date"].dt.date.max()
    dates = [last_day + timedelta(days=i) for i in range(1, days + 1)]
    future = pd.DataFrame({
        "delivery_date": dates,
        "day_number": [(d - first_day).days for d in dates],
        "weekday": [d.weekday() for d in dates],
        "month": [d.month for d in dates],
    })
    future["predicted_litres"] = model.predict(future[columns]).clip(min=0).round(2)
    return future[["delivery_date", "predicted_litres"]].to_dict(orient="records")
