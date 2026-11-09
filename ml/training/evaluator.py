from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


class ModelEvaluator:
    """
    Standardized evaluation suite for demand forecasting models.
    Computes MAE, RMSE, WAPE, and RMSLE with robust zero-handling
    and non-negative constraints.
    """

    @staticmethod
    def calculate_metrics(
        y_true: Union_Array,
        y_pred: Union_Array,
    ) -> Dict[str, float]:
        """
        Compute standard regression and demand forecasting metrics:
            - MAE: Mean Absolute Error
            - RMSE: Root Mean Squared Error
            - WAPE: Weighted Absolute Percentage Error (%)
            - RMSLE: Root Mean Squared Logarithmic Error
        Also reports diagnostic metrics:
            - count
            - actual_zero_pct
            - mean_actual
            - mean_predicted
            - negative_preds_count
        """
        y_t = np.asarray(y_true, dtype=float)
        y_p = np.asarray(y_pred, dtype=float)

        if len(y_t) != len(y_p):
            raise ValueError(f"Length mismatch: y_true ({len(y_t)}) vs y_pred ({len(y_p)})")

        n = len(y_t)
        if n == 0:
            return {
                "mae": 0.0,
                "rmse": 0.0,
                "wape": 0.0,
                "rmsle": 0.0,
                "count": 0,
                "actual_zero_pct": 0.0,
                "mean_actual": 0.0,
                "mean_predicted": 0.0,
                "negative_preds_count": 0,
            }

        # Negative prediction tracking before clipping
        neg_count = int(np.sum(y_p < 0.0))

        # Enforce non-negativity constraint for predictions
        y_p_clipped = np.maximum(0.0, y_p)
        y_t_non_neg = np.maximum(0.0, y_t)

        # 1. MAE
        abs_errors = np.abs(y_t - y_p_clipped)
        mae = float(np.mean(abs_errors))

        # 2. RMSE
        squared_errors = (y_t - y_p_clipped) ** 2
        rmse = float(np.sqrt(np.mean(squared_errors)))

        # 3. WAPE (sum of absolute errors / sum of actuals * 100)
        sum_actual = float(np.sum(np.abs(y_t)))
        sum_abs_err = float(np.sum(abs_errors))
        if sum_actual > 0.0:
            wape = float((sum_abs_err / sum_actual) * 100.0)
        else:
            wape = 0.0 if sum_abs_err == 0.0 else float("nan")

        # 4. RMSLE
        log_actual = np.log1p(y_t_non_neg)
        log_pred = np.log1p(y_p_clipped)
        rmsle = float(np.sqrt(np.mean((log_pred - log_actual) ** 2)))

        # 5. Diagnostic distributions
        zero_pct = float(np.mean(y_t == 0.0) * 100.0)
        mean_act = float(np.mean(y_t))
        mean_pred = float(np.mean(y_p_clipped))

        return {
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "wape": round(wape, 4) if not np.isnan(wape) else float("nan"),
            "rmsle": round(rmsle, 4),
            "count": n,
            "actual_zero_pct": round(zero_pct, 2),
            "mean_actual": round(mean_act, 4),
            "mean_predicted": round(mean_pred, 4),
            "negative_preds_count": neg_count,
        }

    @classmethod
    def evaluate_dataframe(
        cls,
        df: pd.DataFrame,
        actual_col: str = "quantity_sold",
        pred_col: str = "prediction",
    ) -> Dict[str, float]:
        """
        Evaluate predictions directly on a pandas DataFrame.
        """
        return cls.calculate_metrics(df[actual_col].values, df[pred_col].values)

    @classmethod
    def evaluate_by_group(
        cls,
        df: pd.DataFrame,
        group_col: str,
        actual_col: str = "quantity_sold",
        pred_col: str = "prediction",
    ) -> pd.DataFrame:
        """
        Calculate metrics partitioned by group (e.g. store_nbr, family).
        """
        records = []
        for grp_val, group_df in df.groupby(group_col, observed=True):
            m = cls.calculate_metrics(group_df[actual_col].values, group_df[pred_col].values)
            m[group_col] = grp_val
            records.append(m)

        res_df = pd.DataFrame(records)
        # Move group_col to first column
        cols = [group_col] + [c for c in res_df.columns if c != group_col]
        return res_df[cols].sort_values(by="wape", ascending=True).reset_index(drop=True)


Union_Array = Any
