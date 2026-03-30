from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Callable, Mapping
from urllib import error as urlerror
from urllib import request as urlrequest

WINDOWS_USER_CHANNEL = "windows-user"
DEFAULT_MANIFEST_URL = (
    "https://raw.githubusercontent.com/zach/psi_repo/windows-user/docs/windows/windows_user_release_manifest.json"
)
MANIFEST_URL_ENV = "PSI_WINDOWS_USER_MANIFEST_URL"
_VERSION_RE = re.compile(r"^v(?P<maj>\d+)\.(?P<min>\d+)\.(?P<patch>\d+)(?P<track>[a-z])(?P<rev>\d+)$")


def _parse_psi_version(version: str) -> tuple[int, int, int, str, int] | None:
    m = _VERSION_RE.match(str(version or "").strip())
    if not m:
        return None
    return (
        int(m.group("maj")),
        int(m.group("min")),
        int(m.group("patch")),
        str(m.group("track")),
        int(m.group("rev")),
    )


def compare_psi_versions(local_version: str, remote_version: str) -> int | None:
    """Return -1 if local<remote, 0 if equal, 1 if local>remote, None if unparsable."""
    lv = _parse_psi_version(local_version)
    rv = _parse_psi_version(remote_version)
    if lv is None or rv is None:
        return None
    if lv < rv:
        return -1
    if lv > rv:
        return 1
    return 0


def fetch_remote_manifest(url: str, *, timeout_sec: float = 4.0) -> Mapping[str, Any]:
    req = urlrequest.Request(url, headers={"Accept": "application/json", "User-Agent": "PSI-Windows-Update-Check/1"})
    with urlrequest.urlopen(req, timeout=timeout_sec) as resp:
        payload = resp.read()
    raw = json.loads(payload.decode("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Manifest payload is not an object.")
    return raw


def _manifest_url() -> str:
    return str(os.getenv(MANIFEST_URL_ENV) or DEFAULT_MANIFEST_URL).strip()


def _invalid(reason: str, *, local_version: str, manifest_url: str) -> dict[str, Any]:
    return {
        "status": "check_failed",
        "message": f"Update check failed: {reason}",
        "local_version": local_version,
        "channel": WINDOWS_USER_CHANNEL,
        "manifest_url": manifest_url,
        "remote_version": "",
        "check_only": True,
    }


def check_windows_user_update(
    *,
    local_version: str,
    check_requested: bool,
    platform_name: str | None = None,
    fetch_manifest: Callable[[str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    platform_name = platform_name or sys.platform
    manifest_url = _manifest_url()
    out = {
        "status": "idle",
        "message": "Not checked yet.",
        "local_version": local_version,
        "channel": WINDOWS_USER_CHANNEL,
        "manifest_url": manifest_url,
        "remote_version": "",
        "check_only": True,
    }
    if not str(platform_name).lower().startswith("win"):
        out["status"] = "windows_only"
        out["message"] = "Windows-user update checks are available only on Windows installs."
        return out
    if not check_requested:
        return out

    loader = fetch_manifest or (lambda url: fetch_remote_manifest(url, timeout_sec=4.0))
    try:
        manifest = loader(manifest_url)
    except (urlerror.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return _invalid(str(exc), local_version=local_version, manifest_url=manifest_url)

    channel = str(manifest.get("channel") or "").strip()
    remote_version = str(manifest.get("version") or "").strip()
    required_assets = manifest.get("required_assets") if isinstance(manifest.get("required_assets"), dict) else {}
    desktop_icon = str(required_assets.get("desktop_icon") or "").strip()
    out["remote_version"] = remote_version

    if channel != WINDOWS_USER_CHANNEL:
        return _invalid(
            f"manifest channel '{channel or 'missing'}' is not '{WINDOWS_USER_CHANNEL}'",
            local_version=local_version,
            manifest_url=manifest_url,
        )
    if not remote_version:
        return _invalid("manifest version is missing", local_version=local_version, manifest_url=manifest_url)
    if not desktop_icon:
        return _invalid(
            "manifest required_assets.desktop_icon is missing",
            local_version=local_version,
            manifest_url=manifest_url,
        )

    cmp = compare_psi_versions(local_version, remote_version)
    if cmp is None:
        out["status"] = "check_failed"
        out["message"] = "Update check failed: unable to compare version format."
        return out
    if cmp < 0:
        out["status"] = "update_available"
        out["message"] = f"Update available: {remote_version} (installed: {local_version})."
        return out
    if cmp == 0:
        out["status"] = "up_to_date"
        out["message"] = f"PSI is up to date ({local_version})."
        return out

    out["status"] = "up_to_date"
    out["message"] = f"Installed build ({local_version}) is newer than channel manifest ({remote_version})."
    return out
