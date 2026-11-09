from typing import Any, Dict, List
from ml.anomaly_detection.hybrid_scorer import AnomalyDirection, AnomalySeverity


class AnomalyExplanationService:
    """
    Deterministic explanation and recommendation service for sales anomalies.
    Distinguishes:
      1. Confirmed evidence (factual numerical observations).
      2. Possible explanations (contextual hypotheses).
      3. Recommended actions (prioritized operational checks).
    No LLM required; auditable, transparent, and reproducible.
    """

    @classmethod
    def generate_explanation_and_actions(
        cls,
        product_name: str,
        branch_name: str,
        observed_quantity: float,
        expected_quantity: float,
        severity: AnomalySeverity,
        direction: AnomalyDirection,
        detector_evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Synthesize plain-language business explanations and prioritized action recommendations.
        """
        diff = observed_quantity - expected_quantity
        pct_diff = (diff / expected_quantity * 100.0) if expected_quantity > 0.0 else (100.0 if observed_quantity > 0 else 0.0)

        # 1. Confirmed Evidence Summary
        stat_info = detector_evidence.get("statistical", {})
        forecast_info = detector_evidence.get("forecast", {})
        z_score = stat_info.get("robust_z_score", 0.0)

        evidence_items = [
            f"Observed sales of {observed_quantity:,.1f} units vs baseline expected {expected_quantity:,.1f} units ({pct_diff:+.1f}% deviation).",
            f"Robust statistical Z-score: {z_score:+.2f} (baseline median: {stat_info.get('baseline_median', 0.0):,.1f}, MAD: {stat_info.get('baseline_mad', 0.0):,.1f}).",
        ]
        if forecast_info.get("status") == "VALID":
            evidence_items.append(
                f"Model forecast was {forecast_info.get('predicted_forecast', 0.0):,.1f} units (residual error: {forecast_info.get('residual', 0.0):+.1f} units)."
            )

        # 2. Possible Explanations & Recommended Actions by Direction
        possible_explanations: List[str] = []
        recommended_actions: List[str] = []

        if direction == AnomalyDirection.SPIKE:
            title = f"{severity.value} severity sales spike detected for {product_name} at {branch_name}."
            possible_explanations.extend([
                "Unplanned commercial promotion, flash discount, or seasonal surge.",
                "Institutional bulk order or large commercial customer purchase.",
                "Competitor stockout nearby driving redirect traffic to this branch.",
                "Duplicate scanning or data entry error in point-of-sale recording.",
            ])
            recommended_actions.extend([
                "Audit local promotional records and corporate marketing calendar for active promotions.",
                "Inspect current available inventory to ensure adequate buffer against secondary stockout.",
                "Cross-check POS register receipts for multi-case bulk transaction identifiers.",
                "Evaluate whether this spike warrants an emergency replenishment purchase order.",
            ])

        elif direction == AnomalyDirection.DROP:
            title = f"{severity.value} severity sales drop detected for {product_name} at {branch_name}."
            possible_explanations.extend([
                "Stockout or shelf depletion preventing customer fulfillment despite healthy demand.",
                "Local competitor promotion or aggressive price undercutting.",
                "Severe weather event, transport disruption, or local holiday reducing store foot traffic.",
                "Product placement change or misplaced inventory batch in store storage.",
            ])
            recommended_actions.extend([
                "Check physical shelf availability and warehouse on-hand stock records.",
                "Review branch store opening hours and regional weather/holiday alerts on the date.",
                "Verify whether supplier delivery delays caused out-of-stock conditions.",
                "Inspect competitor pricing and local store merchandising placement.",
            ])

        elif direction == AnomalyDirection.ZERO_SALES:
            title = f"Unexpected zero sales detected for {product_name} at {branch_name}."
            possible_explanations.extend([
                "Complete inventory exhaustion (stockout) with zero physical units available.",
                "Temporary store closure, power outage, or POS register system offline.",
                "Barcode scanning failure or catalog de-listing error.",
                "Missing data ingestion or delayed daily sales ETL sync for this branch.",
            ])
            recommended_actions.extend([
                "Verify branch inventory record to confirm if on-hand stock reached zero.",
                "Check branch transaction logs to verify if the branch was open and processing other sales.",
                "Verify barcode register scan validity with the branch store manager.",
                "Check ETL data import logs for missing store-product ingestion batches.",
            ])

        elif direction == AnomalyDirection.FORECAST_DEVIATION:
            title = f"{severity.value} severity forecast deviation detected for {product_name} at {branch_name}."
            possible_explanations.extend([
                "Structural demand shift or trend alteration not yet captured by historical autoregressive lags.",
                "Atypical external covariate shock (e.g. abrupt oil price swing or untracked holiday).",
                "Cannibalization from newly introduced substitute product in the same merchandise family.",
            ])
            recommended_actions.extend([
                "Review family-level sales trajectory across neighboring branches.",
                "Check recent promotional schedules for substitute items in this product family.",
                "Evaluate model residual tracking to determine if retraining or feature update is required.",
            ])

        else:
            title = f"{severity.value} sales anomaly detected for {product_name} at {branch_name}."
            possible_explanations.append("Statistical deviation from historical empirical baseline.")
            recommended_actions.append("Review branch sales records and investigate operational conditions.")

        explanation_text = f"{title} {' '.join(possible_explanations[:2])}"

        return {
            "title": title,
            "explanation": explanation_text,
            "confirmed_evidence": evidence_items,
            "possible_explanations": possible_explanations,
            "recommended_actions": recommended_actions,
        }
