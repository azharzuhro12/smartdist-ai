import math
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


class StatisticalAnomalyDetector:
    """
    Robust statistical detector for daily sales time series.
    Uses rolling median, Median Absolute Deviation (MAD), robust Z-score, and IQR.
    Strictly excludes current observation from its own historical baseline to prevent leakage.
    Handles sparse demand and zero MAD safely.
    """

    DEFAULT_WINDOW = 28
    MIN_OBSERVATIONS = 7

    @staticmethod
    def calculate_mad(values: np.ndarray, median_val: Optional[float] = None) -> float:
        """
        Calculate Median Absolute Deviation (MAD):
            MAD = median(|x_i - median(X)|)
        """
        if len(values) == 0:
            return 0.0
        med = float(np.median(values)) if median_val is None else median_val
        return float(np.median(np.abs(values - med)))

    @classmethod
    def evaluate_series(
        cls,
        history_series: Union[List[float], np.ndarray, pd.Series],
        observed_value: float,
        window: int = DEFAULT_WINDOW,
        min_history: int = MIN_OBSERVATIONS,
    ) -> Dict[str, Union[float, int, str, bool, None]]:
        """
        Evaluate a single observed point against its historical baseline.

        Formula:
            Robust Z-score:
                Z_robust = 0.6745 * (x_t - median(X)) / MAD(X)
            where 0.6745 is the consistency constant for the normal distribution:
            E[MAD] = 0.6745 * sigma.

            When MAD == 0:
                If standard deviation sigma > 0:
                    Z_robust = (x_t - median(X)) / sigma
                Else (all historical values identical):
                    If x_t == median: Z_robust = 0.0
                    Else: Z_robust = +10.0 (if x_t > median) or -10.0 (if x_t < median)
        """
        obs = float(observed_value)
        arr = np.array(history_series, dtype=float)
        # Filter finite values only
        arr = arr[np.isfinite(arr)]

        # Take the most recent 'window' observations strictly prior to current observation
        if len(arr) > window:
            arr = arr[-window:]

        if len(arr) < min_history:
            return {
                "detector": "STATISTICAL",
                "status": "INSUFFICIENT_DATA",
                "sample_size": len(arr),
                "baseline_median": None,
                "baseline_mad": None,
                "baseline_mean": None,
                "baseline_std": None,
                "iqr_lower": None,
                "iqr_upper": None,
                "robust_z_score": 0.0,
                "absolute_deviation": 0.0,
                "percentage_deviation": 0.0,
                "is_spike": False,
                "is_drop": False,
                "is_zero_sales": False,
            }

        median_val = float(np.median(arr))
        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
        mad_val = cls.calculate_mad(arr, median_val)

        q25 = float(np.percentile(arr, 25))
        q75 = float(np.percentile(arr, 75))
        iqr = q75 - q25
        iqr_lower = max(0.0, q25 - 1.5 * iqr)
        iqr_upper = q75 + 1.5 * iqr

        diff = obs - median_val
        abs_diff = abs(diff)
        pct_diff = (diff / median_val * 100.0) if median_val > 1e-4 else (100.0 if obs > 0 else 0.0)

        # Robust Z-score calculation with zero-MAD protection
        if mad_val > 1e-6:
            z_score = 0.6745 * diff / mad_val
        elif std_val > 1e-6:
            z_score = diff / std_val
        else:
            if abs_diff < 1e-6:
                z_score = 0.0
            else:
                z_score = 10.0 if diff > 0 else -10.0

        is_zero_sales = (obs == 0.0 and median_val > 2.0)
        is_spike = (z_score >= 3.0 or (obs > iqr_upper and z_score >= 2.0))
        is_drop = (z_score <= -3.0 or (obs < iqr_lower and z_score <= -2.0) or is_zero_sales)

        return {
            "detector": "STATISTICAL",
            "status": "VALID",
            "sample_size": len(arr),
            "baseline_median": round(median_val, 4),
            "baseline_mad": round(mad_val, 4),
            "baseline_mean": round(mean_val, 4),
            "baseline_std": round(std_val, 4),
            "iqr_lower": round(iqr_lower, 4),
            "iqr_upper": round(iqr_upper, 4),
            "robust_z_score": round(float(z_score), 4),
            "absolute_deviation": round(diff, 4),
            "percentage_deviation": round(pct_diff, 2),
            "is_spike": is_spike,
            "is_drop": is_drop,
            "is_zero_sales": is_zero_sales,
        }

    @classmethod
    def evaluate_batch(
        cls,
        df: pd.DataFrame,
        target_col: str = "quantity_sold",
        date_col: str = "date",
        group_cols: List[str] = ["store_nbr", "product_id"],
        window: int = DEFAULT_WINDOW,
        min_history: int = MIN_OBSERVATIONS,
    ) -> pd.DataFrame:
        """
        Evaluate time series across groups with zero leakage.
        For each date t, baseline is strictly rows in [t - window, t - 1].
        """
        res = df.copy()
        res[date_col] = pd.to_datetime(res[date_col])
        res = res.sort_values(by=group_cols + [date_col]).reset_index(drop=True)

        results = []
        for _, group in res.groupby(group_cols, observed=True):
            vals = group[target_col].to_numpy(dtype=float)
            for idx in range(len(group)):
                hist = vals[:idx]  # Strictly prior rows
                eval_res = cls.evaluate_series(hist, vals[idx], window=window, min_history=min_history)
                results.append(eval_res)

        eval_df = pd.DataFrame(results)
        for col in eval_df.columns:
            res[f"stat_{col}"] = eval_df[col].values

        return res
