import tomllib
from pathlib import Path


def test_pyproject_declares_fastmcp_optional_dependency_and_extra():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    dependencies = payload["tool"]["poetry"]["dependencies"]
    fastmcp_dep = dependencies["fastmcp"]

    assert isinstance(fastmcp_dep, dict)
    assert fastmcp_dep["optional"] is True

    extras = payload["tool"]["poetry"]["extras"]
    assert "fastmcp" in extras
    assert "fastmcp" in extras["fastmcp"]
