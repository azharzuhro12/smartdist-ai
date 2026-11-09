from pathlib import Path
from decimal import Decimal
from typing import Dict

# Base paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DATA_DIR = PROJECT_ROOT / "ml" / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "ml" / "data" / "processed"
FEATURES_DATA_DIR = PROJECT_ROOT / "ml" / "data" / "features"

# Dataset origins
DATA_ORIGIN_KAGGLE = "KAGGLE_PUBLIC"
DATA_ORIGIN_SYNTHETIC = "SYNTHETIC"
DATASET_NAME_STORE_SALES = "store-sales-time-series-forecasting"

# Estimated baseline unit prices and cost margins by product family
# Enables realistic financial sales_amount calculation from Kaggle quantity_sold
FAMILY_PRICE_REFERENCE: Dict[str, Dict[str, Decimal]] = {
    "AUTOMOTIVE": {"unit_price": Decimal("25.00"), "unit_cost": Decimal("18.00")},
    "BABY CARE": {"unit_price": Decimal("15.50"), "unit_cost": Decimal("11.00")},
    "BEAUTY": {"unit_price": Decimal("18.00"), "unit_cost": Decimal("12.50")},
    "BEVERAGES": {"unit_price": Decimal("3.50"), "unit_cost": Decimal("2.10")},
    "BOOKS": {"unit_price": Decimal("12.00"), "unit_cost": Decimal("8.00")},
    "BREAD/BAKERY": {"unit_price": Decimal("2.75"), "unit_cost": Decimal("1.60")},
    "CELEBRATION": {"unit_price": Decimal("8.50"), "unit_cost": Decimal("5.20")},
    "CLEANING": {"unit_price": Decimal("6.20"), "unit_cost": Decimal("4.00")},
    "DAIRY": {"unit_price": Decimal("4.10"), "unit_cost": Decimal("2.80")},
    "DELI": {"unit_price": Decimal("7.80"), "unit_cost": Decimal("5.40")},
    "EGGS": {"unit_price": Decimal("3.20"), "unit_cost": Decimal("2.20")},
    "FROZEN FOODS": {"unit_price": Decimal("6.90"), "unit_cost": Decimal("4.80")},
    "GROCERY I": {"unit_price": Decimal("5.00"), "unit_cost": Decimal("3.50")},
    "GROCERY II": {"unit_price": Decimal("4.50"), "unit_cost": Decimal("3.10")},
    "HARDWARE": {"unit_price": Decimal("14.00"), "unit_cost": Decimal("9.50")},
    "HOME AND KITCHEN I": {"unit_price": Decimal("22.00"), "unit_cost": Decimal("15.00")},
    "HOME AND KITCHEN II": {"unit_price": Decimal("28.00"), "unit_cost": Decimal("19.00")},
    "HOME APPLIANCES": {"unit_price": Decimal("85.00"), "unit_cost": Decimal("60.00")},
    "HOME CARE": {"unit_price": Decimal("7.50"), "unit_cost": Decimal("5.00")},
    "LADIESWEAR": {"unit_price": Decimal("32.00"), "unit_cost": Decimal("20.00")},
    "LAWN AND GARDEN": {"unit_price": Decimal("19.50"), "unit_cost": Decimal("13.00")},
    "LINGERIE": {"unit_price": Decimal("16.00"), "unit_cost": Decimal("9.50")},
    "LIQUOR,WINE,BEER": {"unit_price": Decimal("14.50"), "unit_cost": Decimal("9.80")},
    "MAGAZINES": {"unit_price": Decimal("5.50"), "unit_cost": Decimal("3.80")},
    "MEATS": {"unit_price": Decimal("9.20"), "unit_cost": Decimal("6.80")},
    "PERSONAL CARE": {"unit_price": Decimal("6.50"), "unit_cost": Decimal("4.20")},
    "PET SUPPLIES": {"unit_price": Decimal("13.00"), "unit_cost": Decimal("8.50")},
    "PLAYERS AND ELECTRONICS": {"unit_price": Decimal("95.00"), "unit_cost": Decimal("70.00")},
    "POULTRY": {"unit_price": Decimal("8.00"), "unit_cost": Decimal("5.80")},
    "PREPARED FOODS": {"unit_price": Decimal("6.00"), "unit_cost": Decimal("4.00")},
    "PRODUCE": {"unit_price": Decimal("3.00"), "unit_cost": Decimal("1.90")},
    "SCHOOL AND OFFICE SUPPLIES": {"unit_price": Decimal("4.50"), "unit_cost": Decimal("2.80")},
    "SEAFOOD": {"unit_price": Decimal("12.50"), "unit_cost": Decimal("9.00")},
}

DEFAULT_FAMILY_PRICING = {"unit_price": Decimal("10.00"), "unit_cost": Decimal("6.50")}
