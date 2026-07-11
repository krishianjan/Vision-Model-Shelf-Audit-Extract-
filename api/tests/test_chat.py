import pytest
from httpx import AsyncClient, ASGITransport
import uuid
import json
from unittest.mock import MagicMock, AsyncMock

from src.main import app
from src.auth import get_current_user, AuthUser

@pytest.fixture
def mock_auth_headers():
    return {"Authorization": "Bearer test-token"}

@pytest.fixture
async def ac():
    # Setup dependency override
    test_user = AuthUser(user_id=uuid.uuid4(), org_id=uuid.uuid4(), email='test@kosha.ai')
    app.dependency_overrides[get_current_user] = lambda: test_user
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
        
    # Cleanup dependency override
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_chat_lowest_facings(ac, mock_auth_headers, monkeypatch):
    # Mock LLM to return valid SQL
    async def mock_groq(messages):
        if len(messages) == 2:  # Pass 1
            return {
                "answer": "Looking up the lowest Tito's facings...",
                "sql_used": "SELECT a.name as store_name, ao.facings FROM audit_observations ao JOIN shelf_audits sa ON sa.id = ao.audit_id JOIN accounts a ON a.id = sa.account_id WHERE ao.brand_read ILIKE '%Tito%' ORDER BY ao.facings ASC LIMIT 1;",
                "tables_touched": ["audit_observations", "shelf_audits", "accounts"]
            }
        else:  # Pass 3
            return {
                "answer": "Store 123 has the lowest Tito's facings with a count of 2.",
                "sql_used": "SELECT a.name as store_name, ao.facings FROM audit_observations ao JOIN shelf_audits sa ON sa.id = ao.audit_id JOIN accounts a ON a.id = sa.account_id WHERE ao.brand_read ILIKE '%Tito%' ORDER BY ao.facings ASC LIMIT 1;",
                "tables_touched": ["audit_observations", "shelf_audits", "accounts"]
            }
            
    monkeypatch.setattr("src.routes.chat._call_groq", mock_groq)
    
    # Need to mock the DB fetch as well since we don't have seeded data
    class MockConn:
        async def fetch(self, sql):
            return [{"store_name": "Store 123", "facings": 2}]
        async def execute(self, sql, *args):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
            
    class MockTx:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass

    # Override the DB acquire logic
    mock_db = MagicMock()
    mock_acq = MagicMock()
    mock_acq.__aenter__.return_value = MockConn()
    mock_db.acquire.return_value = mock_acq
    
    # Need to properly patch the transaction
    MockConn.transaction = MagicMock(return_value=MockTx())
    
    # Use monkeypatch on request.app.state.db inside the route, but it's easier to patch the app instance
    app.state.db = mock_db
    
    resp = await ac.post("/chat", json={"question": "which of my stores has the lowest Tito's facings"}, headers=mock_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "Store 123" in data["answer"]
    assert "2" in data["answer"]
    assert "SELECT" in data["sql_used"].upper()
    assert "accounts" in data["tables_touched"]

@pytest.mark.asyncio
async def test_chat_drop_table(ac, mock_auth_headers, monkeypatch):
    async def mock_groq(messages):
        return {
            "answer": "Executing drop table...",
            "sql_used": "DROP TABLE shelf_audits;",
            "tables_touched": ["shelf_audits"]
        }
            
    monkeypatch.setattr("src.routes.chat._call_groq", mock_groq)
    
    resp = await ac.post("/chat", json={"question": "DROP TABLE audits"}, headers=mock_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "not allowed to execute destructive queries" in data["answer"].lower()

@pytest.mark.asyncio
async def test_chat_weather_out_of_scope(ac, mock_auth_headers, monkeypatch):
    async def mock_groq(messages):
        return {
            "answer": "I can only answer questions about your shelf audit activity.",
            "sql_used": None,
            "tables_touched": []
        }
            
    monkeypatch.setattr("src.routes.chat._call_groq", mock_groq)
    
    resp = await ac.post("/chat", json={"question": "What's the weather?"}, headers=mock_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "shelf audit" in data["answer"].lower()
    assert data["sql_used"] is None

