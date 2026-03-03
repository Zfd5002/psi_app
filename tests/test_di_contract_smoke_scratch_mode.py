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


def test_prepare_two_run_db_copies_use_seeded_base_and_isolate_runs(tmp_path: Path) -> None:
    source_db = tmp_path / "live.sqlite"
    source_db.write_text("baseline\n", encoding="utf-8")
    scratch_dir = tmp_path / "scratch"

    def _seed_once(path: Path) -> None:
        path.write_text(path.read_text(encoding="utf-8") + "seeded\n", encoding="utf-8")

    base_db, run1_db, run2_db = smoke._prepare_two_run_db_copies(
        source_db,
        scratch_dir=scratch_dir,
        seed_once_fn=_seed_once,
    )
    assert base_db == scratch_dir / "di_contract_smoke_base.sqlite"
    assert run1_db == scratch_dir / "di_contract_smoke_run1.sqlite"
    assert run2_db == scratch_dir / "di_contract_smoke_run2.sqlite"
    assert base_db.read_text(encoding="utf-8") == "baseline\nseeded\n"
    assert run1_db.read_text(encoding="utf-8") == "baseline\nseeded\n"
    assert run2_db.read_text(encoding="utf-8") == "baseline\nseeded\n"

    # Simulate a write in run1; run2 must stay unchanged.
    run1_db.write_text("mutated-run1\n", encoding="utf-8")
    assert run2_db.read_text(encoding="utf-8") == "baseline\nseeded\n"


def test_difference_classifier_reports_timestamp_drift(capsys) -> None:
    a = {"x": "created_at='2026-03-03 12:00:00.123456'", "y": {"z": 1}}
    b = {"x": "created_at='2026-03-03 12:00:01.654321'", "y": {"z": 1}}
    smoke._print_difference_classifier(a, b)
    err = capsys.readouterr().err
    assert "class=timestamp_drift" in err
