"""Contract tests for security-sensitive human API mutations."""

HIGH_RISK_REQUESTS = (
    ("/api/auth/login", "post"),
    ("/api/auth/register", "post"),
    ("/api/auth/reset-password", "post"),
    ("/api/auth/change-password", "post"),
)


def test_high_risk_mutations_have_typed_requests(app):
    from app.openapi import get_openapi_api
    from app.openapi.register import enrich_spec

    api = get_openapi_api(app)
    with app.app_context():
        paths = enrich_spec(api.spec.to_dict())["paths"]

    for path, method in HIGH_RISK_REQUESTS:
        operation = paths[path][method]
        assert "requestBody" in operation or operation.get("parameters"), path


def test_login_validation_uses_human_error_envelope(client):
    response = client.post("/api/auth/login", json={"username": "demo"})

    assert response.status_code == 400
    assert response.get_json() == {
        "code": 0,
        "msg": "Invalid request data",
        "data": {"errors": {"json": {"password": ["Missing data for required field."]}}},
    }
