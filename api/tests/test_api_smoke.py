import base64
import hashlib
import hmac
from pathlib import Path
import shutil
import time
from datetime import UTC, datetime, timedelta

import httpx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import reset_engine
from app.integrations.cafe24.oauth_client import Cafe24OAuthTokens
from app.integrations.cafe24.sync_service import Cafe24SyncService
from app.models import Claim


def login_as(client: TestClient, email: str = "manager@alpha-seller.local", password: str = "demo1234") -> dict:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()


def latest_job_id(payload: dict, expected_job_type: str) -> int:
    recent_jobs = payload.get("recent_jobs") or []
    assert recent_jobs
    assert recent_jobs[0]["job_type"] == expected_job_type
    return recent_jobs[0]["id"]


def wait_for_job(
    client: TestClient,
    job_id: int,
    *,
    terminal_statuses: tuple[str, ...] = ("succeeded", "dead_letter"),
    timeout_seconds: float = 5.0,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last_payload: dict | None = None

    while time.monotonic() < deadline:
        client.post("/api/jobs/process-pending")
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        last_payload = response.json()
        if last_payload["status"] in terminal_statuses:
            return last_payload
        time.sleep(0.05)

    raise AssertionError(f"Timed out waiting for job {job_id}. Last payload: {last_payload}")


def test_auth_session_and_merchant_scope(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "auth-session"
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
        session_payload = login_as(client)
        assert session_payload["email"] == "manager@alpha-seller.local"
        assert session_payload["role"] == "manager"
        assert session_payload["merchant"]["mall_name"] == "alpha-seller"

        me = client.get("/api/auth/session")
        assert me.status_code == 200
        assert me.json()["merchant"]["mall_name"] == "alpha-seller"

        alpha_claims = client.get("/api/claims")
        assert alpha_claims.status_code == 200
        alpha_orders = {item["order_no"] for item in alpha_claims.json()}
        assert "CM-240301-001" in alpha_orders
        assert "BT-240301-001" not in alpha_orders


def test_beta_merchant_isolated_from_alpha_data(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "merchant-isolation"
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
        login_as(client, email="manager@beta-select.local")
        beta_claims = client.get("/api/claims")
        assert beta_claims.status_code == 200
        beta_orders = {item["order_no"] for item in beta_claims.json()}
        assert beta_orders == {"BT-240301-001", "BT-240301-002"}

        hidden_alpha = client.get("/api/claims?q=CM-240301-001")
        assert hidden_alpha.status_code == 200
        assert hidden_alpha.json() == []


def test_agent_role_cannot_update_policy_and_cannot_view_audit_logs(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "agent-role"
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
        login_as(client, email="agent@alpha-seller.local")

        detail = client.get("/api/claims/1")
        assert detail.status_code == 200
        assert detail.json()["audit_logs"] == []

        update_policy = client.put(
            "/api/policy",
            json={
                "exchange_window_days": 7,
                "return_window_days": 7,
                "return_shipping_fee": 3500,
                "exchange_shipping_fee": 6000,
                "refund_rule_text": "updated",
                "exception_rule_text": "updated",
            },
        )
        assert update_policy.status_code == 403


def test_claim_reply_send_can_keep_claim_open(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "send-reply-open"
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
        login_as(client)
        client.post("/api/claims/2/draft-reply")
        response = client.post(
            "/api/claims/2/send-reply",
            json={"reply_body": "manual reply body", "actor": "qa_operator", "mark_done": False},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "in_review"
        assert payload["automation"]["reply_sent"] is True
        assert payload["automation"]["follow_up_needed"] is True
        assert payload["automation"]["reply_sent_by"] == "manager@alpha-seller.local"
        assert payload["automation"]["latest_delivery_status"] == "sent"
        assert payload["automation"]["latest_delivery_channel"] == "manual_handoff"
        assert payload["automation"]["delivery_attempt_count"] == 1
        assert payload["reply_deliveries"][0]["status"] == "sent"
        assert payload["reply_deliveries"][0]["channel"] == "manual_handoff"
        assert payload["audit_logs"][0]["event_type"] == "reply_sent"
        assert payload["audit_logs"][0]["payload_json"]["mark_done"] is False

        filtered_claims = client.get("/api/claims?follow_up_needed=true")
        assert filtered_claims.status_code == 200
        filtered_payload = filtered_claims.json()
        assert len(filtered_payload) == 1
        assert filtered_payload[0]["order_no"] == "CM-240301-002"
        assert filtered_payload[0]["automation"]["follow_up_needed"] is True

        filtered_summary = client.get("/api/dashboard/summary?follow_up_needed=true")
        assert filtered_summary.status_code == 200
        summary_payload = filtered_summary.json()
        assert summary_payload["total_claims"] == 1
        assert summary_payload["follow_up_needed_claims"] == 1


def test_reply_sent_filter_and_summary(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "reply-sent-filter"
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
        login_as(client)
        client.post("/api/claims/1/draft-reply")
        response = client.post(
            "/api/claims/1/send-reply",
            json={"reply_body": "manual reply body", "actor": "qa_operator", "mark_done": True},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["automation"]["reply_sent"] is True
        assert payload["automation"]["follow_up_needed"] is False
        assert payload["automation"]["reply_sent_at"] is not None
        assert payload["automation"]["reply_sent_by"] == "manager@alpha-seller.local"
        assert payload["automation"]["latest_delivery_status"] == "sent"
        assert payload["reply_deliveries"][0]["status"] == "sent"

        filtered_claims = client.get("/api/claims?reply_sent=true")
        assert filtered_claims.status_code == 200
        filtered_payload = filtered_claims.json()
        assert len(filtered_payload) == 1
        assert filtered_payload[0]["order_no"] == "CM-240301-001"
        assert filtered_payload[0]["automation"]["reply_sent"] is True

        filtered_summary = client.get("/api/dashboard/summary?reply_sent=true")
        assert filtered_summary.status_code == 200
        summary_payload = filtered_summary.json()
        assert summary_payload["total_claims"] == 1
        assert summary_payload["reply_sent_claims"] == 1


def test_claim_reply_send_records_message_and_completes_claim(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "send-reply"
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
        login_as(client)
        draft_response = client.post("/api/claims/1/draft-reply")
        assert draft_response.status_code == 200

        send_response = client.post(
            "/api/claims/1/send-reply",
            json={
                "reply_body": "?덈뀞?섏꽭?? 援먰솚 ?덉감瑜??덈궡?쒕━寃좎뒿?덈떎.",
                "actor": "qa_operator",
                "mark_done": True,
            },
        )
        assert send_response.status_code == 200
        payload = send_response.json()
        assert payload["status"] == "done"
        assert payload["messages"][-1]["role"] == "merchant"
        assert payload["messages"][-1]["body"] == "?덈뀞?섏꽭?? 援먰솚 ?덉감瑜??덈궡?쒕━寃좎뒿?덈떎."
        assert payload["audit_logs"][0]["event_type"] == "reply_sent"
        assert payload["audit_logs"][0]["actor"] == "manager@alpha-seller.local"
        assert payload["audit_logs"][0]["payload_json"]["mark_done"] is True
        assert payload["audit_logs"][0]["payload_json"]["source"] == "manual_edit"
        assert payload["reply_deliveries"][0]["status"] == "sent"
        assert payload["reply_deliveries"][0]["channel"] == "manual_handoff"


def test_reply_delivery_failure_can_be_retried(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "reply-delivery-retry"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    monkeypatch.setenv("REPLY_DELIVERY_MODE", "webhook")
    monkeypatch.setenv("REPLY_DELIVERY_WEBHOOK_URL", "https://reply-delivery.test/send")
    get_settings.cache_clear()
    reset_engine()

    call_count = {"value": 0}

    class FakeWebhookClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, headers=None):
            assert url == "https://reply-delivery.test/send"
            call_count["value"] += 1
            if call_count["value"] == 1:
                return httpx.Response(502, json={"error": "upstream unavailable"})
            return httpx.Response(200, json={"delivery_id": "delivery-2", "status": "sent"})

    monkeypatch.setattr("app.reply_delivery.webhook_provider.httpx.Client", FakeWebhookClient)

    from app.main import app

    with TestClient(app) as client:
        login_as(client)
        client.post("/api/claims/1/draft-reply")

        failed = client.post(
            "/api/claims/1/send-reply",
            json={"reply_body": "retry me", "actor": "qa_operator", "mark_done": True},
        )
        assert failed.status_code == 502

        detail_after_failure = client.get("/api/claims/1")
        assert detail_after_failure.status_code == 200
        failed_payload = detail_after_failure.json()
        assert failed_payload["automation"]["reply_sent"] is False
        assert failed_payload["automation"]["latest_delivery_status"] == "failed"
        assert failed_payload["automation"]["can_retry_delivery"] is True
        assert failed_payload["reply_deliveries"][0]["status"] == "failed"

        retried = client.post(
            "/api/claims/1/retry-reply-delivery",
            json={"actor": "qa_operator", "mark_done": True},
        )
        assert retried.status_code == 200
        retried_payload = retried.json()
        assert retried_payload["status"] == "done"
        assert retried_payload["automation"]["reply_sent"] is True
        assert retried_payload["automation"]["latest_delivery_status"] == "sent"
        assert retried_payload["automation"]["delivery_attempt_count"] == 2
        assert retried_payload["reply_deliveries"][0]["status"] == "sent"
        assert retried_payload["reply_deliveries"][1]["status"] == "failed"
        assert retried_payload["audit_logs"][0]["event_type"] == "reply_resent"


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
        login_as(client)
        response = client.get("/api/claims")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload) >= 12
        assert payload[0]["reason_preview"]


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
        login_as(client)
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
        login_as(client)
        response = client.post(
            "/api/claims/1/notes",
            json={"note": "怨좉컼???ъ쭊 ?ъ쟾 ?꾨떖 ?덉젙", "actor": "qa_operator"},
        )
        assert response.status_code == 200
        payload = response.json()
        latest_log = payload["audit_logs"][0]
        assert latest_log["event_type"] == "internal_note_added"
        assert latest_log["actor"] == "manager@alpha-seller.local"
        assert latest_log["payload_json"]["note"] == "怨좉컼???ъ쭊 ?ъ쟾 ?꾨떖 ?덉젙"


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
        login_as(client)
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
        login_as(client)
        base_status = client.get("/api/integrations/cafe24")
        assert base_status.status_code == 200
        base_pending = base_status.json()["pending_webhooks"]

        response = client.post(
            "/api/integrations/cafe24/mock-webhook",
            json={"event_type": "claim.return.requested", "order_no": "CM-240301-011"},
        )
        assert response.status_code == 200
        payload = response.json()
        job_id = latest_job_id(payload, "cafe24.mock_webhook")
        assert wait_for_job(client, job_id)["status"] == "succeeded"

        status_response = client.get("/api/integrations/cafe24")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        assert status_payload["pending_webhooks"] == base_pending + 1
        assert status_payload["recent_events"][0]["event_type"] == "mock_webhook"
        assert status_payload["recent_events"][0]["status"] == "received"
        assert "CM-240301-011" in status_payload["recent_events"][0]["detail"]
        assert "답변 초안 생성 완료" in status_payload["recent_events"][0]["detail"]
        assert status_payload["recent_events"][0]["claim_id"] is not None
        assert status_payload["recent_events"][0]["order_no"] == "CM-240301-011"

        claim_response = client.get(f"/api/claims/{status_payload['recent_events'][0]['claim_id']}")
        assert claim_response.status_code == 200
        claim_payload = claim_response.json()
        assert claim_payload["order_no"] == "CM-240301-011"
        assert claim_payload["category"] == "return"
        assert claim_payload["status"] == "in_review"
        assert claim_payload["urgency"] == "medium"
        assert claim_payload["ai_label"] == "return_request"
        assert claim_payload["automation"]["auto_triaged"] is True
        assert claim_payload["automation"]["reply_ready"] is True
        assert claim_payload["automation"]["draft_reply_preview"] is not None
        assert claim_payload["automation"]["source_event"] == "claim.return.requested"
        assert claim_payload["automation"]["classification_confidence"] is not None
        assert claim_payload["automation"]["draft_reply_confidence"] is not None
        assert claim_payload["audit_logs"][0]["event_type"] == "cafe24_mock_webhook_auto_triaged"
        assert claim_payload["audit_logs"][1]["event_type"] == "draft_reply_generated"
        assert claim_payload["audit_logs"][2]["event_type"] == "claim_classified"
        assert claim_payload["audit_logs"][3]["event_type"] == "cafe24_mock_webhook_received"
        assert claim_payload["messages"][-1]["role"] == "system"
        assert {action["action_type"] for action in claim_payload["suggested_actions"]} >= {"classification", "draft_reply"}

        list_response = client.get("/api/claims")
        assert list_response.status_code == 200
        claim_list_item = next(item for item in list_response.json() if item["order_no"] == "CM-240301-011")
        assert claim_list_item["automation"]["auto_triaged"] is True
        assert claim_list_item["automation"]["reply_ready"] is True
        assert claim_list_item["automation"]["draft_reply_preview"] is not None
        assert claim_list_item["reason_preview"]


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
        login_as(client)
        response = client.get(
            "/api/integrations/cafe24/callback?code=demo-code&state=claimmate-local-1",
            follow_redirects=False,
        )
        assert response.status_code == 307
        location = response.headers["location"]
        assert location.startswith("/integrations/cafe24/?")
        assert "oauth_result=error" in location
        assert "oauth_state=claimmate-local-1" in location

        status = client.get("/api/integrations/cafe24")
        assert status.status_code == 200
        assert status.json()["recent_events"][0]["event_type"] == "oauth_callback"
        assert status.json()["recent_events"][0]["status"] == "error"


def test_cafe24_live_oauth_connects_and_refreshes_token(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "cafe24-live-oauth"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    monkeypatch.setenv("CAFE24_CLIENT_ID", "demo-client")
    monkeypatch.setenv("CAFE24_CLIENT_SECRET", "demo-secret")
    monkeypatch.setenv("CAFE24_REDIRECT_URI", "http://127.0.0.1:8000/api/integrations/cafe24/callback")
    get_settings.cache_clear()
    reset_engine()

    def fake_exchange_code(self, mall_id: str, code: str) -> Cafe24OAuthTokens:
        assert mall_id == "alpha-seller"
        assert code == "live-code"
        return Cafe24OAuthTokens(
            access_token="live-access-token",
            refresh_token="live-refresh-token",
            token_type="Bearer",
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=2),
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
            scopes=["mall.read_order", "mall.read_claim"],
            raw_response={"access_token": "live-access-token"},
        )

    def fake_refresh_token(self, mall_id: str, refresh_token: str) -> Cafe24OAuthTokens:
        assert mall_id == "alpha-seller"
        assert refresh_token == "live-refresh-token"
        return Cafe24OAuthTokens(
            access_token="refreshed-access-token",
            refresh_token="live-refresh-token",
            token_type="Bearer",
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=4),
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
            scopes=["mall.read_order", "mall.read_claim"],
            raw_response={"access_token": "refreshed-access-token"},
        )

    monkeypatch.setattr("app.integrations.cafe24.oauth_client.Cafe24OAuthClient.exchange_code", fake_exchange_code)
    monkeypatch.setattr("app.integrations.cafe24.oauth_client.Cafe24OAuthClient.refresh_access_token", fake_refresh_token)

    from app.main import app

    with TestClient(app) as client:
        login_as(client)
        callback = client.get(
            "/api/integrations/cafe24/callback?code=live-code&state=claimmate-live-1",
            follow_redirects=False,
        )
        assert callback.status_code == 307
        assert "oauth_result=connected" in callback.headers["location"]

        status_response = client.get("/api/integrations/cafe24")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        assert status_payload["connected"] is True
        assert status_payload["connection_mode"] == "live_connected"
        assert status_payload["mall_id"] == "alpha-seller"
        assert status_payload["access_token_expires_at"] is not None
        assert status_payload["next_action_type"] == "live_sync"

        refresh_response = client.post("/api/integrations/cafe24/refresh-token")
        assert refresh_response.status_code == 200
        refresh_payload = refresh_response.json()
        assert refresh_payload["status"] == "refreshed"
        assert refresh_payload["access_token_expires_at"] is not None


def test_cafe24_live_sync_imports_orders_shipments_and_claims(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "cafe24-live-sync"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    monkeypatch.setenv("CAFE24_CLIENT_ID", "demo-client")
    monkeypatch.setenv("CAFE24_CLIENT_SECRET", "demo-secret")
    monkeypatch.setenv("CAFE24_REDIRECT_URI", "http://127.0.0.1:8000/api/integrations/cafe24/callback")
    get_settings.cache_clear()
    reset_engine()

    def fake_exchange_code(self, mall_id: str, code: str) -> Cafe24OAuthTokens:
        assert mall_id == "alpha-seller"
        assert code == "live-code"
        return Cafe24OAuthTokens(
            access_token="live-access-token",
            refresh_token="live-refresh-token",
            token_type="Bearer",
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=2),
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
            scopes=["mall.read_order", "mall.read_claim"],
            raw_response={"access_token": "live-access-token"},
        )

    def fake_list_orders(self, mall_id: str, access_token: str, *, limit: int = 20) -> list[dict[str, object]]:
        assert mall_id == "alpha-seller"
        assert access_token == "live-access-token"
        assert limit == 20
        return [
            {
                "order_id": "9001",
                "order_no": "CAFE24-9001",
                "buyer": {"name": "김민지"},
                "items": [{"product_name": "레이어드 카디건"}],
                "order_status": "exchange requested",
            },
            {
                "order_id": "9002",
                "order_no": "CAFE24-9002",
                "buyer_name": "박서윤",
                "product_name": "코튼 셔츠",
                "order_status": "shipping",
            },
        ]

    def fake_list_order_shipments(
        self,
        mall_id: str,
        access_token: str,
        order_id: str,
    ) -> list[dict[str, object]]:
        assert mall_id == "alpha-seller"
        assert access_token == "live-access-token"
        if order_id == "9001":
            return [{"shipping_status": "교환 대기"}]
        if order_id == "9002":
            return [{"shipping_status": "delay"}]
        return []

    monkeypatch.setattr("app.integrations.cafe24.oauth_client.Cafe24OAuthClient.exchange_code", fake_exchange_code)
    monkeypatch.setattr("app.integrations.cafe24.oauth_client.Cafe24OAuthClient.list_orders", fake_list_orders)
    monkeypatch.setattr(
        "app.integrations.cafe24.oauth_client.Cafe24OAuthClient.list_order_shipments",
        fake_list_order_shipments,
    )

    from app.main import app

    with TestClient(app) as client:
        login_as(client)
        callback = client.get(
            "/api/integrations/cafe24/callback?code=live-code&state=claimmate-live-1",
            follow_redirects=False,
        )
        assert callback.status_code == 307
        assert "oauth_result=connected" in callback.headers["location"]

        sync_response = client.post("/api/integrations/cafe24/live-sync")
        assert sync_response.status_code == 200
        sync_payload = sync_response.json()
        assert sync_payload["last_sync_result"] == "live_completed"
        assert sync_payload["synced_orders"] == 2
        assert sync_payload["synced_claims"] == 2
        assert sync_payload["recent_events"][0]["event_type"] == "live_sync"
        assert sync_payload["next_action_type"] == "open_link"

        claims_response = client.get("/api/claims?q=CAFE24-900")
        assert claims_response.status_code == 200
        claims_payload = claims_response.json()
        assert {claim["order_no"] for claim in claims_payload} == {"CAFE24-9001", "CAFE24-9002"}
        categories = {claim["order_no"]: claim["category"] for claim in claims_payload}
        assert categories["CAFE24-9001"] == "exchange"
        assert categories["CAFE24-9002"] == "delivery"
        assert all(claim["automation"]["auto_triaged"] is True for claim in claims_payload)

        dashboard_response = client.get("/api/dashboard/summary")
        assert dashboard_response.status_code == 200
        dashboard_payload = dashboard_response.json()
        assert dashboard_payload["cafe24"]["last_sync_result"] == "live_completed"


def test_cafe24_live_webhook_verifies_signature_and_dedupes(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "cafe24-live-webhook"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    monkeypatch.setenv("CAFE24_CLIENT_ID", "demo-client")
    monkeypatch.setenv("CAFE24_CLIENT_SECRET", "demo-secret")
    monkeypatch.setenv("CAFE24_REDIRECT_URI", "http://127.0.0.1:8000/api/integrations/cafe24/callback")
    monkeypatch.setenv("CAFE24_WEBHOOK_SECRET", "super-secret")
    get_settings.cache_clear()
    reset_engine()

    def fake_exchange_code(self, mall_id: str, code: str) -> Cafe24OAuthTokens:
        return Cafe24OAuthTokens(
            access_token="live-access-token",
            refresh_token="live-refresh-token",
            token_type="Bearer",
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=2),
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
            scopes=["mall.read_order"],
            raw_response={"access_token": "live-access-token"},
        )

    monkeypatch.setattr("app.integrations.cafe24.oauth_client.Cafe24OAuthClient.exchange_code", fake_exchange_code)

    from app.main import app

    with TestClient(app) as client:
        login_as(client)
        client.get("/api/integrations/cafe24/callback?code=live-code&state=claimmate-live-1", follow_redirects=False)

        body = b'{"mall_id":"alpha-seller","event_type":"claim.exchange.requested","order_no":"CM-240301-001"}'
        signature = base64.b64encode(hmac.new(b"super-secret", body, hashlib.sha256).digest()).decode("utf-8")
        headers = {
            "content-type": "application/json",
            "x-cafe24-signature": signature,
            "x-cafe24-delivery-id": "delivery-1",
            "x-cafe24-event-type": "claim.exchange.requested",
        }

        first = client.post("/api/integrations/cafe24/webhook/live", content=body, headers=headers)
        assert first.status_code == 202
        first_payload = first.json()
        assert first_payload["duplicate"] is False
        assert first_payload["event_type"] == "claim.exchange.requested"
        assert first_payload["status"] == "queued"
        assert first_payload["job_id"] is not None
        assert first_payload["claim_id"] is None
        assert first_payload["retry_count"] == 0
        assert first_payload["failed_reason"] is None
        assert wait_for_job(client, first_payload["job_id"])["status"] == "succeeded"

        second = client.post("/api/integrations/cafe24/webhook/live", content=body, headers=headers)
        assert second.status_code == 202
        second_payload = second.json()
        assert second_payload["duplicate"] is True
        assert second_payload["status"] == "duplicate"

        status_response = client.get("/api/integrations/cafe24")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        assert status_payload["connected"] is True
        assert status_payload["webhook_endpoint_ready"] is True
        assert status_payload["pending_webhooks"] == 0
        assert status_payload["failed_webhooks"] == 0
        assert status_payload["recent_events"][0]["event_type"] == "live_webhook"


def test_cafe24_live_webhook_failures_can_be_retried(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "cafe24-live-webhook-retry"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    monkeypatch.setenv("CAFE24_CLIENT_ID", "demo-client")
    monkeypatch.setenv("CAFE24_CLIENT_SECRET", "demo-secret")
    monkeypatch.setenv("CAFE24_REDIRECT_URI", "http://127.0.0.1:8000/api/integrations/cafe24/callback")
    monkeypatch.setenv("CAFE24_WEBHOOK_SECRET", "super-secret")
    get_settings.cache_clear()
    reset_engine()

    def fake_exchange_code(self, mall_id: str, code: str) -> Cafe24OAuthTokens:
        return Cafe24OAuthTokens(
            access_token="live-access-token",
            refresh_token="live-refresh-token",
            token_type="Bearer",
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=2),
            refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
            scopes=["mall.read_order"],
            raw_response={"access_token": "live-access-token"},
        )

    call_count = {"value": 0}

    def flaky_process(session, merchant_id: int, event_type: str, payload: dict[str, object]):
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise ValueError("temporary processing failure")
        return session.get(Claim, 1)

    monkeypatch.setattr("app.integrations.cafe24.oauth_client.Cafe24OAuthClient.exchange_code", fake_exchange_code)
    monkeypatch.setattr("app.integrations.cafe24.live_service.process_live_webhook_claim", flaky_process)

    from app.main import app

    with TestClient(app) as client:
        login_as(client)
        client.get("/api/integrations/cafe24/callback?code=live-code&state=claimmate-live-1", follow_redirects=False)

        body = b'{"mall_id":"alpha-seller","event_type":"claim.exchange.requested","order_no":"CM-240301-001"}'
        signature = base64.b64encode(hmac.new(b"super-secret", body, hashlib.sha256).digest()).decode("utf-8")
        headers = {
            "content-type": "application/json",
            "x-cafe24-signature": signature,
            "x-cafe24-delivery-id": "delivery-retry-1",
            "x-cafe24-event-type": "claim.exchange.requested",
        }

        failed = client.post("/api/integrations/cafe24/webhook/live", content=body, headers=headers)
        assert failed.status_code == 202
        failed_payload = failed.json()
        assert failed_payload["status"] == "queued"
        assert failed_payload["job_id"] is not None

        failed_job = wait_for_job(
            client,
            failed_payload["job_id"],
            terminal_statuses=("retry_scheduled", "dead_letter"),
        )
        assert failed_job["status"] == "retry_scheduled"
        assert failed_job["retry_count"] == 1
        assert failed_job["error_message"] == "temporary processing failure"
        assert failed_job["available_at"] is not None

        status_response = client.get("/api/integrations/cafe24")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        assert status_payload["failed_webhooks"] == 1
        assert status_payload["retryable_webhooks"] == 1
        assert status_payload["next_action_type"] == "retry_failed_webhooks"

        retried = client.post("/api/integrations/cafe24/webhook/live/retry-failed")
        assert retried.status_code == 200
        retry_job_id = latest_job_id(retried.json(), "cafe24.retry_failed_webhooks")
        assert wait_for_job(client, retry_job_id)["status"] == "succeeded"

        refreshed_status = client.get("/api/integrations/cafe24")
        assert refreshed_status.status_code == 200
        retried_payload = refreshed_status.json()
        assert retried_payload["failed_webhooks"] == 0
        assert retried_payload["retryable_webhooks"] == 0
        assert call_count["value"] == 2


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
        login_as(client)
        synced = client.post("/api/integrations/cafe24/mock-sync")
        assert synced.status_code == 200
        assert len(synced.json()["recent_events"]) >= 1

        cleared = client.post("/api/integrations/cafe24/clear-activity")
        assert cleared.status_code == 200
        payload = cleared.json()
        assert payload["recent_events"] == []
        assert payload["last_sync_result"] == "mock_completed"


def test_mock_cafe24_status_persists_after_engine_reset(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "cafe24-mock-persist"
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
        login_as(client)
        synced = client.post("/api/integrations/cafe24/mock-sync")
        assert synced.status_code == 200
        assert synced.json()["last_sync_result"] == "mock_completed"

    get_settings.cache_clear()
    reset_engine()

    with TestClient(app) as client:
        login_as(client)
        status = client.get("/api/integrations/cafe24")
        assert status.status_code == 200
        payload = status.json()
        assert payload["last_sync_result"] == "mock_completed"
        assert payload["recent_events"][0]["event_type"] == "mock_sync"


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
        login_as(client)
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
def test_claims_and_summary_support_automation_filters(monkeypatch) -> None:
    temp_root = Path(".tmp") / "tests" / "automation-filters"
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
        login_as(client)
        response = client.post(
            "/api/integrations/cafe24/mock-webhook",
            json={"event_type": "claim.exchange.requested", "order_no": "CM-240301-001"},
        )
        assert response.status_code == 200

        filtered_claims = client.get("/api/claims?auto_triaged=true&reply_ready=true")
        assert filtered_claims.status_code == 200
        filtered_payload = filtered_claims.json()
        assert len(filtered_payload) == 1
        assert filtered_payload[0]["order_no"] == "CM-240301-001"
        assert filtered_payload[0]["automation"]["auto_triaged"] is True
        assert filtered_payload[0]["automation"]["reply_ready"] is True
        assert filtered_payload[0]["automation"]["draft_reply_preview"] is not None

        filtered_summary = client.get("/api/dashboard/summary?auto_triaged=true&reply_ready=true")
        assert filtered_summary.status_code == 200
        summary_payload = filtered_summary.json()
        assert summary_payload["total_claims"] == 1
        assert summary_payload["auto_triaged_claims"] == 1
        assert summary_payload["reply_ready_claims"] == 1

        source_filtered_claims = client.get("/api/claims?source_event=claim.exchange.requested")
        assert source_filtered_claims.status_code == 200
        source_filtered_payload = source_filtered_claims.json()
        assert len(source_filtered_payload) == 1
        assert source_filtered_payload[0]["order_no"] == "CM-240301-001"
        assert source_filtered_payload[0]["automation"]["source_event"] == "claim.exchange.requested"

        source_filtered_summary = client.get("/api/dashboard/summary?source_event=claim.exchange.requested")
        assert source_filtered_summary.status_code == 200
        source_summary_payload = source_filtered_summary.json()
        assert source_summary_payload["total_claims"] == 1
        assert source_summary_payload["auto_triaged_claims"] == 1

