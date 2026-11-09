from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.models.business import Branch, Inventory, Product, ProductSupplier, Supplier, Warehouse
from backend.app.schemas.inventory_forecast import (
    InventoryForecastSnapshot,
    ValidationReportResponse,
    ValidationResultItem,
)
from backend.app.services.snapshot_service import InventoryForecastSnapshotService


class IntegrationValidator:
    """
    Validates data quality, relational integrity, operational constraints,
    and consistency between inventory balances, suppliers, and demand forecasts.
    """

    @classmethod
    def validate_snapshot(
        cls,
        snapshot: InventoryForecastSnapshot,
    ) -> List[ValidationResultItem]:
        """
        Run targeted validation checks against a specific product-branch snapshot.
        """
        results: List[ValidationResultItem] = []
        now_utc = datetime.now(timezone.utc)
        pid = snapshot.product_id
        bid = snapshot.branch_id

        # 1. Check Missing Inventory Record
        if snapshot.current_stock is None:
            results.append(
                ValidationResultItem(
                    validation_name="inventory_record_existence",
                    status="WARNING",
                    severity="MEDIUM",
                    description=f"No active inventory record found for product {pid} in branch {bid}.",
                    product_id=pid,
                    branch_id=bid,
                    timestamp=now_utc,
                )
            )
        else:
            results.append(
                ValidationResultItem(
                    validation_name="inventory_record_existence",
                    status="PASS",
                    severity="INFO",
                    description="Inventory balance record is present.",
                    product_id=pid,
                    branch_id=bid,
                    timestamp=now_utc,
                )
            )

        # 2. Check Stock Value Validity
        if snapshot.current_stock is not None:
            if snapshot.current_stock < 0:
                results.append(
                    ValidationResultItem(
                        validation_name="physical_stock_non_negative",
                        status="FAIL",
                        severity="CRITICAL",
                        description=f"Negative physical stock detected: {snapshot.current_stock}.",
                        product_id=pid,
                        branch_id=bid,
                        timestamp=now_utc,
                    )
                )
            else:
                results.append(
                    ValidationResultItem(
                        validation_name="physical_stock_non_negative",
                        status="PASS",
                        severity="INFO",
                        description="Physical stock is non-negative.",
                        product_id=pid,
                        branch_id=bid,
                        timestamp=now_utc,
                    )
                )

            # Check Reserved Stock Constraint
            if snapshot.reserved_stock is not None and snapshot.reserved_stock > snapshot.current_stock:
                results.append(
                    ValidationResultItem(
                        validation_name="reserved_le_current_stock",
                        status="WARNING",
                        severity="HIGH",
                        description=f"Reserved stock ({snapshot.reserved_stock}) exceeds physical stock ({snapshot.current_stock}).",
                        product_id=pid,
                        branch_id=bid,
                        timestamp=now_utc,
                    )
                )
            else:
                results.append(
                    ValidationResultItem(
                        validation_name="reserved_le_current_stock",
                        status="PASS",
                        severity="INFO",
                        description="Reserved stock is within physical stock limits.",
                        product_id=pid,
                        branch_id=bid,
                        timestamp=now_utc,
                    )
                )

        # 3. Check Supplier & Lead Time
        if snapshot.supplier is None:
            results.append(
                ValidationResultItem(
                    validation_name="supplier_assignment",
                    status="WARNING",
                    severity="MEDIUM",
                    description=f"No active supplier mapped for product {pid}.",
                    product_id=pid,
                    branch_id=bid,
                    timestamp=now_utc,
                )
            )
        else:
            results.append(
                ValidationResultItem(
                    validation_name="supplier_assignment",
                    status="PASS",
                    severity="INFO",
                    description=f"Supplier {snapshot.supplier.supplier_code} mapped successfully.",
                    product_id=pid,
                    branch_id=bid,
                    timestamp=now_utc,
                )
            )

            if snapshot.supplier_lead_time_days is None or snapshot.supplier_lead_time_days <= 0:
                results.append(
                    ValidationResultItem(
                        validation_name="supplier_lead_time_validity",
                        status="WARNING",
                        severity="MEDIUM",
                        description=f"Invalid or missing supplier lead time: {snapshot.supplier_lead_time_days}.",
                        product_id=pid,
                        branch_id=bid,
                        timestamp=now_utc,
                    )
                )
            else:
                results.append(
                    ValidationResultItem(
                        validation_name="supplier_lead_time_validity",
                        status="PASS",
                        severity="INFO",
                        description=f"Valid supplier lead time: {snapshot.supplier_lead_time_days} days.",
                        product_id=pid,
                        branch_id=bid,
                        timestamp=now_utc,
                    )
                )

        # 4. Check Forecast Horizon & Value Validity
        if not snapshot.daily_forecasts:
            results.append(
                ValidationResultItem(
                    validation_name="forecast_availability",
                    status="WARNING",
                    severity="HIGH",
                    description=f"No forecast output generated for horizon {snapshot.forecast_horizon_days}d.",
                    product_id=pid,
                    branch_id=bid,
                    timestamp=now_utc,
                )
            )
        else:
            if len(snapshot.daily_forecasts) != snapshot.forecast_horizon_days:
                results.append(
                    ValidationResultItem(
                        validation_name="forecast_horizon_completeness",
                        status="WARNING",
                        severity="MEDIUM",
                        description=f"Forecast records count ({len(snapshot.daily_forecasts)}) does not match horizon ({snapshot.forecast_horizon_days}).",
                        product_id=pid,
                        branch_id=bid,
                        timestamp=now_utc,
                    )
                )
            else:
                results.append(
                    ValidationResultItem(
                        validation_name="forecast_horizon_completeness",
                        status="PASS",
                        severity="INFO",
                        description="Forecast horizon record count is complete.",
                        product_id=pid,
                        branch_id=bid,
                        timestamp=now_utc,
                    )
                )

            # Check for negative predictions
            neg_preds = [f for f in snapshot.daily_forecasts if f.predicted_demand < 0.0]
            if neg_preds:
                results.append(
                    ValidationResultItem(
                        validation_name="forecast_non_negative",
                        status="FAIL",
                        severity="CRITICAL",
                        description=f"Detected {len(neg_preds)} negative demand forecast values.",
                        product_id=pid,
                        branch_id=bid,
                        timestamp=now_utc,
                    )
                )
            else:
                results.append(
                    ValidationResultItem(
                        validation_name="forecast_non_negative",
                        status="PASS",
                        severity="INFO",
                        description="All predicted demand values are non-negative.",
                        product_id=pid,
                        branch_id=bid,
                        timestamp=now_utc,
                    )
                )

        return results

    @classmethod
    def run_system_wide_validation(
        cls,
        db: Session,
        sample_limit: int = 50,
        product_id: Optional[int] = None,
        branch_id: Optional[int] = None,
    ) -> ValidationReportResponse:
        """
        Execute system-wide validation across database tables and sample snapshots.
        """
        now_utc = datetime.now(timezone.utc)
        all_results: List[ValidationResultItem] = []

        # 1. Global Database Constraint Checks: Duplicate Inventory Records
        dup_query = (
            select(Inventory.product_id, Inventory.warehouse_id, func.count().label("cnt"))
            .group_by(Inventory.product_id, Inventory.warehouse_id)
            .having(func.count() > 1)
        )
        duplicates = db.execute(dup_query).all()
        if duplicates:
            all_results.append(
                ValidationResultItem(
                    validation_name="inventory_uniqueness",
                    status="FAIL",
                    severity="CRITICAL",
                    description=f"Found {len(duplicates)} duplicate inventory records across (product_id, warehouse_id).",
                    timestamp=now_utc,
                )
            )
        else:
            all_results.append(
                ValidationResultItem(
                    validation_name="inventory_uniqueness",
                    status="PASS",
                    severity="INFO",
                    description="No duplicate inventory records found.",
                    timestamp=now_utc,
                )
            )

        # 2. Check for Products without Suppliers
        orphaned_products_query = (
            select(Product.id)
            .outerjoin(ProductSupplier, Product.id == ProductSupplier.product_id)
            .where(ProductSupplier.id.is_(None))
        )
        orphaned = db.execute(orphaned_products_query).scalars().all()
        if orphaned:
            all_results.append(
                ValidationResultItem(
                    validation_name="product_supplier_coverage",
                    status="WARNING",
                    severity="MEDIUM",
                    description=f"{len(orphaned)} products have no registered supplier mappings.",
                    timestamp=now_utc,
                )
            )
        else:
            all_results.append(
                ValidationResultItem(
                    validation_name="product_supplier_coverage",
                    status="PASS",
                    severity="INFO",
                    description="All master products are mapped to at least one supplier.",
                    timestamp=now_utc,
                )
            )

        # 3. Check for Stale Inventory Balances (> 90 days)
        stale_threshold = now_utc - timedelta(days=90)
        stale_count = db.scalar(
            select(func.count()).select_from(Inventory).where(Inventory.last_updated < stale_threshold)
        ) or 0
        if stale_count > 0:
            all_results.append(
                ValidationResultItem(
                    validation_name="inventory_freshness",
                    status="WARNING",
                    severity="LOW",
                    description=f"{stale_count} inventory records have not been refreshed in > 90 days.",
                    timestamp=now_utc,
                )
            )
        else:
            all_results.append(
                ValidationResultItem(
                    validation_name="inventory_freshness",
                    status="PASS",
                    severity="INFO",
                    description="Inventory records are within freshness thresholds.",
                    timestamp=now_utc,
                )
            )

        # 4. Sample Snapshot Validation
        if product_id is not None and branch_id is not None:
            snapshot = InventoryForecastSnapshotService.get_snapshot(
                db=db, product_id=product_id, branch_id=branch_id, horizon_days=7
            )
            snapshot_results = cls.validate_snapshot(snapshot)
            all_results.extend(snapshot_results)
        else:
            # Sample first N products across primary branch 1
            sample_products = db.execute(select(Product.id).limit(sample_limit)).scalars().all()
            for pid in sample_products:
                try:
                    snapshot = InventoryForecastSnapshotService.get_snapshot(
                        db=db, product_id=pid, branch_id=1, horizon_days=7
                    )
                    snapshot_results = cls.validate_snapshot(snapshot)
                    all_results.extend(snapshot_results)
                except Exception as e:
                    all_results.append(
                        ValidationResultItem(
                            validation_name="snapshot_generation",
                            status="FAIL",
                            severity="HIGH",
                            description=f"Snapshot generation failed for product {pid}, branch 1: {e}",
                            product_id=pid,
                            branch_id=1,
                            timestamp=now_utc,
                        )
                    )

        # 5. Aggregate Summary
        passed = sum(1 for r in all_results if r.status == "PASS")
        warnings = sum(1 for r in all_results if r.status == "WARNING")
        failures = sum(1 for r in all_results if r.status == "FAIL")

        overall = "PASS"
        if failures > 0:
            overall = "FAIL"
        elif warnings > 0:
            overall = "WARNING"

        return ValidationReportResponse(
            total_validations=len(all_results),
            passed_count=passed,
            warning_count=warnings,
            failure_count=failures,
            overall_status=overall,
            results=all_results,
            evaluated_at=now_utc,
        )
