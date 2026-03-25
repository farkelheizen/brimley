"""Tests for SecretSource model and secrets utility functions."""

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


# ---------------------------------------------------------------------------
# resolve_secrets — provider source (B08-S9)
# ---------------------------------------------------------------------------


class _MockContainer:
    """Minimal container stub for testing provider secret resolution."""

    def __init__(self, providers: dict) -> None:
        self._providers = providers

    def resolve(self, name: str) -> str:
        if name not in self._providers:
            raise KeyError(f"No provider '{name}'")
        return self._providers[name]


def test_resolve_secrets_provider_source() -> None:
    container = _MockContainer({"get_token": "secret-value"})
    secrets = {"token": [SecretSource(provider="get_token")]}
    resolved = resolve_secrets(secrets, "fn", container=container)
    assert resolved == {"token": "secret-value"}


def test_resolve_secrets_provider_no_container_raises() -> None:
    secrets = {"token": [SecretSource(provider="get_token")]}
    with pytest.raises(BrimleySecretResolutionError, match="no DI container"):
        resolve_secrets(secrets, "fn", container=None)


def test_resolve_secrets_provider_resolution_failure_raises() -> None:
    container = _MockContainer({})  # provider not registered
    secrets = {"token": [SecretSource(provider="missing_provider")]}
    with pytest.raises(BrimleySecretResolutionError, match="missing_provider"):
        resolve_secrets(secrets, "fn", container=container)


def test_resolve_secrets_provider_non_string_raises() -> None:
    class _BadContainer:
        def resolve(self, _name: str) -> int:
            return 42

    secrets = {"token": [SecretSource(provider="get_token")]}
    with pytest.raises(BrimleySecretResolutionError, match="non-string"):
        resolve_secrets(secrets, "fn", container=_BadContainer())


def test_resolve_secrets_env_then_provider_env_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """env source checked first; if set, provider is not called."""
    monkeypatch.setenv("MY_TOKEN", "from-env")
    container = _MockContainer({"get_token": "from-provider"})
    secrets = {
        "token": [
            SecretSource(env="MY_TOKEN"),
            SecretSource(provider="get_token"),
        ]
    }
    resolved = resolve_secrets(secrets, "fn", container=container)
    assert resolved["token"] == "from-env"


def test_resolve_secrets_env_missing_falls_back_to_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When env source is missing, the provider source is used as fallback."""
    monkeypatch.delenv("MISSING_VAR", raising=False)
    container = _MockContainer({"get_token": "from-provider"})
    secrets = {
        "token": [
            SecretSource(env="MISSING_VAR"),
            SecretSource(provider="get_token"),
        ]
    }
    resolved = resolve_secrets(secrets, "fn", container=container)
    assert resolved["token"] == "from-provider"


def test_resolve_secrets_mixed_keys_with_provider() -> None:
    """Multiple secrets, some from env, some from provider."""
    container = _MockContainer({"db_pass": "db-secret"})
    secrets = {
        "api_key": [SecretSource(provider="db_pass")],
        "other": [SecretSource(provider="db_pass")],
    }
    resolved = resolve_secrets(secrets, "fn", container=container)
    assert resolved["api_key"] == "db-secret"
    assert resolved["other"] == "db-secret"
