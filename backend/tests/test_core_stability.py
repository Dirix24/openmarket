import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier

import httpx
import pytest
from fastapi.testclient import TestClient

from openmarket.backup import copy_database
from openmarket.config import Settings
from openmarket.db import Database
from openmarket.http_security import MAX_BODY_BYTES
from openmarket.main import create_app
from openmarket.models import ProviderError
from openmarket.portfolio import PortfolioError, PortfolioStore
from openmarket.providers import base
from openmarket.providers.stooq import StooqProvider


@pytest.mark.parametrize("kind", ["buy", "sell"])
def test_concurrent_trades_use_current_balance_or_position(settings, monkeypatch, kind):
    db = Database(settings)
    db.init()
    store = PortfolioStore(db)
    pid = store.create("Dos operadores", paper=True)["id"]
    store.add_transaction(pid, {"type": "deposit", "amount": 100})
    if kind == "sell":
        store.add_transaction(pid, {"type": "buy", "symbol": "AAPL", "quantity": 1, "price": 80})

    starting = Barrier(2)
    read = store.positions_state
    legacy_read = Barrier(2)

    def synchronize_legacy_snapshot(pid, conn=None):
        if conn is not None:
            return read(pid, conn)
        snapshot = read(pid)
        legacy_read.wait(timeout=5)
        return snapshot

    monkeypatch.setattr(store, "positions_state", synchronize_legacy_snapshot)

    def order():
        starting.wait(timeout=5)
        try:
            store.add_transaction(pid, {"type": kind, "symbol": "AAPL", "quantity": 1, "price": 80})
        except PortfolioError:
            return "rejected"
        return "executed"

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(lambda _: order(), range(2))) == ["executed", "rejected"]
    restarted = Database(settings)
    restarted.init()
    state = PortfolioStore(restarted).positions_state(pid)
    assert state["cash"] == (20 if kind == "buy" else 100)
    assert state["positions"].get("AAPL", {}).get("qty", 0) == (1 if kind == "buy" else 0)


def test_backup_reads_committed_data_and_rejects_overwrite(settings, tmp_path):
    db = Database(settings)
    db.init()
    PortfolioStore(db).create("Persistente")
    backup = tmp_path / "backup.db"
    restored = tmp_path / "restored.db"
    copy_database(Path(settings.db_path), backup)
    copy_database(backup, restored)
    with pytest.raises(FileExistsError):
        copy_database(backup, restored)
    recovered_db = Database(replace(settings, db_path=str(restored)))
    recovered_db.init()
    assert PortfolioStore(recovered_db).list()[0]["name"] == "Persistente"
    with db.connect() as connection:
        connection.execute("UPDATE meta SET value = '999' WHERE key = 'schema_version'")
    with pytest.raises(RuntimeError, match="incompatible"):
        db.init()


def test_local_api_denies_remote_peer_even_with_local_host(settings):
    app = create_app(replace(settings, api_token=""))
    with TestClient(app, base_url="http://localhost", client=("192.0.2.10", 5555)) as client:
        assert client.get("/api/portfolios").status_code == 403


def test_remote_api_uses_token_and_prevents_cache(settings):
    token = "a" * 48
    app = create_app(replace(settings, api_token=token))
    with TestClient(app, base_url="https://openmarket.example", client=("192.0.2.10", 5555)) as client:
        denied = client.get("/api/portfolios")
        assert denied.status_code == 401
        assert denied.headers["WWW-Authenticate"] == "Bearer"
        assert denied.headers["X-Content-Type-Options"] == "nosniff"
        assert denied.headers["Cache-Control"] == "no-store"
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/ready").status_code == 401
        result = client.get("/api/ready", headers={"Authorization": f"Bearer {token}"})
        assert result.json() == {"status": "ready"}


def test_limits_and_strict_json_validation(client):
    assert client.post("/api/portfolios", content=b"x" * (MAX_BODY_BYTES + 1)).status_code == 413
    portfolio = client.post("/api/portfolios", json={"name": "Prueba", "paper": True}).json()["id"]
    response = client.post(f"/api/portfolios/{portfolio}/transactions", content='{"type":"deposit","amount":NaN}',
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "NaN" not in response.text


def test_streaming_body_without_content_length_is_limited(settings):
    async def check():
        async def chunks():
            yield b"x" * MAX_BODY_BYTES
            yield b"x"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app(settings), client=("127.0.0.1", 50000)),
            base_url="http://localhost",
        ) as client:
            response = await client.post("/api/portfolios", content=chunks())
            assert response.status_code == 413
    asyncio.run(check())


def test_demo_fallback_requires_opt_in(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENMARKET_DEMO_FALLBACK", raising=False)
    defaults = Settings(db_path=str(tmp_path / "clean.db"), offline=True)
    with TestClient(create_app(defaults), base_url="http://localhost", client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/health").json()["demo_fallback"] is False
        assert client.get("/api/assets/AAPL").status_code == 503
        base.set_transport(httpx.MockTransport(lambda _: pytest.fail("el diagnóstico offline llamó a la red")))
        result = client.post("/api/diagnostics").json()
        assert result["offline"] and len(result["results"]) == 1
        assert result["results"][0]["kind"] == "aviso"


def test_provider_does_not_follow_redirects_or_include_secrets(settings):
    calls = []

    def redirect(request):
        calls.append(request.url.host)
        return httpx.Response(302, headers={"Location": "https://other.example/?key=private"})

    base.set_transport(httpx.MockTransport(redirect))
    provider = StooqProvider(settings)
    with pytest.raises(ProviderError, match=r"^stooq: HTTP 302$"):
        provider.http_get("https://stooq.com/q/d/l/", {"apikey": "unlisted-key"})
    with pytest.raises(ProviderError, match="destino local"):
        provider.http_get("https://127.0.0.1/")
    assert calls == ["stooq.com"]
