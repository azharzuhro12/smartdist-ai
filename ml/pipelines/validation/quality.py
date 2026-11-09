import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
import pandas as pd
from sqlalchemy.orm import Session
from backend.app.core.logging import logger
from backend.app.models.audit import DataQualityResult


class DataQualityValidator:
    """
    Executes data quality checks and records validation metrics.
    """

    @staticmethod
    def validate_stores_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Validate store master data.
        """
        total_rows = len(df)
        issues: List[str] = []

        # Missing values
        missing_count = int(df[["store_nbr", "city", "state"]].isnull().sum().sum())
        if missing_count > 0:
            issues.append(f"Found {missing_count} missing values in store critical columns")

        # Duplicate store numbers
        dup_mask = df.duplicated(subset=["store_nbr"], keep=False)
        duplicate_count = int(dup_mask.sum())
        if duplicate_count > 0:
            issues.append(f"Found {duplicate_count} duplicate store_nbr entries")

        # Invalid store numbers
        invalid_nbr = df[df["store_nbr"] <= 0]
        if not invalid_nbr.empty:
            issues.append(f"Found {len(invalid_nbr)} non-positive store_nbr entries")

        # Filter valid records
        valid_df = df[~dup_mask & (df["store_nbr"] > 0) & df["city"].notnull() & df["state"].notnull()].copy()
        rejected_rows = total_rows - len(valid_df)

        status = "PASSED" if rejected_rows == 0 else ("WARNING" if len(valid_df) > 0 else "FAILED")

        summary = {
            "validation_name": "stores_integrity_check",
            "total_records": total_rows,
            "valid_records": len(valid_df),
            "failed_records": rejected_rows,
            "missing_values": missing_count,
            "duplicate_records": duplicate_count,
            "validation_status": status,
            "issues": issues,
        }
        return valid_df, summary

    @staticmethod
    def validate_sales_chunk(
        df: pd.DataFrame,
        valid_branch_ids: set,
        valid_product_map: Dict[str, int],
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Validate sales records against date, numeric, branch, and product domain constraints.
        """
        total_rows = len(df)
        issues: List[str] = []

        # 1. Date format check
        parsed_dates = pd.to_datetime(df["date"], errors="coerce")
        invalid_dates_count = int(parsed_dates.isnull().sum())
        if invalid_dates_count > 0:
            issues.append(f"Found {invalid_dates_count} unparseable dates")

        # 2. Non-negative quantity / sales check
        neg_sales_mask = df["sales"] < 0
        neg_sales_count = int(neg_sales_mask.sum())
        if neg_sales_count > 0:
            issues.append(f"Found {neg_sales_count} negative sales values")

        # 3. Non-negative promotion check
        neg_promo_mask = df["onpromotion"] < 0
        neg_promo_count = int(neg_promo_mask.sum())
        if neg_promo_count > 0:
            issues.append(f"Found {neg_promo_count} negative onpromotion values")

        # 4. Referential integrity: branch must exist
        invalid_branches_mask = ~df["store_nbr"].isin(valid_branch_ids)
        invalid_branches_count = int(invalid_branches_mask.sum())
        if invalid_branches_count > 0:
            issues.append(f"Found {invalid_branches_count} sales referencing unknown store_nbr")

        # 5. Referential integrity: product family must exist
        invalid_products_mask = ~df["family"].isin(valid_product_map.keys())
        invalid_products_count = int(invalid_products_mask.sum())
        if invalid_products_count > 0:
            issues.append(f"Found {invalid_products_count} sales referencing unknown product family")

        # 6. Duplicates check on (date, store_nbr, family)
        dup_mask = df.duplicated(subset=["date", "store_nbr", "family"], keep="first")
        duplicate_count = int(dup_mask.sum())
        if duplicate_count > 0:
            issues.append(f"Found {duplicate_count} duplicate sales entries")

        # Discard invalid records
        valid_mask = (
            parsed_dates.notnull()
            & (~neg_sales_mask)
            & (~neg_promo_mask)
            & (~invalid_branches_mask)
            & (~invalid_products_mask)
            & (~dup_mask)
        )

        valid_df = df[valid_mask].copy()
        rejected_rows = total_rows - len(valid_df)
        status = "PASSED" if rejected_rows == 0 else ("WARNING" if len(valid_df) > 0 else "FAILED")

        summary = {
            "validation_name": "daily_sales_validation",
            "total_records": total_rows,
            "valid_records": len(valid_df),
            "failed_records": rejected_rows,
            "missing_values": invalid_dates_count,
            "duplicate_records": duplicate_count,
            "validation_status": status,
            "issues": issues,
        }
        return valid_df, summary

    @staticmethod
    def validate_inventory_data(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Validate synthetic inventory records against physical domain bounds.
        """
        total = len(records)
        valid_records: List[Dict[str, Any]] = []
        issues: List[str] = []
        failed = 0

        for r in records:
            stock = r.get("stock_quantity", 0)
            reserved = r.get("reserved_quantity", 0)
            reorder = r.get("reorder_point", 0)
            safety = r.get("safety_stock", 0)

            if stock < 0:
                issues.append(f"Negative stock {stock} for product {r.get('product_id')}")
                failed += 1
                continue
            if reserved < 0 or reserved > stock:
                issues.append(f"Reserved {reserved} exceeds stock {stock}")
                failed += 1
                continue
            if reorder < 0:
                issues.append(f"Negative reorder point {reorder}")
                failed += 1
                continue
            if safety < 0:
                issues.append(f"Negative safety stock {safety}")
                failed += 1
                continue

            valid_records.append(r)

        status = "PASSED" if failed == 0 else ("WARNING" if valid_records else "FAILED")
        summary = {
            "validation_name": "inventory_integrity_check",
            "total_records": total,
            "valid_records": len(valid_records),
            "failed_records": failed,
            "missing_values": 0,
            "duplicate_records": 0,
            "validation_status": status,
            "issues": issues[:10],
        }
        return valid_records, summary

    @staticmethod
    def save_quality_result(db: Session, dataset_name: str, summary: Dict[str, Any]) -> DataQualityResult:
        """
        Persist validation metrics to the data_quality_results table.
        """
        result = DataQualityResult(
            dataset_name=dataset_name,
            validation_name=summary.get("validation_name", "generic_validation"),
            total_records=summary.get("total_records", 0),
            failed_records=summary.get("failed_records", 0),
            validation_status=summary.get("validation_status", "PASSED"),
            details=json.dumps(summary),
            executed_at=datetime.now(timezone.utc),
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        logger.info(
            f"Logged data quality result: {result.validation_name} - status={result.validation_status}, failed={result.failed_records}/{result.total_records}"
        )
        return result
