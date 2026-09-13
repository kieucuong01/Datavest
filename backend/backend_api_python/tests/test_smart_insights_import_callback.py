from __future__ import annotations

import hashlib
import hmac
import json
import time

from flask import Flask


def _signed_headers(secret: str, body: bytes, *, timestamp: str | None = None) -> dict[str, str]:
    timestamp = timestamp or str(int(time.time()))
    signature = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("ascii") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-DataVest-Smart-Insights-Timestamp": timestamp,
        "X-DataVest-Smart-Insights-Signature": signature,
    }


def _client(monkeypatch, calls: list[tuple[str, ...]]):
    from app.services.smart_insights.import_callback import (
        create_internal_snapshot_import_blueprint,
    )

    secret = "smart-insights-callback-secret"
    monkeypatch.setenv("CRYPTO_INSIGHTS_IMPORT_CALLBACK_SECRET", secret)
    app = Flask(__name__)
    app.register_blueprint(
        create_internal_snapshot_import_blueprint(
            lambda source_codes: calls.append(tuple(source_codes)) or {
                "queued": True,
                "sourceCount": len(source_codes),
            }
        )
    )
    return app.test_client(), secret


def test_snapshot_import_callback_verifies_signature_and_enqueues_sources(monkeypatch):
    calls: list[tuple[str, ...]] = []
    client, secret = _client(monkeypatch, calls)
    body = json.dumps(
        {"sourceCodes": ["farside-btc-etf", "farside-eth-etf"]},
        separators=(",", ":"),
    ).encode("utf-8")

    response = client.post(
        "/api/internal/smart-insights/snapshot-import",
        data=body,
        headers=_signed_headers(secret, body),
    )

    assert response.status_code == 202
    assert response.get_json() == {
        "accepted": True,
        "queued": True,
        "sourceCount": 2,
    }
    assert calls == [("farside-btc-etf", "farside-eth-etf")]


def test_snapshot_import_callback_rejects_invalid_signature(monkeypatch):
    calls: list[tuple[str, ...]] = []
    client, _secret = _client(monkeypatch, calls)

    response = client.post(
        "/api/internal/smart-insights/snapshot-import",
        json={"sourceCodes": ["farside-btc-etf"]},
        headers={
            "X-DataVest-Smart-Insights-Timestamp": str(int(time.time())),
            "X-DataVest-Smart-Insights-Signature": "invalid",
        },
    )

    assert response.status_code == 401
    assert calls == []
