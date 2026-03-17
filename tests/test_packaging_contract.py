import tomllib
from pathlib import Path


def test_pyproject_declares_fastmcp_optional_dependency_and_extra():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    optional_deps = payload["project"]["optional-dependencies"]
    assert "fastmcp" in optional_deps, "fastmcp extra missing from [project.optional-dependencies]"
    assert any("fastmcp" in dep for dep in optional_deps["fastmcp"]), (
        "fastmcp package not listed in the fastmcp extra"
    )

    # fastmcp must NOT appear in the required dependencies
    required = payload["project"].get("dependencies", [])
    assert not any("fastmcp" in dep for dep in required), (
        "fastmcp must be optional-only, not in required dependencies"
    )
