from datetime import date, datetime
from typing import Generator, List, Tuple, Union
import pandas as pd


class TimeSeriesSplitter:
    """
    Enforces strict chronological data splitting for time-series evaluation.
    Guarantees no future information leakage across train, validation, and test partitions.
    """

    @staticmethod
    def split_by_dates(
        df: pd.DataFrame,
        train_end: Union[str, date],
        val_end: Union[str, date],
        date_col: str = "date",
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Split dataset into non-overlapping chronological partitions:
            - Train:      date <= train_end
            - Validation: train_end < date <= val_end
            - Test:       date > val_end
        """
        train_end_str = str(train_end)
        val_end_str = str(val_end)

        dates = df[date_col].astype(str)

        train_mask = dates <= train_end_str
        val_mask = (dates > train_end_str) & (dates <= val_end_str)
        test_mask = dates > val_end_str

        train_df = df[train_mask].copy().reset_index(drop=True)
        val_df = df[val_mask].copy().reset_index(drop=True)
        test_df = df[test_mask].copy().reset_index(drop=True)

        return train_df, val_df, test_df

    @staticmethod
    def expanding_window_split(
        df: pd.DataFrame,
        folds: int = 3,
        val_days: int = 30,
        date_col: str = "date",
    ) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        """
        Expanding-window cross-validation generator for time-series.
        Training window expands forward while validation window shifts incrementally into the future.
        """
        unique_dates = sorted(df[date_col].astype(str).unique())
        total_days = len(unique_dates)

        required_days = val_days * folds
        if total_days <= required_days:
            raise ValueError(
                f"Insufficient historical dates ({total_days}) for {folds} folds of {val_days} days."
            )

        start_train_len = total_days - required_days

        for i in range(folds):
            train_cutoff_idx = start_train_len + (i * val_days)
            val_cutoff_idx = train_cutoff_idx + val_days

            train_end_date = unique_dates[train_cutoff_idx - 1]
            val_end_date = unique_dates[val_cutoff_idx - 1]

            dates = df[date_col].astype(str)
            train_df = df[dates <= train_end_date].copy().reset_index(drop=True)
            val_df = (
                df[(dates > train_end_date) & (dates <= val_end_date)]
                .copy()
                .reset_index(drop=True)
            )

            yield train_df, val_df
