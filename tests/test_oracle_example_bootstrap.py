from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import DatabaseError

from oracle_examples.app.bootstrap import _execute_ddl, initialize_oracle_demo_schema


def _make_context_with_connection(connection: MagicMock):
    engine = MagicMock()
    transaction = MagicMock()
    transaction.__enter__.return_value = connection
    transaction.__exit__.return_value = False
    engine.begin.return_value = transaction
    context = SimpleNamespace(databases={"default": engine})
    return context, engine


def test_execute_ddl_ignores_existing_object_error():
    connection = MagicMock()
    connection.execute.side_effect = DatabaseError("ddl", {}, Exception("ORA-00955: name is already used by an existing object"))

    _execute_ddl(connection, "CREATE TABLE demo_table (id NUMBER)")


def test_execute_ddl_raises_unexpected_database_error():
    connection = MagicMock()
    connection.execute.side_effect = DatabaseError("ddl", {}, Exception("ORA-00600: internal error"))

    with pytest.raises(DatabaseError):
        _execute_ddl(connection, "CREATE TABLE demo_table (id NUMBER)")


def test_initialize_oracle_demo_schema_creates_tables_and_seeds_rows(monkeypatch):
    executed_ddl: list[str] = []

    def fake_execute_ddl(connection, statement: str) -> None:
        executed_ddl.append(" ".join(statement.split()))

    monkeypatch.setattr("oracle_examples.app.bootstrap._execute_ddl", fake_execute_ddl)

    connection = MagicMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    connection.execute.side_effect = [count_result, None, None]
    context, engine = _make_context_with_connection(connection)

    initialize_oracle_demo_schema(context)

    engine.begin.assert_called_once()
    assert len(executed_ddl) == 2
    assert "CREATE TABLE brimley_demo_customers" in executed_ddl[0]
    assert "CREATE TABLE brimley_demo_startup_events" in executed_ddl[1]
    assert connection.execute.call_count == 3

    seeded_rows = connection.execute.call_args_list[1].args[1]
    assert len(seeded_rows) == 3
    assert seeded_rows[0]["email"] == "ada@example.com"