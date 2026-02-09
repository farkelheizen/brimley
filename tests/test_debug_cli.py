import pytest
from typer.testing import CliRunner
from brimley.cli.main import app

def test_debug_output():
    runner = CliRunner()
    result = runner.invoke(app, ["invoke", "myfunc"])
    print("\n--- DEBUG STDOUT ---")
    print(result.stdout)
    print("--- DEBUG STDERR ---")
    try:
        print(result.stderr)
    except:
        pass
    print("--------------------")


