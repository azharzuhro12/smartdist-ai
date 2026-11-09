import pandas as pd


class CalendarFeatureExtractor:
    """
    Extracts deterministic temporal and calendar features from date series.
    Pure functional transformation: no future leakage risk.
    """

    @staticmethod
    def add_calendar_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
        """
        Add standard calendar attributes to the DataFrame.
        """
        res = df.copy()
        date_series = pd.to_datetime(res[date_col])

        res["year"] = date_series.dt.year.astype("int32")
        res["month"] = date_series.dt.month.astype("int8")
        res["day"] = date_series.dt.day.astype("int8")
        res["day_of_week"] = date_series.dt.dayofweek.astype("int8")
        res["day_of_month"] = date_series.dt.day.astype("int8")
        res["week_of_year"] = date_series.dt.isocalendar().week.astype("int8")
        res["quarter"] = date_series.dt.quarter.astype("int8")
        res["is_weekend"] = (res["day_of_week"] >= 5).astype("int8")
        res["is_month_start"] = date_series.dt.is_month_start.astype("int8")
        res["is_month_end"] = date_series.dt.is_month_end.astype("int8")

        return res
