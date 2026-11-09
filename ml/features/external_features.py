from pathlib import Path
from typing import Optional
import pandas as pd
from ml.pipelines.common.constants import RAW_DATA_DIR


class ExternalFeatureExtractor:
    """
    Cleans, aligns, and merges external predictors (oil prices, holiday calendars,
    store metadata, and transaction traffic) with strict prevention of row duplication.
    """

    @staticmethod
    def load_clean_oil_prices(file_path: Optional[Path] = None) -> pd.DataFrame:
        """
        Load crude oil prices, create a continuous date sequence, and interpolate missing days
        (weekends and market holidays) using forward-fill followed by backward-fill.
        """
        path = file_path or (RAW_DATA_DIR / "oil.csv")
        oil = pd.read_csv(path)
        oil["date"] = pd.to_datetime(oil["date"])

        # Create continuous date range to cover weekends
        full_dates = pd.date_range(start=oil["date"].min(), end=oil["date"].max(), freq="D")
        full_df = pd.DataFrame({"date": full_dates})
        merged = pd.merge(full_df, oil, on="date", how="left")

        # Forward-fill and backward-fill
        merged["oil_price"] = merged["dcoilwtico"].ffill().bfill()
        merged["date_str"] = merged["date"].dt.strftime("%Y-%m-%d")

        return merged[["date_str", "oil_price"]].rename(columns={"date_str": "date"})

    @staticmethod
    def load_clean_holidays(file_path: Optional[Path] = None) -> pd.DataFrame:
        """
        Load holiday events, resolve multiple events on the same date, filter transferred holidays,
        and create unambiguous calendar indicators.
        """
        path = file_path or (RAW_DATA_DIR / "holidays_events.csv")
        holidays = pd.read_csv(path)

        # Exclude transferred holidays (they were moved to another date)
        active_holidays = holidays[~holidays["transferred"]].copy()

        # Group by date to prevent Cartesian product duplicates on multi-event dates
        # Prioritize: National > Regional > Local
        locale_priority = {"National": 3, "Regional": 2, "Local": 1}
        active_holidays["priority"] = active_holidays["locale"].map(locale_priority).fillna(0)
        sorted_holidays = active_holidays.sort_values(by=["date", "priority"], ascending=[True, False])

        # Deduplicate to 1 primary holiday per date
        primary_holidays = sorted_holidays.drop_duplicates(subset=["date"], keep="first").copy()

        primary_holidays["is_holiday"] = 1
        primary_holidays["is_national_holiday"] = (primary_holidays["locale"] == "National").astype("int8")
        primary_holidays["is_work_day"] = (primary_holidays["type"] == "Work Day").astype("int8")
        primary_holidays["holiday_type"] = primary_holidays["type"].astype(str)

        cols = ["date", "is_holiday", "is_national_holiday", "is_work_day", "holiday_type"]
        return primary_holidays[cols]

    @staticmethod
    def load_transactions(file_path: Optional[Path] = None) -> pd.DataFrame:
        """
        Load daily customer transaction traffic per store.
        """
        path = file_path or (RAW_DATA_DIR / "transactions.csv")
        tx = pd.read_csv(path)
        tx["date"] = tx["date"].astype(str)
        tx["transactions"] = tx["transactions"].fillna(0).astype("int32")
        return tx[["date", "store_nbr", "transactions"]]

    @classmethod
    def enrich_dataset(
        cls,
        df: pd.DataFrame,
        stores_file: Optional[Path] = None,
        oil_file: Optional[Path] = None,
        holidays_file: Optional[Path] = None,
        transactions_file: Optional[Path] = None,
        include_transactions: bool = True,
    ) -> pd.DataFrame:
        """
        Enrich input sales panel with store metadata, oil prices, holiday indicators, and transactions.
        """
        res = df.copy()
        res["date"] = res["date"].astype(str)

        # 1. Merge store metadata if store_type / cluster not present
        if "store_type" not in res.columns:
            stores_path = stores_file or (RAW_DATA_DIR / "stores.csv")
            stores = pd.read_csv(stores_path)
            stores_meta = stores[["store_nbr", "type", "cluster"]].rename(columns={"type": "store_type", "cluster": "store_cluster"})
            res = pd.merge(res, stores_meta, on="store_nbr", how="left")

        # 2. Merge clean oil prices if not already present
        if "oil_price" not in res.columns:
            oil_df = cls.load_clean_oil_prices(oil_file)
            res = pd.merge(res, oil_df, on="date", how="left")
        # Forward-fill chronologically so date t never uses future oil prices (> t);
        # only leading initial NaNs before the first valid observation use bfill or constant 60.0
        res = res.sort_values(by=["date"]).reset_index(drop=True)
        res["oil_price"] = res["oil_price"].ffill().bfill().fillna(60.0)

        # 3. Merge holiday indicators if not already present
        if "is_holiday" not in res.columns:
            holidays_df = cls.load_clean_holidays(holidays_file)
            res = pd.merge(res, holidays_df, on="date", how="left")
        res["is_holiday"] = res.get("is_holiday", pd.Series(0, index=res.index)).fillna(0).astype("int8")
        res["is_national_holiday"] = res.get("is_national_holiday", pd.Series(0, index=res.index)).fillna(0).astype("int8")
        res["is_work_day"] = res.get("is_work_day", pd.Series(0, index=res.index)).fillna(0).astype("int8")
        res["holiday_type"] = res.get("holiday_type", pd.Series("None", index=res.index)).fillna("None")

        # 4. Merge transactions if requested and not already present
        # Note: If transactions represent future store visits on date T, it should only be used as a lagged predictor or contemporaneous covariate if available
        if include_transactions and "transactions" not in res.columns:
            tx_df = cls.load_transactions(transactions_file)
            res = pd.merge(res, tx_df, on=["date", "store_nbr"], how="left")
        if "transactions" in res.columns:
            res["transactions"] = res["transactions"].fillna(0).astype("int32")

        return res
