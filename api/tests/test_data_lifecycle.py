from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import bootstrap_database, get_session_factory, reset_engine
from app.models import Claim, Merchant, MerchantDataOrigin
from app.services.claim_service import get_claim, list_claims
from app.services.data_lifecycle import purge_soft_deleted_claims, reset_demo_data, soft_delete_claim
from app.services.seed import seed_demo_data


def configure_temp_database(monkeypatch, slug: str, *, app_env: str = "development", seed_demo_data_enabled: bool = True) -> None:
    temp_root = Path(".tmp") / "tests" / slug
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    database_url = f"sqlite:///{temp_root.joinpath('claimmate-test.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("SEED_DEMO_DATA", "true" if seed_demo_data_enabled else "false")
    get_settings.cache_clear()


def test_production_bootstrap_does_not_seed_demo_data(monkeypatch) -> None:
    configure_temp_database(monkeypatch, "production-bootstrap", app_env="production", seed_demo_data_enabled=True)
    reset_engine()

    bootstrap_database(force=True)
    session = get_session_factory()()
    try:
        merchant_count = session.scalar(select(func.count(Merchant.id)))
        assert merchant_count == 0
    finally:
        session.close()


def test_reset_demo_data_preserves_live_merchants(monkeypatch) -> None:
    configure_temp_database(monkeypatch, "reset-demo-data", seed_demo_data_enabled=False)
    reset_engine()

    bootstrap_database(force=True)
    session = get_session_factory()()
    try:
        live_merchant = Merchant(
            name="라이브 스토어 운영팀",
            mall_name="live-store",
            data_origin=MerchantDataOrigin.LIVE,
        )
        session.add(live_merchant)
        session.commit()

        seed_demo_data(session)
        before_reset = session.scalar(select(func.count(Merchant.id)))
        assert before_reset == 3

        result = reset_demo_data(session)
        assert result["deleted_demo_merchants"] == 2
        assert result["reseeded_demo_merchants"] == 2

        merchants = list(session.scalars(select(Merchant).order_by(Merchant.mall_name.asc())))
        assert [merchant.mall_name for merchant in merchants] == ["alpha-seller", "beta-select", "live-store"]
        assert sum(merchant.data_origin == MerchantDataOrigin.DEMO for merchant in merchants) == 2
        assert sum(merchant.data_origin == MerchantDataOrigin.LIVE for merchant in merchants) == 1
    finally:
        session.close()


def test_soft_deleted_claims_are_hidden_and_purgeable(monkeypatch) -> None:
    configure_temp_database(monkeypatch, "soft-delete-claim")
    reset_engine()

    bootstrap_database(force=True)
    session = get_session_factory()()
    try:
        claim = session.scalar(select(Claim).where(Claim.order_no == "CM-240301-001"))
        assert claim is not None

        deleted_claim = soft_delete_claim(
            session,
            claim.id,
            actor="ops_script",
            reason="lifecycle cleanup",
            retain_days=0,
        )
        assert deleted_claim.deleted_at is not None
        assert deleted_claim.deleted_by == "ops_script"
        assert deleted_claim.retention_until is not None

        visible_orders = {item.order_no for item in list_claims(session)}
        assert "CM-240301-001" not in visible_orders

        try:
            get_claim(session, claim.id)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("soft deleted claims should be hidden from get_claim")

        purged = purge_soft_deleted_claims(session, now=datetime.now(UTC) + timedelta(minutes=1))
        assert purged == 1
        assert session.get(Claim, claim.id) is None
    finally:
        session.close()
