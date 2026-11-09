# Standard Operating Procedure: Inventory Replenishment & Stock Control

**Document ID:** SOP-INV-001  
**Category:** Inventory Management  
**Section:** Policies & Formulas  
**Effective Date:** 2024-01-01  
**Last Updated:** 2024-11-01  
**Target Audience:** Inventory Planners, Store Managers, Supply Chain Operations  

---

## 1. Objective and Scope
This Standard Operating Procedure defines the mathematical models, decision thresholds, and operational rules for inventory replenishment across all retail stores and distribution centers in the SmartDist AI network.

## 2. Target Cycle Service Levels (CSL)
Service level targets reflect the probability of not stocking out during a replenishment cycle:
- **Class A Staples (Fast Moving / Essential Grocery & Dairy):** Target CSL = 98.0% ($z \approx 2.054$)
- **Class B Standard Merchandise (General Foods & Cleaning):** Target CSL = 95.0% ($z \approx 1.645$)
- **Class C Slow Moving / Specialty Goods:** Target CSL = 90.0% ($z \approx 1.282$)

## 3. Safety Stock (SS) Calculation
Safety stock mitigates uncertainty in both customer demand and supplier replenishment lead times.

### 3.1 Combined Uncertainty Formula
$$SS = z \cdot \sqrt{\bar{L} \cdot \sigma_D^2 + \bar{D}^2 \cdot \sigma_L^2}$$
Where:
- $z$: Inverse standard normal cumulative distribution function for target CSL
- $\bar{L}$: Mean supplier lead time in days
- $\sigma_L$: Standard deviation of supplier lead time
- $\bar{D}$: Mean daily sales demand (units/day)
- $\sigma_D$: Standard deviation of daily sales demand

### 3.2 Lead-Time-Only Demand Uncertainty (Constant Lead Time)
When lead time is deterministic or variability is minimal ($\sigma_L \approx 0$):
$$SS = z \cdot \sigma_D \cdot \sqrt{L}$$

### 3.3 Non-Parametric (Empirical) Fallback
For intermittent or highly skewed demand distributions where normality assumptions fail, the empirical quantile approach is used:
$$SS = \text{Quantile}_{CSL}(D_L) - \bar{D}_L$$
where $D_L$ represents the empirical lead-time demand distribution.

## 4. Reorder Point (ROP) Determination
The Reorder Point is the inventory threshold that signals an immediate replenishment order:
$$ROP = (\bar{D} \cdot \bar{L}) + SS$$
Where:
- $\bar{D} \cdot \bar{L}$: Expected lead-time demand (units)
- $SS$: Safety stock buffer (units)

**Rule:** When Effective Inventory (On-Hand + On-Order - Backorders) $\le ROP$, a purchase order recommendation must be generated automatically.

## 5. Economic Order Quantity (EOQ)
Optimal lot size balancing annual fixed order costs and holding carrying costs:
$$EOQ = \sqrt{\frac{2 \cdot D_{annual} \cdot S}{H}}$$
Where:
- $D_{annual}$: Annualized demand ($365 \cdot \bar{D}$)
- $S$: Fixed cost per purchase order (default standard = $50.00)
- $H$: Annual inventory holding cost per unit ($H = h_{rate} \cdot C_{unit}$, default holding rate $h_{rate} = 0.20$ or 20% of unit cost)

### Batch Size and Minimum Order Quantity (MOQ)
Orders must be rounded up to the nearest supplier pack size or pallet tier, and must respect supplier MOQ:
$$\text{Order Quantity} = \max(\text{MOQ}, \lceil EOQ / \text{PackSize} \rceil \cdot \text{PackSize})$$

## 6. Stockout Risk Classification
The probability of stockout before the next replenishment arrives:
- **CRITICAL (> 40%):** Immediate expedited replenishment or inter-branch transfer required.
- **HIGH (20% - 40%):** Generate urgent purchase order within 24 hours.
- **MEDIUM (10% - 20%):** Regular replenishment batch processing.
- **LOW (< 10%):** Healthy inventory buffer; no intervention needed.

