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


def test_top_level_di_exports_importable() -> None:
    """All public DI symbols added in v0.8 must be importable from the top-level package."""
    from brimley import BrimleyContext, Depends, on_shutdown, on_startup, provider  # noqa: F401

    assert callable(provider), "provider must be callable"
    assert callable(on_startup), "on_startup must be callable"
    assert callable(on_shutdown), "on_shutdown must be callable"
    assert callable(Depends), "Depends must be callable"
    assert BrimleyContext is not None, "BrimleyContext must be importable"


def test_di_symbols_in_dunder_all() -> None:
    """All new DI exports must appear in brimley.__all__."""
    import brimley

    expected = {"provider", "on_startup", "on_shutdown", "Depends", "BrimleyContext"}
    missing = expected - set(brimley.__all__)
    assert not missing, f"Missing from brimley.__all__: {missing}"


def test_brimley_context_is_top_level_reexport() -> None:
    """`from brimley import BrimleyContext` must yield the same class as the canonical import."""
    from brimley import BrimleyContext as TopLevel
    from brimley.core.context import BrimleyContext as Canonical

    assert TopLevel is Canonical, (
        "brimley.BrimleyContext must be the same object as brimley.core.context.BrimleyContext"
    )
