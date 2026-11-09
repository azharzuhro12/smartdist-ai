import pandas as pd
import pytest
from ml.validation.time_series_split import TimeSeriesSplitter


def test_chronological_split_by_dates():
    """
    Verify chronological train/val/test splitting produces strictly sequential,
    non-overlapping partitions with no shuffling or leakage.
    """
    dates = pd.date_range("2023-01-01", periods=100, freq="D")
    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "quantity_sold": [float(i) for i in range(100)],
    })

    train_end = "2023-02-15"
    val_end = "2023-03-15"

    train_df, val_df, test_df = TimeSeriesSplitter.split_by_dates(
        df, train_end=train_end, val_end=val_end, date_col="date"
    )

    # 1. Total counts must equal original row count
    assert len(train_df) + len(val_df) + len(test_df) == len(df)

    # 2. Strict chronological boundaries
    assert train_df["date"].max() <= train_end
    assert val_df["date"].min() > train_end
    assert val_df["date"].max() <= val_end
    assert test_df["date"].min() > val_end

    # 3. No overlap in dates
    train_dates = set(train_df["date"])
    val_dates = set(val_df["date"])
    test_dates = set(test_df["date"])

    assert len(train_dates.intersection(val_dates)) == 0
    assert len(val_dates.intersection(test_dates)) == 0
    assert len(train_dates.intersection(test_dates)) == 0


def test_expanding_window_split():
    """
    Verify expanding window time-series cross-validation expands training folds
    and moves validation window forward without future leakage.
    """
    dates = pd.date_range("2023-01-01", periods=90, freq="D")
    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "target": range(90),
    })

    splits = list(TimeSeriesSplitter.expanding_window_split(df, folds=3, val_days=10, date_col="date"))
    assert len(splits) == 3

    prev_train_len = 0
    for fold_idx, (train_fold, val_fold) in enumerate(splits):
        # Validation fold must have exactly 10 days
        assert len(val_fold) == 10
        # Train fold must expand
        assert len(train_fold) > prev_train_len
        prev_train_len = len(train_fold)
        # Train strictly precedes validation
        assert train_fold["date"].max() < val_fold["date"].min()
