from pathlib import Path
from typing import Optional, Tuple
import pandas as pd
from backend.app.core.logging import logger
from backend.app.db.session import SessionLocal
from backend.app.models.business import Branch, DailySale, Product
from ml.features.feature_pipeline import TimeSeriesFeaturePipeline
from ml.pipelines.common.constants import PROCESSED_DATA_DIR, RAW_DATA_DIR
from ml.validation.time_series_split import TimeSeriesSplitter
from sqlalchemy import select


class DatasetBuilder:
    """
    Builds training-ready ML datasets by reading historical daily_sales, executing feature
    engineering, and producing chronologically partitioned splits.
    """

    FEATURE_COLUMNS = [
        # Identifiers & Grouping
        "store_nbr",
        "product_id",
        # Calendar Features
        "year",
        "month",
        "day",
        "day_of_week",
        "day_of_month",
        "week_of_year",
        "quarter",
        "is_weekend",
        "is_month_start",
        "is_month_end",
        # External Predictors
        "oil_price",
        "transactions",
        "is_holiday",
        "is_national_holiday",
        "is_work_day",
        "store_type",
        "store_cluster",
        "promotion_quantity",
        # Lag Features
        "lag_1",
        "lag_7",
        "lag_14",
        "lag_28",
        # Rolling Features
        "rolling_mean_7",
        "rolling_mean_14",
        "rolling_mean_28",
        "rolling_std_7",
        "rolling_std_14",
        "rolling_std_28",
    ]

    TARGET_COLUMN = "quantity_sold"

    @classmethod
    def load_sales_from_database(
        cls,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Load daily sales from PostgreSQL including branch source_store_number and product metadata.
        """
        db = SessionLocal()
        try:
            query = (
                select(
                    DailySale.sale_date.label("date"),
                    Branch.source_store_number.label("store_nbr"),
                    DailySale.product_id,
                    Product.source_family.label("family"),
                    DailySale.quantity_sold,
                    DailySale.promotion_quantity,
                )
                .join(Branch, DailySale.branch_id == Branch.id)
                .join(Product, DailySale.product_id == Product.id)
            )

            if start_date:
                query = query.where(DailySale.sale_date >= start_date)
            if end_date:
                query = query.where(DailySale.sale_date <= end_date)

            query = query.order_by(DailySale.sale_date, Branch.source_store_number, DailySale.product_id)

            df = pd.read_sql(query, con=db.bind)
            # Ensure proper types
            df["date"] = df["date"].astype(str)
            df["quantity_sold"] = df["quantity_sold"].astype(float)
            df["promotion_quantity"] = df["promotion_quantity"].astype(int)

            logger.info(f"Loaded {len(df)} daily sales records from database.")
            return df
        finally:
            db.close()

    @classmethod
    def build_feature_dataset(
        cls,
        sales_df: pd.DataFrame,
        drop_na_lags: bool = True,
    ) -> pd.DataFrame:
        """
        Execute feature pipeline on sales DataFrame.
        """
        pipeline = TimeSeriesFeaturePipeline(
            target_col=cls.TARGET_COLUMN,
            group_cols=["store_nbr", "product_id"],
            date_col="date",
            lags=[1, 7, 14, 28],
            rolling_windows=[7, 14, 28],
            drop_na_lags=drop_na_lags,
        )

        features_df = pipeline.transform(sales_df)

        # Fill any remaining NaNs in rolling std for constant/short series with 0.0
        std_cols = [c for c in features_df.columns if "rolling_std" in c]
        for col in std_cols:
            features_df[col] = features_df[col].fillna(0.0)

        # Categorical string conversions
        if "store_type" in features_df.columns:
            features_df["store_type"] = features_df["store_type"].astype("category")
        if "holiday_type" in features_df.columns:
            features_df["holiday_type"] = features_df["holiday_type"].astype("category")

        logger.info(
            f"Built feature dataset with {len(features_df)} rows and {len(features_df.columns)} columns."
        )
        return features_df

    @classmethod
    def create_and_save_splits(
        cls,
        features_df: pd.DataFrame,
        train_end: str = "2013-10-31",
        val_end: str = "2013-11-30",
        output_dir: Optional[Path] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Split feature dataset into chronological Train, Validation, and Test partitions and persist to disk.
        """
        out_dir = output_dir or PROCESSED_DATA_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        train_df, val_df, test_df = TimeSeriesSplitter.split_by_dates(
            features_df, train_end=train_end, val_end=val_end, date_col="date"
        )

        train_path = out_dir / "train_features.parquet"
        val_path = out_dir / "val_features.parquet"
        test_path = out_dir / "test_features.parquet"

        train_df.to_parquet(train_path, index=False)
        val_df.to_parquet(val_path, index=False)
        test_df.to_parquet(test_path, index=False)

        logger.info(
            f"Saved chronological splits: Train={len(train_df)} ({train_path.name}), "
            f"Val={len(val_df)} ({val_path.name}), Test={len(test_df)} ({test_path.name})"
        )

        return train_df, val_df, test_df
