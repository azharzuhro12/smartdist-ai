# Dataset Documentation & Source Mapping

## 1. Dataset Source

- **Dataset**: Kaggle Store Sales - Time Series Forecasting
- **Competition Host**: Corporación Favorita (Major Ecuadorian Retailer)
- **URL**: https://www.kaggle.com/competitions/store-sales-time-series-forecasting
- **Downloaded Location**: `ml/data/raw/`

## 2. File Specifications & Schema

| File Name | Size | Rows | Columns | Description |
|---|---|---|---|---|
| `stores.csv` | 1.4 KB | 54 | `store_nbr`, `city`, `state`, `type`, `cluster` | Metadata for 54 retail store branches across Ecuador |
| `train.csv` | 117 MB | 3,000,888 | `id`, `date`, `store_nbr`, `family`, `sales`, `onpromotion` | Daily sales by store and product family (2013-01-01 to 2017-08-15) |
| `transactions.csv` | 1.5 MB | 83,488 | `date`, `store_nbr`, `transactions` | Total daily customer foot-traffic transactions per store |
| `oil.csv` | 21 KB | 1,218 | `date`, `dcoilwtico` | Daily West Texas Intermediate (WTI) crude oil price |
| `holidays_events.csv`| 22 KB | 350 | `date`, `type`, `locale`, `locale_name`, `description`, `transferred` | National, regional, and municipal holidays |

## 3. Business Domain Mapping

| Raw Dataset Element | SmartDist AI Entity | Column Mapping | Rationale |
|---|---|---|---|
| `stores.csv` -> `store_nbr` | `branches` | `source_store_number` | Preserves original competition store ID while assigning internal PK |
| `stores.csv` -> `city`, `state` | `branches` | `city`, `state` | Retains geographical context for regional demand analysis |
| `train.csv` -> `family` | `categories` | `category_code`, `category_name` | Maps merchandise families to normalized categories (`CAT-<FAMILY>`) |
| `train.csv` -> `family` | `products` | `source_family`, `product_code` | Models standard product SKU per family (`PRD-<FAMILY>`) |
| `train.csv` -> `sales` | `daily_sales` | `quantity_sold` | Fractional sales supported via `NUMERIC(14, 4)` |
| `train.csv` -> `sales * price`| `daily_sales`| `sales_amount` | Monetary sales value derived from reference unit price per family |
| `train.csv` -> `onpromotion` | `daily_sales` | `promotion_quantity` | Promotional item quantity sold |

## 4. Synthetic Data Generation Assumptions

Because inventory balances, warehouses, and supplier contracts are proprietary and not included in public retail sales datasets:
1. **Warehouses**: 4 regional distribution centers located in Quito, Guayaquil, Cuenca, and Ambato.
2. **Suppliers**: 6 vendor partners with lead times ranging from 3 to 21 days and minimum order quantities of 15–100 units.
3. **Inventory Levels**: Realistic safety stock (20–80 units) and reorder points (50–200 units) assigned per warehouse-product pair, with reserved stock bounded to `<= stock_quantity`.
4. **Data Tagging**: All synthetic records carry `data_origin = 'SYNTHETIC'` to prevent confusing simulated inventory with real Kaggle sales data.
