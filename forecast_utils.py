import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_squared_error
from datetime import timedelta

def create_features(df, n_lags=7):
    """Create lag features for supervised learning"""
    df = df.copy()
    for i in range(1, n_lags + 1):
        df[f"lag_{i}"] = df["Quantity"].shift(i)
    return df.dropna()

def forecast_with_xgboost(df, forecast_days=30, n_lags=7):
    """Train XGBoost model to forecast future demand"""
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date")
    df = df.set_index("Date").resample("D").sum().fillna(0).reset_index()

    # Create lag features
    df_supervised = create_features(df, n_lags)

    # Train/test split
    train = df_supervised[:-forecast_days]
    test = df_supervised[-forecast_days:]

    X_train = train.drop(columns=["Date", "Quantity"])
    y_train = train["Quantity"]
    X_test = test.drop(columns=["Date", "Quantity"])

    # Train model
    model = xgb.XGBRegressor(objective="reg:squarederror", n_estimators=100)
    model.fit(X_train, y_train)

    # Forecast future
    last_known = df_supervised.iloc[-forecast_days:].copy()
    future_dates = []

    preds = []
    last_row = last_known.iloc[-1][1:].values

    for i in range(forecast_days):
        X_pred = last_row[-n_lags:]
        y_pred = model.predict([X_pred])[0]
        preds.append(y_pred)
        last_row = np.append(last_row[1:], y_pred)
        future_dates.append(df["Date"].max() + timedelta(days=i + 1))

    result = pd.DataFrame({
        "Date": future_dates,
        "Forecast Qty": np.round(preds, 2)
    })

    return result
