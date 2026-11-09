# SmartDist AI — Next.js Business Intelligence Dashboard Guide

## 1. Overview
The SmartDist AI Business Intelligence Dashboard is built using Next.js 14 App Router, TypeScript, Tailwind CSS, Lucide React, and Recharts.

Located at `frontend/`, it communicates with the FastAPI backend at `http://localhost:8035/api/v1`.

## 2. Page Hierarchy & Capabilities

```
frontend/src/app/
├── layout.tsx         # Global shell (Sidebar navigation + Sticky Header with health status)
├── page.tsx           # Executive Overview Dashboard (KPIs, volume bar chart, anomaly table)
├── sales/page.tsx     # Sales Analytics (Top products, branch rankings, volume/revenue toggle)
├── forecasting/page.tsx # Machine Learning Demand Forecasting (7, 14, 30-day forecast curves)
├── inventory/page.tsx # Intelligent Inventory Decision Engine (SS, ROP, EOQ, Reorder triggers)
├── anomalies/page.tsx # Anomaly Explorer (Status filter, severity badges, triage modal & PATCH)
└── assistant/page.tsx # AI Business Copilot (Conversational interface, tool badges, citations)
```

## 3. Running the Dashboard
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in any modern web browser.

## 4. Production Build Verification
The dashboard has been verified with `npm run build`:
- 100% TypeScript strict type check passing.
- 9 static routes prerendered.
- Zero hydration errors or lint warnings.

