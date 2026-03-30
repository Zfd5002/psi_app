from __future__ import annotations

from psi.services import windows_update as svc


def test_compare_psi_versions_orders_expected() -> None:
    assert svc.compare_psi_versions("v1.3.0d166", "v1.3.0d167") == -1
    assert svc.compare_psi_versions("v1.3.0d167", "v1.3.0d167") == 0
    assert svc.compare_psi_versions("v1.3.0d168", "v1.3.0d167") == 1


def test_check_windows_user_update_reports_available() -> None:
    def _manifest(_url: str):
        return {
            "channel": "windows-user",
            "version": "v1.3.0d167",
            "required_assets": {"desktop_icon": "assets/windows/psi_desktop_icon.ico"},
        }

    out = svc.check_windows_user_update(
        local_version="v1.3.0d166",
        check_requested=True,
        platform_name="win32",
        fetch_manifest=_manifest,
    )
    assert out["status"] == "update_available"
    assert out["remote_version"] == "v1.3.0d167"


def test_check_windows_user_update_requires_windows_channel_manifest() -> None:
    def _manifest(_url: str):
        return {
            "channel": "main",
            "version": "v1.3.0d167",
            "required_assets": {"desktop_icon": "assets/windows/psi_desktop_icon.ico"},
        }

    out = svc.check_windows_user_update(
        local_version="v1.3.0d166",
        check_requested=True,
        platform_name="win32",
        fetch_manifest=_manifest,
    )
    assert out["status"] == "check_failed"
    assert "channel" in str(out["message"]).lower()


def test_check_windows_user_update_windows_only_guard() -> None:
    out = svc.check_windows_user_update(
        local_version="v1.3.0d166",
        check_requested=True,
        platform_name="linux",
        fetch_manifest=lambda _url: {},
    )
    assert out["status"] == "windows_only"
