from __future__ import annotations

import io
import json
import socket
import socketserver
import threading
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel
from rich.console import Console

import brimley.cli.formatter as formatter_module


class ReplRPCRequest(BaseModel):
    command: str


class ReplRPCResponse(BaseModel):
    ok: bool
    continue_session: bool = True
    output: str = ""
    error: str | None = None


def send_repl_rpc_command(
    host: str,
    port: int,
    command: str,
    timeout_seconds: float = 5.0,
) -> ReplRPCResponse:
    request = ReplRPCRequest(command=command)
    payload = request.model_dump_json() + "\n"

    with socket.create_connection((host, port), timeout=timeout_seconds) as sock:
        sock.sendall(payload.encode("utf-8"))
        sock_file = sock.makefile("rb")
        line = sock_file.readline()

    if not line:
        return ReplRPCResponse(ok=False, continue_session=True, error="No response from daemon.")

    try:
        response_payload = json.loads(line.decode("utf-8"))
        return ReplRPCResponse.model_validate(response_payload)
    except Exception as exc:
        return ReplRPCResponse(ok=False, continue_session=True, error=f"Invalid daemon response: {exc}")


@dataclass
class _ReplRPCContext:
    handle: Callable[[str], ReplRPCResponse]


class _ReplRPCHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        context = self.server.rpc_context
        line = self.rfile.readline()
        if not line:
            return

        try:
            request_payload = json.loads(line.decode("utf-8"))
            request = ReplRPCRequest.model_validate(request_payload)
            response = context.handle(request.command)
        except Exception as exc:
            response = ReplRPCResponse(ok=False, continue_session=True, error=str(exc))

        self.wfile.write((response.model_dump_json() + "\n").encode("utf-8"))


class _ThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


class ReplRPCDaemon:
    def __init__(self, host: str, port: int, repl_session) -> None:
        self.host = host
        self.port = port
        self.repl_session = repl_session
        self._server = _ThreadingTCPServer((host, port), _ReplRPCHandler)
        self._server.rpc_context = _ReplRPCContext(handle=self._handle_command)

    @contextmanager
    def _capture_output(self):
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        previous_console = formatter_module.error_console
        formatter_module.error_console = Console(
            file=stderr_buffer,
            force_terminal=False,
            color_system=None,
            highlight=False,
        )
        try:
            with redirect_stdout(stdout_buffer):
                yield stdout_buffer, stderr_buffer
        finally:
            formatter_module.error_console = previous_console

    def _handle_command(self, command: str) -> ReplRPCResponse:
        should_continue = True
        with self._capture_output() as (stdout_buffer, stderr_buffer):
            if command.startswith("/"):
                should_continue = self.repl_session.handle_admin_command(command)
            else:
                self.repl_session.handle_command(command)

        output = f"{stderr_buffer.getvalue()}{stdout_buffer.getvalue()}"

        if not should_continue:
            threading.Thread(target=self.shutdown, daemon=True).start()

        return ReplRPCResponse(
            ok=True,
            continue_session=should_continue,
            output=output,
        )

    def serve_forever(self) -> None:
        self._server.serve_forever(poll_interval=0.2)

    def shutdown(self) -> None:
        self._server.shutdown()
        self._server.server_close()
