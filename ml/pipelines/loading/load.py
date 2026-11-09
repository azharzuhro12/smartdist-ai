from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.models.audit import DataImportLog
from backend.app.models.business import Branch, Category, DailySale, Product


class DataLoader:
    """
    Loads transformed records into PostgreSQL using transactions, batch inserts, and audit logs.
    """

    @staticmethod
    def start_import_log(db: Session, source_file: str, dataset_name: str) -> DataImportLog:
        log = DataImportLog(
            source_file=source_file,
            dataset_name=dataset_name,
            records_processed=0,
            records_inserted=0,
            records_rejected=0,
            status="IN_PROGRESS",
            started_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def finish_import_log(
        db: Session,
        log: DataImportLog,
        status: str,
        processed: int,
        inserted: int,
        rejected: int,
        error_summary: Optional[str] = None,
    ) -> None:
        log.status = status
        log.records_processed = processed
        log.records_inserted = inserted
        log.records_rejected = rejected
        log.error_summary = error_summary
        log.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            f"Completed import log #{log.id}: {status} (processed={processed}, inserted={inserted}, rejected={rejected})"
        )

    @staticmethod
    def load_branches(db: Session, branches: List[Dict[str, Any]]) -> int:
        """
        Idempotently insert or update branches.
        """
        inserted = 0
        for b_data in branches:
            existing = db.execute(
                select(Branch).where(Branch.source_store_number == b_data["source_store_number"])
            ).scalar_one_or_none()

            if not existing:
                branch = Branch(**b_data)
                db.add(branch)
                inserted += 1
            else:
                # Update attributes if needed
                existing.branch_name = b_data["branch_name"]
                existing.city = b_data["city"]
                existing.state = b_data["state"]
                existing.store_type = b_data.get("store_type")
                existing.cluster = b_data.get("cluster")

        db.commit()
        logger.info(f"Loaded branches: {inserted} newly inserted out of {len(branches)} processed.")
        return inserted

    @staticmethod
    def load_categories_and_products(
        db: Session,
        categories: List[Dict[str, Any]],
        products: List[Dict[str, Any]],
    ) -> tuple[int, int]:
        """
        Idempotently insert categories and products.
        """
        cat_inserted = 0
        prod_inserted = 0

        # Load categories
        cat_map = {}
        for c_data in categories:
            cat = db.execute(
                select(Category).where(Category.category_code == c_data["category_code"])
            ).scalar_one_or_none()

            if not cat:
                cat = Category(**c_data)
                db.add(cat)
                db.flush()
                cat_inserted += 1
            cat_map[c_data["category_code"]] = cat.id

        # Load products
        for p_data in products:
            prod = db.execute(
                select(Product).where(Product.product_code == p_data["product_code"])
            ).scalar_one_or_none()

            if not prod:
                cat_id = cat_map[p_data["category_code"]]
                prod = Product(
                    product_code=p_data["product_code"],
                    product_name=p_data["product_name"],
                    category_id=cat_id,
                    source_family=p_data["source_family"],
                    unit_of_measure=p_data["unit_of_measure"],
                    is_active=p_data["is_active"],
                    data_origin=p_data["data_origin"],
                )
                db.add(prod)
                prod_inserted += 1

        db.commit()
        logger.info(
            f"Loaded catalog: {cat_inserted} new categories, {prod_inserted} new products."
        )
        return cat_inserted, prod_inserted

    @staticmethod
    def load_daily_sales_batch(
        db: Session,
        sales_records: List[Dict[str, Any]],
        batch_size: int = 5_000,
    ) -> int:
        """
        Batch upsert daily sales records using PostgreSQL ON CONFLICT DO UPDATE.
        Ensures idempotent reruns.
        """
        if not sales_records:
            return 0

        total_inserted = 0
        for i in range(0, len(sales_records), batch_size):
            batch = sales_records[i : i + batch_size]
            stmt = insert(DailySale).values(batch)
            upsert_stmt = stmt.on_conflict_do_update(
                constraint="uq_daily_sales_date_branch_product",
                set_={
                    "quantity_sold": stmt.excluded.quantity_sold,
                    "sales_amount": stmt.excluded.sales_amount,
                    "promotion_quantity": stmt.excluded.promotion_quantity,
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            db.execute(upsert_stmt)
            db.commit()
            total_inserted += len(batch)

        logger.info(f"Upserted {total_inserted} daily sales records.")
        return total_inserted
