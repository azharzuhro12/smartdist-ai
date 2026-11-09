"""
Tests for AI Assistant FastAPI REST API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_api_chat_policy_endpoint():
    response = client.post(
        "/api/v1/assistant/chat",
        json={"query": "What is the policy for calculating safety stock?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "POLICY_SOP"
    assert data["tool_used"] == "rag_policy_lookup"
    assert len(data["citations"]) > 0


def test_api_chat_sql_endpoint():
    response = client.post(
        "/api/v1/assistant/chat",
        json={"query": "What are the top 3 selling products by volume?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "SAFE_SQL"
    assert data["tool_used"] == "safe_sql_agent"
    assert data["data"]["row_count"] == 3


def test_api_list_workflows():
    response = client.get("/api/v1/assistant/workflows")
    assert response.status_code == 200
    data = response.json()
    workflow_ids = [w["id"] for w in data["workflows"]]
    assert "executive_briefing" in workflow_ids
    assert "replenishment_explanation" in workflow_ids
    assert "anomaly_root_cause" in workflow_ids


def test_api_execute_workflow():
    response = client.post(
        "/api/v1/assistant/workflow",
        json={"workflow_name": "executive_briefing", "parameters": {}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["workflow"] == "executive_briefing"
    assert "Executive Daily Briefing" in data["title"]


def test_api_safe_sql_endpoint_success():
    response = client.post(
        "/api/v1/assistant/sql",
        json={"query": "Show sales by branch"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["row_count"] > 0


def test_api_safe_sql_endpoint_injection_blocked():
    response = client.post(
        "/api/v1/assistant/sql",
        json={"query": "DROP TABLE daily_sales"},
    )
    # The API catches SQLValidationError and returns 400 Bad Request
    assert response.status_code == 400
    assert "SQL Query failed" in response.json()["detail"]


def test_api_policy_search_endpoint():
    response = client.post(
        "/api/v1/assistant/policy-search",
        json={"query": "purchase order approval limits", "top_k": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["passages"]) > 0
    assert "POL-PROC-002" in [p["doc_id"] for p in data["passages"]]

