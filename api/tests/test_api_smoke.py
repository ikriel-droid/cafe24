from pathlib import Path
import shutil

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import reset_engine
from app.integrations.cafe24.sync_service import Cafe24SyncService


def test_claims_endpoint_bootstraps_database(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "health"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    get_settings.cache_clear()
    reset_engine()

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/claims")
        assert response.status_code == 200
        assert len(response.json()) >= 12


def test_claims_endpoint_supports_search(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "search"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    get_settings.cache_clear()
    reset_engine()

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/claims?q=오배송")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["order_no"] == "CM-240301-004"
        assert payload[0]["category"] == "misdelivery"


def test_claim_note_is_recorded_in_audit_log(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "notes"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    get_settings.cache_clear()
    reset_engine()

    from app.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/claims/1/notes",
            json={"note": "고객이 사진 사전 전달 예정", "actor": "qa_operator"},
        )
        assert response.status_code == 200
        payload = response.json()
        latest_log = payload["audit_logs"][0]
        assert latest_log["event_type"] == "internal_note_added"
        assert latest_log["actor"] == "qa_operator"
        assert latest_log["payload_json"]["note"] == "고객이 사진 사전 전달 예정"


def test_cafe24_mock_sync_status(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "cafe24"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    Cafe24SyncService.reset_state()
    get_settings.cache_clear()
    reset_engine()

    from app.main import app

    with TestClient(app) as client:
        initial = client.get("/api/integrations/cafe24")
        assert initial.status_code == 200
        assert initial.json()["connection_mode"] == "offline_mock"
        assert initial.json()["last_sync_result"] == "not_started"
        assert initial.json()["health_status"] == "attention"
        assert initial.json()["next_action_type"] == "mock_sync"
        assert initial.json()["next_action_label"] == "Run Mock Sync"
        assert initial.json()["webhook_endpoint_ready"] is True

        synced = client.post("/api/integrations/cafe24/mock-sync")
        assert synced.status_code == 200
        payload = synced.json()
        assert payload["last_sync_result"] == "mock_completed"
        assert payload["synced_claims"] >= 12
        assert payload["last_synced_at"] is not None
        assert payload["health_status"] == "setup_needed"
        assert payload["next_action_type"] == "open_link"
        assert payload["next_action_href"] == "/integrations/cafe24"
        assert payload["recent_events"][0]["event_type"] == "mock_sync"
        assert payload["recent_events"][0]["batch_id"] == payload["last_sync_batch_id"]


def test_cafe24_mock_webhook_increases_pending_count(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "cafe24-webhook"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    Cafe24SyncService.reset_state()
    get_settings.cache_clear()
    reset_engine()

    from app.main import app

    with TestClient(app) as client:
        base_status = client.get("/api/integrations/cafe24")
        assert base_status.status_code == 200
        base_pending = base_status.json()["pending_webhooks"]

        response = client.post(
            "/api/integrations/cafe24/mock-webhook",
            json={"event_type": "claim.return.requested", "order_no": "CM-240301-011"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["pending_webhooks"] == base_pending + 1
        assert payload["recent_events"][0]["event_type"] == "mock_webhook"
        assert payload["recent_events"][0]["status"] == "received"
        assert "CM-240301-011" in payload["recent_events"][0]["detail"]
        assert "답변 초안 생성 완료" in payload["recent_events"][0]["detail"]
        assert payload["recent_events"][0]["claim_id"] is not None
        assert payload["recent_events"][0]["order_no"] == "CM-240301-011"

        claim_response = client.get(f"/api/claims/{payload['recent_events'][0]['claim_id']}")
        assert claim_response.status_code == 200
        claim_payload = claim_response.json()
        assert claim_payload["order_no"] == "CM-240301-011"
        assert claim_payload["category"] == "return"
        assert claim_payload["status"] == "in_review"
        assert claim_payload["urgency"] == "medium"
        assert claim_payload["ai_label"] == "return_request"
        assert claim_payload["audit_logs"][0]["event_type"] == "cafe24_mock_webhook_auto_triaged"
        assert claim_payload["audit_logs"][1]["event_type"] == "draft_reply_generated"
        assert claim_payload["audit_logs"][2]["event_type"] == "claim_classified"
        assert claim_payload["audit_logs"][3]["event_type"] == "cafe24_mock_webhook_received"
        assert claim_payload["messages"][-1]["role"] == "system"
        assert {action["action_type"] for action in claim_payload["suggested_actions"]} >= {"classification", "draft_reply"}


def test_cafe24_callback_redirects_to_console(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "cafe24-callback"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    Cafe24SyncService.reset_state()
    get_settings.cache_clear()
    reset_engine()

    from app.main import app

    with TestClient(app) as client:
        response = client.get(
            "/api/integrations/cafe24/callback?code=demo-code&state=claimmate-local-1",
            follow_redirects=False,
        )
        assert response.status_code == 307
        location = response.headers["location"]
        assert location.startswith("/integrations/cafe24/?")
        assert "oauth_result=received" in location
        assert "oauth_state=claimmate-local-1" in location

        status = client.get("/api/integrations/cafe24")
        assert status.status_code == 200
        assert status.json()["recent_events"][0]["event_type"] == "oauth_callback"
        assert status.json()["recent_events"][0]["status"] == "received"


def test_cafe24_activity_can_be_cleared(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "cafe24-clear"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    Cafe24SyncService.reset_state()
    get_settings.cache_clear()
    reset_engine()

    from app.main import app

    with TestClient(app) as client:
        synced = client.post("/api/integrations/cafe24/mock-sync")
        assert synced.status_code == 200
        assert len(synced.json()["recent_events"]) >= 1

        cleared = client.post("/api/integrations/cafe24/clear-activity")
        assert cleared.status_code == 200
        payload = cleared.json()
        assert payload["recent_events"] == []
        assert payload["last_sync_result"] == "mock_completed"


def test_dashboard_summary_includes_cafe24_overview(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "dashboard-cafe24"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    Cafe24SyncService.reset_state()
    get_settings.cache_clear()
    reset_engine()

    from app.main import app

    with TestClient(app) as client:
        initial = client.get("/api/dashboard/summary")
        assert initial.status_code == 200
        assert initial.json()["cafe24"]["health_status"] == "attention"
        assert initial.json()["cafe24"]["next_action_type"] == "mock_sync"
        assert initial.json()["cafe24"]["latest_event_title"] is None

        client.post("/api/integrations/cafe24/mock-webhook", json={"event_type": "delivery.delay.reported"})
        refreshed = client.get("/api/dashboard/summary")
        assert refreshed.status_code == 200
        payload = refreshed.json()
        assert payload["cafe24"]["pending_webhooks"] >= 1
        assert payload["cafe24"]["latest_event_title"] == "배송 지연 알림 webhook received"
        assert payload["cafe24"]["latest_event_status"] == "received"
        assert payload["cafe24"]["latest_event_occurred_at"] is not None
