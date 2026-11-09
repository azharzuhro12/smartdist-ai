# SmartDist AI — RAG Knowledge Base Architecture

## 1. Overview
The SmartDist AI RAG (Retrieval-Augmented Generation) Knowledge System indexes operational policies, Standard Operating Procedures (SOPs), and procurement guidelines. It provides grounded citations and formula definitions to the AI assistant and optimization engines.

## 2. Ingested Policy Documents
The system indexes four core governance documents under `ai_assistant/rag/documents/`:

1. **`sop_inventory_replenishment.md` (`SOP-INV-001`)**:
   - Target Cycle Service Levels (CSL: 98% Class A, 95% Class B, 90% Class C).
   - Safety stock combined uncertainty formula:
     $$SS = z \cdot \sqrt{\bar{L} \cdot \sigma_D^2 + \bar{D}^2 \cdot \sigma_L^2}$$
   - Reorder Point formula ($ROP = \bar{D}\bar{L} + SS$).
   - Economic Order Quantity ($EOQ = \sqrt{2DS/H}$).
   - Stockout risk classification tiers.

2. **`procurement_policy.md` (`POL-PROC-002`)**:
   - Supplier tiers (Tier 1 Strategic, Tier 2 Secondary, Tier 3 Spot).
   - Lead time standards (Local 3 days, Regional 6 days, Import 21 days).
   - Lead time variability buffer multiplier (+15% SS if $\sigma_L/\bar{L} > 0.30$).
   - Purchase order approval thresholds ($1k, $10k, $50k).

3. **`sales_anomaly_guidelines.md` (`SOP-OPS-003`)**:
   - Anomaly typology: Volume Spike ($z > 3$), Volume Drop ($z < -2.5$), Forecast Residual ($|y - \hat{y}| > 2.5 \cdot \text{MAE}$).
   - Severity scoring SLA: Critical (4h), High (24h), Medium (5 days).
   - Investigation checklist and triage status progression.

4. **`store_operations.md` (`SOP-OPS-004`)**:
   - Store formats (A Hypermarket, B Supermarket, C Express).
   - Receiving delivery windows (04:00 - 07:30, 20:30 - 23:00).
   - Emergency inter-branch store transfer constraints.
   - December 25 Christmas network closure rule.

## 3. Chunking & Indexing Strategy
- **Semantic Chunking**: Documents are parsed by markdown headers (`## Section Heading`) and further split into overlapping passages (~350–500 characters, 50 characters overlap).
- **Metadata Tagging**: Each chunk is indexed with `doc_id`, `title`, `category`, and `section`.
- **Hybrid Storage & Retrieval**:
  - Primary: ChromaDB persistent vector collection (`smartdist_policies`).
  - High-performance fallback: Scikit-learn TF-IDF bi-gram cosine vector index with zero network overhead.

