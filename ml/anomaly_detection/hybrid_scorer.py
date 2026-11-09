from enum import Enum
from typing import Any, Dict, List, Optional
import numpy as np


class AnomalySeverity(str, Enum):
    NORMAL = "NORMAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyDirection(str, Enum):
    SPIKE = "SPIKE"
    DROP = "DROP"
    ZERO_SALES = "ZERO_SALES"
    FORECAST_DEVIATION = "FORECAST_DEVIATION"
    TREND_SHIFT = "TREND_SHIFT"
    NORMAL = "NORMAL"
    OTHER = "OTHER"


class HybridAnomalyScorer:
    """
    Unified multi-evidence anomaly scoring engine.
    Combines:
      - Statistical robust Z-score (S_s)
      - Standardized forecast residual (S_f)
      - ML Isolation Forest outlier score (S_m)

    Normalizes detector scores to [0.0, 1.0].
    Dynamically renormalizes weights when any detector reports INSUFFICIENT_DATA or UNAVAILABLE:
        w_norm_i = w_i / sum(w_available)
        S_final = sum(w_norm_i * S_i)

    Calibrates severity thresholds:
        [0.0, 0.40)  -> NORMAL
        [0.40, 0.60) -> LOW
        [0.60, 0.75) -> MEDIUM
        [0.75, 0.90) -> HIGH
        [0.90, 1.00] -> CRITICAL
    """

    DEFAULT_WEIGHTS = {
        "statistical": 0.40,
        "forecast": 0.35,
        "ml": 0.25,
    }

    SEVERITY_THRESHOLDS = [
        (0.90, AnomalySeverity.CRITICAL),
        (0.75, AnomalySeverity.HIGH),
        (0.60, AnomalySeverity.MEDIUM),
        (0.40, AnomalySeverity.LOW),
        (0.00, AnomalySeverity.NORMAL),
    ]

    @classmethod
    def normalize_z_score(cls, z: float) -> float:
        """
        Maps unbounded real Z-score into [0.0, 1.0].
        |Z| <= 1.0  -> 0.0 - 0.20
        |Z| == 3.0  -> ~0.65
        |Z| >= 5.0  -> ~0.90+
        Formula: 2 * (1 / (1 + exp(-0.6 * |Z|)) - 0.5)
        """
        abs_z = abs(float(z))
        norm_val = 2.0 * (1.0 / (1.0 + np.exp(-0.6 * abs_z)) - 0.5)
        return float(np.clip(norm_val, 0.0, 1.0))

    @classmethod
    def compute_hybrid_score(
        cls,
        stat_result: Dict[str, Any],
        forecast_result: Optional[Dict[str, Any]] = None,
        ml_result: Optional[Dict[str, Any]] = None,
        custom_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Combine available detector results into unified hybrid score and severity classification.
        """
        weights_config = custom_weights or cls.DEFAULT_WEIGHTS
        available_scores: Dict[str, float] = {}
        active_weights: Dict[str, float] = {}

        # 1. Statistical detector
        if stat_result.get("status") == "VALID":
            z_s = stat_result.get("robust_z_score", 0.0)
            norm_s = cls.normalize_z_score(z_s)
            available_scores["statistical"] = norm_s
            active_weights["statistical"] = weights_config.get("statistical", 0.40)

        # 2. Forecast residual detector
        if forecast_result and forecast_result.get("status") == "VALID":
            z_f = forecast_result.get("standardized_score", 0.0)
            norm_f = cls.normalize_z_score(z_f)
            available_scores["forecast"] = norm_f
            active_weights["forecast"] = weights_config.get("forecast", 0.35)

        # 3. ML detector
        if ml_result and ml_result.get("status") == "VALID":
            ml_score = float(ml_result.get("anomaly_score", 0.0))
            available_scores["ml"] = ml_score
            active_weights["ml"] = weights_config.get("ml", 0.25)

        # Fallback if no detector has valid data
        if not available_scores:
            return {
                "hybrid_score": 0.0,
                "severity": AnomalySeverity.NORMAL,
                "direction": AnomalyDirection.NORMAL,
                "is_anomaly": False,
                "weights_used": {},
                "detector_scores": {},
                "status": "INSUFFICIENT_DATA",
            }

        # Renormalize active weights so sum == 1.0
        total_weight = sum(active_weights.values())
        renormalized_weights = {k: v / total_weight for k, v in active_weights.items()}

        final_score = sum(available_scores[k] * renormalized_weights[k] for k in available_scores)
        final_score = float(np.clip(final_score, 0.0, 1.0))

        # Determine Severity
        severity = AnomalySeverity.NORMAL
        for thresh, sev in cls.SEVERITY_THRESHOLDS:
            if final_score >= thresh:
                severity = sev
                break

        # Determine Direction
        direction = AnomalyDirection.NORMAL
        is_spike = stat_result.get("is_spike", False)
        is_drop = stat_result.get("is_drop", False)
        is_zero = stat_result.get("is_zero_sales", False)

        if is_zero:
            direction = AnomalyDirection.ZERO_SALES
        elif is_spike:
            direction = AnomalyDirection.SPIKE
        elif is_drop:
            direction = AnomalyDirection.DROP
        elif forecast_result and forecast_result.get("is_significant_deviation", False):
            direction = AnomalyDirection.FORECAST_DEVIATION
        elif severity in [AnomalySeverity.MEDIUM, AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]:
            # Directional inference from deviations
            diff = stat_result.get("absolute_deviation", 0.0)
            direction = AnomalyDirection.SPIKE if diff > 0 else AnomalyDirection.DROP

        is_anomaly = severity != AnomalySeverity.NORMAL

        return {
            "hybrid_score": round(final_score, 4),
            "severity": severity,
            "direction": direction,
            "is_anomaly": is_anomaly,
            "weights_used": {k: round(v, 4) for k, v in renormalized_weights.items()},
            "detector_scores": {k: round(v, 4) for k, v in available_scores.items()},
            "status": "VALID",
        }
