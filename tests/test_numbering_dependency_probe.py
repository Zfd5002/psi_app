from __future__ import annotations

import importlib

from psi.core import deps


def test_numbering_dependency_status_reports_missing_components(monkeypatch) -> None:
    real_import_module = importlib.import_module

    def fake_import(name: str, package: str | None = None):
        if name in ("abnumber", "anarci"):
            raise ImportError(f"{name} missing")
        return real_import_module(name, package)

    monkeypatch.setattr(deps.importlib, "import_module", fake_import)
    out = deps.numbering_dependency_status()
    assert out["ok"] is False
    assert "abnumber" in out["missing"]
    assert "anarci" in out["missing"]
    assert out["components"]["abnumber"]["available"] is False
    assert out["components"]["anarci"]["available"] is False


def test_numbering_dependency_status_ok_when_all_components_present(monkeypatch) -> None:
    monkeypatch.setattr(deps, "_probe_dependency", lambda *_args, **_kwargs: deps.DependencyProbe(True, "x", None))
    out = deps.numbering_dependency_status()
    assert out["ok"] is True
    assert out["missing"] == []
    assert out["components"]["abnumber"]["available"] is True
    assert out["components"]["anarci"]["available"] is True
    assert out["components"]["biopython"]["available"] is True

