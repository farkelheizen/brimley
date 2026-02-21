from pathlib import Path

from brimley.infrastructure.database import _resolve_database_url


def test_resolve_database_url_resolves_relative_sqlite_path_against_base_dir(tmp_path: Path):
    resolved = _resolve_database_url("sqlite:///./data.db", base_dir=tmp_path)

    expected = f"sqlite:///{(tmp_path / 'data.db').resolve()}"
    assert resolved == expected


def test_resolve_database_url_keeps_absolute_sqlite_path(tmp_path: Path):
    absolute_db = (tmp_path / "abs.db").resolve()
    url = f"sqlite:///{absolute_db}"

    resolved = _resolve_database_url(url, base_dir=tmp_path)

    assert resolved == url


def test_resolve_database_url_keeps_memory_and_non_sqlite_urls(tmp_path: Path):
    assert _resolve_database_url("sqlite:///:memory:", base_dir=tmp_path) == "sqlite:///:memory:"
    assert _resolve_database_url("postgresql://localhost/db", base_dir=tmp_path) == "postgresql://localhost/db"
