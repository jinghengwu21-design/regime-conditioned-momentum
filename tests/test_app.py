"""HTTP contract tests against a real ephemeral loopback server."""
from http.server import ThreadingHTTPServer
from threading import Thread
import httpx
import pytest
from research_agent.server import Handler

@pytest.fixture(scope="module")
def api():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False, timeout=30) as client:
        yield client
    server.shutdown()
    server.server_close()
    thread.join()

def test_status_exposes_no_credentials(api):
    response = api.get("/api/status")
    assert response.status_code == 200
    assert set(response.json()) == {"service", "version", "model_configured"}

def test_research_runs_real_graph_with_changed_fees(api):
    response = api.post("/api/research", json={"fee_bps": 8})
    assert response.status_code == 200
    result = response.json()
    assert 11000 < result["base"]["metrics"]["final_equity"] < 11100
    assert result["reviews"][-1]["passed"]
    assert "local_run_dir" not in result

def test_numeric_fault_is_rejected_then_repaired(api):
    response = api.post("/api/research", json={"scenario": "numeric_mismatch"})
    result = response.json()
    assert response.status_code == 200
    assert result["repaired"]
    assert [r["passed"] for r in result["reviews"]] == [False, True]

@pytest.mark.parametrize("body", [{"fee_bps": 100}, {"mode": "unknown"}, {"asset": "ETH"}, {"execute_shell": True}])
def test_invalid_request_does_not_run(api, body):
    assert api.post("/api/research", json=body).status_code == 422

def test_cross_origin_post_is_rejected(api):
    assert api.post("/api/research", json={}, headers={"Origin": "https://unrelated.example"}).status_code == 403

def test_wrong_content_type_and_large_body_are_rejected(api):
    assert api.post("/api/research", content="{}").status_code == 415
    assert api.post("/api/research", content="x" * 20001, headers={"Content-Type": "application/json"}).status_code == 413
