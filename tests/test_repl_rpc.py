import threading
import time

from brimley.runtime.daemon import allocate_ephemeral_port
from brimley.runtime.repl_rpc import ReplRPCDaemon, send_repl_rpc_command


class FakeReplSession:
    def __init__(self):
        self.commands: list[str] = []
        self.admin_commands: list[str] = []

    def handle_command(self, line: str):
        self.commands.append(line)
        print(f"executed:{line}")

    def handle_admin_command(self, line: str) -> bool:
        self.admin_commands.append(line)
        print(f"admin:{line}")
        return line != "/quit"


def test_repl_rpc_forwards_function_command():
    host = "127.0.0.1"
    port = allocate_ephemeral_port(host=host)
    session = FakeReplSession()
    daemon = ReplRPCDaemon(host=host, port=port, repl_session=session)

    thread = threading.Thread(target=daemon.serve_forever, daemon=True)
    thread.start()

    time.sleep(0.05)
    response = send_repl_rpc_command(host, port, "hello name=rpc")

    assert response.ok is True
    assert response.continue_session is True
    assert "executed:hello name=rpc" in response.output
    assert session.commands == ["hello name=rpc"]

    daemon.shutdown()
    thread.join(timeout=1)


def test_repl_rpc_quit_request_stops_daemon():
    host = "127.0.0.1"
    port = allocate_ephemeral_port(host=host)
    session = FakeReplSession()
    daemon = ReplRPCDaemon(host=host, port=port, repl_session=session)

    thread = threading.Thread(target=daemon.serve_forever, daemon=True)
    thread.start()

    time.sleep(0.05)
    response = send_repl_rpc_command(host, port, "/quit")

    assert response.ok is True
    assert response.continue_session is False
    assert "admin:/quit" in response.output

    thread.join(timeout=1)
    assert not thread.is_alive()
