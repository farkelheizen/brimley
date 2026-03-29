"""Task function example: a periodic reconciler that logs a status summary.

Demonstrates the @function(task={...}) pattern introduced in Brimley 0.9.
The task is discovered by the Scanner, scheduled by the TaskScheduler, and
executed automatically in repl and mcp-serve modes.

Run in REPL to see the task registered and scheduled:

    PYTHONPATH=../src poetry run brimley repl --root .

    # Check task status:
    brimley > /tasks

    # Invoke manually (bypasses overlap guard):
    brimley > reconciler {}

Exit with /quit — the scheduler will stop gracefully with a 30-second grace
period for any in-flight run to complete.
"""

import asyncio
import json
import logging

from brimley import BrimleyContext, Depends, function, on_startup, provider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# A minimal provider that acts as a "ledger" the reconciler checks.
# In a real application this would be a database connection or an HTTP client.
# ---------------------------------------------------------------------------


@provider(name="ledger", scope="singleton")
def build_ledger() -> dict:
    """Create a shared in-memory ledger (singleton)."""
    return {"pending": 0, "processed": 0, "errors": 0}


@on_startup
async def seed_ledger(ctx: BrimleyContext, ledger: dict = Depends("ledger")) -> None:
    """Seed the ledger with some initial pending work at startup."""
    ledger["pending"] = 5
    logger.info("Ledger seeded: %s pending items", ledger["pending"])


# ---------------------------------------------------------------------------
# The managed task function.
#
# Key task parameters (all optional except interval):
#   interval        — how often to run ("1m 30s", "30s", "2h", etc.)
#   immediate       — run once immediately at startup before the first interval
#   retries         — how many times to retry on exception before giving up
#   retry_interval  — backoff between retries ("5s exponential", "10s fixed")
# ---------------------------------------------------------------------------


@function(
    name="reconciler",
    task={
        "interval": "30s",
        "immediate": True,
        "retries": 3,
        "retry_interval": "5s exponential",
    },
)
async def reconciler(
    ctx: BrimleyContext,
    ledger=Depends("ledger"),
) -> str:
    """Periodic reconciler: processes pending ledger items and reports status.

    In a real deployment this might:
    - Poll an external API for unprocessed events.
    - Reconcile a local cache against a database.
    - Emit a health metric to a monitoring system.
    """
    logger.info("Reconciler starting — %d pending items", ledger["pending"])

    # Simulate doing work: drain pending items one at a time.
    processed_this_run = 0
    while ledger["pending"] > 0:
        await asyncio.sleep(0.01)  # simulate I/O
        ledger["pending"] -= 1
        ledger["processed"] += 1
        processed_this_run += 1

    result = {
        "processed_this_run": processed_this_run,
        "total_processed": ledger["processed"],
        "remaining_pending": ledger["pending"],
        "errors": ledger["errors"],
    }

    logger.info("Reconciler complete: %s", result)
    return json.dumps(result)
