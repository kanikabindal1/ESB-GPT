"""
Shared pytest fixtures: TestClient, sample API record, sample retriever results.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """FastAPI TestClient using the real app."""
    return TestClient(app)


@pytest.fixture
def sample_api_record():
    """One API record matching data/apis.json shape (e.g. api_001)."""
    return {
        "id": "api_001",
        "name": "GetCustomerOrders",
        "description": "Retrieves all orders placed by a customer within a date range.",
        "use_cases": ["order history", "customer lookup", "purchase tracking"],
        "input": {
            "customer_id": "string, required",
            "from_date": "ISO date, optional",
            "to_date": "ISO date, optional",
        },
        "output": {
            "orders": "array of order objects",
            "total_count": "integer",
            "status": "string",
        },
        "method": "GET",
        "endpoint": "/customers/{id}/orders",
        "tags": ["orders", "customers", "e-commerce"],
    }


@pytest.fixture
def sample_retriever_results(sample_api_record):
    """Fake retriever search results for use in retriever and API tests."""
    return [
        {
            "id": "api_001",
            "record": sample_api_record,
            "document": "GetCustomerOrders — Retrieves all orders...",
            "distance": 0.2,
            "similarity": 0.9,
            "match_type": "direct",
        },
        {
            "id": "api_002",
            "record": {
                "id": "api_002",
                "name": "GetOrderById",
                "description": "Returns a single order by id.",
                "input": {"order_id": "string"},
                "output": {"order": "object"},
            },
            "document": "GetOrderById — Returns...",
            "distance": 0.8,
            "similarity": 0.6,
            "match_type": "closest",
        },
    ]
