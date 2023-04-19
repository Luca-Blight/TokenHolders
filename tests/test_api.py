from fastapi.testclient import TestClient
from app.server.main import app


client = TestClient(app)


def test_get_token_holders():
    response = client.get("/token_holders")
    assert response.status_code == 200
    assert len(response.json()["token_holders"]) == 100  # Check default limit

    response = client.get("/token_holders?top_token_holders=10&order_by=asc")
    assert response.status_code == 200
    assert len(response.json()["token_holders"]) == 10
    assert (
        response.json()["token_holders"][0]["balance"]
        < response.json()["token_holders"][-1]["balance"]
    )


def test_get_token_holder():
    response = client.get("/token_holders/0x742d35Cc6634C0532925a3b844Bc454e4438f44e")

    assert response.status_code == 200
    assert "address" in response.json()["token_holder"][0]
    assert "balance" in response.json()["token_holder"][0]
    assert "weekly_balance_change" in response.json()["token_holder"][0]

    response = client.get(
        "/token_holders/0x742d35Cc6634C0532925a3b844Bc454e4438f44e?balance=true"
    )
    assert response.status_code == 200
    assert "balance" in response.json()["token_holder"][0]
    assert "weekly_balance_change" not in response.json()["token_holder"][0]

    response = client.get(
        "/token_holders/0x742d35Cc6634C0532925a3b844Bc454e4438f44e?weekly_balance_change=true"
    )
    assert response.status_code == 200
    assert "balance" not in response.json()["token_holder"][0]
    assert "weekly_balance_change" in response.json()["token_holder"][0]


def test_invalid_order_by():
    response = client.get("/token_holders?order_by=invalid")
    assert response.status_code == 400
    assert "Invalid order_by value." in response.json()["detail"]
