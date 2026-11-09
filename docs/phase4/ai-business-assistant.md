# SmartDist AI — AI Business Assistant & Workflows

## 1. Overview
The AI Business Assistant serves as an intelligent operational copilot for retail supply chain operators, category managers, demand planners, and store supervisors. It bridges natural language conversational interaction with backend machine learning models, database aggregations, and governance documents.

> [!NOTE]
> **Deterministic & Local Execution Model**
> The assistant orchestrator (`ai_assistant/orchestrator.py`) operates as a deterministic, rule-based semantic router and response synthesizer. It runs completely locally on the server without calling external cloud LLMs (such as OpenAI GPT-4, Anthropic Claude, or Google Gemini). This design delivers:
> - **Zero Third-Party Dependency**: Unaffected by external API outages, latency jitter, or rate limiting.
> - **100% Data Provenance**: Every metric returned is directly grounded in local PostgreSQL tables, trained ML models, or internal SOP policy files.
> - **Zero Hallucination**: Tool outputs are rendered verbatim into structured templates with strict provenance attribution.

---

## 2. Supported Operational Intents
The orchestrator handles 6 operational categories:

| Intent | Trigger Queries | Tool Invoked | Grounding / Provenance |
|---|---|---|---|
| `POLICY_SOP` | "What is the policy for safety stock?", "Purchase order approval limits" | `RAGPolicyTool` | `POLICY_DOCS` with document & section citation |
| `DEMAND_FORECAST` | "Forecast demand for product 13 next 7 days", "Sales outlook" | `ForecastTool` | `MODEL_GENERATED` (LightGBM Multi-Step) |
| `INVENTORY_OPTIMIZATION` | "Evaluate inventory for product 13 branch 44", "Should we reorder?" | `InventoryOptimizationTool` | `DERIVED` (SS, ROP, EOQ, Stockout Risk) |
| `ANOMALY_DETECTION` | "Show recent sales anomalies", "Critical alerts" | `AnomalyDetectionTool` | `MODEL_GENERATED` (Ensemble Detectors) |
| `SAFE_SQL` | "What are the top 5 selling products by volume?", "Branch rankings" | `SafeSQLTool` | `KAGGLE_PUBLIC` (PostgreSQL 16) |
| `WORKFLOW` | Multi-step end-to-end operational investigations | Workflow Engine | Composite multi-source provenance |

---

## 3. Pre-Packaged Business Workflows

### 3.1 Executive Daily Briefing (`executive_briefing`)
Synthesizes top sales volume drivers from `daily_sales`, operational anomaly incident counts from `sales_anomalies`, and priority inventory stockout risks from the decision engine into a unified briefing for operations leadership.

### 3.2 Replenishment Decision Explanation (`replenishment_explanation`)
Deconstructs why a specific product at a specific branch requires an order:
1. Queries current stock position from database.
2. Computes empirical/parametric safety stock buffer and reorder point threshold.
3. Cites the governance rule from `SOP-INV-001`.
4. Recommends the optimal EOQ lot size rounded to supplier MOQ.

### 3.3 Anomaly Root Cause Investigation (`anomaly_root_cause`)
Performs automated incident triage on flagged sales surges or drops:
1. Calculates percentage deviation between observed and expected volume.
2. Formulates root cause hypothesis (promotional surge, phantom stockout, sensor error).
3. Attaches standard triage checklist from `SOP-OPS-003`.

---

## 4. REST API Contract

```http
POST /api/v1/assistant/chat
Content-Type: application/json

{
  "query": "What are the top 3 selling products by volume?"
}
```

**Response Example:**
```json
{
  "query": "What are the top 3 selling products by volume?",
  "intent": "SAFE_SQL",
  "answer": "### Business Analytics Query Result\n**Generated Safe SQL:** `SELECT p.id, p.product_name...`\n\n| id | product_name | total_quantity_sold |\n| 13 | Grocery I (Standard SKU) | 58,339,929.0 |\n| 4 | Beverages (Standard SKU) | 21,777,880.0 |\n| 8 | Cleaning (Standard SKU) | 17,514,515.0 |",
  "tool_used": "safe_sql_agent",
  "citations": [],
  "data": { "row_count": 3 },
  "provenance": "KAGGLE_PUBLIC (Ecuadorian Grocery Sales 2013)"
}
```

### Workflow Trigger Endpoint:
```http
POST /api/v1/assistant/workflow
Content-Type: application/json

{
  "workflow_name": "replenishment_explanation",
  "parameters": {
    "product_id": 13,
    "branch_id": 44
  }
}
```
