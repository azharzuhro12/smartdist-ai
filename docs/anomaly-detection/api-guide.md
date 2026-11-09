# SmartDist AI — Anomaly Detection REST API Guide

All anomaly detection endpoints are registered under `/api/v1/anomalies` with OpenAPI documentation accessible at `/docs`.

## 1. Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/anomalies/detect` | Execute batch sales anomaly detection (sync or async via Celery). |
| `GET` | `/api/v1/anomalies/runs/{run_id}` | Retrieve status and progress of an anomaly detection execution run. |
| `GET` | `/api/v1/anomalies/summary` | Aggregate metrics on network anomalies, severity breakdown, and trends. |
| `GET` | `/api/v1/anomalies` | Paginated query of detected anomalies with multi-criteria filtering. |
| `GET` | `/api/v1/anomalies/{anomaly_id}` | Detailed representation of a specific anomaly with full detector evidence. |
| `PATCH` | `/api/v1/anomalies/{anomaly_id}/status` | Transition operational investigation status and record resolution notes. |

---

## 2. API Examples

### 2.1 Trigger Anomaly Detection Run (`POST /api/v1/anomalies/detect`)

#### Request:
```json
{
  "start_date": "2013-12-01",
  "end_date": "2013-12-31",
  "branch_id": 1,
  "product_id": null,
  "sensitivity": 1.0,
  "async_mode": false
}
```

#### Response (`200 OK`):
```json
{
  "id": 2,
  "status": "COMPLETED",
  "started_at": "2026-11-09T09:14:48.371234Z",
  "completed_at": "2026-11-09T09:14:51.218942Z",
  "detection_window_start": "2013-12-01",
  "detection_window_end": "2013-12-31",
  "total_observations": 990,
  "anomalies_detected": 175,
  "model_version": "v1",
  "error_message": null
}
```

---

### 2.2 Network Anomaly Summary (`GET /api/v1/anomalies/summary`)

#### Response (`200 OK`):
```json
{
  "total_anomalies": 175,
  "critical_count": 28,
  "high_count": 64,
  "medium_count": 83,
  "low_count": 0,
  "spikes_count": 55,
  "drops_count": 35,
  "zero_sales_count": 6,
  "forecast_deviations_count": 79,
  "affected_branches_count": 1,
  "affected_products_count": 26,
  "status_breakdown": {
    "NEW": 174,
    "INVESTIGATING": 1,
    "CONFIRMED": 0,
    "FALSE_POSITIVE": 0,
    "RESOLVED": 0
  },
  "severity_breakdown": {
    "CRITICAL": 28,
    "HIGH": 64,
    "MEDIUM": 83,
    "LOW": 0
  },
  "date_trend": [
    {"date": "2013-12-01", "count": 14},
    {"date": "2013-12-02", "count": 8}
  ],
  "data_provenance": "KAGGLE_PUBLIC",
  "generated_at": "2026-11-09T09:15:00.000000Z"
}
```

---

### 2.3 Update Investigation Status (`PATCH /api/v1/anomalies/{id}/status`)

#### Request:
```json
{
  "status": "INVESTIGATING",
  "resolution_note": "Store manager contacted to audit weekend bulk purchase."
}
```

#### Response (`200 OK`):
```json
{
  "id": 1,
  "investigation_status": "INVESTIGATING",
  "resolution_note": "Store manager contacted to audit weekend bulk purchase."
}
```
Valid statuses: `NEW`, `INVESTIGATING`, `CONFIRMED`, `FALSE_POSITIVE`, `RESOLVED`.
