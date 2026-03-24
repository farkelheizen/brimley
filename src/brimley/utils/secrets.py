"""
Brimley secrets resolution.

``resolve_secrets`` implements the ordered-source resolution defined in ADR-0003.
In v0.8+ both ``env`` and ``provider`` sources are supported.  ``provider``
sources are resolved via the :class:`~brimley.core.container.BrimleyContainer`
injected at call time.
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, Any, Collection, Dict, List, Optional

if TYPE_CHECKING:
    from brimley.core.models import SecretSource


# ---------------------------------------------------------------------------
# Correlation-keyed secret registry (thread-safe, module-level)
# ---------------------------------------------------------------------------

_secret_registry: Dict[str, frozenset[str]] = {}
_registry_lock = threading.Lock()


def register_secrets(correlation_id: str, values: Collection[str]) -> None:
    """Register resolved secret values for the given correlation ID.

    Registered values are used by the Loguru sink filter to scrub log messages.
    """
    # Skip values that are too short to redact safely (avoids false positives).
    filtered = frozenset(v for v in values if len(v) > 2)
    if not filtered:
        return
    with _registry_lock:
        existing = _secret_registry.get(correlation_id, frozenset())
        _secret_registry[correlation_id] = existing | filtered


def clear_secrets(correlation_id: str) -> None:
    """Remove registered secrets for the given correlation ID."""
    with _registry_lock:
        _secret_registry.pop(correlation_id, None)


def get_registered_secrets(correlation_id: str) -> frozenset[str]:
    """Return the set of secret values registered for *correlation_id*."""
    with _registry_lock:
        return _secret_registry.get(correlation_id, frozenset())


def redact_secrets(message: str, secret_values: Collection[str]) -> str:
    """Replace each secret value in *message* with ``***REDACTED***``.

    Values with length ≤ 2 are skipped to avoid false-positive redaction of
    common short strings.
    """
    for value in secret_values:
        if len(value) > 2:
            message = message.replace(value, "***REDACTED***")
    return message


class BrimleySecretResolutionError(ValueError):
    """
    Raised when a secret cannot be resolved from any declared source.

    Inherits from ``ValueError`` so that parsers can raise it during scanning
    and the Scanner converts it into a ``BrimleyDiagnostic`` entry.
    """


def validate_secrets_no_provider(
    secrets: Optional[Dict[str, List["SecretSource"]]],
    func_name: str,
    file_path: str,
) -> None:
    """
    Validate that no ``provider`` sources are declared in the secrets block.

    Called at **scanner load time** to enforce ADR-0003's v0.7 constraint:
    ``provider`` sources are structurally valid YAML but require DI (v0.8+).
    Raises ``BrimleySecretResolutionError`` (a ``ValueError`` subclass) so the
    Scanner converts it into a ``BrimleyDiagnostic`` with ``ERR_PARSE_FAILURE``.
    """
    if not secrets:
        return
    for key, sources in secrets.items():
        for source in sources:
            if source.provider is not None:
                raise BrimleySecretResolutionError(
                    f"Secret '{key}' in function '{func_name}' (at {file_path}) "
                    f"declares a 'provider' source, which requires Dependency "
                    f"Injection (v0.8+). In v0.7 only 'env' sources are supported."
                )


def resolve_secrets(
    secrets: Optional[Dict[str, List["SecretSource"]]],
    func_name: str,
    container: Optional[Any] = None,
) -> Dict[str, str]:
    """
    Resolve all named secrets from their declared sources.

    For each named secret the ordered source list is tried in sequence; the
    first non-empty value wins.  Both ``env`` and ``provider`` sources are
    evaluated.  ``provider`` sources require *container* to be supplied.

    Args:
        secrets: Mapping of secret name → ordered list of :class:`SecretSource`.
        func_name: Name of the calling function (used in error messages).
        container: Optional :class:`~brimley.core.container.BrimleyContainer`
            instance.  Required when any source has ``provider`` set.

    Raises:
        BrimleySecretResolutionError: If all sources for any secret are
            exhausted without producing a value, or if a ``provider`` source
            is encountered without a container.
    """
    if not secrets:
        return {}

    resolved: Dict[str, str] = {}
    for key, sources in secrets.items():
        value: Optional[str] = None
        for source in sources:
            if source.env is not None:
                value = os.environ.get(source.env)
                if value is not None:
                    break
            elif source.provider is not None:
                if container is None:
                    raise BrimleySecretResolutionError(
                        f"Secret '{key}' for function '{func_name}' declares a "
                        f"'provider' source ('{source.provider}') but no DI container "
                        f"is available."
                    )
                try:
                    provider_value = container.resolve(source.provider)
                except Exception as exc:
                    raise BrimleySecretResolutionError(
                        f"Failed to resolve provider '{source.provider}' for secret "
                        f"'{key}' in function '{func_name}': {exc}"
                    ) from exc
                if not isinstance(provider_value, str):
                    raise BrimleySecretResolutionError(
                        f"Provider '{source.provider}' returned a non-string value "
                        f"({type(provider_value).__name__}) for secret '{key}' in "
                        f"function '{func_name}'. Provider secrets must return str."
                    )
                value = provider_value
                break
        if value is None:
            raise BrimleySecretResolutionError(
                f"Could not resolve secret '{key}' for function '{func_name}'. "
                f"No source produced a value (checked: "
                f"{[s.env or f'provider:{s.provider}' for s in sources]})."
            )
        resolved[key] = value

    return resolved
