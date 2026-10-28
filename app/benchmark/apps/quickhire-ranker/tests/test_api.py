from app.main import app


def test_ranking_endpoint_returns_200():
    client = app.test_client()
    resp = client.get("/ranking/42")
    assert resp.status_code == 200
