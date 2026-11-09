from decimal import Decimal
from typing import Any, Dict, List
import pandas as pd
from ml.pipelines.common.constants import (
    DATA_ORIGIN_KAGGLE,
    DATASET_NAME_STORE_SALES,
    DEFAULT_FAMILY_PRICING,
    FAMILY_PRICE_REFERENCE,
)


class DataTransformer:
    """
    Transforms raw CSV data into clean, typed business dictionaries ready for database loading.
    """

    @staticmethod
    def transform_stores_to_branches(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Transform raw stores DataFrame to Branch entities.
        """
        branches = []
        for _, row in df.iterrows():
            store_nbr = int(row["store_nbr"])
            branches.append({
                "branch_code": f"BR-{store_nbr:03d}",
                "branch_name": f"Branch Store #{store_nbr} - {row['city']}",
                "city": str(row["city"]).strip(),
                "state": str(row["state"]).strip(),
                "source_store_number": store_nbr,
                "store_type": str(row["type"]).strip() if pd.notnull(row.get("type")) else None,
                "cluster": int(row["cluster"]) if pd.notnull(row.get("cluster")) else None,
                "data_origin": DATA_ORIGIN_KAGGLE,
            })
        return branches

    @staticmethod
    def transform_families_to_categories_and_products(
        families: List[str],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Transform distinct product families into Category and Product master entries.
        """
        categories = []
        products = []

        for family in families:
            family_clean = family.strip()
            # Category code formatting: CAT-BREAD_BAKERY
            cat_slug = family_clean.replace("/", "_").replace(" ", "_").upper()
            cat_code = f"CAT-{cat_slug}"
            prod_code = f"PRD-{cat_slug}"
            readable_name = family_clean.title()

            categories.append({
                "category_code": cat_code,
                "category_name": readable_name,
                "description": f"Merchandise category for {readable_name} from retail dataset.",
            })

            products.append({
                "product_code": prod_code,
                "product_name": f"{readable_name} (Standard SKU)",
                "category_code": cat_code,
                "source_family": family_clean,
                "unit_of_measure": "UNIT",
                "is_active": True,
                "data_origin": DATA_ORIGIN_KAGGLE,
            })

        return categories, products

    @staticmethod
    def transform_sales_chunk(
        chunk_df: pd.DataFrame,
        branch_id_map: Dict[int, int],  # source_store_number -> branch.id
        product_id_map: Dict[str, int],  # source_family -> product.id
    ) -> List[Dict[str, Any]]:
        """
        Transform daily sales chunk into DailySale records with calculated sales amounts.
        """
        records = []
        for _, row in chunk_df.iterrows():
            store_nbr = int(row["store_nbr"])
            family = str(row["family"]).strip()
            branch_id = branch_id_map.get(store_nbr)
            product_id = product_id_map.get(family)

            if not branch_id or not product_id:
                continue

            qty = Decimal(str(round(float(row["sales"]), 4)))
            pricing = FAMILY_PRICE_REFERENCE.get(family, DEFAULT_FAMILY_PRICING)
            unit_price = pricing["unit_price"]
            sales_amount = (qty * unit_price).quantize(Decimal("0.01"))
            promo = int(row["onpromotion"]) if pd.notnull(row["onpromotion"]) else 0

            # Parse date string YYYY-MM-DD
            sale_date = pd.to_datetime(row["date"]).date()

            records.append({
                "sale_date": sale_date,
                "branch_id": branch_id,
                "product_id": product_id,
                "quantity_sold": qty,
                "sales_amount": sales_amount,
                "promotion_quantity": promo,
                "source_dataset": DATASET_NAME_STORE_SALES,
                "data_origin": DATA_ORIGIN_KAGGLE,
            })

        return records
