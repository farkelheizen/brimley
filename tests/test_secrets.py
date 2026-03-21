"""Tests for SecretSource model and secrets utility functions (Brimley 0.7)."""

import os
import pytest

from brimley.core.models import SecretSource
from brimley.utils.secrets import (
    BrimleySecretResolutionError,
    resolve_secrets,
    validate_secrets_no_provider,
)


# ---------------------------------------------------------------------------
# SecretSource model validation
# ---------------------------------------------------------------------------


def test_secret_source_env_valid() -> None:
    src = SecretSource(env="MY_VAR")
    assert src.env == "MY_VAR"
    assert src.provider is None


def test_secret_source_provider_valid() -> None:
    src = SecretSource(provider="my_creds")
    assert src.provider == "my_creds"
    assert src.env is None


def test_secret_source_both_raises() -> None:
    with pytest.raises(Exception):
        SecretSource(env="A", provider="B")


def test_secret_source_neither_raises() -> None:
    with pytest.raises(Exception):
        SecretSource()


# ---------------------------------------------------------------------------
# validate_secrets_no_provider
# ---------------------------------------------------------------------------


def test_validate_no_provider_ok() -> None:
    secrets = {"token": [SecretSource(env="MY_TOKEN")]}
    # Should not raise.
    validate_secrets_no_provider(secrets, func_name="fn", file_path="/fake.yaml")


def test_validate_provider_raises() -> None:
    secrets = {"token": [SecretSource(provider="vault")]}
    with pytest.raises(BrimleySecretResolutionError, match="provider"):
        validate_secrets_no_provider(secrets, func_name="fn", file_path="/fake.yaml")


def test_validate_mixed_raises_on_provider() -> None:
    secrets = {
        "token": [
            SecretSource(env="TOKEN_ENV"),
            SecretSource(provider="vault"),
        ]
    }
    with pytest.raises(BrimleySecretResolutionError):
        validate_secrets_no_provider(secrets, func_name="fn", file_path="/fake.yaml")


def test_validate_none_secrets_ok() -> None:
    validate_secrets_no_provider(None, func_name="fn", file_path="/fake.yaml")


def test_validate_empty_secrets_ok() -> None:
    validate_secrets_no_provider({}, func_name="fn", file_path="/fake.yaml")


# ---------------------------------------------------------------------------
# resolve_secrets
# ---------------------------------------------------------------------------


def test_resolve_secrets_env_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_TOKEN", "abc123")
    secrets = {"token": [SecretSource(env="MY_TOKEN")]}
    resolved = resolve_secrets(secrets, "fn")
    assert resolved == {"token": "abc123"}


def test_resolve_secrets_env_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_VAR", raising=False)
    secrets = {"token": [SecretSource(env="MISSING_VAR")]}
    with pytest.raises(BrimleySecretResolutionError, match="MISSING_VAR"):
        resolve_secrets(secrets, "fn")


def test_resolve_secrets_none_returns_empty() -> None:
    assert resolve_secrets(None, "fn") == {}


def test_resolve_secrets_empty_returns_empty() -> None:
    assert resolve_secrets({}, "fn") == {}


def test_resolve_secrets_multiple_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEY_A", "valueA")
    monkeypatch.setenv("KEY_B", "valueB")
    secrets = {
        "a": [SecretSource(env="KEY_A")],
        "b": [SecretSource(env="KEY_B")],
    }
    resolved = resolve_secrets(secrets, "fn")
    assert resolved == {"a": "valueA", "b": "valueB"}


def test_resolve_secrets_ordered_first_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIRST", "win")
    monkeypatch.setenv("SECOND", "lose")
    secrets = {
        "token": [
            SecretSource(env="FIRST"),
            SecretSource(env="SECOND"),
        ]
    }
    resolved = resolve_secrets(secrets, "fn")
    assert resolved["token"] == "win"


def test_resolve_secrets_second_wins_when_first_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FIRST_MISSING", raising=False)
    monkeypatch.setenv("SECOND_PRESENT", "found")
    secrets = {
        "token": [
            SecretSource(env="FIRST_MISSING"),
            SecretSource(env="SECOND_PRESENT"),
        ]
    }
    resolved = resolve_secrets(secrets, "fn")
    assert resolved["token"] == "found"
