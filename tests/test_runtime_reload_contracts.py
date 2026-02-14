import pytest

from brimley.runtime.reload_contracts import (
    RELOAD_DOMAIN_ORDER,
    DomainReloadInput,
    ReloadDomain,
    WatcherEvent,
    WatcherState,
    evaluate_domain_swap_policy,
    has_critical_diagnostics,
    transition_watcher_state,
)
from brimley.utils.diagnostics import BrimleyDiagnostic


def _diag(severity: str) -> BrimleyDiagnostic:
    return BrimleyDiagnostic(
        file_path="test.md",
        error_code="ERR_TEST",
        message="test",
        severity=severity,
    )


def test_reload_domain_order_contract():
    assert RELOAD_DOMAIN_ORDER == [
        ReloadDomain.ENTITIES,
        ReloadDomain.FUNCTIONS,
        ReloadDomain.MCP_TOOLS,
    ]


def test_has_critical_diagnostics_blocks_error_and_critical():
    assert has_critical_diagnostics([_diag("error")]) is True
    assert has_critical_diagnostics([_diag("critical")]) is True
    assert has_critical_diagnostics([_diag("warning")]) is False


def test_evaluate_domain_swap_policy_allows_independent_success_domains():
    decisions = evaluate_domain_swap_policy(
        {
            ReloadDomain.ENTITIES: DomainReloadInput(diagnostics=[]),
            ReloadDomain.FUNCTIONS: DomainReloadInput(diagnostics=[]),
            ReloadDomain.MCP_TOOLS: DomainReloadInput(diagnostics=[]),
        }
    )

    assert decisions[ReloadDomain.ENTITIES].can_swap is True
    assert decisions[ReloadDomain.FUNCTIONS].can_swap is True
    assert decisions[ReloadDomain.MCP_TOOLS].can_swap is True


def test_evaluate_domain_swap_policy_blocks_downstream_on_entities_failure():
    decisions = evaluate_domain_swap_policy(
        {
            ReloadDomain.ENTITIES: DomainReloadInput(diagnostics=[_diag("critical")]),
            ReloadDomain.FUNCTIONS: DomainReloadInput(diagnostics=[]),
            ReloadDomain.MCP_TOOLS: DomainReloadInput(diagnostics=[]),
        }
    )

    assert decisions[ReloadDomain.ENTITIES].can_swap is False
    assert decisions[ReloadDomain.FUNCTIONS].can_swap is False
    assert decisions[ReloadDomain.MCP_TOOLS].can_swap is False


def test_evaluate_domain_swap_policy_blocks_mcp_only_when_functions_fail():
    decisions = evaluate_domain_swap_policy(
        {
            ReloadDomain.ENTITIES: DomainReloadInput(diagnostics=[]),
            ReloadDomain.FUNCTIONS: DomainReloadInput(diagnostics=[_diag("error")]),
            ReloadDomain.MCP_TOOLS: DomainReloadInput(diagnostics=[]),
        }
    )

    assert decisions[ReloadDomain.ENTITIES].can_swap is True
    assert decisions[ReloadDomain.FUNCTIONS].can_swap is False
    assert decisions[ReloadDomain.MCP_TOOLS].can_swap is False


def test_watcher_state_machine_happy_path_contract():
    state = WatcherState.STOPPED
    state = transition_watcher_state(state, WatcherEvent.START)
    state = transition_watcher_state(state, WatcherEvent.FILE_CHANGE)
    state = transition_watcher_state(state, WatcherEvent.DEBOUNCE_WINDOW_OPEN)
    state = transition_watcher_state(state, WatcherEvent.DEBOUNCE_ELAPSED)
    state = transition_watcher_state(state, WatcherEvent.RELOAD_SUCCESS)

    assert state == WatcherState.WATCHING


def test_watcher_state_machine_failure_returns_to_watching():
    state = WatcherState.RELOADING
    next_state = transition_watcher_state(state, WatcherEvent.RELOAD_FAILURE)
    assert next_state == WatcherState.WATCHING


def test_watcher_state_machine_invalid_transition_raises():
    with pytest.raises(ValueError):
        transition_watcher_state(WatcherState.WATCHING, WatcherEvent.RELOAD_SUCCESS)
