# SmartDist AI — Technical Documentation Index

Welcome to the engineering documentation for **SmartDist AI: Intelligent Distribution & Retail Management System**.

---

## Documentation Navigation

```text
docs/
├── architecture/                     # System Topology & Data Flow
│   ├── system-architecture.md        # Multi-tier container architecture & isolation
│   ├── data-flow.md                  # Transactional and analytical data pipelines
│   └── etl-pipeline.md               # Raw sales ingestion and validation pipeline
├── machine-learning/                 # ML Models, Forecasting & Training
│   ├── forecasting.md                # Multi-horizon forecasting architecture
│   ├── feature-engineering.md        # Lag, rolling, calendar, and external features
│   ├── model-evaluation.md           # Holdout test set metrics (MAE, RMSE, WAPE)
│   ├── model-selection.md            # Baseline vs XGBoost vs Champion LightGBM
│   ├── validation-strategy.md        # Chronological train/val/test splits (zero lookahead)
│   └── inference-guide.md            # Online and batch prediction inference pipeline
├── inventory/                        # Operations Research & Replenishment
│   ├── inventory-optimization.md     # Formulas for Safety Stock, ROP, and EOQ
│   ├── stockout-risk.md              # Days-of-supply runout and Monte Carlo simulation
│   └── inventory-forecast-integration.md # Feed-forward loop from demand forecasts to POs
├── anomaly-detection/                # Multi-Evidence Scoring Engine
│   ├── methodology.md                # Triangulated scoring (Z-score + Residual + IsolationForest)
│   ├── architecture.md               # Real-time and batch detection architectures
│   └── evaluation.md                 # Precision, recall, and synthetic benchmark results
├── ai-assistant/                     # Business Assistant & Safe Text-to-SQL
│   ├── architecture.md               # Master intent classification and tool routing
│   ├── rag.md                        # ChromaDB semantic SOP policy retrieval
│   ├── sql-security.md               # Text-to-SQL regex validation and readonly DB boundaries
│   └── dashboard-guide.md            # User interface interaction guide
├── security/                         # Security Controls & Hardening Runbooks
│   ├── authentication-and-rbac.md    # Argon2id, HS256 JWT, and role-based permissions
│   ├── database-security.md          # PostgreSQL least-privilege role segregation
│   └── security-operations.md        # CSRF tokens, fail-closed rate limits, and incident response
├── deployment/                       # Production Operations & Infrastructure
│   ├── deployment-guide.md           # Docker Compose production deployment SOP
│   ├── portfolio-demo-guide.md       # 5–7 Minute technical interview walkthrough guide
│   ├── database-backup-restore.md    # Custom compressed pg_dump and fail-safe restore SOP
│   └── monitoring-and-troubleshooting.md # Health checks, X-Request-ID, and operational runbook
├── audit/                            # Milestone Engineering Audits
│   ├── phase2-final-audit.md         # Phase 2 Data engineering audit
│   ├── phase3.3-final-statistical-audit.md # Phase 3 Forecasting & inventory audit
│   ├── phase4-final-engineering-audit.md # Phase 4 AI Assistant audit
│   ├── phase5-final-verification.md  # Phase 5 Security hardening verification
│   ├── phase6-portfolio-audit.md     # Phase 6.1 Portfolio readiness audit
│   ├── phase6.2-documentation-organization.md # Phase 6.2 Documentation reorganization audit
│   ├── phase6.4-application-demo.md  # Phase 6.4 Live demo & authentic screenshot audit
│   ├── phase6.5-final-portfolio-audit.md # Phase 6.5 Final release readiness audit
│   └── phase6.5-github-publication-checklist.md # GitHub pre-publication release checklist
└── dataset-and-asset-licensing.md    # Dataset provenance, synthetic data & IP boundaries
```

---

## Quick Reference Guides

- **Deploying to Production:** Read [`deployment/deployment-guide.md`](deployment/deployment-guide.md)
- **Understanding ML Forecasting:** Read [`machine-learning/forecasting.md`](machine-learning/forecasting.md)
- **Inventory Formulas ($SS, ROP, EOQ$):** Read [`inventory/inventory-optimization.md`](inventory/inventory-optimization.md)
- **Database Backup & Recovery:** Read [`deployment/database-backup-restore.md`](deployment/database-backup-restore.md)
- **Licensing & Data Attribution:** Read [`dataset-and-asset-licensing.md`](dataset-and-asset-licensing.md)

