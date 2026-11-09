from typing import List, Optional
import pandas as pd
from ml.features.calendar_features import CalendarFeatureExtractor
from ml.features.external_features import ExternalFeatureExtractor
from ml.features.lag_features import LagFeatureExtractor
from ml.features.rolling_features import RollingFeatureExtractor


class TimeSeriesFeaturePipeline:
    """
    End-to-end time-series feature engineering pipeline.
    Combines calendar, external, lag, and rolling features while guaranteeing zero future leakage.
    """

    def __init__(
        self,
        target_col: str = "quantity_sold",
        group_cols: List[str] = ["store_nbr", "product_id"],
        date_col: str = "date",
        lags: List[int] = [1, 7, 14, 28],
        rolling_windows: List[int] = [7, 14, 28],
        drop_na_lags: bool = True,
    ):
        self.target_col = target_col
        self.group_cols = group_cols
        self.date_col = date_col
        self.lags = lags
        self.rolling_windows = rolling_windows
        self.drop_na_lags = drop_na_lags

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Execute full feature transformations on input panel.
        """
        res = df.copy()

        # 1. Calendar features
        res = CalendarFeatureExtractor.add_calendar_features(res, date_col=self.date_col)

        # 2. External features (oil, holidays, store metadata, transactions)
        res = ExternalFeatureExtractor.enrich_dataset(res)

        # 3. Lag features (strictly historical shifts per series group)
        res = LagFeatureExtractor.add_lag_features(
            res,
            target_col=self.target_col,
            group_cols=self.group_cols,
            date_col=self.date_col,
            lags=self.lags,
        )

        # 4. Rolling features (strictly shifted by 1 to exclude current day T)
        res = RollingFeatureExtractor.add_rolling_features(
            res,
            target_col=self.target_col,
            group_cols=self.group_cols,
            date_col=self.date_col,
            windows=self.rolling_windows,
        )

        # 5. Drop initial rows that contain NaNs from the largest lag window (e.g. first 28 days) if requested
        if self.drop_na_lags:
            max_lag = max(self.lags)
            lag_cols = [f"lag_{k}" for k in self.lags]
            res = res.dropna(subset=lag_cols).reset_index(drop=True)

        return res
