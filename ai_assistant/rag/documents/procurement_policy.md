# Procurement Policy & Supplier Management Framework

**Document ID:** POL-PROC-002  
**Category:** Procurement & Sourcing  
**Section:** Governance, Lead Times & Approval Limits  
**Effective Date:** 2024-01-01  
**Last Updated:** 2024-11-01  
**Target Audience:** Purchasing Officers, Supply Chain Directors, Category Managers  

---

## 1. Purpose & Principles
This policy governs supplier selection, lead-time variance tracking, purchase order approvals, and contract performance management to maintain high inventory availability and minimize procurement costs.

## 2. Supplier Categorization and SLA Standards
Suppliers are classified into three distinct tiers:
- **Tier 1 (Strategic Partners):** Primary suppliers representing top 80% volume. Required SLA on-time in-full (OTIF) $\ge 95\%$, max lead-time variability $\sigma_L \le 1.0$ day.
- **Tier 2 (Secondary / Preferred):** Alternate suppliers maintaining pre-approved terms. Required OTIF $\ge 90\%$, $\sigma_L \le 2.0$ days.
- **Tier 3 (Spot / Tactical):** Ad-hoc suppliers engaged during regional shortages or unexpected demand spikes.

## 3. Lead Time Standards by Geographic Scope
Expected baseline delivery lead times from PO dispatch to warehouse receiving dock:
- **Local Metropolitan Suppliers:** 2 to 4 business days ($\bar{L} = 3$ days).
- **National / Regional Distribution:** 5 to 7 business days ($\bar{L} = 6$ days).
- **Imported / Cross-Border Suppliers:** 14 to 28 business days ($\bar{L} = 21$ days).

### Lead Time Variance Buffering Rule
If a supplier's rolling 90-day lead-time standard deviation $\sigma_L$ exceeds 30% of their mean lead time ($\sigma_L / \bar{L} > 0.30$), the inventory engine automatically applies a 15% safety stock multiplier until 30 consecutive days of on-time deliveries occur.

## 4. Purchase Order Approval Matrix
Approval thresholds are enforced based on total purchase order gross value:
- **Under $1,000 USD:** Automated system dispatch or single-click Store Manager approval.
- **$1,000 to $10,000 USD:** Procurement Specialist or Senior Inventory Controller review required within 1 business day.
- **$10,000 to $50,000 USD:** Supply Chain Director approval required.
- **Above $50,000 USD:** Chief Operating Officer (COO) and Chief Financial Officer (CFO) dual authorization.

## 5. Minimum Order Quantity (MOQ) and Volume Discounts
- All replenishment orders must meet the contractually agreed MOQ.
- If calculated EOQ is less than supplier MOQ, the system flags the item as "MOQ Bound" and recalculates carrying cost tradeoffs before releasing the order.
- Volume discount breaks are evaluated automatically against incremental holding costs over a 90-day horizon.

## 6. Supplier Non-Performance and Dispute Escalation
Suppliers failing to meet 90% OTIF over any calendar quarter receive a formal Corrective Action Request (CAR). Repeated failure within 60 days results in primary allocation shifting to the designated Tier 2 alternate supplier.

