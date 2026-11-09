import os
from pathlib import Path
from typing import Generator, List, Optional
import pandas as pd
from backend.app.core.logging import logger
from ml.pipelines.common.constants import RAW_DATA_DIR


class DataExtractor:
    """
    Handles robust extraction and inspection of raw CSV datasets.
    """

    @staticmethod
    def verify_file_exists(file_path: Path) -> bool:
        if not file_path.exists():
            logger.error(f"Required raw data file not found at: {file_path}")
            return False
        return True

    @staticmethod
    def extract_stores(file_path: Optional[Path] = None) -> pd.DataFrame:
        """
        Extract and validate stores dataset from stores.csv.
        """
        path = file_path or (RAW_DATA_DIR / "stores.csv")
        if not DataExtractor.verify_file_exists(path):
            raise FileNotFoundError(f"stores.csv not found at {path}")

        df = pd.read_csv(path)
        required_cols = {"store_nbr", "city", "state", "type", "cluster"}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise ValueError(f"stores.csv missing required columns: {missing_cols}")

        logger.info(f"Successfully extracted {len(df)} stores from {path.name}")
        return df

    @staticmethod
    def extract_categories_and_products(train_file_path: Optional[Path] = None) -> List[str]:
        """
        Extract distinct product families from train.csv without reading the entire 116MB file.
        """
        path = train_file_path or (RAW_DATA_DIR / "train.csv")
        if not DataExtractor.verify_file_exists(path):
            raise FileNotFoundError(f"train.csv not found at {path}")

        families = set()
        chunk_size = 100_000
        for chunk in pd.read_csv(path, usecols=["family"], chunksize=chunk_size):
            families.update(chunk["family"].dropna().unique())

        sorted_families = sorted(list(families))
        logger.info(f"Extracted {len(sorted_families)} distinct product families from {path.name}")
        return sorted_families

    @staticmethod
    def extract_daily_sales_stream(
        train_file_path: Optional[Path] = None,
        chunk_size: int = 50_000,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_rows: Optional[int] = None,
    ) -> Generator[pd.DataFrame, None, None]:
        """
        Stream daily sales chunks from train.csv to prevent excessive memory usage.
        Optionally filter by date range or max_rows for staged processing.
        """
        path = train_file_path or (RAW_DATA_DIR / "train.csv")
        if not DataExtractor.verify_file_exists(path):
            raise FileNotFoundError(f"train.csv not found at {path}")

        required_cols = {"date", "store_nbr", "family", "sales", "onpromotion"}
        total_rows_yielded = 0

        for chunk in pd.read_csv(path, chunksize=chunk_size):
            missing_cols = required_cols - set(chunk.columns)
            if missing_cols:
                raise ValueError(f"train.csv chunk missing required columns: {missing_cols}")

            # Chronological optimization: if chunk starts after end_date, remaining chunks will too
            if end_date and chunk["date"].min() > end_date:
                logger.info(f"Reached date beyond end_date ({end_date}); ending stream early.")
                break

            if start_date:
                chunk = chunk[chunk["date"] >= start_date]
            if end_date:
                chunk = chunk[chunk["date"] <= end_date]

            if chunk.empty:
                continue

            if max_rows and (total_rows_yielded + len(chunk) > max_rows):
                remaining = max_rows - total_rows_yielded
                if remaining > 0:
                    yield chunk.iloc[:remaining]
                break

            total_rows_yielded += len(chunk)
            yield chunk

        logger.info(f"Streamed total of {total_rows_yielded} sales records from {path.name}")
