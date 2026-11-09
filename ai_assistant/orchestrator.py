"""
AI Assistant Orchestrator for SmartDist AI.
Coordinates intent classification, multi-tool routing, business workflows,
grounded synthesis, and data provenance tracking.
"""

import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from ai_assistant.tools.sales_tool import SalesAnalyticsTool
from ai_assistant.tools.forecast_tool import ForecastTool
from ai_assistant.tools.inventory_tool import InventoryOptimizationTool
from ai_assistant.tools.anomaly_tool import AnomalyDetectionTool
from ai_assistant.tools.rag_tool import RAGPolicyTool
from ai_assistant.tools.sql_tool import SafeSQLTool


class AssistantIntent:
    POLICY = "POLICY_SOP"
    FORECAST = "DEMAND_FORECAST"
    INVENTORY = "INVENTORY_OPTIMIZATION"
    ANOMALY = "ANOMALY_DETECTION"
    SQL = "SAFE_SQL"
    WORKFLOW = "WORKFLOW"
    GENERAL = "GENERAL"


class AIAssistantOrchestrator:
    """Master orchestrator for the SmartDist AI Assistant."""

    def __init__(self):
        self.sales_tool = SalesAnalyticsTool()
        self.forecast_tool = ForecastTool()
        self.inventory_tool = InventoryOptimizationTool()
        self.anomaly_tool = AnomalyDetectionTool()
        self.rag_tool = RAGPolicyTool()
        self.sql_tool = SafeSQLTool()

    def classify_intent(self, query: str) -> str:
        """Classifies user query into the appropriate operational intent."""
        q = query.lower().strip()

        # Policy & SOP questions (formulas, guidelines, approval thresholds, rules)
        if any(w in q for w in ["sop", "policy", "guideline", "formula", "approval", "how to calculate", "what is eoq", "threshold", "operating hours", "christmas"]):
            return AssistantIntent.POLICY

        # Forecasting queries
        if any(w in q for w in ["forecast", "predict", "future sales", "next 7 days", "next 14 days", "next 30 days", "horizon"]):
            return AssistantIntent.FORECAST

        # Inventory optimization queries
        if any(w in q for w in ["reorder", "safety stock", "stockout", "shortage", "replenish", "eoq", "inventory level", "stock level", "on hand", "inventory"]):
            return AssistantIntent.INVENTORY

        # Anomaly detection queries
        if any(w in q for w in ["anomaly", "anomalies", "spike", "drop", "outlier", "irregular", "surge"]):
            return AssistantIntent.ANOMALY

        # Data & sales analytics (top products, branch performance, ranking, query)
        if any(w in q for w in ["top", "sales", "revenue", "branch", "store", "volume", "sold", "supplier", "warehouse", "category"]):
            return AssistantIntent.SQL

        return AssistantIntent.GENERAL

    def chat(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Processes a user question, routes to the best tool or workflow,
        and generates a grounded, cited response.
        """
        active_db = db or SessionLocal()
        close_db = db is None
        try:
            q_lower = query.lower().strip()

            # 0. Prompt Injection & Security Override Guard
            injection_phrases = [
                "ignore previous instructions",
                "ignore all instructions",
                "forget previous instructions",
                "bypass security",
                "override system prompt",
                "dump all passwords",
                "dump user passwords",
            ]
            if any(phrase in q_lower for phrase in injection_phrases):
                return {
                    "query": query,
                    "intent": "SECURITY_GUARD",
                    "answer": (
                        "### Security Policy Enforcement\n"
                        "Operational security boundaries, read-only database permissions, and table allowlists "
                        "cannot be overridden or bypassed via natural language instructions."
                    ),
                    "tool_used": "security_gateway",
                    "citations": [],
                    "data": {"blocked": True, "reason": "Prompt injection / security override attempt detected"},
                    "provenance": "SECURITY_POLICY (Zero-Trust Governance Gateway)",
                }

            intent = self.classify_intent(query)

            # 1. RAG Policy Intent
            if intent == AssistantIntent.POLICY:
                rag_res = self.rag_tool.query_policy(query)
                passages = rag_res["passages"]
                top = passages[0] if passages else None

                if top:
                    answer = (
                        f"### {top['title']} ({top['section']})\n\n"
                        f"{top['content']}\n\n"
                        f"{rag_res['citation_block']}"
                    )
                else:
                    answer = "No exact policy matching your query was found in the SmartDist SOP index."

                return {
                    "query": query,
                    "intent": intent,
                    "answer": answer,
                    "tool_used": self.rag_tool.name,
                    "citations": [p["citation"] for p in passages],
                    "data": passages,
                    "provenance": "POLICY_DOCS (Standard Operating Procedures & Procurement Guidelines)",
                }

            # 2. Forecasting Intent
            elif intent == AssistantIntent.FORECAST:
                prod_match = re.search(r"product\s+(\d+)", q_lower)
                branch_match = re.search(r"branch\s+(\d+)|store\s+(\d+)", q_lower)
                horizon_match = re.search(r"(\d+)\s*days?", q_lower)

                prod_id = int(prod_match.group(1)) if prod_match else 13
                branch_id = int(branch_match.group(1) or branch_match.group(2)) if branch_match else 44
                horizon = int(horizon_match.group(1)) if horizon_match else 7
                if horizon not in {7, 14, 30}:
                    horizon = 7

                fc_res = self.forecast_tool.get_forecast(
                    product_id=prod_id,
                    branch_id=branch_id,
                    horizon_days=horizon,
                    db=active_db,
                )

                pts = fc_res.get("daily_forecasts") or fc_res.get("forecast_points") or []
                total_fc = sum(
                    (p.get("predicted_demand") if "predicted_demand" in p else p.get("forecasted_quantity", 0))
                    for p in pts
                )
                mean_daily = total_fc / len(pts) if pts else 0.0

                answer = (
                    f"### Demand Forecast ({horizon}-Day Horizon)\n"
                    f"- **Product ID:** {prod_id}\n"
                    f"- **Branch ID:** {branch_id}\n"
                    f"- **Total Predicted Demand:** {total_fc:,.1f} units\n"
                    f"- **Daily Average Demand:** {mean_daily:,.1f} units/day\n"
                    f"- **Model Version:** {fc_res.get('model_version', 'LGBM_MultiStep_v1')}\n\n"
                    f"Demand is projected recursively using lag and rolling calendar features."
                )

                return {
                    "query": query,
                    "intent": intent,
                    "answer": answer,
                    "tool_used": self.forecast_tool.name,
                    "citations": [],
                    "data": fc_res,
                    "provenance": "MODEL_GENERATED (LightGBM Recursive Multi-Step Forecast)",
                }

            # 3. Inventory Optimization Intent
            elif intent == AssistantIntent.INVENTORY:
                prod_match = re.search(r"product\s+(\d+)", q_lower)
                branch_match = re.search(r"branch\s+(\d+)|store\s+(\d+)", q_lower)

                if prod_match and branch_match:
                    prod_id = int(prod_match.group(1))
                    branch_id = int(branch_match.group(1) or branch_match.group(2))
                    inv_res = self.inventory_tool.evaluate_item(prod_id, branch_id, db=active_db)

                    rec = inv_res.get("recommendation", {})
                    stockout_prob = inv_res.get("stockout_risk", {}).get("stockout_probability")
                    stockout_pct_str = f"{stockout_prob * 100:.1f}%" if stockout_prob is not None else "N/A"

                    ss_val = inv_res.get("safety_stock", {}).get("safety_stock")
                    ss_str = f"{ss_val:,.1f}" if ss_val is not None else "N/A"
                    rop_val = inv_res.get("reorder_point", {}).get("reorder_point")
                    rop_str = f"{rop_val:,.1f}" if rop_val is not None else "N/A"

                    order_qty = rec.get("recommended_order_quantity", 0)
                    decision = str(rec.get("decision", "MAINTAIN"))
                    explanation = rec.get("explanation", "Inventory evaluated successfully.")

                    answer = (
                        f"### Inventory Decision Evaluation\n"
                        f"- **Product:** {inv_res.get('product_name')} (ID: {prod_id})\n"
                        f"- **Branch:** {inv_res.get('branch_name')} (ID: {branch_id})\n"
                        f"- **Available Stock:** {inv_res.get('available_stock', 'Not Set')} units\n"
                        f"- **Safety Stock (SS):** {ss_str} units\n"
                        f"- **Reorder Point (ROP):** {rop_str} units\n"
                        f"- **Stockout Probability:** {stockout_pct_str}\n"
                        f"- **Recommendation:** **{decision}** (Order Quantity: {order_qty} units)\n\n"
                        f"**Explanation:** {explanation}"
                    )
                    return {
                        "query": query,
                        "intent": intent,
                        "answer": answer,
                        "tool_used": self.inventory_tool.name,
                        "citations": ["[SOP-INV-001] Inventory Replenishment & Stock Control"],
                        "data": inv_res,
                        "provenance": "DERIVED (Unified Inventory Decision Engine: SS, ROP, EOQ)",
                    }
                else:
                    summary_res = self.inventory_tool.get_summary(size=5, db=active_db)
                    items = summary_res.get("items", [])
                    reorders = [
                        i for i in items
                        if (i.get("recommended_order_quantity") or i.get("recommendation", {}).get("recommended_order_quantity", 0)) > 0
                    ]
                    total_evaluated = summary_res.get("total", summary_res.get("total_items", len(items)))
                    total_reorders = summary_res.get("total_reorder_required", len(reorders))

                    lines = [
                        "### Inventory Optimization Overview",
                        f"- **Total Products Evaluated:** {total_evaluated}",
                        f"- **Immediate Reorder Triggers:** {total_reorders} items requiring replenishment",
                        "\n**Priority Replenishment Recommendations:**",
                    ]
                    target_items = reorders[:5] if reorders else items[:5]
                    for it in target_items:
                        p_name = it.get("product_name")
                        b_name = it.get("branch_name")
                        rec_dict = it.get("recommendation", {})
                        rec_qty = (
                            it.get("recommended_order_quantity")
                            if "recommended_order_quantity" in it
                            else rec_dict.get("recommended_order_quantity", 0)
                        )
                        urgency = it.get("risk_category") or rec_dict.get("urgency_level", "NORMAL")
                        lines.append(f"- **{p_name}** at *{b_name}*: Order **{rec_qty} units** [Risk/Urgency: {urgency}]")

                    answer = "\n".join(lines)
                    return {
                        "query": query,
                        "intent": intent,
                        "answer": answer,
                        "tool_used": self.inventory_tool.name,
                        "citations": ["[SOP-INV-001] Inventory Replenishment & Stock Control"],
                        "data": summary_res,
                        "provenance": "DERIVED (Unified Inventory Decision Engine: SS, ROP, EOQ)",
                    }

            # 4. Anomaly Detection Intent
            elif intent == AssistantIntent.ANOMALY:
                summary = self.anomaly_tool.get_summary(db=active_db)
                recent = self.anomaly_tool.get_recent_anomalies(limit=5, db=active_db)
                sev_map = summary.get("severity_breakdown") or summary.get("severity_counts") or {}
                status_map = summary.get("status_breakdown") or {}
                pending_triage = summary.get(
                    "pending_triage",
                    status_map.get("NEW", 0) + status_map.get("INVESTIGATING", 0),
                )
                crit_cnt = summary.get("critical_count", sev_map.get("CRITICAL", 0))
                high_cnt = summary.get("high_count", sev_map.get("HIGH", 0))

                lines = [
                    "### Sales Anomaly Detection Summary",
                    f"- **Total Anomalies in System:** {summary.get('total_anomalies', 0)}",
                    f"- **Pending Triage:** {pending_triage}",
                    f"- **Critical Severity Count:** {crit_cnt}",
                    f"- **High Severity Count:** {high_cnt}",
                    "\n**Recent High-Severity Sales Anomalies:**",
                ]

                for a in recent:
                    lines.append(
                        f"- **{a['date']} — {a['product_name']} at {a['branch_name']}:** "
                        f"{a['direction']} (Observed: {a['observed_qty']:.0f}, Expected: {a['expected_qty']:.0f}, "
                        f"Severity: {a['severity']})\n"
                        f"  *Cause:* {a['explanation'][:160]}..."
                    )

                answer = "\n".join(lines)
                return {
                    "query": query,
                    "intent": intent,
                    "answer": answer,
                    "tool_used": self.anomaly_tool.name,
                    "citations": ["[SOP-OPS-003] Sales Anomaly Detection, Classification & Investigation Guidelines"],
                    "data": {"summary": summary, "recent": recent},
                    "provenance": "MODEL_GENERATED (Phase 4.1 Hybrid Statistical + ML Anomaly Ensemble)",
                }

            # 5. Safe Text-to-SQL Intent (Sales, branches, suppliers, general aggregates)
            else:
                sql_res = self.sql_tool.execute_natural_query(query, db=active_db)
                rows = sql_res.get("rows", [])
                cols = sql_res.get("columns", [])

                lines = [
                    "### Business Analytics Query Result",
                    f"**Generated Safe SQL:** `{sql_res.get('sql')}`\n",
                    f"**Rows Returned:** {sql_res.get('row_count')} | **Execution Time:** {sql_res.get('execution_time_ms')}ms\n",
                ]

                if rows and cols:
                    header = "| " + " | ".join(cols) + " |"
                    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
                    lines.append(header)
                    lines.append(sep)
                    for r in rows[:10]:
                        row_vals = [str(r.get(c, "")) for c in cols]
                        lines.append("| " + " | ".join(row_vals) + " |")

                answer = "\n".join(lines)
                return {
                    "query": query,
                    "intent": intent,
                    "answer": answer,
                    "tool_used": self.sql_tool.name,
                    "citations": [],
                    "data": sql_res,
                    "provenance": sql_res.get("provenance", "ENTERPRISE_DB"),
                }

        finally:
            if close_db:
                active_db.close()

    def execute_workflow(self, workflow_name: str, params: Optional[Dict[str, Any]] = None, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Executes an end-to-end multi-step business workflow.
        Supported workflows:
        - 'sales_investigation'
        - 'inventory_shortage'
        - 'replenishment_explanation'
        - 'anomaly_root_cause'
        - 'demand_forecast_analysis'
        - 'executive_briefing'
        """
        params = params or {}
        active_db = db or SessionLocal()
        close_db = db is None
        try:
            name = workflow_name.lower().strip()

            if name == "executive_briefing":
                top_sales = self.sales_tool.get_top_products(limit=3, db=active_db)
                anom_summary = self.anomaly_tool.get_summary(db=active_db)
                inv_summary = self.inventory_tool.get_summary(size=5, db=active_db)

                sev_map = anom_summary.get("severity_breakdown") or anom_summary.get("severity_counts") or {}
                crit_cnt = anom_summary.get("critical_count", sev_map.get("CRITICAL", 0))
                high_cnt = anom_summary.get("high_count", sev_map.get("HIGH", 0))
                total_inv = inv_summary.get("total", inv_summary.get("total_items", 0))
                reorder_cnt = inv_summary.get("total_reorder_required", 0)

                briefing = (
                    "## SmartDist Executive Daily Briefing\n\n"
                    "### 1. Revenue & Sales Drivers\n"
                    f"- Top product family: **{top_sales[0]['product_name']}** with {top_sales[0]['units_sold']:,.0f} units sold.\n"
                    f"- Second highest: **{top_sales[1]['product_name']}** with {top_sales[1]['units_sold']:,.0f} units sold.\n\n"
                    "### 2. Operational Anomalies\n"
                    f"- Total recorded anomalies: **{anom_summary.get('total_anomalies', 0)}**\n"
                    f"- High/Critical severity flags: **{high_cnt} High / {crit_cnt} Critical**\n\n"
                    "### 3. Inventory Availability & Replenishment\n"
                    f"- Evaluated inventory lines: **{total_inv}**\n"
                    f"- Active reorder triggers: **{reorder_cnt}** items requiring replenishment per SOP-INV-001.\n"
                )
                return {
                    "workflow": name,
                    "title": "Executive Daily Briefing",
                    "report": briefing,
                    "citations": [
                        "[SOP-INV-001] Standard Operating Procedure: Inventory Replenishment & Stock Control",
                        "[SOP-OPS-003] Sales Anomaly Detection, Classification & Investigation Guidelines",
                    ],
                    "sections": {
                        "sales": top_sales,
                        "anomalies": anom_summary,
                        "inventory": inv_summary,
                    },
                    "provenance": "COMPOSITE (Kaggle Public Sales + Anomaly Detector + Decision Engine)",
                }

            elif name == "replenishment_explanation":
                prod_id = params.get("product_id", 13)
                branch_id = params.get("branch_id", 44)
                inv_eval = self.inventory_tool.evaluate_item(prod_id, branch_id, db=active_db)
                policy = self.rag_tool.query_policy("What is the formula for safety stock and reorder point?", top_k=1)

                rec = inv_eval.get("recommendation", {})
                stockout_prob = inv_eval.get("stockout_risk", {}).get("stockout_probability")
                stockout_str = f"{stockout_prob * 100:.1f}%" if stockout_prob is not None else "Undefined"

                ss_val = inv_eval.get("safety_stock", {}).get("safety_stock", 0.0)
                rop_val = inv_eval.get("reorder_point", {}).get("reorder_point", 0.0)
                decision = str(rec.get("decision", "MAINTAIN"))
                order_qty = rec.get("recommended_order_quantity", 0)

                explanation = (
                    f"## Replenishment Decision Explanation\n\n"
                    f"**Target:** {inv_eval.get('product_name')} at {inv_eval.get('branch_name')}\n\n"
                    f"### Stock Position vs Policy Thresholds\n"
                    f"- **Current Available Inventory:** {inv_eval.get('available_stock', 'Not Set')} units\n"
                    f"- **Calculated Safety Stock (SS):** {ss_val:,.1f} units\n"
                    f"- **Reorder Point (ROP):** {rop_val:,.1f} units\n"
                    f"- **Stockout Probability:** {stockout_str}\n\n"
                    f"### Policy Governance Rule\n"
                    f"According to **{policy['passages'][0]['citation'] if policy['passages'] else 'SOP-INV-001'}**:\n"
                    f"> *A replenishment order is triggered whenever Available/Effective Inventory <= ROP.*\n\n"
                    f"### Recommended Action\n"
                    f"- **Decision:** **{decision}**\n"
                    f"- **Suggested Quantity:** {order_qty} units (EOQ rounded to supplier MOQ)\n"
                    f"- **Urgency:** {rec.get('urgency_level', 'NONE')}\n"
                    f"- **Notes:** {rec.get('explanation', '')}\n"
                )
                return {
                    "workflow": name,
                    "title": "Replenishment Decision Explanation",
                    "report": explanation,
                    "data": inv_eval,
                    "citations": [p["citation"] for p in policy.get("passages", [])],
                    "provenance": "DERIVED (Unified Inventory Decision Engine + SOP-INV-001)",
                }

            elif name == "anomaly_root_cause":
                anom_list = self.anomaly_tool.get_recent_anomalies(limit=1, db=active_db)
                if not anom_list:
                    return {"workflow": name, "title": "Anomaly Investigation", "report": "No anomalies found."}

                target = anom_list[0]
                guidelines = self.rag_tool.query_policy("How to investigate sales anomaly and root cause?", top_k=1)

                report = (
                    f"## Anomaly Root Cause Investigation\n\n"
                    f"**Incident ID:** {target['anomaly_id']} | **Date:** {target['date']}\n"
                    f"**Entity:** {target['product_name']} at {target['branch_name']}\n\n"
                    f"### Variance Analysis\n"
                    f"- **Observed Sales:** {target['observed_qty']:.1f} units\n"
                    f"- **Expected Baseline:** {target['expected_qty']:.1f} units\n"
                    f"- **Deviation:** {target['deviation']:.1f} units ({target['direction']})\n"
                    f"- **Severity Score:** {target['anomaly_score']:.3f} ({target['severity']})\n\n"
                    f"### Root Cause Diagnosis\n"
                    f"{target['explanation']}\n\n"
                    f"### Standard Operating Triage Protocol\n"
                    f"{guidelines['passages'][0]['content'] if guidelines['passages'] else 'Follow SOP-OPS-003'}\n"
                )
                return {
                    "workflow": name,
                    "title": "Anomaly Root Cause Investigation",
                    "report": report,
                    "data": target,
                    "citations": [p["citation"] for p in guidelines.get("passages", [])],
                    "provenance": "MODEL_GENERATED (Phase 4.1 Hybrid Ensemble + SOP-OPS-003)",
                }

            else:
                return self.execute_workflow("executive_briefing", params, db=active_db)

        finally:
            if close_db:
                active_db.close()
