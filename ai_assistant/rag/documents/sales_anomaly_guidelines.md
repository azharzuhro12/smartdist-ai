# Sales Anomaly Detection, Classification & Investigation Guidelines

**Document ID:** SOP-OPS-003  
**Category:** Operations & Anomaly Management  
**Section:** Anomaly Types, Root Cause Triage & Action Workflows  
**Effective Date:** 2024-01-01  
**Last Updated:** 2024-11-01  
**Target Audience:** Demand Planners, Anomaly Response Team, Store Operations  

---

## 1. Objective
Provide standard operating rules for detecting, classifying, investigating, and resolving abnormal retail sales events across stores and distribution channels.

## 2. Core Anomaly Typology
SmartDist AI classifies sales anomalies into three primary functional types:

### 2.1 Volume Spike (Positive Outlier)
- **Definition:** Daily sales exceed normal baseline by $> 3.0$ standard deviations ($z > 3$) or $> 300\%$ of the 30-day median.
- **Typical Causes:** Local bulk commercial purchases, unannounced marketing/promotions, localized festivals or events, competitor outages, or scan-gun data entry errors.
- **System Impact:** Sudden inventory drawdown, premature stockouts if not replenished rapidly.

### 2.2 Volume Drop / Zero Sales (Negative Outlier)
- **Definition:** Daily sales drop below $-2.5$ standard deviations or drop to zero units when historical daily average exceeds 10 units.
- **Typical Causes:** Severe on-shelf stockout (phantom inventory), POS terminal outage, unexpected store closure, inclement weather, or product recall.
- **System Impact:** Lost revenue, unfulfilled customer demand, distorted downward forecast bias if unflagged.

### 2.3 Forecast Residual Anomaly
- **Definition:** Divergence between model predicted demand $\hat{y}$ and actual observed sales $y$ where absolute residual $|y - \hat{y}| > 2.5 \times \text{MAE}_{\text{historical}}$.
- **Typical Causes:** Structural demand shifts, cannibalization from new product introductions, or holiday misalignment.

## 3. Severity Scoring and SLA Matrix
Each anomaly is assigned an anomaly severity score between $0.0$ and $1.0$:
- **CRITICAL (Severity $\ge 0.80$):** High-impact event (e.g. key staple zero sales with positive on-hand balance). Resolution SLA: 4 hours. Immediate store audit notification dispatched.
- **HIGH (Severity $0.60$ to $0.79$):** Significant divergence affecting high-volume branch-product pairs. Resolution SLA: 24 hours.
- **MEDIUM (Severity $0.40$ to $0.59$):** Moderate divergence. Triage during weekly planning cycle (within 5 business days).
- **LOW (Severity $< 0.40$):** Informational flag. Stored for model re-training and feature extraction.

## 4. Root Cause Triage Protocol
When an anomaly is surfaced by the system:
1. **Verify Physical Stock:** Check for phantom inventory (system shows stock > 0, physical shelf is empty).
2. **Review External Context:** Check promotion calendar, public holidays, local weather disruptions, or nearby store closures.
3. **Inspect POS / Pipeline Integrity:** Verify data pipeline import logs for missing hourly batches or duplicate records.
4. **Update Status in System:**
   - `DETECTED`: Initial automated identification.
   - `INVESTIGATING`: Assigned to store manager or demand planner.
   - `CONFIRMED`: Real-world demand surge or verified operational incident.
   - `FALSE_POSITIVE`: Sensor or data artifact explained without physical impact.
   - `RESOLVED`: Corrective action taken (restock, inventory adjustment, or data correction).

