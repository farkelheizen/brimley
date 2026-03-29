"""One-time script to write test_task_reload.py."""
import textwrap

content = textwrap.dedent('''\
    """test_task_reload.py - Tests for B09-S12: hot-reload task warning."""
    from __future__ import annotations
    import sys
    from pathlib import Path
    from unittest.mock import MagicMock
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from brimley.core.models import PythonFunction, TaskConfig
    from brimley.core.registry import Registry
    from brimley.runtime.reload_engine import PartitionedReloadEngine


    def _cfg(**kw):
        return TaskConfig(**{"interval": "30s", **kw})


    def _fn(name, task=None):
        return PythonFunction(name=name, type="python_function", return_shape="string", task=task)


    def _ctx(fns):
        r = Registry()
        for f in fns:
            r.register(f)
        m = MagicMock()
        m.functions = r
        return m


    class TestDetect:
        def setup_method(self):
            self.e = PartitionedReloadEngine()

        def d(self, old, new):
            return self.e._detect_task_metadata_changes_from_snapshot(old, new)

        def test_unchanged(self):
            assert self.d([_fn("w", _cfg())], [_fn("w", _cfg())]) == []

        def test_no_task_fn_no_warn(self):
            assert self.d([_fn("w")], [_fn("w")]) == []

        def test_interval_change(self):
            w = self.d([_fn("w", _cfg(interval="30s"))], [_fn("w", _cfg(interval="5m"))])
            assert len(w) == 1 and w[0].error_code == "WARN_TASK_SCHEDULE_CHANGED"

        def test_immediate_change(self):
            w = self.d([_fn("w", _cfg(immediate=False))], [_fn("w", _cfg(immediate=True))])
            assert len(w) == 1

        def test_retries_change(self):
            w = self.d([_fn("w", _cfg(retries=3))], [_fn("w", _cfg(retries=5))])
            assert len(w) == 1

        def test_retry_interval_change(self):
            w = self.d(
                [_fn("w", _cfg(retry_interval="1s exponential"))],
                [_fn("w", _cfg(retry_interval="5s fixed"))],
            )
            assert len(w) == 1

        def test_message_mentions_restart(self):
            w = self.d([_fn("w", _cfg(interval="30s"))], [_fn("w", _cfg(interval="1m"))])
            assert "restart" in w[0].message.lower()

        def test_severity_warning(self):
            w = self.d([_fn("w", _cfg(interval="30s"))], [_fn("w", _cfg(interval="1m"))])
            assert w[0].severity == "warning"

        def test_new_fn_warning(self):
            w = self.d([], [_fn("new", _cfg(interval="1m"))])
            assert len(w) == 1 and w[0].error_code == "WARN_NEW_TASK_FUNCTION"

        def test_fn_gains_task(self):
            w = self.d([_fn("h")], [_fn("h", _cfg(interval="30s"))])
            assert len(w) == 1 and w[0].error_code == "WARN_NEW_TASK_FUNCTION"

        def test_name_in_message(self):
            w = self.d([], [_fn("new_worker", _cfg())])
            assert "new_worker" in w[0].message

        def test_new_fn_restart_in_msg(self):
            w = self.d([], [_fn("x", _cfg())])
            assert "restart" in w[0].message.lower()

        def test_only_changed_warns(self):
            old = [_fn("a", _cfg(interval="30s")), _fn("b", _cfg(interval="1m"))]
            new = [_fn("a", _cfg(interval="5m")), _fn("b", _cfg(interval="1m"))]
            w = self.d(old, new)
            assert len(w) == 1 and "a" in w[0].message

        def test_snapshot_not_mutated(self):
            orig = _fn("w", _cfg(interval="30s"))
            self.d([orig], [_fn("w", _cfg(interval="5m"))])
            assert orig.task.interval == "30s"


    class TestIntegration:
        def setup_method(self):
            self.e = PartitionedReloadEngine()

        def _scan(self, fns):
            from brimley.discovery.scanner import BrimleyScanResult
            return BrimleyScanResult(functions=fns, entities=[])

        def test_schedule_change_in_diagnostics(self):
            ctx = _ctx([_fn("worker", _cfg(interval="30s"))])
            r = self.e.apply_reload_with_policy(ctx, self._scan([_fn("worker", _cfg(interval="5m"))]))
            assert "WARN_TASK_SCHEDULE_CHANGED" in [d.error_code for d in r.diagnostics]

        def test_new_task_fn_in_diagnostics(self):
            ctx = _ctx([_fn("existing")])
            r = self.e.apply_reload_with_policy(ctx, self._scan([_fn("fresh", _cfg(interval="1m"))]))
            assert "WARN_NEW_TASK_FUNCTION" in [d.error_code for d in r.diagnostics]

        def test_no_warning_when_unchanged(self):
            ctx = _ctx([_fn("worker", _cfg(interval="30s"))])
            r = self.e.apply_reload_with_policy(ctx, self._scan([_fn("worker", _cfg(interval="30s"))]))
            assert not [d for d in r.diagnostics if "WARN_TASK" in d.error_code]
''')

with open("tests/test_task_reload.py", "w") as f:
    f.write(content)

print("Done")
