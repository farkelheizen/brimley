from pathlib import Path

from brimley.core.context import BrimleyContext
from brimley.infrastructure import logging as logging_infra


class FakeLogger:
    def __init__(self) -> None:
        self.remove_calls = 0
        self.add_calls: list[dict] = []

    def remove(self) -> None:
        self.remove_calls += 1

    def add(self, sink, **kwargs):
        self.add_calls.append({"sink": sink, **kwargs})
        return len(self.add_calls)


def test_initialize_logging_skips_when_managed_disabled(monkeypatch):
    fake_logger = FakeLogger()
    monkeypatch.setattr(logging_infra, "_logger", fake_logger)

    ctx = BrimleyContext(config_dict={"brimley": {"logging": {"managed": False}}})
    logging_infra.initialize_logging_for_context(ctx)

    assert fake_logger.remove_calls == 0
    assert fake_logger.add_calls == []


def test_initialize_logging_adds_stderr_sink(monkeypatch):
    fake_logger = FakeLogger()
    monkeypatch.setattr(logging_infra, "_logger", fake_logger)

    ctx = BrimleyContext(config_dict={"brimley": {"logging": {"level": "warning"}}})
    logging_infra.initialize_logging_for_context(ctx)

    assert fake_logger.remove_calls == 1
    assert len(fake_logger.add_calls) == 1
    assert fake_logger.add_calls[0]["sink"] is logging_infra.sys.stderr
    assert fake_logger.add_calls[0]["level"] == "WARNING"
    assert "format" in fake_logger.add_calls[0]


def test_initialize_logging_adds_jsonl_file_sink_with_rotation_and_retention(monkeypatch, tmp_path):
    fake_logger = FakeLogger()
    monkeypatch.setattr(logging_infra, "_logger", fake_logger)

    ctx = BrimleyContext(
        config_dict={
            "brimley": {
                "logging": {
                    "file": {
                        "path": "logs/brimley.log",
                        "level": "debug",
                        "format": "jsonl",
                        "rotation": "10 MB",
                        "retention": "7 days",
                    }
                }
            }
        }
    )
    ctx.app["root_dir"] = str(tmp_path)

    logging_infra.initialize_logging_for_context(ctx)

    assert fake_logger.remove_calls == 1
    assert len(fake_logger.add_calls) == 2

    file_sink = fake_logger.add_calls[1]
    expected_path = tmp_path / "logs" / "brimley.log"
    assert file_sink["sink"] == str(expected_path)
    assert file_sink["level"] == "DEBUG"
    assert file_sink["serialize"] is True
    assert file_sink["rotation"] == "10 MB"
    assert file_sink["retention"] == "7 days"


def test_initialize_logging_uses_absolute_file_path(monkeypatch, tmp_path):
    fake_logger = FakeLogger()
    monkeypatch.setattr(logging_infra, "_logger", fake_logger)

    absolute_log_file = tmp_path / "absolute.log"
    ctx = BrimleyContext(
        config_dict={
            "brimley": {
                "logging": {
                    "file": {
                        "path": str(absolute_log_file),
                        "format": "text",
                    }
                }
            }
        }
    )

    logging_infra.initialize_logging_for_context(ctx)

    assert len(fake_logger.add_calls) == 2
    assert fake_logger.add_calls[1]["sink"] == str(absolute_log_file)
    assert fake_logger.add_calls[1]["serialize"] is False
