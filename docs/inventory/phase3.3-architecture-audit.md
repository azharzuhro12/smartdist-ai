# SmartDist AI — Phase 3.3 Architecture Audit & Implementation Plan
## Intelligent Inventory Optimization, Stockout Risk & Replenishment Decision Engine

**Author**: Principal AI Engineer, Senior Machine Learning Engineer & Backend Architect  
**Project**: SmartDist AI (Intelligent Distribution & Retail Management System)  
**Date**: November 9, 2026  
**Status**: APPROVED FOR FULL IMPLEMENTATION  

---

## 1. System Context & Audit Findings

The objective of Phase 3.3 is to develop a complete, testable, and mathematically justified inventory optimization engine connecting historical sales, LightGBM demand forecasts, warehouse inventory balances, and supplier purchasing constraints.

### 1.1 Existing Component Inventory & Reusability Matrix
| Component | Location | Status | Reuse Strategy |
| :--- | :--- | :--- | :--- |
| **Relational Business Models** | `backend/app/models/business.py` | Operational | Direct reuse: `Product`, `Branch`, `Warehouse`, `Supplier`, `ProductSupplier`, `Inventory`, `DailySale`. |
| **Forecasting Model Artifacts** | `ml/artifacts/` | Operational | Direct reuse: Champion `LightGBMForecaster` (`lightgbm_v1.joblib`). |
| **Forecasting Predictor** | `ml/inference/predictor.py` | Operational | Direct reuse: Multi-step recursive forecasting without future-target leakage. |
| **Inventory Service** | `backend/app/services/inventory_service.py` | Operational | Direct reuse: Balance retrieval, `available_stock = current_stock - reserved_stock`, supplier terms. |
| **Forecast Integration** | `backend/app/services/forecast_service.py` | Operational | Direct reuse: Horizon-aware daily forecast retrieval. |
| **Snapshot Service** | `backend/app/services/snapshot_service.py` | Operational | Direct reuse: Consolidated inventory + demand metrics. |
| **Integration Validator** | `backend/app/services/integration_validator.py` | Operational | Direct reuse: 38 multi-point data health checks. |

### 1.2 Data Limitations & Assumptions
1. **Demand Dataset Scope**: Observed historical demand covers the year 2013 across 54 Ecuadorian branches and 33 product families (`quantity_sold`).
2. **Forecast Error Residuals**: Out-of-sample forecast residuals are derived by evaluating the champion LightGBM model on the validation partition (`val_features.parquet`, November 2013). This guarantees that forecast error distributions are non-leaking and truly representative of forward prediction uncertainty.
3. **Inventory & Supplier Provenance**: Physical warehouse balances and supplier parameters are synthetic (`data_origin = 'SYNTHETIC'`). All monetary inventory metrics will be explicitly labeled as simulated in reports and API responses.
4. **Inbound Inventory**: Because purchase order lifecycle tracking is not yet implemented in PostgreSQL, $\text{inbound\_stock}$ is transparently set to 0 in inventory position calculations.

---

## 2. Target Architecture for Phase 3.3

```
backend/app/
├── schemas/
│   ├── inventory_forecast.py          # Phase 3.3.1 contracts
│   └── inventory_optimization.py      # Phase 3.3 optimization, risk & simulation contracts
├── services/
│   ├── inventory_service.py           # Balance & supplier retrieval
│   ├── forecast_service.py            # Champion model forecast integration
│   ├── snapshot_service.py            # Consolidated snapshot
│   ├── integration_validator.py       # Data consistency validator
│   ├── safety_stock_service.py        # Lead-time demand, residuals, empirical & normal SS, ROP
│   ├── stockout_risk_service.py       # Monte Carlo risk simulation & probability categorization
│   ├── eoq_service.py                 # EOQ, MOQ adjustment, order multiples, holding & order costs
│   ├── replenishment_service.py       # Reorder decision engine & human-readable explanations
│   ├── simulation_service.py          # Discrete-time inventory simulation (baseline vs. optimized)
│   └── decision_engine.py             # Unified end-to-end decision orchestrator
└── api/v1/endpoints/
    └── inventory.py                   # Extended REST API suite
```

---

## 3. Mathematical Specifications

### 3.1 Expected Lead-Time Demand ($d_L$)
$$d_L = \sum_{t=1}^{L} \hat{y}_t$$
where $L$ is supplier lead time in days and $\hat{y}_t$ is the recursive predicted demand for day $t$.

### 3.2 Safety Stock ($SS$)
- **Primary Empirical Quantile Method**:
  $$SS_{\text{empirical}} = \max\left(0, \text{Quantile}(e_L, \text{service\_level})\right)$$
  where $e_L = \sum_{t=1}^{L} (y_t - \hat{y}_t)$ represents cumulative out-of-sample lead-time forecast errors.
- **Normal Approximation Fallback**:
  $$SS_{\text{normal}} = Z \times \sigma_{e} \times \sqrt{L}$$
  where $Z = \Phi^{-1}(\text{service\_level})$ ($Z_{0.90} \approx 1.282, Z_{0.95} \approx 1.645, Z_{0.99} \approx 2.326$) and $\sigma_e \approx \text{RMSE}$.

### 3.3 Dynamic Reorder Point ($ROP$)
$$ROP = d_L + SS$$

### 3.4 Economic Order Quantity ($EOQ$)
$$EOQ = \sqrt{\frac{2 \times D \times S}{H}}$$
where:
- $D = \bar{d} \times 365$ (annualized forecast demand rate)
- $S$ = procurement order cost (default \$50.00/order)
- $H = c \times h_{\text{rate}}$ (annual holding cost per unit, with default $h_{\text{rate}} = 0.20$)
- Supplier constraint adjustment: $Q^* = \max(EOQ, MOQ)$, rounded to integer order multiples if specified.

### 3.5 Replenishment Recommendation Logic
- **Inventory Position**: $\text{Pos} = \text{available\_stock} + \text{inbound\_stock}$
- **Decision Hierarchy**:
  - If $\text{Pos} \le SS$: `URGENT_REORDER`
  - If $\text{Pos} \le ROP$: `REORDER`
  - If $\text{Pos} > ROP$: `NO_ACTION`
  - If data missing: `INSUFFICIENT_DATA`
- **Target Order-Up-To Level**: $S_{\text{target}} = ROP + Q^*$
- **Recommended Order Quantity**:
  $$Q_{\text{rec}} = \max\left(Q^*, S_{\text{target}} - \text{Pos}\right)$$
  adjusted to satisfy $MOQ$ and integer packaging constraints.

---

## 4. Verification & Testing Strategy
- **Unit & Statistical Tests**: Analytical verification of SS, ROP, EOQ, Monte Carlo seed invariance, and edge cases ($D=0, S=0, H=0$).
- **Replenishment Policy Tests**: Strict verification that supplier constraints (MOQ, order multiples) are respected and clear explanations are emitted.
- **Simulation Validation**: Discrete-time historical backtest verifying fill rate, stockout frequency, inventory turnover, and total modeled costs without decision-time lookahead bias.
- **Regression Suite**: Ensure all 75 existing tests continue to pass.
