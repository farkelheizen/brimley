import pytest
from typer.testing import CliRunner
from brimley.cli.main import app
from pathlib import Path

runner = CliRunner()

def test_repl_quit(tmp_path):
    (tmp_path / "funcs").mkdir()
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input="quit\n")
    assert result.exit_code == 0
    assert "Exiting Brimley REPL" in result.stdout

def test_repl_invoke_hello(tmp_path):
    # Setup
    (tmp_path / "funcs").mkdir()
    f = tmp_path / "funcs" / "hello.md"
    f.write_text("""---
name: hello
type: template_function
return_shape: string
arguments:
  inline:
    name: string 
---
Hello {{ args.name }}""")

    # REPL Input: call hello, then quit
    repl_input = "hello {name: REPL}\nquit\n"
    
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input=repl_input)
    
    assert result.exit_code == 0
    assert "Hello REPL" in result.stdout

def test_repl_reset(tmp_path):
    (tmp_path / "funcs").mkdir()
    
    # 1. Start empty
    # 2. Add file
    # 3. 'reset'
    # 4. Call file
    
    # This is tricky because the process logic happens in memory. 
    # Scanner only scans disk. 
    # We can simulate this by mocking the scanner or writing to disk mid-test?
    # Writing to disk mid-test works if the REPL loop yields execution.
    # Typer runner input is all pre-buffered. 
    
    # We can't really modify disk "during" the `runner.invoke` call effortlessly unless we used threads.
    # We will test 'reset' simply by checking the message for now.
    
    result = runner.invoke(app, ["repl", "--root", str(tmp_path)], input="reset\nquit\n")
    assert "Reloading..." in result.stdout
    assert "Rescan complete" in result.stdout

def test_repl_file_input(tmp_path):
    (tmp_path / "funcs").mkdir()
    f = tmp_path / "funcs" / "hello.md"
    f.write_text("""---
name: hello
type: template_function
return_shape: string
arguments:
  inline:
    name: string 
---
Hello {{ args.name }}""")
    
    arg_file = tmp_path / "args.json"
    arg_file.write_text('{"name": "FileLoader"}')

    # Input: hello @args.json
    repl_input = f"hello @{str(arg_file)}\nquit\n"
    
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input=repl_input)
    assert "Hello FileLoader" in result.stdout

def test_repl_multiline_input(tmp_path):
    (tmp_path / "funcs").mkdir()
    f = tmp_path / "funcs" / "hello.md"
    f.write_text("""---
name: hello
type: template_function
return_shape: string
arguments:
  inline:
    name: string 
---
Hello {{ args.name }}""")

    # Trigger multiline by NOT providing args on first line
    # Then provide args, then empty line
    repl_input = "hello\nname: MultiLine\n\nquit\n"
    
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input=repl_input)
    assert "** Enter multi-line input" in result.stdout # We expect this prompt
    assert "Hello MultiLine" in result.stdout

def test_repl_admin_help(tmp_path):
    (tmp_path / "funcs").mkdir()
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input="/help\n/quit\n")
    assert "/settings" in result.stdout
    assert "/config" in result.stdout
    assert "/state" in result.stdout
    assert "/functions" in result.stdout

def test_repl_admin_settings(tmp_path):
    (tmp_path / "funcs").mkdir()
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input="/settings\n/quit\n")
    assert '"env": "development"' in result.stdout

def test_repl_admin_functions(tmp_path):
    (tmp_path / "funcs").mkdir()
    f = tmp_path / "funcs" / "hello.md"
    f.write_text("---\nname: hello\ntype: template_function\nreturn_shape: string\n---\nHi")
    
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input="/functions\n/quit\n")
    assert "[template_function] hello" in result.stdout

def test_repl_admin_invalid(tmp_path):
    (tmp_path / "funcs").mkdir()
    result = runner.invoke(app, ["repl", "--root", str(tmp_path / "funcs")], input="/unknown_cmd\n/quit\n")
    assert "Unknown admin command: /unknown_cmd" in result.stdout
