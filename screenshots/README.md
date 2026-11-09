# SmartDist AI — Visual Documentation & Screenshot Guide

This directory houses official visual assets and dashboard captures showcasing SmartDist AI's production user interface.

---

## Directory Hierarchy & Target Files

```text
screenshots/
├── README.md
├── dashboard/
│   ├── executive-overview.png        # Route: /
│   └── sales-analytics.png           # Route: /sales
├── forecasting/
│   └── demand-forecasting.png        # Route: /forecasting
├── inventory/
│   └── inventory-optimization.png    # Route: /inventory
├── anomalies/
│   └── anomaly-detection.png         # Route: /anomalies
└── assistant/
    └── ai-business-assistant.png     # Route: /assistant
```

---

## Step-by-Step Capture Instructions

### 1. Launch Backend and In-Memory Services
Ensure PostgreSQL and Redis containers are running:
```bash
docker compose up -d postgres redis
```
Launch the FastAPI application server:
```bash
PYTHONPATH=. .venv/bin/python -m uvicorn backend.app.main:app --port 8035
```

### 2. Launch Next.js Frontend
In a separate terminal session:
```bash
cd frontend
npm run dev
```

### 3. Authenticate
- Open your browser at `http://localhost:3000`.
- Sign in using the default administrative credentials:
  - **Username:** `admin`
  - **Password:** `Admin@SmartDist2026!`

### 4. Capture Guidelines & Specifications
- **Aspect Ratio & Resolution:** 16:9 standard desktop resolution (**1920 × 1080** recommended).
- **Privacy Hygiene:**
  - Do **NOT** capture browser address bars containing internal tokens or passwords.
  - Ensure local operating system taskbars, personal notification banners, and browser bookmark bars are cropped out.
- **Image Format:** PNG (lossless compression).
- **Save Locations:**
  - Executive Overview -> `screenshots/dashboard/executive-overview.png`
  - Sales Analytics -> `screenshots/dashboard/sales-analytics.png`
  - Demand Forecasting -> `screenshots/forecasting/demand-forecasting.png`
  - Inventory Optimization -> `screenshots/inventory/inventory-optimization.png`
  - Anomaly Detection -> `screenshots/anomalies/anomaly-detection.png`
  - AI Business Assistant -> `screenshots/assistant/ai-business-assistant.png`
