import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy.stats import norm
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.models.business import Branch, Product, ProductSupplier, Supplier
from backend.app.schemas.inventory_optimization import (
    LeadTimeDemandResult,
    ReorderPointResult,
    SafetyStockResult,
    ServiceLevelEnum,
)
from backend.app.services.forecast_service import ForecastIntegrationService
from backend.app.services.inventory_service import InventoryService
from ml.pipelines.common.constants import PROCESSED_DATA_DIR
from ml.training.model_registry import ModelRegistry


class SafetyStockService:
    """
    Production statistical engine for calculating expected lead-time demand,
    out-of-sample forecast error distributions, empirical safety stock buffers,
    and dynamic reorder points.
    """

    # Service Level to Z-score mapping (standard normal inverse CDF)
    SERVICE_LEVEL_Z_MAP = {
        0.90: 1.2816,
        0.95: 1.6449,
        0.98: 2.0537,
        0.99: 2.3263,
    }

    _cached_val_residuals: Optional[pd.DataFrame] = None

    @classmethod
    def _load_out_of_sample_residuals(cls, data_dir: Path = PROCESSED_DATA_DIR) -> pd.DataFrame:
        """
        Load and compute genuine out-of-sample forecast residuals (e = y_true - y_pred)
        using the validation partition (November 2013) evaluated with the champion model.
        """
        if cls._cached_val_residuals is not None:
            return cls._cached_val_residuals

        val_path = data_dir / "val_features.parquet"
        if not val_path.exists():
            logger.warning(f"Validation parquet {val_path} not found. Using parametric fallback.")
            return pd.DataFrame()

        try:
            val_df = pd.read_parquet(val_path)
            registry = ModelRegistry()
            model = registry.load_model("lightgbm", version="v1")
            from ml.training.train import APPROVED_FEATURE_COLS

            X_val = val_df[APPROVED_FEATURE_COLS]
            y_val = val_df["quantity_sold"].to_numpy(dtype=float)
            y_pred = model.predict(X_val)

            # Error = actual - predicted (positive error means demand exceeded forecast)
            val_df["residual"] = y_val - y_pred
            cls._cached_val_residuals = val_df[["date", "store_nbr", "product_id", "family", "residual", "quantity_sold"]].copy()
            logger.info(f"Loaded {len(cls._cached_val_residuals)} out-of-sample residuals for uncertainty analysis.")
            return cls._cached_val_residuals
        except Exception as e:
            logger.warning(f"Failed to extract out-of-sample residuals: {e}. Using parametric approximation.")
            return pd.DataFrame()

    @classmethod
    def calculate_lead_time_demand(
        cls,
        db: Session,
        product_id: int,
        branch_id: int,
        lead_time_days: Optional[int] = None,
    ) -> LeadTimeDemandResult:
        """
        Calculate expected cumulative demand over the supplier lead-time replenishment window:
            lead_time_demand = sum(daily_forecast[t] for t in 1..L)
        """
        # Resolve supplier lead time if not provided
        if lead_time_days is None:
            inv = InventoryService.get_inventory_for_product_branch(db, product_id, branch_id)
            if not inv.supplier or inv.supplier.lead_time_days is None:
                raise ValueError(f"No supplier lead time configured for product {product_id}.")
            lead_time_days = inv.supplier.lead_time_days

        if lead_time_days <= 0:
            raise ValueError(f"Lead time must be positive. Received: {lead_time_days}.")

        # Select appropriate forecast horizon (7, 14, or 30 days) covering the lead time
        if lead_time_days <= 7:
            horizon = 7
        elif lead_time_days <= 14:
            horizon = 14
        elif lead_time_days <= 30:
            horizon = 30
        else:
            raise ValueError(
                f"Lead time of {lead_time_days} days exceeds maximum supported forecasting horizon of 30 days."
            )

        # Retrieve daily forecast sequence
        fc_resp = ForecastIntegrationService.get_forecast(
            db=db, product_id=product_id, branch_id=branch_id, horizon_days=horizon
        )

        if fc_resp.status == "UNAVAILABLE" or not fc_resp.daily_forecasts:
            logger.warning(f"Forecast unavailable for product {product_id}, branch {branch_id}.")
            return LeadTimeDemandResult(
                lead_time_days=lead_time_days,
                expected_lead_time_demand=0.0,
                daily_lead_time_forecast=[],
                status="UNAVAILABLE",
            )

        # Extract daily forecasts for the exact lead-time window [1..L]
        lead_time_records = fc_resp.daily_forecasts[:lead_time_days]
        daily_values = [r.predicted_demand for r in lead_time_records]
        total_lead_time_demand = float(sum(daily_values))

        start_date = lead_time_records[0].date if lead_time_records else None
        end_date = lead_time_records[-1].date if lead_time_records else None

        return LeadTimeDemandResult(
            lead_time_days=lead_time_days,
            expected_lead_time_demand=round(total_lead_time_demand, 4),
            daily_lead_time_forecast=[round(v, 4) for v in daily_values],
            forecast_start_date=start_date,
            forecast_end_date=end_date,
            status="AVAILABLE",
        )

    MIN_SAMPLE_SIZE = 20

    @classmethod
    def _calculate_variance_inflation(
        cls,
        lead_time_days: int,
        rho: float,
        clamp_negative: bool = True,
    ) -> float:
        """
        Calculate variance inflation factor (VIF) due to AR(1) temporal autocorrelation.
        Exact stationary AR(1) cumulative error variance over lead time L:
            Var(E_L) = sigma_e^2 * (L + 2 * sum_{k=1}^{L-1} (L - k) * rho^k)
                     = sigma_e^2 * L * VIF(L, rho)
        where:
            VIF(L, rho) = 1 + (2 / L) * sum_{k=1}^{L-1} (L - k) * rho^k

        By default (clamp_negative=True), negative autocorrelation (rho < 0) is clamped
        to VIF = 1.0 as a conservative operational policy so noisy negative sample
        autocorrelation does not shrink safety stock below the i.i.d. baseline.
        When clamp_negative=False, the exact analytical AR(1) factor (< 1.0 for rho < 0)
        is returned with a positive variance floor.
        """
        if lead_time_days <= 1 or not np.isfinite(rho) or rho == 0.0:
            return 1.0
        if clamp_negative and rho <= 0.0:
            return 1.0

        rho_clamped = float(np.clip(rho, -0.99, 0.99))
        terms = [((lead_time_days - k) / lead_time_days) * (rho_clamped ** k) for k in range(1, lead_time_days)]
        raw_vif = 1.0 + 2.0 * sum(terms)
        if clamp_negative:
            return max(1.0, float(raw_vif))
        return max(0.05, float(raw_vif))

    @staticmethod
    def _clean_finite_residuals(series: pd.Series) -> pd.Series:
        """Filter out NaN, +inf, and -inf values from a residual series."""
        numeric = pd.to_numeric(series, errors="coerce")
        return numeric[np.isfinite(numeric)]

    @classmethod
    def _compute_within_series_autocorr(cls, df: pd.DataFrame) -> float:
        """
        Compute lag-1 autocorrelation strictly within chronological (store_nbr, product_id)
        trajectories to avoid artificial correlation across store/product boundaries.
        """
        if df.empty:
            return 0.0
        group_cols = [c for c in ["store_nbr", "product_id"] if c in df.columns]
        rhos: List[float] = []
        weights: List[int] = []

        if group_cols:
            grouped = df.groupby(group_cols, observed=True)
        else:
            grouped = [(None, df)]

        for _, grp in grouped:
            sorted_grp = grp.sort_values("date") if "date" in grp.columns else grp
            clean = cls._clean_finite_residuals(sorted_grp["residual"])
            if len(clean) > 2 and float(np.std(clean, ddof=1)) > 1e-6:
                r = clean.autocorr(lag=1)
                if np.isfinite(r):
                    rhos.append(float(r))
                    weights.append(len(clean))

        if not rhos:
            return 0.0
        return float(np.average(rhos, weights=weights))

    @classmethod
    def calculate_safety_stock(
        cls,
        db: Session,
        product_id: int,
        branch_id: int,
        lead_time_days: int,
        service_level: float = 0.95,
        clamp_negative_autocorr: bool = True,
    ) -> SafetyStockResult:
        """
        Calculate safety stock buffer based on cumulative lead-time forecast error uncertainty.
        Error sign convention:
            e_t = A_t - F_t (positive when actual demand exceeds forecast)
            E_L = sum_{t=1}^L e_t
            SS_empirical = max(0, Q_alpha(E_L))
            SS_parametric = max(0, L * mu_e + Z_alpha * sqrt(Var(E_L)))

        Implements hierarchical fallback:
          1. Specific series (store_nbr, product_id) cumulative errors (N >= 20)
          2. Product pooled across all branches cumulative errors (N >= 20)
          3. Product family pooled cumulative errors (N >= 20)
          4. Parametric normal approximation with exact AR(1) VIF and linear bias L * mu_e
          5. Insufficient data status fallback (when < 2 finite daily residuals exist)
        """
        if not (0.50 <= service_level < 1.0):
            raise ValueError(f"Service level must be between 0.50 and 0.999. Received: {service_level}.")
        if lead_time_days <= 0:
            raise ValueError(f"Lead time must be positive. Received: {lead_time_days}.")

        branch = db.get(Branch, branch_id)
        product = db.get(Product, product_id)
        if not branch or not product:
            raise ValueError(f"Invalid branch ({branch_id}) or product ({product_id}).")

        store_nbr = branch.source_store_number
        family = product.source_family
        residuals_df = cls._load_out_of_sample_residuals()

        if residuals_df.empty or "residual" not in residuals_df.columns:
            return SafetyStockResult(
                service_level=service_level,
                safety_stock=0.0,
                safety_stock_rounded=0,
                method="INSUFFICIENT_DATA",
                fallback_level="INSUFFICIENT_DATA",
                forecast_error_std=0.0,
                mean_bias=0.0,
                autocorrelation_lag1=0.0,
                lead_time_days=lead_time_days,
                lead_time_error_quantile=None,
                sample_size=0,
                confidence_note="No out-of-sample validation residuals available.",
                data_provenance="UNAVAILABLE",
            )

        # -------------------------------------------------------------------
        # Hierarchical Cumulative Lead-Time Error Extraction
        # -------------------------------------------------------------------
        cum_errors: List[float] = []
        fallback_level = "SERIES"
        active_df: pd.DataFrame = pd.DataFrame()
        daily_res: np.ndarray = np.array([])

        # Level 1: Series-specific (store_nbr, product_id)
        series_df = residuals_df[
            (residuals_df["store_nbr"] == store_nbr) & (residuals_df["product_id"] == product_id)
        ].sort_values("date")
        series_clean = cls._clean_finite_residuals(series_df["residual"]) if not series_df.empty else pd.Series(dtype=float)

        if len(series_clean) > 0:
            daily_res = series_clean.to_numpy(dtype=float)
            active_df = series_df
            rolling_series = series_clean.rolling(lead_time_days, min_periods=lead_time_days).sum().dropna().to_numpy(dtype=float)
            rolling_series = rolling_series[np.isfinite(rolling_series)]
            if len(rolling_series) >= cls.MIN_SAMPLE_SIZE:
                cum_errors = list(rolling_series)
                fallback_level = "SERIES"

        # Level 2: Product pooled across all branches
        prod_df = residuals_df[residuals_df["product_id"] == product_id]
        prod_clean = cls._clean_finite_residuals(prod_df["residual"]) if not prod_df.empty else pd.Series(dtype=float)
        if len(cum_errors) < cls.MIN_SAMPLE_SIZE and len(prod_clean) > 0:
            pooled_cums = []
            for _, s_group in prod_df.groupby("store_nbr"):
                s_clean = cls._clean_finite_residuals(s_group.sort_values("date")["residual"])
                s_rolled = s_clean.rolling(lead_time_days, min_periods=lead_time_days).sum().dropna().to_numpy(dtype=float)
                s_rolled = s_rolled[np.isfinite(s_rolled)]
                pooled_cums.extend(s_rolled)
            if len(pooled_cums) >= cls.MIN_SAMPLE_SIZE:
                cum_errors = pooled_cums
                fallback_level = "PRODUCT_POOLED"
                daily_res = prod_clean.to_numpy(dtype=float)
                active_df = prod_df
            elif len(daily_res) < 2:
                daily_res = prod_clean.to_numpy(dtype=float)
                active_df = prod_df

        # Level 3: Product family pooled across products and branches
        if len(cum_errors) < cls.MIN_SAMPLE_SIZE and family and "family" in residuals_df.columns:
            fam_df = residuals_df[residuals_df["family"] == family]
            fam_clean = cls._clean_finite_residuals(fam_df["residual"]) if not fam_df.empty else pd.Series(dtype=float)
            if len(fam_clean) > 0:
                fam_cums = []
                for _, f_group in fam_df.groupby(["store_nbr", "product_id"]):
                    f_clean = cls._clean_finite_residuals(f_group.sort_values("date")["residual"])
                    f_rolled = f_clean.rolling(lead_time_days, min_periods=lead_time_days).sum().dropna().to_numpy(dtype=float)
                    f_rolled = f_rolled[np.isfinite(f_rolled)]
                    fam_cums.extend(f_rolled)
                if len(fam_cums) >= cls.MIN_SAMPLE_SIZE:
                    cum_errors = fam_cums
                    fallback_level = "FAMILY_POOLED"
                    daily_res = fam_clean.to_numpy(dtype=float)
                    active_df = fam_df
                elif len(daily_res) < 2:
                    daily_res = fam_clean.to_numpy(dtype=float)
                    active_df = fam_df

        # Level 5: Insufficient Data Check (never fall back to global RMSE)
        if len(daily_res) < 2:
            return SafetyStockResult(
                service_level=service_level,
                safety_stock=0.0,
                safety_stock_rounded=0,
                method="INSUFFICIENT_DATA",
                fallback_level="INSUFFICIENT_DATA",
                forecast_error_std=0.0,
                mean_bias=0.0,
                autocorrelation_lag1=0.0,
                lead_time_days=lead_time_days,
                lead_time_error_quantile=None,
                sample_size=len(daily_res),
                confidence_note=(
                    f"Insufficient finite out-of-sample residual observations (n={len(daily_res)} < 2) "
                    "to estimate residual variance reliably."
                ),
                data_provenance="INSUFFICIENT_DATA",
            )

        # Compute daily residual statistics (bias, std, within-series lag-1 autocorrelation)
        mean_bias = float(np.mean(daily_res))
        sigma_e = float(np.std(daily_res, ddof=1))
        autocorr_val = cls._compute_within_series_autocorr(active_df) if sigma_e > 1e-6 else 0.0

        # -------------------------------------------------------------------
        # 1. Empirical Quantile Evaluation (Levels 1, 2, 3)
        #    Note: Empirical cumulative errors E_L = sum_{t=1}^L e_t already
        #    incorporate observed bias; L * mu_e is NOT added again.
        # -------------------------------------------------------------------
        if len(cum_errors) >= cls.MIN_SAMPLE_SIZE:
            quantile_val = float(np.percentile(cum_errors, service_level * 100.0))
            ss_val = max(0.0, quantile_val)

            note = (
                f"Empirical quantile SS at {service_level*100:.0f}% service level from {len(cum_errors)} "
                f"cumulative {lead_time_days}-day lead-time errors ({fallback_level} level). "
                f"Residual bias: {mean_bias:+.2f}, std: {sigma_e:.2f}, lag-1 autocorr: {autocorr_val:.2f}."
            )

            return SafetyStockResult(
                service_level=service_level,
                safety_stock=round(ss_val, 4),
                safety_stock_rounded=int(math.ceil(ss_val)),
                method="EMPIRICAL_QUANTILE",
                fallback_level=fallback_level,
                forecast_error_std=round(sigma_e, 4),
                mean_bias=round(mean_bias, 4),
                autocorrelation_lag1=round(autocorr_val, 4),
                lead_time_days=lead_time_days,
                lead_time_error_quantile=round(quantile_val, 4),
                sample_size=len(cum_errors),
                confidence_note=note,
                data_provenance="OBSERVED_OUT_OF_SAMPLE_VALIDATION",
            )

        # -------------------------------------------------------------------
        # 2. Parametric Autocorrelation-Adjusted Fallback (Level 4)
        #    E[E_L] = L * mu_e
        #    Var(E_L) = sigma_e^2 * (L + 2 * sum_{k=1}^{L-1} (L - k) * rho^k)
        #    Q_alpha(E_L) = L * mu_e + Z_alpha * sqrt(Var(E_L))
        #    SS = max(0.0, Q_alpha(E_L))
        # -------------------------------------------------------------------
        z_score = cls.SERVICE_LEVEL_Z_MAP.get(service_level, float(norm.ppf(service_level)))
        vif = cls._calculate_variance_inflation(
            lead_time_days, autocorr_val, clamp_negative=clamp_negative_autocorr
        )
        sigma_lead_time = sigma_e * math.sqrt(lead_time_days * vif)

        bias_lead_time = mean_bias * lead_time_days
        parametric_quantile = bias_lead_time + z_score * sigma_lead_time
        ss_parametric = max(0.0, parametric_quantile)

        note = (
            f"Parametric normal SS with autocorrelation correction (VIF={vif:.2f}, lag-1 rho={autocorr_val:.2f}) "
            f"due to insufficient lead-time cumulative error samples (< {cls.MIN_SAMPLE_SIZE}). "
            f"Daily residual std: {sigma_e:.2f}, daily bias: {mean_bias:+.2f}, expected cumulative bias: {bias_lead_time:+.2f}."
        )

        return SafetyStockResult(
            service_level=service_level,
            safety_stock=round(ss_parametric, 4),
            safety_stock_rounded=int(math.ceil(ss_parametric)),
            method="NORMAL_APPROXIMATION",
            fallback_level="PARAMETRIC",
            forecast_error_std=round(sigma_e, 4),
            mean_bias=round(mean_bias, 4),
            autocorrelation_lag1=round(autocorr_val, 4),
            lead_time_days=lead_time_days,
            lead_time_error_quantile=round(parametric_quantile, 4),
            sample_size=len(daily_res),
            confidence_note=note,
            data_provenance="OBSERVED_OUT_OF_SAMPLE_VALIDATION",
        )

    @classmethod
    def calculate_reorder_point(
        cls,
        db: Session,
        product_id: int,
        branch_id: int,
        service_level: float = 0.95,
        lead_time_days: Optional[int] = None,
    ) -> ReorderPointResult:
        """
        Calculate dynamic reorder point:
            reorder_point = expected_lead_time_demand + safety_stock
        """
        # 1. Lead-Time Demand
        ltd_result = cls.calculate_lead_time_demand(
            db=db, product_id=product_id, branch_id=branch_id, lead_time_days=lead_time_days
        )

        # 2. Safety Stock
        ss_result = cls.calculate_safety_stock(
            db=db,
            product_id=product_id,
            branch_id=branch_id,
            lead_time_days=ltd_result.lead_time_days,
            service_level=service_level,
        )

        rop = ltd_result.expected_lead_time_demand + ss_result.safety_stock
        rop_rounded = int(math.ceil(rop))

        # 3. Retrieve Available Inventory
        inv = InventoryService.get_inventory_for_product_branch(db, product_id, branch_id)
        avail = inv.available_stock

        # 4. Determine Reorder Status
        if avail is None:
            reorder_status = "INSUFFICIENT_DATA"
        elif avail <= ss_result.safety_stock_rounded:
            reorder_status = "URGENT_REORDER"
        elif avail <= rop_rounded:
            reorder_status = "REORDER_NOW"
        else:
            reorder_status = "HEALTHY"

        return ReorderPointResult(
            expected_lead_time_demand=ltd_result.expected_lead_time_demand,
            safety_stock=ss_result.safety_stock,
            reorder_point=round(rop, 4),
            reorder_point_rounded=rop_rounded,
            current_available_stock=avail,
            reorder_status=reorder_status,
        )
