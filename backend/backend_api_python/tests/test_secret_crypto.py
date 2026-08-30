from app.utils.secret_crypto import decrypt_secret_blob, encrypt_secret_blob


def test_dedicated_mfa_key_survives_session_key_rotation(monkeypatch):
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", "mfa-key-a")
    monkeypatch.setenv("SECRET_KEY", "session-key-a")
    encrypted = encrypt_secret_blob("totp-secret")

    monkeypatch.setenv("SECRET_KEY", "session-key-b")

    assert decrypt_secret_blob(encrypted) == "totp-secret"


def test_session_key_ciphertext_remains_readable_after_mfa_key_is_added(monkeypatch):
    monkeypatch.delenv("MFA_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("SECRET_KEY", "legacy-session-key")
    encrypted = encrypt_secret_blob("legacy-mfa-secret")

    monkeypatch.setenv("MFA_ENCRYPTION_KEY", "new-mfa-key")

    assert decrypt_secret_blob(encrypted) == "legacy-mfa-secret"
