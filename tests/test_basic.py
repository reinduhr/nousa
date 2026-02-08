from starlette.testclient import TestClient

from src.main import app  # ← this is your Starlette app

def test_root_page_loads():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "<html" in response.text.lower()   # very basic check that it's HTML