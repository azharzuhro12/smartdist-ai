import numpy as np
import pandas as pd
import pytest
from ml.features.calendar_features import CalendarFeatureExtractor
from ml.features.lag_features import LagFeatureExtractor
from ml.features.rolling_features import RollingFeatureExtractor


def test_calendar_features():
    """Verify deterministic extraction of temporal calendar features."""
    dates = pd.date_range("2023-01-01", periods=10, freq="D")
    df = pd.DataFrame({"date": dates.strftime("%Y-%m-%d")})

    res = CalendarFeatureExtractor.add_calendar_features(df, date_col="date")

    # 2023-01-01 was a Sunday (day_of_week=6, is_weekend=1, is_month_start=1, quarter=1)
    row0 = res.iloc[0]
    assert row0["year"] == 2023
    assert row0["month"] == 1
    assert row0["day"] == 1
    assert row0["day_of_week"] == 6
    assert row0["is_weekend"] == 1
    assert row0["is_month_start"] == 1
    assert row0["is_month_end"] == 0
    assert row0["quarter"] == 1


def test_lag_features_correctness_and_group_isolation():
    """
    Verify lag features strictly mirror historical values and do not leak
    between distinct series groups (different store_nbr or product_id).
    """
    dates = [f"2023-01-{i:02d}" for i in range(1, 35)]
    # Series 1: store 1, product 1, values 1..34
    s1 = pd.DataFrame({
        "date": dates,
        "store_nbr": 1,
        "product_id": 101,
        "quantity_sold": [float(i) for i in range(1, 35)],
    })
    # Series 2: store 2, product 101, values 101..134
    s2 = pd.DataFrame({
        "date": dates,
        "store_nbr": 2,
        "product_id": 101,
        "quantity_sold": [float(100 + i) for i in range(1, 35)],
    })
    df = pd.concat([s1, s2], ignore_index=True)

    res = LagFeatureExtractor.add_lag_features(
        df,
        target_col="quantity_sold",
        group_cols=["store_nbr", "product_id"],
        date_col="date",
        lags=[1, 7, 14, 28],
    )

    # Check Series 1 at index 30 (date 2023-01-31, quantity_sold=31)
    s1_res = res[(res["store_nbr"] == 1) & (res["date"] == "2023-01-31")].iloc[0]
    assert s1_res["quantity_sold"] == 31.0
    assert s1_res["lag_1"] == 30.0
    assert s1_res["lag_7"] == 24.0
    assert s1_res["lag_14"] == 17.0
    assert s1_res["lag_28"] == 3.0

    # Check Series 2 at index 30 (date 2023-01-31, quantity_sold=131)
    # Must NOT have contaminated from Series 1
    s2_res = res[(res["store_nbr"] == 2) & (res["date"] == "2023-01-31")].iloc[0]
    assert s2_res["quantity_sold"] == 131.0
    assert s2_res["lag_1"] == 130.0
    assert s2_res["lag_7"] == 124.0
    assert s2_res["lag_14"] == 117.0
    assert s2_res["lag_28"] == 103.0


def test_rolling_features_zero_future_leakage():
    """
    CRITICAL TEST: Verify rolling statistics on day T strictly exclude day T's target value.
    If day T's quantity_sold is mutated, rolling_mean and rolling_std on day T must NOT change.
    """
    dates = [f"2023-01-{i:02d}" for i in range(1, 20)]
    # Target values: 10.0 for every day except day 10
    values_base = [10.0] * len(dates)

    df_base = pd.DataFrame({
        "date": dates,
        "store_nbr": 1,
        "product_id": 1,
        "quantity_sold": values_base,
    })

    res_base = RollingFeatureExtractor.add_rolling_features(
        df_base,
        target_col="quantity_sold",
        group_cols=["store_nbr", "product_id"],
        date_col="date",
        windows=[7],
    )

    # Now create a mutated dataset where on day 10 (2023-01-10), quantity_sold jumps to 999999.0
    values_mutated = list(values_base)
    values_mutated[9] = 999999.0  # index 9 is day 10

    df_mutated = pd.DataFrame({
        "date": dates,
        "store_nbr": 1,
        "product_id": 1,
        "quantity_sold": values_mutated,
    })

    res_mutated = RollingFeatureExtractor.add_rolling_features(
        df_mutated,
        target_col="quantity_sold",
        group_cols=["store_nbr", "product_id"],
        date_col="date",
        windows=[7],
    )

    # Day 10 in res_base vs res_mutated:
    # Because day 10's target was changed, rolling_mean_7 on day 10 MUST BE IDENTICAL
    # because day 10's window only looks at days 3..9 (all 10.0)!
    row10_base = res_base[res_base["date"] == "2023-01-10"].iloc[0]
    row10_mutated = res_mutated[res_mutated["date"] == "2023-01-10"].iloc[0]

    assert row10_base["rolling_mean_7"] == 10.0
    assert row10_mutated["rolling_mean_7"] == 10.0, (
        f"LEAKAGE DETECTED: rolling_mean_7 on day T changed when day T target was mutated! "
        f"Got {row10_mutated['rolling_mean_7']} instead of 10.0"
    )
    assert row10_base["rolling_std_7"] == 0.0
    assert row10_mutated["rolling_std_7"] == 0.0

    # On day 11 (2023-01-11), day 10 IS in the historical window, so rolling_mean_7 SHOULD change
    row11_base = res_base[res_base["date"] == "2023-01-11"].iloc[0]
    row11_mutated = res_mutated[res_mutated["date"] == "2023-01-11"].iloc[0]
    assert row11_mutated["rolling_mean_7"] > row11_base["rolling_mean_7"]
