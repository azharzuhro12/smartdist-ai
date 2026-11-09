import math
from typing import Dict, List, Optional, Union
import numpy as np
import pandas as pd
from backend.app.services.safety_stock_service import SafetyStockService


class ForecastResidualAnomalyDetector:
    """
    Evaluates observed sales against out-of-sample forecast expectations.

    Residual formulation:
        e_t = A_t - F_t
        Standardized residual score:
            Z_forecast = (e_t - mu_e) / sigma_e

    Where mu_e (mean bias) and sigma_e (residual std) are derived from
    valid out-of-sample historical validation residuals (November 2013).
    Hierarchical fallback (Series -> Product-Pooled -> Family-Pooled) guarantees
    robust dispersion parameters without ever using in-sample training residuals or global RMSE.
    """

    @classmethod
    def evaluate_residual(
        cls,
        observed_actual: float,
        predicted_forecast: float,
        residuals_df: Optional[pd.DataFrame] = None,
        store_nbr: Optional[int] = None,
        product_id: Optional[int] = None,
        family: Optional[str] = None,
        min_samples: int = 10,
    ) -> Dict[str, Union[float, int, str, bool, None]]:
        """
        Evaluate forecast residual for a single observation.
        """
        actual = float(observed_actual)
        forecast = max(0.0, float(predicted_forecast))
        residual = actual - forecast
        abs_res = abs(residual)
        pct_dev = (residual / forecast * 100.0) if forecast > 1e-4 else (100.0 if actual > 0 else 0.0)

        ref_df = residuals_df if residuals_df is not None else SafetyStockService._load_out_of_sample_residuals()

        fallback_level = "SERIES"
        res_pool = np.array([])

        if ref_df is not None and not ref_df.empty and "residual" in ref_df.columns:
            # Level 1: Specific series
            if store_nbr is not None and product_id is not None:
                s_df = ref_df[(ref_df["store_nbr"] == store_nbr) & (ref_df["product_id"] == product_id)]
                if not s_df.empty:
                    clean_s = s_df["residual"].dropna().to_numpy(dtype=float)
                    clean_s = clean_s[np.isfinite(clean_s)]
                    if len(clean_s) >= min_samples:
                        res_pool = clean_s
                        fallback_level = "SERIES"

            # Level 2: Product pooled across all branches
            if len(res_pool) < min_samples and product_id is not None:
                p_df = ref_df[ref_df["product_id"] == product_id]
                if not p_df.empty:
                    clean_p = p_df["residual"].dropna().to_numpy(dtype=float)
                    clean_p = clean_p[np.isfinite(clean_p)]
                    if len(clean_p) >= min_samples:
                        res_pool = clean_p
                        fallback_level = "PRODUCT_POOLED"

            # Level 3: Family pooled
            if len(res_pool) < min_samples and family is not None and "family" in ref_df.columns:
                f_df = ref_df[ref_df["family"] == family]
                if not f_df.empty:
                    clean_f = f_df["residual"].dropna().to_numpy(dtype=float)
                    clean_f = clean_f[np.isfinite(clean_f)]
                    if len(clean_f) >= min_samples:
                        res_pool = clean_f
                        fallback_level = "FAMILY_POOLED"

        if len(res_pool) < 2:
            return {
                "detector": "FORECAST_RESIDUAL",
                "status": "INSUFFICIENT_DATA",
                "fallback_level": "INSUFFICIENT_DATA",
                "observed_actual": actual,
                "predicted_forecast": forecast,
                "residual": round(residual, 4),
                "percentage_deviation": round(pct_dev, 2),
                "expected_bias": None,
                "residual_std": None,
                "standardized_score": 0.0,
                "is_significant_deviation": False,
            }

        mean_bias = float(np.mean(res_pool))
        sigma_e = float(np.std(res_pool, ddof=1))

        if sigma_e > 1e-6:
            z_score = (residual - mean_bias) / sigma_e
        else:
            z_score = 0.0 if abs_res < 1e-6 else (10.0 if residual > 0 else -10.0)

        is_significant = abs(z_score) >= 2.5 or (abs_res > 10.0 and abs(z_score) >= 2.0)

        return {
            "detector": "FORECAST_RESIDUAL",
            "status": "VALID",
            "fallback_level": fallback_level,
            "sample_size": len(res_pool),
            "observed_actual": round(actual, 4),
            "predicted_forecast": round(forecast, 4),
            "residual": round(residual, 4),
            "percentage_deviation": round(pct_dev, 2),
            "expected_bias": round(mean_bias, 4),
            "residual_std": round(sigma_e, 4),
            "standardized_score": round(float(z_score), 4),
            "is_significant_deviation": is_significant,
        }
