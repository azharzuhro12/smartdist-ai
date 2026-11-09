from typing import List
import pandas as pd


class LagFeatureExtractor:
    """
    Creates historical lag features per time-series group (e.g. store_nbr, product_id).
    Strictly uses historical observations: lag_k on date T is target on date T - k.
    """

    DEFAULT_LAGS = [1, 7, 14, 28]

    @staticmethod
    def add_lag_features(
        df: pd.DataFrame,
        target_col: str = "quantity_sold",
        group_cols: List[str] = ["store_nbr", "product_id"],
        date_col: str = "date",
        lags: List[int] = DEFAULT_LAGS,
    ) -> pd.DataFrame:
        """
        Compute lag features per group.
        Ensures strict chronological sorting within each group before shifting.
        """
        res = df.copy()
        # Sort chronologically within group
        sort_order = group_cols + [date_col]
        res = res.sort_values(by=sort_order).reset_index(drop=True)

        grouped = res.groupby(group_cols, observed=True)[target_col]

        for lag in lags:
            col_name = f"lag_{lag}"
            # Shift within each series group
            res[col_name] = grouped.shift(lag)

        return res
