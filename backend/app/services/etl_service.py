from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.db.session import SessionLocal
from backend.app.models.audit import DataImportLog, DataQualityResult
from backend.app.models.business import (
    Branch,
    Category,
    DailySale,
    Inventory,
    Product,
    ProductSupplier,
    Supplier,
    Warehouse,
)
from ml.pipelines.common.constants import DATASET_NAME_STORE_SALES
from ml.pipelines.ingestion.extract import DataExtractor
from ml.pipelines.loading.load import DataLoader
from ml.pipelines.synthetic.inventory_generator import SyntheticInventoryGenerator
from ml.pipelines.transformation.transform import DataTransformer
from ml.pipelines.validation.quality import DataQualityValidator


class ETLService:
    """
    Orchestrates the entire Data Engineering pipeline: Extraction, Quality Validation,
    Transformation, Loading, and Synthetic Inventory Generation.
    """

    @classmethod
    def execute_pipeline(
        cls,
        max_sales_rows: Optional[int] = 50_000,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute the end-to-end data pipeline.
        """
        db = SessionLocal()
        import_log = DataLoader.start_import_log(
            db, source_file="stores.csv & train.csv", dataset_name=DATASET_NAME_STORE_SALES
        )

        total_processed = 0
        total_inserted = 0
        total_rejected = 0

        try:
            logger.info("Starting Phase 2 ETL Pipeline execution...")

            # ------------------------------------------------------------------
            # 1. Stores -> Branches
            # ------------------------------------------------------------------
            stores_df = DataExtractor.extract_stores()
            valid_stores_df, stores_quality = DataQualityValidator.validate_stores_data(stores_df)
            DataQualityValidator.save_quality_result(db, DATASET_NAME_STORE_SALES, stores_quality)

            branches_data = DataTransformer.transform_stores_to_branches(valid_stores_df)
            new_branches = DataLoader.load_branches(db, branches_data)
            total_processed += len(stores_df)
            total_inserted += new_branches
            total_rejected += stores_quality["failed_records"]

            # ------------------------------------------------------------------
            # 2. Families -> Categories & Products
            # ------------------------------------------------------------------
            families = DataExtractor.extract_categories_and_products()
            cats_data, prods_data = DataTransformer.transform_families_to_categories_and_products(families)
            new_cats, new_prods = DataLoader.load_categories_and_products(db, cats_data, prods_data)
            total_processed += len(families)
            total_inserted += new_cats + new_prods

            # Build ID lookups for sales transformation
            branches = db.execute(select(Branch)).scalars().all()
            branch_id_map = {b.source_store_number: b.id for b in branches}
            valid_branch_numbers = set(branch_id_map.keys())

            products = db.execute(select(Product)).scalars().all()
            product_id_map = {p.source_family: p.id for p in products}

            # ------------------------------------------------------------------
            # 3. Stream & Ingest Daily Sales Chunks
            # ------------------------------------------------------------------
            sales_stream = DataExtractor.extract_daily_sales_stream(
                chunk_size=25_000,
                max_rows=max_sales_rows,
                start_date=start_date,
                end_date=end_date,
            )

            sales_processed = 0
            sales_inserted = 0
            sales_rejected = 0

            for chunk_df in sales_stream:
                sales_processed += len(chunk_df)
                valid_chunk_df, chunk_quality = DataQualityValidator.validate_sales_chunk(
                    chunk_df, valid_branch_numbers, product_id_map
                )
                sales_rejected += chunk_quality["failed_records"]

                if not valid_chunk_df.empty:
                    sales_records = DataTransformer.transform_sales_chunk(
                        valid_chunk_df, branch_id_map, product_id_map
                    )
                    inserted_chunk = DataLoader.load_daily_sales_batch(db, sales_records)
                    sales_inserted += inserted_chunk

            # Record overall sales quality metrics
            sales_quality_summary = {
                "validation_name": "daily_sales_batch_validation",
                "total_records": sales_processed,
                "valid_records": sales_processed - sales_rejected,
                "failed_records": sales_rejected,
                "missing_values": 0,
                "duplicate_records": 0,
                "validation_status": "PASSED" if sales_rejected == 0 else "WARNING",
            }
            DataQualityValidator.save_quality_result(db, DATASET_NAME_STORE_SALES, sales_quality_summary)

            total_processed += sales_processed
            total_inserted += sales_inserted
            total_rejected += sales_rejected

            # ------------------------------------------------------------------
            # 4. Generate Synthetic Inventory, Warehouses, and Suppliers
            # ------------------------------------------------------------------
            generator = SyntheticInventoryGenerator(seed=42)
            warehouses = generator.generate_warehouses(db)
            suppliers = generator.generate_suppliers(db)
            inv_stats = generator.generate_product_suppliers_and_inventory(db, warehouses, suppliers)

            synthetic_entities_count = len(warehouses) + len(suppliers) + inv_stats["inventory_records"]
            total_processed += synthetic_entities_count
            total_inserted += synthetic_entities_count

            # Finish log
            DataLoader.finish_import_log(
                db,
                import_log,
                status="COMPLETED",
                processed=total_processed,
                inserted=total_inserted,
                rejected=total_rejected,
            )

            result = {
                "status": "COMPLETED",
                "import_log_id": import_log.id,
                "records_processed": total_processed,
                "records_inserted": total_inserted,
                "records_rejected": total_rejected,
                "breakdown": {
                    "source_stores_processed": len(stores_df),
                    "branches_loaded": new_branches,
                    "categories_loaded": new_cats,
                    "products_loaded": new_prods,
                    "sales_rows_processed": sales_processed,
                    "sales_rows_upserted": sales_inserted,
                    "sales_rows_rejected": sales_rejected,
                    "synthetic_warehouses": len(warehouses),
                    "synthetic_suppliers": len(suppliers),
                    "synthetic_inventory_records": inv_stats["inventory_records"],
                },
                "sales_records_inserted": sales_inserted,
                "synthetic_inventory_records": inv_stats["inventory_records"],
            }
            return result

        except Exception as exc:
            logger.error(f"ETL Pipeline execution failed: {exc}", exc_info=True)
            DataLoader.finish_import_log(
                db,
                import_log,
                status="FAILED",
                processed=total_processed,
                inserted=total_inserted,
                rejected=total_rejected,
                error_summary=str(exc),
            )
            raise exc
        finally:
            db.close()

    @classmethod
    def get_summary(cls, db: Session) -> Dict[str, Any]:
        """
        Calculate aggregated data engineering volume metrics.
        """
        branches_count = db.scalar(select(func.count(Branch.id))) or 0
        categories_count = db.scalar(select(func.count(Category.id))) or 0
        products_count = db.scalar(select(func.count(Product.id))) or 0
        daily_sales_count = db.scalar(select(func.count(DailySale.id))) or 0
        warehouses_count = db.scalar(select(func.count(Warehouse.id))) or 0
        suppliers_count = db.scalar(select(func.count(Supplier.id))) or 0
        inventory_count = db.scalar(select(func.count(Inventory.id))) or 0

        # Sales date range
        date_stats = db.execute(
            select(func.min(DailySale.sale_date), func.max(DailySale.sale_date))
        ).one()
        min_date, max_date = date_stats[0], date_stats[1]

        # Inventory totals
        inv_stats = db.execute(
            select(
                func.coalesce(func.sum(Inventory.stock_quantity), 0),
                func.coalesce(func.sum(Inventory.reserved_quantity), 0),
            )
        ).one()
        total_stock = int(inv_stats[0])
        total_reserved = int(inv_stats[1])

        return {
            "branches": branches_count,
            "categories": categories_count,
            "products": products_count,
            "daily_sales_records": daily_sales_count,
            "warehouses": warehouses_count,
            "suppliers": suppliers_count,
            "inventory_records": inventory_count,
            "total_physical_stock": total_stock,
            "total_reserved_stock": total_reserved,
            "available_stock": max(0, total_stock - total_reserved),
            "sales_start_date": min_date.isoformat() if min_date else None,
            "sales_end_date": max_date.isoformat() if max_date else None,
        }
