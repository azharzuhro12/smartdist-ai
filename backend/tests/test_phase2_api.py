from fastapi.testclient import TestClient


def test_api_data_summary(client: TestClient):
    """Verify GET /api/v1/data/summary returns accurate aggregated metrics."""
    res = client.get("/api/v1/data/summary")
    assert res.status_code == 200
    data = res.json()
    assert "branches" in data
    assert "products" in data
    assert "daily_sales_records" in data
    assert data["branches"] >= 54
    assert data["products"] >= 33


def test_api_data_quality(client: TestClient):
    """Verify GET /api/v1/data/quality lists historical validation results."""
    res = client.get("/api/v1/data/quality?limit=5")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        assert "validation_name" in data[0]
        assert "validation_status" in data[0]


def test_api_products_pagination_and_search(client: TestClient):
    """Verify GET /api/v1/products paginates and filters by search query."""
    res = client.get("/api/v1/products?page=1&size=5&search=Beverages")
    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 1
    assert data["size"] == 5
    assert len(data["items"]) >= 1
    assert "Beverages" in data["items"][0]["product_name"]


def test_api_branches_pagination(client: TestClient):
    """Verify GET /api/v1/branches paginates stores."""
    res = client.get("/api/v1/branches?page=1&size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 54
    assert len(data["items"]) == 10
    assert data["items"][0]["branch_code"].startswith("BR-")


def test_api_sales_daily_filtering(client: TestClient):
    """Verify GET /api/v1/sales/daily filters by branch."""
    res = client.get("/api/v1/sales/daily?branch_id=1&size=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) <= 5
    for item in data["items"]:
        assert item["branch_id"] == 1


def test_api_inventory_listing(client: TestClient):
    """Verify GET /api/v1/inventory lists stock balances."""
    res = client.get("/api/v1/inventory?size=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) <= 5
    if data["items"]:
        inv = data["items"][0]
        assert inv["data_origin"] == "SYNTHETIC"
        assert inv["available_quantity"] == inv["stock_quantity"] - inv["reserved_quantity"]


def test_api_suppliers_listing(client: TestClient):
    """Verify GET /api/v1/suppliers lists suppliers."""
    res = client.get("/api/v1/suppliers?size=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) >= 1
