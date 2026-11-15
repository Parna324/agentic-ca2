"""API contract and end-to-end smoke tests."""
import time

from fastapi.testclient import TestClient

from main import app


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_review_pipeline_persists_result():
    content = "--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,4 @@\n+def greet(name):\n+    password = 'secret-value'\n+    return 'hello ' + name\n"
    with TestClient(app) as client:
        response = client.post("/api/reviews", json={
            "diff_text": content,
            "repo_name": "test-repo",
            "language": "python",
            "submission_type": "diff",
        })
        assert response.status_code == 200
        review_id = response.json()["id"]
        for _ in range(30):
            detail = client.get(f"/api/reviews/{review_id}").json()
            if detail["status"] in {"COMPLETED", "FAILED"}:
                break
            time.sleep(0.05)
    assert detail["status"] == "COMPLETED"
    assert detail["merge_decision"] == "REQUEST_CHANGES"
    assert detail["findings"]
