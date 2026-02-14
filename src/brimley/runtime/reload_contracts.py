from __future__ import annotations

from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field

from brimley.utils.diagnostics import BrimleyDiagnostic


class ReloadDomain(str, Enum):
    """Domain partitions used by the reload pipeline."""

    ENTITIES = "entities"
    FUNCTIONS = "functions"
    MCP_TOOLS = "mcp_tools"


RELOAD_DOMAIN_ORDER: List[ReloadDomain] = [
    ReloadDomain.ENTITIES,
    ReloadDomain.FUNCTIONS,
    ReloadDomain.MCP_TOOLS,
]


class WatcherState(str, Enum):
    """High-level states for polling watcher lifecycle and reload progression."""

    STOPPED = "stopped"
    WATCHING = "watching"
    CHANGE_DETECTED = "change_detected"
    DEBOUNCING = "debouncing"
    RELOADING = "reloading"


class WatcherEvent(str, Enum):
    """Events that drive watcher state transitions."""

    START = "start"
    FILE_CHANGE = "file_change"
    DEBOUNCE_WINDOW_OPEN = "debounce_window_open"
    DEBOUNCE_ELAPSED = "debounce_elapsed"
    RELOAD_SUCCESS = "reload_success"
    RELOAD_FAILURE = "reload_failure"
    STOP = "stop"


class DomainReloadInput(BaseModel):
    """Inputs used to evaluate if a domain swap is safe for this cycle."""

    model_config = ConfigDict(extra="forbid")

    diagnostics: List[BrimleyDiagnostic] = Field(default_factory=list)


class DomainSwapDecision(BaseModel):
    """Output policy decision for one domain in a reload cycle."""

    model_config = ConfigDict(extra="forbid")

    can_swap: bool
    blocked_reason: str | None = None


def has_critical_diagnostics(diagnostics: List[BrimleyDiagnostic]) -> bool:
    """Returns True when diagnostics include severities that must block domain swap."""

    return any(d.severity in {"error", "critical"} for d in diagnostics)


def evaluate_domain_swap_policy(
    domain_inputs: Dict[ReloadDomain, DomainReloadInput],
) -> Dict[ReloadDomain, DomainSwapDecision]:
    """Apply dependency-aware domain swap policy for one reload cycle.

    Dependency order is fixed:
    - entities
    - functions (depends on entities)
    - mcp_tools (depends on functions)

    Failure policy:
    - A domain with critical diagnostics is blocked.
    - Downstream domains are blocked when required upstream domain is blocked.
    - Independent domains remain swappable when they have no blocking diagnostics
      and dependencies are satisfied.
    """

    decisions: Dict[ReloadDomain, DomainSwapDecision] = {}

    entities_input = domain_inputs.get(ReloadDomain.ENTITIES, DomainReloadInput())
    if has_critical_diagnostics(entities_input.diagnostics):
        decisions[ReloadDomain.ENTITIES] = DomainSwapDecision(
            can_swap=False,
            blocked_reason="entities domain has critical diagnostics",
        )
    else:
        decisions[ReloadDomain.ENTITIES] = DomainSwapDecision(can_swap=True)

    functions_input = domain_inputs.get(ReloadDomain.FUNCTIONS, DomainReloadInput())
    if not decisions[ReloadDomain.ENTITIES].can_swap:
        decisions[ReloadDomain.FUNCTIONS] = DomainSwapDecision(
            can_swap=False,
            blocked_reason="functions depend on successful entities domain",
        )
    elif has_critical_diagnostics(functions_input.diagnostics):
        decisions[ReloadDomain.FUNCTIONS] = DomainSwapDecision(
            can_swap=False,
            blocked_reason="functions domain has critical diagnostics",
        )
    else:
        decisions[ReloadDomain.FUNCTIONS] = DomainSwapDecision(can_swap=True)

    mcp_input = domain_inputs.get(ReloadDomain.MCP_TOOLS, DomainReloadInput())
    if not decisions[ReloadDomain.FUNCTIONS].can_swap:
        decisions[ReloadDomain.MCP_TOOLS] = DomainSwapDecision(
            can_swap=False,
            blocked_reason="mcp_tools depend on successful functions domain",
        )
    elif has_critical_diagnostics(mcp_input.diagnostics):
        decisions[ReloadDomain.MCP_TOOLS] = DomainSwapDecision(
            can_swap=False,
            blocked_reason="mcp_tools domain has critical diagnostics",
        )
    else:
        decisions[ReloadDomain.MCP_TOOLS] = DomainSwapDecision(can_swap=True)

    return decisions


def transition_watcher_state(current: WatcherState, event: WatcherEvent) -> WatcherState:
    """Compute the next watcher state for a given event.

    This state machine defines the contract used by watcher/runtime orchestration.
    Invalid transitions raise ValueError.
    """

    if event == WatcherEvent.STOP:
        return WatcherState.STOPPED

    if current == WatcherState.STOPPED:
        if event == WatcherEvent.START:
            return WatcherState.WATCHING
        raise ValueError(f"Invalid watcher transition: {current} -> {event}")

    if current == WatcherState.WATCHING:
        if event == WatcherEvent.FILE_CHANGE:
            return WatcherState.CHANGE_DETECTED
        raise ValueError(f"Invalid watcher transition: {current} -> {event}")

    if current == WatcherState.CHANGE_DETECTED:
        if event == WatcherEvent.DEBOUNCE_WINDOW_OPEN:
            return WatcherState.DEBOUNCING
        raise ValueError(f"Invalid watcher transition: {current} -> {event}")

    if current == WatcherState.DEBOUNCING:
        if event == WatcherEvent.FILE_CHANGE:
            return WatcherState.CHANGE_DETECTED
        if event == WatcherEvent.DEBOUNCE_ELAPSED:
            return WatcherState.RELOADING
        raise ValueError(f"Invalid watcher transition: {current} -> {event}")

    if current == WatcherState.RELOADING:
        if event in {WatcherEvent.RELOAD_SUCCESS, WatcherEvent.RELOAD_FAILURE}:
            return WatcherState.WATCHING
        raise ValueError(f"Invalid watcher transition: {current} -> {event}")

    raise ValueError(f"Unknown watcher state: {current}")
