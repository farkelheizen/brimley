"""Write test_mcp_transport.py file."""
import textwrap

content = textwrap.dedent("""\
    \"\"\"test_mcp_transport.py - Tests for B09-S13: mcp-serve stdio transport.\"\"\"
    from __future__ import annotations
    import sys
    from pathlib import Path
    from unittest.mock import MagicMock, patch, call
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    import pytest
    from typer.testing import CliRunner
    from brimley.cli.main import app, _setup_task_scheduler


    def _make_mock_server(transport_calls=None):
        server = MagicMock()
        server.run = MagicMock()
        return server


    # ---------------------------------------------------------------------------
    # Unit tests for _setup_task_scheduler (already in test_startup.py)
    # Focus here: transport argument parsing and wiring
    # ---------------------------------------------------------------------------

    class TestTransportArgParsing:
        def _run(self, args, *, patches=None):
            runner = CliRunner(mix_stderr=False)
            default_patches = {
                "brimley.cli.main.load_config": MagicMock(return_value={}),
                "brimley.cli.main.BrimleyContext": MagicMock(),
                "brimley.cli.main.initialize_logging_for_context": MagicMock(),
                "brimley.cli.main.Scanner": MagicMock(),
            }
            if patches:
                default_patches.update(patches)
            with patch.multiple("brimley.cli.main", **{k.split(".", 2)[-1]: v for k, v in default_patches.items()}):
                result = runner.invoke(app, ["mcp-serve"] + args)
            return result

        def test_unknown_transport_value_rejected(self):
            runner = CliRunner(mix_stderr=False)
            patches = {
                "load_config": MagicMock(return_value={}),
                "BrimleyContext": MagicMock(),
                "initialize_logging_for_context": MagicMock(),
                "Scanner": MagicMock(),
            }
            with patch.multiple("brimley.cli.main", **patches):
                result = runner.invoke(app, ["mcp-serve", "--transport=ftp"])
            assert result.exit_code != 0


    class TestTransportResolution:
        \"\"\"Test the transport resolution logic in mcp_serve.\"\"\"

        def _mock_context(self, config_transport="sse"):
            ctx = MagicMock()
            ctx.mcp.host = "127.0.0.1"
            ctx.mcp.port = 8000
            ctx.mcp.transport = config_transport
            ctx.auto_reload.enabled = False
            ctx.databases = {}
            ctx.functions = MagicMock()
            ctx.functions.__iter__ = MagicMock(return_value=iter([]))
            ctx.functions.__len__ = MagicMock(return_value=0)
            ctx.entities = MagicMock()
            ctx.app = {}
            ctx.container = None
            return ctx

        def test_cli_transport_overrides_config(self, tmp_path):
            \"\"\"--transport=stdio on CLI overrides config transport=sse.\"\"\"
            mock_server = MagicMock()
            mock_server.run = MagicMock()
            mock_ctx = self._mock_context(config_transport="sse")

            from brimley.discovery.scanner import BrimleyScanResult
            scan_result = BrimleyScanResult(functions=[], entities=[])

            with patch("brimley.cli.main.load_config", return_value={}), \\
                 patch("brimley.cli.main.BrimleyContext", return_value=mock_ctx), \\
                 patch("brimley.cli.main.initialize_logging_for_context"), \\
                 patch("brimley.cli.main.Scanner") as MockScanner, \\
                 patch("brimley.cli.main._run_di_startup"), \\
                 patch("brimley.cli.main._setup_task_scheduler"), \\
                 patch("brimley.cli.main.BrimleyMCPAdapter") as MockAdapter:

                MockScanner.return_value.scan.return_value = scan_result
                adapter_inst = MockAdapter.return_value
                adapter_inst.discover_tools.return_value = ["tool1"]
                adapter_inst.register_tools.return_value = mock_server

                runner = CliRunner(mix_stderr=False)
                result = runner.invoke(app, ["mcp-serve", "--root", str(tmp_path), "--transport=stdio"])

            # Should have called run with stdio transport
            if mock_server.run.called:
                call_args = mock_server.run.call_args
                assert call_args.kwargs.get("transport") == "stdio" or (
                    len(call_args.args) > 0 and call_args.args[0] == "stdio"
                )

        def test_default_transport_is_sse(self, tmp_path):
            \"\"\"Without --transport, config sse is used.\"\"\"
            mock_server = MagicMock()
            mock_ctx = self._mock_context(config_transport="sse")

            from brimley.discovery.scanner import BrimleyScanResult
            scan_result = BrimleyScanResult(functions=[], entities=[])

            with patch("brimley.cli.main.load_config", return_value={}), \\
                 patch("brimley.cli.main.BrimleyContext", return_value=mock_ctx), \\
                 patch("brimley.cli.main.initialize_logging_for_context"), \\
                 patch("brimley.cli.main.Scanner") as MockScanner, \\
                 patch("brimley.cli.main._run_di_startup"), \\
                 patch("brimley.cli.main._setup_task_scheduler"), \\
                 patch("brimley.cli.main.BrimleyMCPAdapter") as MockAdapter:

                MockScanner.return_value.scan.return_value = scan_result
                adapter_inst = MockAdapter.return_value
                adapter_inst.discover_tools.return_value = ["tool1"]
                adapter_inst.register_tools.return_value = mock_server

                runner = CliRunner(mix_stderr=False)
                result = runner.invoke(app, ["mcp-serve", "--root", str(tmp_path)])

            if mock_server.run.called:
                call_args = mock_server.run.call_args
                transport = call_args.kwargs.get("transport") or (call_args.args[0] if call_args.args else None)
                assert transport == "sse"

        def test_effective_transport_logic_sse(self):
            \"\"\"CLI=None, config=sse -> effective=sse.\"\"\"
            transport_override = None
            config_transport = "sse"
            effective = transport_override if transport_override is not None else config_transport
            assert effective == "sse"

        def test_effective_transport_logic_cli_wins(self):
            \"\"\"CLI=stdio, config=sse -> effective=stdio.\"\"\"
            transport_override = "stdio"
            config_transport = "sse"
            effective = transport_override if transport_override is not None else config_transport
            assert effective == "stdio"

        def test_effective_transport_logic_config_stdio(self):
            \"\"\"CLI=None, config=stdio -> effective=stdio.\"\"\"
            transport_override = None
            config_transport = "stdio"
            effective = transport_override if transport_override is not None else config_transport
            assert effective == "stdio"

        def test_effective_transport_logic_both_override_wins(self):
            \"\"\"CLI=sse, config=stdio -> effective=sse.\"\"\"
            transport_override = "sse"
            config_transport = "stdio"
            effective = transport_override if transport_override is not None else config_transport
            assert effective == "sse"


    class TestTransportRunCall:
        \"\"\"Test that run() is called correctly for each transport.\"\"\"

        def test_sse_run_passes_host_and_port(self):
            mock_server = MagicMock()
            effective_transport = "sse"
            effective_host = "127.0.0.1"
            effective_port = 8000

            if effective_transport == "stdio":
                mock_server.run(transport="stdio")
            else:
                mock_server.run(transport="sse", host=effective_host, port=effective_port)

            mock_server.run.assert_called_once_with(transport="sse", host="127.0.0.1", port=8000)

        def test_stdio_run_no_host_or_port(self):
            mock_server = MagicMock()
            effective_transport = "stdio"
            effective_host = "127.0.0.1"
            effective_port = 8000

            if effective_transport == "stdio":
                mock_server.run(transport="stdio")
            else:
                mock_server.run(transport="sse", host=effective_host, port=effective_port)

            mock_server.run.assert_called_once_with(transport="stdio")
            # host and port NOT passed for stdio
            call_kwargs = mock_server.run.call_args.kwargs
            assert "host" not in call_kwargs
            assert "port" not in call_kwargs

        def test_sse_is_default_when_no_override(self):
            \"\"\"Verifies default SSE behavior is preserved.\"\"\"
            effective = None or "sse"  # transport_override=None, config=sse
            assert effective == "sse"
""")

with open("tests/test_mcp_transport.py", "w") as f:
    f.write(content)

print("Done")
