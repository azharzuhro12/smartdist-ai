from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from ml.anomaly_detection.hybrid_scorer import AnomalyDirection, AnomalySeverity, HybridAnomalyScorer
from ml.anomaly_detection.statistical_detector import StatisticalAnomalyDetector


class SyntheticAnomalyInjector:
    """
    Isolated evaluation utility for benchmarking sales anomaly detection.
    Applies controlled mathematical perturbations to historical time-series sequences.

    IMPORTANT:
    Evaluation perturbations are strictly isolated in memory and evaluation benchmarks;
    they are NEVER written into production database sales tables.
    """

    INJECTION_TYPES = [
        "SUDDEN_SPIKE_100",   # Sudden +100% surge
        "SUDDEN_SPIKE_300",   # Extreme +300% surge
        "SUDDEN_DROP_70",     # Sudden -70% decline
        "ZERO_SALES_BLOCK",   # Consecutive 3-day zero sales in active item
        "SUSTAINED_UP_SHIFT", # Sustained upward regime shift (+50% for 7 days)
        "SUSTAINED_DOWN_SHIFT",# Sustained downward regime shift (-50% for 7 days)
    ]

    @classmethod
    def inject_synthetic_anomalies(
        cls,
        series: List[float],
        seed: int = 42,
    ) -> Tuple[List[float], List[Dict[str, Any]]]:
        """
        Inject controlled synthetic anomalies into a clean time series.
        Returns:
            (perturbed_series, injection_metadata_list)
        """
        rng = np.random.RandomState(seed)
        n = len(series)
        if n < 20:
            raise ValueError(f"Series length ({n}) too short for controlled benchmark injection.")

        perturbed = list(series)
        injections: List[Dict[str, Any]] = []

        # 1. Sudden Spike (+200% on day 15)
        spike_idx = 15
        orig_val = float(perturbed[spike_idx])
        base_mag = max(orig_val, 10.0)
        spike_val = orig_val + 2.5 * base_mag
        perturbed[spike_idx] = spike_val
        injections.append({
            "index": spike_idx,
            "type": "SUDDEN_SPIKE_250",
            "expected_direction": AnomalyDirection.SPIKE,
            "original_value": orig_val,
            "injected_value": spike_val,
            "severity_expected": AnomalySeverity.HIGH,
        })

        # 2. Sudden Drop (-80% on day 22)
        drop_idx = 22
        orig_val = float(perturbed[drop_idx])
        if orig_val > 5.0:
            drop_val = orig_val * 0.15
            perturbed[drop_idx] = drop_val
            injections.append({
                "index": drop_idx,
                "type": "SUDDEN_DROP_85",
                "expected_direction": AnomalyDirection.DROP,
                "original_value": orig_val,
                "injected_value": drop_val,
                "severity_expected": AnomalySeverity.MEDIUM,
            })

        # 3. Zero Sales Shock on day 26 (for item normally selling > 5 units)
        zero_idx = 26
        orig_val = float(perturbed[zero_idx])
        if orig_val > 5.0:
            perturbed[zero_idx] = 0.0
            injections.append({
                "index": zero_idx,
                "type": "ZERO_SALES_SHOCK",
                "expected_direction": AnomalyDirection.ZERO_SALES,
                "original_value": orig_val,
                "injected_value": 0.0,
                "severity_expected": AnomalySeverity.HIGH,
            })

        # 4. Sustained upward regime shift (days 32 to 38 if series long enough)
        if n >= 40:
            shift_start = 32
            shift_len = 5
            for s_i in range(shift_start, shift_start + shift_len):
                orig_s = float(perturbed[s_i])
                perturbed[s_i] = orig_s + 1.8 * max(orig_s, 10.0)
            injections.append({
                "index": shift_start,
                "type": "SUSTAINED_UP_SHIFT",
                "expected_direction": AnomalyDirection.SPIKE,
                "original_value": float(series[shift_start]),
                "injected_value": float(perturbed[shift_start]),
                "severity_expected": AnomalySeverity.HIGH,
                "duration": shift_len,
            })

        return perturbed, injections

    @classmethod
    def evaluate_detection_benchmark(
        cls,
        clean_series: List[float],
        seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Run statistical detector across injected series and measure:
          - Synthetic Anomaly Detection Rate (True Positive Recall on injected anomalies)
          - False Positive Rate on known normal historical baseline
          - Detection Delay (delay steps from shock inception to detection)
        """
        perturbed_series, injections = cls.inject_synthetic_anomalies(clean_series, seed=seed)
        n = len(perturbed_series)

        injected_indices = {inj["index"]: inj for inj in injections}
        # If sustained shift, include all indices in that window
        for inj in injections:
            if "duration" in inj:
                for d_i in range(inj["index"], inj["index"] + inj["duration"]):
                    injected_indices[d_i] = inj

        detected_indices = set()
        for idx in range(10, n):
            hist = perturbed_series[:idx]
            res = StatisticalAnomalyDetector.evaluate_series(hist, perturbed_series[idx], window=28, min_history=7)
            if res.get("is_spike") or res.get("is_drop") or res.get("is_zero_sales"):
                detected_indices.add(idx)

        # Metrics on Injected Anomalies
        true_positives = 0
        delays = []
        for inj in injections:
            idx = inj["index"]
            dur = inj.get("duration", 1)
            # Check if detected at idx or within duration
            found = False
            for step in range(dur):
                if (idx + step) in detected_indices:
                    found = True
                    delays.append(step)
                    break
            if found:
                true_positives += 1

        detection_rate = (true_positives / len(injections) * 100.0) if injections else 100.0
        avg_delay = float(np.mean(delays)) if delays else 0.0

        # False Positives on clean pre-injection baseline (indices < min(injected_indices) or non-injected)
        non_injected_count = 0
        false_positives = 0
        for idx in range(10, n):
            if idx not in injected_indices:
                non_injected_count += 1
                if idx in detected_indices:
                    false_positives += 1

        fpr = (false_positives / non_injected_count * 100.0) if non_injected_count > 0 else 0.0

        return {
            "total_injected_anomalies": len(injections),
            "true_positives_detected": true_positives,
            "synthetic_detection_rate_pct": round(detection_rate, 2),
            "average_detection_delay_days": round(avg_delay, 2),
            "clean_baseline_observations": non_injected_count,
            "false_positives_count": false_positives,
            "false_positive_rate_pct": round(fpr, 2),
            "injections_detail": injections,
        }
