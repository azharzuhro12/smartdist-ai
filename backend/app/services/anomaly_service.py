from datetime import datetime, timezone
from decimal import Decimal
import math
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy import func, select, desc
from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.models.anomaly import AnomalyDetectionRun, SalesAnomaly
from backend.app.models.business import Branch, DailySale, Product
from ml.anomaly_detection.explanation_service import AnomalyExplanationService
from ml.anomaly_detection.forecast_residual_detector import ForecastResidualAnomalyDetector
from ml.anomaly_detection.hybrid_scorer import AnomalyDirection, AnomalySeverity, HybridAnomalyScorer
from ml.anomaly_detection.ml_detector import MLIsolationForestDetector
from ml.anomaly_detection.statistical_detector import StatisticalAnomalyDetector


class AnomalyDetectionService:
    """
    Core backend service orchestrating multi-detector anomaly evaluation,
    database persistence, idempotent batch runs, and operational queries.
    """

    _cached_ml_detector: Optional[MLIsolationForestDetector] = None

    @classmethod
    def get_ml_detector(cls) -> MLIsolationForestDetector:
        """Lazily load trained IsolationForest detector artifact."""
        if cls._cached_ml_detector is None:
            try:
                cls._cached_ml_detector = MLIsolationForestDetector.load_model()
            except Exception as e:
                logger.warning(f"Could not load ML IsolationForest model: {e}")
                cls._cached_ml_detector = MLIsolationForestDetector(model=None)
        return cls._cached_ml_detector

    @classmethod
    def execute_detection_run(
        cls,
        db: Session,
        start_date: str,
        end_date: str,
        branch_id: Optional[int] = None,
        product_id: Optional[int] = None,
        custom_weights: Optional[Dict[str, float]] = None,
        sensitivity: float = 1.0,
    ) -> AnomalyDetectionRun:
        """
        Execute an end-to-end anomaly detection batch across the requested date window.
        Idempotent: updates existing anomaly records if rerun.
        """
        now_utc = datetime.now(timezone.utc)

        # 1. Initialize Run Record
        run = AnomalyDetectionRun(
            started_at=now_utc,
            status="RUNNING",
            detection_window_start=start_date,
            detection_window_end=end_date,
            branch_id=branch_id,
            product_id=product_id,
            detector_configuration={
                "weights": custom_weights or HybridAnomalyScorer.DEFAULT_WEIGHTS,
                "sensitivity": sensitivity,
                "statistical_window": 28,
            },
            model_version="v1",
            data_provenance="KAGGLE_PUBLIC",
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        try:
            # 2. Extract series combinations to evaluate
            combo_query = select(DailySale.branch_id, DailySale.product_id).distinct()
            if branch_id:
                combo_query = combo_query.where(DailySale.branch_id == branch_id)
            if product_id:
                combo_query = combo_query.where(DailySale.product_id == product_id)

            combos = db.execute(combo_query).all()

            # Pre-load branch and product metadata caches
            branch_map = {b.id: b for b in db.query(Branch).all()}
            product_map = {p.id: p for p in db.query(Product).all()}
            ml_detector = cls.get_ml_detector()

            total_obs = 0
            anomalies_detected = 0

            # 3. Process each series
            for b_id, p_id in combos:
                branch = branch_map.get(b_id)
                product = product_map.get(p_id)
                if not branch or not product:
                    continue

                # Query all sales for this series up to end_date (sorted chronologically)
                # This provides full historical context strictly prior to each date
                sales_stmt = (
                    select(DailySale.sale_date, DailySale.quantity_sold, DailySale.promotion_quantity)
                    .where(
                        DailySale.branch_id == b_id,
                        DailySale.product_id == p_id,
                        DailySale.sale_date <= end_date,
                    )
                    .order_by(DailySale.sale_date.asc())
                )
                records = db.execute(sales_stmt).all()
                if not records:
                    continue

                dates_all = [str(r.sale_date) for r in records]
                qtys_all = [float(r.quantity_sold) for r in records]
                promos_all = [int(r.promotion_quantity) for r in records]

                date_to_idx = {d: i for i, d in enumerate(dates_all)}

                # Evaluate dates strictly in [start_date, end_date]
                target_dates = [d for d in dates_all if d >= start_date]
                total_obs += len(target_dates)

                for t_date in target_dates:
                    curr_idx = date_to_idx[t_date]
                    obs_qty = qtys_all[curr_idx]
                    history_qtys = qtys_all[:curr_idx]  # Excludes current day!

                    # Module A: Statistical evaluation
                    stat_res = StatisticalAnomalyDetector.evaluate_series(
                        history_series=history_qtys,
                        observed_value=obs_qty,
                        window=28,
                        min_history=7,
                    )

                    # Expected quantity from statistical baseline median (or 0.0)
                    exp_qty = stat_res.get("baseline_median") if stat_res.get("baseline_median") is not None else 0.0

                    # Module B: Forecast residual evaluation (if available)
                    fc_res = ForecastResidualAnomalyDetector.evaluate_residual(
                        observed_actual=obs_qty,
                        predicted_forecast=exp_qty,
                        store_nbr=branch.source_store_number,
                        product_id=p_id,
                        family=product.source_family,
                    )

                    # Module C: ML IsolationForest evaluation
                    hist_arr = np.array(history_qtys, dtype=float)
                    rolling_7 = hist_arr[-7:] if len(hist_arr) >= 7 else hist_arr
                    ml_feats = {
                        "quantity_sold": obs_qty,
                        "lag_1": history_qtys[-1] if len(history_qtys) >= 1 else 0.0,
                        "lag_7": history_qtys[-7] if len(history_qtys) >= 7 else 0.0,
                        "rolling_mean_7": float(np.mean(rolling_7)) if len(rolling_7) > 0 else 0.0,
                        "rolling_std_7": float(np.std(rolling_7, ddof=1)) if len(rolling_7) > 1 else 0.0,
                        "day_of_week": pd.to_datetime(t_date).dayofweek,
                        "is_weekend": 1 if pd.to_datetime(t_date).dayofweek >= 5 else 0,
                        "promotion_quantity": promos_all[curr_idx],
                    }
                    ml_res = ml_detector.evaluate_single(ml_feats)

                    # Module D: Hybrid scoring
                    hybrid_res = HybridAnomalyScorer.compute_hybrid_score(
                        stat_result=stat_res,
                        forecast_result=fc_res,
                        ml_result=ml_res,
                        custom_weights=custom_weights,
                    )

                    # Check if flagged as anomaly
                    if hybrid_res.get("is_anomaly", False):
                        anomalies_detected += 1
                        severity = hybrid_res["severity"]
                        direction = hybrid_res["direction"]
                        evidence = {
                            "statistical": stat_res,
                            "forecast": fc_res,
                            "ml": ml_res,
                            "hybrid": hybrid_res,
                        }

                        # Module E: Plain-language explanation & actions
                        expl_info = AnomalyExplanationService.generate_explanation_and_actions(
                            product_name=product.product_name,
                            branch_name=branch.branch_name,
                            observed_quantity=obs_qty,
                            expected_quantity=exp_qty,
                            severity=severity,
                            direction=direction,
                            detector_evidence=evidence,
                        )

                        diff = obs_qty - exp_qty
                        pct_diff = (diff / exp_qty * 100.0) if exp_qty > 0.0 else (100.0 if obs_qty > 0 else 0.0)

                        # Check if record already exists for date + branch + product (idempotency)
                        existing = (
                            db.query(SalesAnomaly)
                            .filter(
                                SalesAnomaly.anomaly_date == t_date,
                                SalesAnomaly.branch_id == b_id,
                                SalesAnomaly.product_id == p_id,
                            )
                            .first()
                        )

                        if existing:
                            existing.detection_run_id = run.id
                            existing.observed_quantity = Decimal(str(round(obs_qty, 4)))
                            existing.expected_quantity = Decimal(str(round(exp_qty, 4)))
                            existing.deviation = Decimal(str(round(diff, 4)))
                            existing.percentage_deviation = Decimal(str(round(pct_diff, 2)))
                            existing.anomaly_score = Decimal(str(round(hybrid_res["hybrid_score"], 4)))
                            existing.severity = severity.value
                            existing.direction = direction.value
                            existing.detector_evidence = evidence
                            existing.explanation = expl_info["explanation"]
                            existing.recommended_actions = expl_info["recommended_actions"]
                        else:
                            anomaly_row = SalesAnomaly(
                                detection_run_id=run.id,
                                anomaly_date=t_date,
                                branch_id=b_id,
                                product_id=p_id,
                                observed_quantity=Decimal(str(round(obs_qty, 4))),
                                expected_quantity=Decimal(str(round(exp_qty, 4))),
                                deviation=Decimal(str(round(diff, 4))),
                                percentage_deviation=Decimal(str(round(pct_diff, 2))),
                                anomaly_score=Decimal(str(round(hybrid_res["hybrid_score"], 4))),
                                severity=severity.value,
                                direction=direction.value,
                                detector_evidence=evidence,
                                explanation=expl_info["explanation"],
                                recommended_actions=expl_info["recommended_actions"],
                                investigation_status="NEW",
                                data_provenance="KAGGLE_PUBLIC",
                            )
                            db.add(anomaly_row)

            # 4. Finalize Run
            run.status = "COMPLETED"
            run.completed_at = datetime.now(timezone.utc)
            run.total_observations = total_obs
            run.anomalies_detected = anomalies_detected
            db.commit()
            db.refresh(run)
            logger.info(f"Anomaly detection run {run.id} finished: {anomalies_detected} anomalies across {total_obs} observations.")
            return run

        except Exception as e:
            db.rollback()
            run.status = "FAILED"
            run.completed_at = datetime.now(timezone.utc)
            run.error_message = str(e)
            db.commit()
            logger.error(f"Anomaly detection run {run.id} failed: {e}", exc_info=True)
            raise e

    @classmethod
    def get_summary(cls, db: Session) -> Dict[str, Any]:
        """
        Aggregate high-level anomaly metrics across the entire enterprise network.
        """
        total = db.query(func.count(SalesAnomaly.id)).scalar() or 0

        crit = db.query(func.count(SalesAnomaly.id)).filter(SalesAnomaly.severity == "CRITICAL").scalar() or 0
        high = db.query(func.count(SalesAnomaly.id)).filter(SalesAnomaly.severity == "HIGH").scalar() or 0
        med = db.query(func.count(SalesAnomaly.id)).filter(SalesAnomaly.severity == "MEDIUM").scalar() or 0
        low = db.query(func.count(SalesAnomaly.id)).filter(SalesAnomaly.severity == "LOW").scalar() or 0

        spikes = db.query(func.count(SalesAnomaly.id)).filter(SalesAnomaly.direction == "SPIKE").scalar() or 0
        drops = db.query(func.count(SalesAnomaly.id)).filter(SalesAnomaly.direction == "DROP").scalar() or 0
        zeros = db.query(func.count(SalesAnomaly.id)).filter(SalesAnomaly.direction == "ZERO_SALES").scalar() or 0
        deviations = db.query(func.count(SalesAnomaly.id)).filter(SalesAnomaly.direction == "FORECAST_DEVIATION").scalar() or 0

        aff_branches = db.query(func.count(func.distinct(SalesAnomaly.branch_id))).scalar() or 0
        aff_prods = db.query(func.count(func.distinct(SalesAnomaly.product_id))).scalar() or 0

        # Status breakdown
        statuses = ["NEW", "INVESTIGATING", "CONFIRMED", "FALSE_POSITIVE", "RESOLVED"]
        status_map = {}
        for s in statuses:
            status_map[s] = db.query(func.count(SalesAnomaly.id)).filter(SalesAnomaly.investigation_status == s).scalar() or 0

        # Date trend (last 30 distinct dates with anomalies)
        trend_stmt = (
            select(SalesAnomaly.anomaly_date, func.count(SalesAnomaly.id))
            .group_by(SalesAnomaly.anomaly_date)
            .order_by(SalesAnomaly.anomaly_date.asc())
        )
        trend_rows = db.execute(trend_stmt).all()
        date_trend = [{"date": r[0], "count": r[1]} for r in trend_rows]

        return {
            "total_anomalies": total,
            "critical_count": crit,
            "high_count": high,
            "medium_count": med,
            "low_count": low,
            "spikes_count": spikes,
            "drops_count": drops,
            "zero_sales_count": zeros,
            "forecast_deviations_count": deviations,
            "affected_branches_count": aff_branches,
            "affected_products_count": aff_prods,
            "status_breakdown": status_map,
            "severity_breakdown": {
                "CRITICAL": crit,
                "HIGH": high,
                "MEDIUM": med,
                "LOW": low,
            },
            "date_trend": date_trend,
            "data_provenance": "KAGGLE_PUBLIC",
            "generated_at": datetime.now(timezone.utc),
        }
