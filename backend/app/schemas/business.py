from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int


# Catalog Schemas
class CategoryResponse(BaseModel):
    id: int
    category_code: str
    category_name: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProductResponse(BaseModel):
    id: int
    product_code: str
    product_name: str
    category_id: int
    source_family: str
    unit_of_measure: str
    is_active: bool
    data_origin: str
    created_at: datetime

    class Config:
        from_attributes = True


# Branch & Warehouse Schemas
class BranchResponse(BaseModel):
    id: int
    branch_code: str
    branch_name: str
    city: str
    state: str
    source_store_number: int
    store_type: Optional[str] = None
    cluster: Optional[int] = None
    data_origin: str
    created_at: datetime

    class Config:
        from_attributes = True


class WarehouseResponse(BaseModel):
    id: int
    warehouse_code: str
    warehouse_name: str
    branch_id: Optional[int] = None
    location: str
    data_origin: str
    created_at: datetime

    class Config:
        from_attributes = True


# Supplier Schemas
class SupplierResponse(BaseModel):
    id: int
    supplier_code: str
    supplier_name: str
    lead_time_days: int
    minimum_order_quantity: int
    is_active: bool
    data_origin: str
    created_at: datetime

    class Config:
        from_attributes = True


# Inventory Schemas
class InventoryResponse(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    stock_quantity: int
    reserved_quantity: int
    available_quantity: int
    reorder_point: int
    safety_stock: int
    last_updated: datetime
    data_origin: str

    class Config:
        from_attributes = True


# Daily Sales Schemas
class DailySaleResponse(BaseModel):
    id: int
    sale_date: date
    branch_id: int
    product_id: int
    quantity_sold: Decimal = Field(..., description="Observed units/quantity sold from Kaggle dataset")
    sales_amount: Decimal = Field(..., description="Estimated revenue derived from (quantity_sold * estimated_unit_price)")
    promotion_quantity: int
    source_dataset: str
    data_origin: str
    is_amount_estimated: bool = Field(
        default=True,
        description="Flag indicating that monetary sales_amount is derived using benchmark family pricing",
    )

    class Config:
        from_attributes = True


# Pipeline & Data Quality Schemas
class DataSummaryResponse(BaseModel):
    branches: int
    categories: int
    products: int
    daily_sales_records: int
    warehouses: int
    suppliers: int
    inventory_records: int
    total_physical_stock: int
    total_reserved_stock: int
    available_stock: int
    sales_start_date: Optional[str] = None
    sales_end_date: Optional[str] = None


class DataQualityItemResponse(BaseModel):
    id: int
    dataset_name: str
    validation_name: str
    total_records: int
    failed_records: int
    validation_status: str
    details: Optional[str] = None
    executed_at: datetime

    class Config:
        from_attributes = True


class ImportRequest(BaseModel):
    max_sales_rows: Optional[int] = Field(default=50_000, ge=1, le=500_000, description="Max rows to stream from sales")
    start_date: Optional[str] = Field(default=None, description="Filter starting YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="Filter ending YYYY-MM-DD")


class ImportResponse(BaseModel):
    message: str
    task_id: str
    status: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Any] = None


class SyntheticGenerationRequest(BaseModel):
    seed: int = Field(default=42, description="Random seed for reproducible generation")


class SyntheticGenerationResponse(BaseModel):
    message: str
    task_id: str
    seed: int
