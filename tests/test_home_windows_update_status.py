from __future__ import annotations

from types import SimpleNamespace

from psi.web.routers import search as search_router


def test_home_includes_windows_update_context(monkeypatch, mkdb, dummy_templates) -> None:
    monkeypatch.setattr(search_router, "get_templates", lambda _request: dummy_templates)
    monkeypatch.setattr(
        search_router.windows_update_svc,
        "check_windows_user_update",
        lambda **_kwargs: {"status": "up_to_date", "message": "ok", "local_version": "v-test"},
    )

    eng, SessionTmp = mkdb()
    try:
        with SessionTmp() as db:
            req = SimpleNamespace(query_params={"check_updates": "1"})
            resp = search_router.home(request=req, db=db)
            assert "windows_update" in resp.context
            assert resp.context["windows_update"]["status"] == "up_to_date"
    finally:
        eng.dispose()
