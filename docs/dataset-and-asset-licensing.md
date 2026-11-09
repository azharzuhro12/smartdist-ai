# SmartDist AI — Dataset, Model & Third-Party Asset Licensing

This document provides a comprehensive accounting of licenses, data provenance, intellectual property boundaries, and usage terms applicable across the SmartDist AI repository.

---

## 1. Summary of Licensing Boundaries

| Asset / Subsystem | Source / Provenance | Applicable License / Terms | Distribution Policy |
| :--- | :--- | :--- | :--- |
| **Original Application Code** | SmartDist AI Developers | **MIT License** | Fully open source, permited for commercial and personal use. |
| **Corporation Favorita Dataset** | Kaggle / Corporation Favorita (2017) | **Kaggle Competition Rules / Non-Commercial Research & Educational Use** | **NOT REDISTRIBUTED** in Git; ignored via `.gitignore`. Download from Kaggle required. |
| **Synthetic Operational Data** | Procedural Generator (`ml/pipelines/synthetic/`) | **MIT License** (Generated Output) | Freely reproducible; explicitly marked as synthetic baseline models. |
| **Trained ML Model Artifacts** | Trained locally on 2013 Favorita subset | **Derivative Work of Open Source Algorithms** | Distributed under open research guidelines for reproducibility; subject to base algorithm licenses. |
| **Documentation & Diagrams** | SmartDist AI Team | **CC BY 4.0** | Permitted with standard attribution. |

---

## 2. Authentic Historical Sales Dataset: Corporation Favorita

### Source & Provenance
- **Dataset Name:** *Corporation Favorita Grocery Sales Forecasting*
- **Host:** Kaggle Competitions (2017)
- **Primary Publisher:** Corporación Favorita (Ecuador)
- **Time Window Utilized:** Full calendar year 2013 (`2013-01-01` to `2013-12-31`, 648,648 rows)
- **Coverage:** 54 physical retail stores across Ecuador, 33 grocery and merchandise product families, daily transaction counts, holiday calendars, and national crude oil prices.

### Licensing & Attribution Terms
- **License Classification:** **Academic & Educational Research / Competition Terms** (Requires Confirmation for Commercial Exploitation).
- **Redistribution Restrictions:** The raw dataset files (`train.csv`, `transactions.csv`, `stores.csv`, `oil.csv`, `holidays_events.csv`) are **explicitly excluded from version control** via `.gitignore` (`ml/data/raw/*.csv`).
- **Academic Citation:**
  > Corporación Favorita. (2017). *Corporación Favorita Grocery Sales Forecasting*. Kaggle. https://www.kaggle.com/c/favorita-grocery-sales-forecasting

> [!IMPORTANT]
> The MIT License applied to this software repository applies **exclusively to original software source code authored for SmartDist AI**. It does **NOT** extend to or re-license the Corporation Favorita dataset.

---

## 3. Synthetic Enterprise Extensions

### Methodology & Scope
To model an enterprise supply chain without exposing proprietary corporate data, operational parameters not present in the public Kaggle dataset were generated procedurally via [`ml/pipelines/synthetic/inventory_generator.py`](../ml/pipelines/synthetic/inventory_generator.py):
1. **Warehouse Distribution Hubs:** 3 regional fulfillment centers with allocated square footage and storage capacities.
2. **Current Stock Balances:** Initialized on-hand inventory levels calibrated against product velocity and holding costs.
3. **Supplier Network & Lead Times:** Synthetic supplier master data with stochastic lead times ($L \sim \text{LogNormal}$), unit purchase costs, and fixed reorder costs ($S$).
4. **Ground-Truth Anomaly Benchmarks:** Programmatically injected demand shocks and zero-sales records (`ml/anomaly_detection/synthetic_benchmark.py`) used solely for objective precision/recall scoring.

### Disclaimer
All inventory levels, supplier names, warehouse capacities, and purchase costs are **fictional simulations** created for demonstration, testing, and operations research validation. They do not reflect the actual internal financials or operations of Corporación Favorita or any commercial entity.

---

## 4. Machine Learning Model Artifacts

Trained serialized models stored in `ml/artifacts/`:
- `lightgbm_v1.joblib` (807 KB)
- `xgboost_v1.joblib` (1,005 KB)
- `seasonal_naive_v1.joblib` (33 KB)
- `isolation_forest_v1.joblib` (960 KB)

### Intellectual Property Status
These model artifacts are statistical representations (decision trees, ensemble weights, and leaf splits) trained locally on the 2013 public historical subset using open-source algorithms (LightGBM, XGBoost, Scikit-Learn). They contain no personally identifiable information (PII) or user credentials. They are provided for instant evaluation, but can be reproduced from scratch using:
```bash
PYTHONPATH=. python -m ml.training.train
```

---

## 5. Third-Party Open Source Libraries & Frameworks

SmartDist AI incorporates established open-source software libraries under standard permissive licenses:

| Component / Library | Upstream License | Usage in Project |
| :--- | :--- | :--- |
| **FastAPI** | MIT License | REST API routing and OpenAPI documentation |
| **Starlette** | BSD-3-Clause | ASGI framework & middleware |
| **Next.js 14** | MIT License | Web frontend UI and server-side rendering |
| **React** | MIT License | User interface component library |
| **PostgreSQL** | PostgreSQL License (BSD-style) | Relational database engine |
| **Redis** | BSD-3-Clause / RSALv2 | In-memory cache & token revocation |
| **Celery** | BSD-3-Clause | Distributed task queue |
| **LightGBM** | MIT License | Gradient boosted decision trees |
| **XGBoost** | Apache 2.0 | Gradient boosted decision trees |
| **Scikit-Learn** | BSD-3-Clause | Machine learning preprocessing & evaluation |
| **Pandas / NumPy** | BSD-3-Clause | Tabular data manipulation & numerical linear algebra |
| **SQLAlchemy** | MIT License | Object-relational mapping (ORM) |
| **Pydantic** | MIT License | Data validation & schema serialization |
| **Argon2-cffi** | MIT License | Cryptographic password hashing |
| **PyJWT** | MIT License | JSON Web Token encoding and verification |
| **ChromaDB** | Apache 2.0 | Local vector database for RAG retrieval |

All third-party copyrights and intellectual property rights remain with their respective copyright holders.

