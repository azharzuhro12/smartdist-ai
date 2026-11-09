from typing import List
import pandas as pd


class RollingFeatureExtractor:
    """
    Computes rolling mean and standard deviation features per time-series group.
    Enforces strict zero-leakage guarantee by shifting the target by 1 day before
    applying rolling aggregations:
        rolling_stat_W(T) = stat(Target[T-W : T-1])
    """

    DEFAULT_WINDOWS = [7, 14, 28]

    @staticmethod
    def add_rolling_features(
        df: pd.DataFrame,
        target_col: str = "quantity_sold",
        group_cols: List[str] = ["store_nbr", "product_id"],
        date_col: str = "date",
        windows: List[int] = DEFAULT_WINDOWS,
    ) -> pd.DataFrame:
        """
        Compute leakage-free rolling statistics per series group.
        """
        res = df.copy()
        sort_order = group_cols + [date_col]
        res = res.sort_values(by=sort_order).reset_index(drop=True)

        # Shift target by 1 to exclude current day T from rolling window
        res["_target_shifted_1"] = res.groupby(group_cols, observed=True)[target_col].shift(1)

        grouped_shifted = res.groupby(group_cols, observed=True)["_target_shifted_1"]

        for window in windows:
            mean_col = f"rolling_mean_{window}"
            std_col = f"rolling_std_{window}"

            res[mean_col] = (
                grouped_shifted.rolling(window=window, min_periods=min(3, window))
                .mean()
                .reset_index(drop=True)
            )
            res[std_col] = (
                grouped_shifted.rolling(window=window, min_periods=min(3, window))
                .std()
                .reset_index(drop=True)
            )

        # Clean up temporary shifted column
        res.drop(columns=["_target_shifted_1"], inplace=True)
        return res
