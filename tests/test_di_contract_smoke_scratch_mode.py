from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from psi.tools import di_contract_smoke as smoke


def test_smoke_runtime_defaults_to_scratch_and_cleans_up(tmp_path: Path) -> None:
    live_db = tmp_path / "live.sqlite"
    live_db.write_bytes(b"sqlite")
    args = Namespace(
        use_live_db=False,
        db_path=str(live_db),
        scratch_dir=str(tmp_path / "scratch"),
        keep_scratch=False,
    )
    with smoke._smoke_db_runtime(args) as runtime:
        assert runtime.use_live_db is False
        assert runtime.live_db == live_db
        assert runtime.scratch_db == (tmp_path / "scratch" / "di_contract_smoke.sqlite")
        assert runtime.active_db == runtime.scratch_db
        assert runtime.active_db.exists()
    assert not (tmp_path / "scratch" / "di_contract_smoke.sqlite").exists()


def test_smoke_runtime_use_live_db_bypasses_scratch_copy(tmp_path: Path) -> None:
    live_db = tmp_path / "live.sqlite"
    live_db.write_bytes(b"sqlite")
    args = Namespace(
        use_live_db=True,
        db_path=str(live_db),
        scratch_dir=str(tmp_path / "scratch"),
        keep_scratch=False,
    )
    with smoke._smoke_db_runtime(args) as runtime:
        assert runtime.use_live_db is True
        assert runtime.active_db == live_db
        assert runtime.scratch_db is None
    assert not (tmp_path / "scratch" / "di_contract_smoke.sqlite").exists()


def test_smoke_runtime_default_mode_copies_and_rebinds(monkeypatch, tmp_path: Path) -> None:
    live_db = tmp_path / "live.sqlite"
    live_db.write_bytes(b"sqlite")
    calls: list[tuple[str, Path, Path | None]] = []

    def _fake_copy(src: Path, dst: Path) -> None:
        calls.append(("copy", src, dst))
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"scratch")

    def _fake_rebind(db_path: Path) -> None:
        calls.append(("rebind", db_path, None))

    monkeypatch.setattr(smoke, "_copy_sqlite_file_bundle", _fake_copy)
    monkeypatch.setattr(smoke, "_rebind_core_db_runtime", _fake_rebind)

    args = Namespace(
        use_live_db=False,
        db_path=str(live_db),
        scratch_dir=str(tmp_path / "scratch"),
        keep_scratch=False,
    )
    with smoke._smoke_db_runtime(args) as runtime:
        assert runtime.active_db == (tmp_path / "scratch" / "di_contract_smoke.sqlite")
        assert runtime.active_db != live_db
    assert calls[0] == ("copy", live_db, tmp_path / "scratch" / "di_contract_smoke.sqlite")
    assert calls[1] == ("rebind", tmp_path / "scratch" / "di_contract_smoke.sqlite", None)
